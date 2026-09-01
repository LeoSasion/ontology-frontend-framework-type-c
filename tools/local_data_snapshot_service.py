from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

from bi_cli_schema import (
    CURRENT_DUCKDB_SCHEMA_VERSION,
    CURRENT_SQLITE_SCHEMA_VERSION,
    assert_control_schema_invariants,
    initialize_schema,
)
from workspace_mutation_lock_service import workspace_mutation_lock


MANIFEST_TABLE = "__aibi_replica_manifest"
REQUIRED_MANIFEST_COLUMNS = {
    "manifest_version",
    "logical_table",
    "source_version",
    "version_id",
    "object_keys_json",
    "object_paths_json",
    "object_hashes_json",
    "schema_fingerprint",
    "content_fingerprint",
    "row_count",
    "published_at",
}
HASH_RE_LENGTH = 64


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_list(value: Any, label: str) -> list[str]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"DuckDB replica manifest has invalid {label} JSON.") from error
    if not isinstance(parsed, list) or any(not isinstance(item, str) or not item for item in parsed):
        raise RuntimeError(f"DuckDB replica manifest has invalid {label} values.")
    return parsed


def _schema_signature(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    return {
        (str(row[0]), str(row[1])): " ".join(str(row[2] or "").split())
        for row in connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index', 'trigger', 'view') "
            "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY type, name"
        )
    }


def _assert_exact_control_schema(connection: sqlite3.Connection) -> None:
    canonical = sqlite3.connect(":memory:")
    try:
        initialize_schema(canonical)
        expected = _schema_signature(canonical)
    finally:
        canonical.close()
    actual = _schema_signature(connection)
    if actual != expected:
        missing = sorted(f"{kind}:{name}" for kind, name in expected.keys() - actual.keys())
        extra = sorted(f"{kind}:{name}" for kind, name in actual.keys() - expected.keys())
        changed = sorted(
            f"{kind}:{name}"
            for kind, name in expected.keys() & actual.keys()
            if expected[(kind, name)] != actual[(kind, name)]
        )
        raise RuntimeError(
            "SQLite control database is not the exact clean v18 schema "
            f"(missing={missing}; extra={extra}; changed={changed})."
        )


def _resolve_object(
    root: Path,
    object_key: str,
    object_hash: str,
    verified_objects: dict[tuple[str, str], tuple[str, int, int, int]] | None = None,
) -> Path:
    normalized = str(object_key).replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if (
        len(parts) != 5
        or parts[0] != "workspaces"
        or len(parts[1]) != 24
        or parts[2] != "objects"
        or parts[3] != object_hash[:2]
        or parts[4] != f"{object_hash}.parquet"
        or len(object_hash) != HASH_RE_LENGTH
        or any(character not in "0123456789abcdef" for character in object_hash)
        or any(character not in "0123456789abcdef" for character in parts[1])
    ):
        raise RuntimeError(f"Dataset object key/hash binding is invalid: {object_key}")
    path = root.joinpath(*parts).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"Dataset object escaped the configured root: {object_key}") from error
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Dataset object is missing: {object_key}")
    stats = path.stat()
    reference = (object_key, object_hash)
    signature = (str(path), int(stats.st_size), int(stats.st_mtime_ns), int(stats.st_ctime_ns))
    if verified_objects is None or verified_objects.get(reference) != signature:
        if _file_hash(path) != object_hash:
            raise RuntimeError(f"Dataset object hash mismatch: {object_key}")
        if verified_objects is not None:
            verified_objects[reference] = signature
    return path


def _sqlite_state(
    path: Path,
    object_root: Path,
    verified_objects: dict[tuple[str, str], tuple[str, int, int, int]],
) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"SQLite v18 control database is missing: {path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        version = assert_control_schema_invariants(connection)
        _assert_exact_control_schema(connection)
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check is None or str(quick_check[0]).lower() != "ok":
            raise RuntimeError("SQLite v18 control database failed PRAGMA quick_check.")
        foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_rows:
            raise RuntimeError("SQLite v18 control database has foreign-key violations.")
        version_rows = {
            str(row["version_id"]): {
                "workspaceId": str(row["workspace_id"]),
                "tableKey": str(row["table_key"]),
                "rowCount": int(row["row_count"]),
                "dataVersion": "",
                "schemaFingerprint": str(row["schema_fingerprint"]),
                "contentFingerprint": str(row["content_fingerprint"]),
                "files": [],
            }
            for row in connection.execute(
                "SELECT version_id, workspace_id, table_key, row_count, schema_fingerprint, content_fingerprint FROM dataset_versions"
            )
        }
        object_refs: set[tuple[str, str]] = set()
        version_object_refs: dict[str, set[tuple[str, str]]] = {version_id: set() for version_id in version_rows}
        for row in connection.execute(
            "SELECT version_id, ordinal, object_key, object_hash, row_count, byte_size "
            "FROM dataset_version_files ORDER BY version_id, ordinal"
        ):
            version_id = str(row["version_id"])
            if version_id not in version_rows:
                raise RuntimeError(f"SQLite dataset manifest references an unknown version: {version_id}")
            object_key = str(row["object_key"])
            object_hash = str(row["object_hash"]).lower()
            object_path = _resolve_object(object_root, object_key, object_hash, verified_objects)
            if object_path.stat().st_size != int(row["byte_size"]):
                raise RuntimeError(f"SQLite dataset object byte size mismatch: {object_key}")
            reference = (object_key, object_hash)
            if reference in version_object_refs[version_id]:
                raise RuntimeError(f"SQLite dataset version contains a duplicate object binding: {object_key}")
            version_object_refs[version_id].add(reference)
            object_refs.add(reference)
            version_rows[version_id]["files"].append(reference)
        active: dict[str, dict[str, Any]] = {}
        for row in connection.execute(
            "SELECT physical_table, active_version_id, data_version, row_count, schema_fingerprint, content_fingerprint "
            "FROM table_registry WHERE active_version_id <> '' ORDER BY physical_table"
        ):
            logical_table = str(row["physical_table"])
            version_id = str(row["active_version_id"])
            version_row = version_rows.get(version_id)
            if version_row is None or not version_row["files"]:
                raise RuntimeError(f"SQLite active table has no complete dataset version: {logical_table}")
            if (
                int(row["row_count"]) != version_row["rowCount"]
                or str(row["schema_fingerprint"]) != version_row["schemaFingerprint"]
                or str(row["content_fingerprint"]) != version_row["contentFingerprint"]
            ):
                raise RuntimeError(f"SQLite active table/version metadata diverged: {logical_table}")
            version_row["dataVersion"] = str(row["data_version"])
            if logical_table in active:
                raise RuntimeError(f"SQLite has duplicate active physical tables: {logical_table}")
            active[logical_table] = {"versionId": version_id, **version_row}
        return {
            "schemaVersion": version,
            "active": active,
            "objectRefs": object_refs,
            "datasetVersionCount": len(version_rows),
        }
    finally:
        connection.close()


def _duckdb_state(
    path: Path,
    object_root: Path,
    sqlite_state: dict[str, Any],
    *,
    expected_path_root: Path | None,
    verified_objects: dict[tuple[str, str], tuple[str, int, int, int]],
) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"DuckDB v2 catalogue is missing: {path}")
    try:
        import duckdb  # type: ignore
    except ImportError as error:
        raise RuntimeError("DuckDB runtime is required to validate a local-data snapshot.") from error
    connection = duckdb.connect(str(path), read_only=True)
    try:
        metadata_rows = connection.execute(
            "SELECT key, value FROM __aibi_schema_metadata ORDER BY key"
        ).fetchall()
        if len(metadata_rows) != 1 or str(metadata_rows[0][0]) != "schema_version" or int(metadata_rows[0][1]) != CURRENT_DUCKDB_SCHEMA_VERSION:
            raise RuntimeError("DuckDB catalogue is not clean schema v2.")
        metadata_columns = {str(row[0]) for row in connection.execute("DESCRIBE __aibi_schema_metadata").fetchall()}
        if metadata_columns != {"key", "value"}:
            raise RuntimeError("DuckDB v2 schema metadata shape is invalid.")
        columns = {str(row[0]) for row in connection.execute(f'DESCRIBE "{MANIFEST_TABLE}"').fetchall()}
        if columns != REQUIRED_MANIFEST_COLUMNS:
            missing = sorted(REQUIRED_MANIFEST_COLUMNS - columns)
            extra = sorted(columns - REQUIRED_MANIFEST_COLUMNS)
            raise RuntimeError(f"DuckDB v2 replica manifest shape is invalid (missing={missing}; extra={extra}).")
        rows = connection.execute(
            f'SELECT manifest_version, logical_table, source_version, version_id, object_keys_json, '
            f'object_paths_json, object_hashes_json, schema_fingerprint, content_fingerprint, row_count '
            f'FROM "{MANIFEST_TABLE}" ORDER BY logical_table'
        ).fetchall()
        active = sqlite_state["active"]
        relations = connection.execute(
            "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        base_tables = {str(name) for name, relation_type in relations if str(relation_type).upper() == "BASE TABLE"}
        views = {str(name) for name, relation_type in relations if str(relation_type).upper() == "VIEW"}
        if base_tables != {"__aibi_schema_metadata", MANIFEST_TABLE}:
            raise RuntimeError(f"DuckDB v2 catalogue contains unsupported base tables: {sorted(base_tables)}")
        if views != set(active):
            raise RuntimeError(
                f"DuckDB v2 view inventory diverged from SQLite active tables (views={sorted(views)}; active={sorted(active)})."
            )
        seen: set[str] = set()
        for row in rows:
            logical_table = str(row[1])
            if int(row[0]) != CURRENT_DUCKDB_SCHEMA_VERSION or logical_table in seen:
                raise RuntimeError(f"DuckDB replica manifest is not v2/unique: {logical_table}")
            seen.add(logical_table)
            sqlite_item = active.get(logical_table)
            if sqlite_item is None:
                raise RuntimeError(f"DuckDB replica has no active SQLite catalogue row: {logical_table}")
            keys = _json_list(row[4], "object_keys")
            paths = _json_list(row[5], "object_paths")
            hashes = [value.lower() for value in _json_list(row[6], "object_hashes")]
            if not keys or len(keys) != len(paths) or len(keys) != len(hashes):
                raise RuntimeError(f"DuckDB replica object bindings are incomplete: {logical_table}")
            expected_files = list(sqlite_item["files"])
            if list(zip(keys, hashes, strict=True)) != expected_files:
                raise RuntimeError(f"SQLite/DuckDB dataset manifests diverged: {logical_table}")
            for object_key, object_hash in zip(keys, hashes, strict=True):
                _resolve_object(object_root, object_key, object_hash, verified_objects)
            normalized_manifest_paths = [str(value).replace("\\", "/") for value in paths]
            if any(Path(value).name != f"{object_hash}.parquet" for value, object_hash in zip(paths, hashes, strict=True)):
                raise RuntimeError(f"DuckDB replica path/hash binding is invalid: {logical_table}")
            if expected_path_root is not None:
                expected_paths = [
                    expected_path_root.resolve().joinpath(*key.split("/")).resolve().as_posix()
                    for key in keys
                ]
                if [Path(value).resolve().as_posix() for value in paths] != expected_paths:
                    raise RuntimeError(f"DuckDB replica paths are not bound to the expected CAS root: {logical_table}")
            if (
                str(row[2]) != (
                    f"{sqlite_item['workspaceId']}:{sqlite_item['tableKey']}:"
                    f"{sqlite_item['dataVersion']}:{sqlite_item['rowCount']}"
                )
                or str(row[3]) != sqlite_item["versionId"]
                or str(row[7]) != sqlite_item["schemaFingerprint"]
                or str(row[8]) != sqlite_item["contentFingerprint"]
                or int(row[9]) != sqlite_item["rowCount"]
            ):
                raise RuntimeError(f"SQLite/DuckDB active version metadata diverged: {logical_table}")
            relation = connection.execute(
                "SELECT table_type FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
                [logical_table],
            ).fetchall()
            if len(relation) != 1 or str(relation[0][0]).upper() != "VIEW":
                raise RuntimeError(f"DuckDB active replica view is missing: {logical_table}")
            view_rows = connection.execute(
                "SELECT view_definition FROM information_schema.views WHERE table_schema = 'main' AND table_name = ?",
                [logical_table],
            ).fetchall()
            if len(view_rows) != 1:
                raise RuntimeError(f"DuckDB active replica view definition is missing: {logical_table}")
            definition = str(view_rows[0][0] or "").replace("\\", "/")
            definition_paths = [value.replace("''", "'") for value in re.findall(r"'((?:''|[^'])+?\.parquet)'", definition)]
            if sorted(definition_paths) != sorted(normalized_manifest_paths):
                raise RuntimeError(f"DuckDB view/manifest object paths diverged: {logical_table}")
        if seen != set(active):
            missing = sorted(set(active) - seen)
            raise RuntimeError("DuckDB replica manifest is missing active SQLite tables: " + ", ".join(missing))
        return {"schemaVersion": CURRENT_DUCKDB_SCHEMA_VERSION, "replicaCount": len(rows)}
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"DuckDB v2 catalogue/manifest validation failed: {error}") from error
    finally:
        connection.close()


def validate_snapshot(
    sqlite_path: Path,
    duckdb_path: Path,
    object_root: Path,
    *,
    expected_path_root: Path | None = None,
) -> dict[str, Any]:
    verified_objects: dict[tuple[str, str], tuple[str, int, int, int]] = {}
    sqlite_state = _sqlite_state(sqlite_path.resolve(), object_root.resolve(), verified_objects)
    duckdb_state = _duckdb_state(
        duckdb_path.resolve(),
        object_root.resolve(),
        sqlite_state,
        expected_path_root=expected_path_root.resolve() if expected_path_root else None,
        verified_objects=verified_objects,
    )
    return {
        "ok": True,
        "schema": "aibi-local-data-snapshot-validation/v2",
        "sqliteSchemaVersion": CURRENT_SQLITE_SCHEMA_VERSION,
        "duckdbSchemaVersion": CURRENT_DUCKDB_SCHEMA_VERSION,
        "datasetVersionCount": sqlite_state["datasetVersionCount"],
        "activeReplicaCount": duckdb_state["replicaCount"],
        "referencedObjectCount": len(sqlite_state["objectRefs"]),
    }


def rebase_duckdb(duckdb_path: Path, object_root: Path, target_object_root: Path) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except ImportError as error:
        raise RuntimeError("DuckDB runtime is required to rebase a restored catalogue.") from error
    connection = duckdb.connect(str(duckdb_path.resolve()))
    try:
        rows = connection.execute(
            f'SELECT logical_table, object_keys_json, object_hashes_json FROM "{MANIFEST_TABLE}" ORDER BY logical_table'
        ).fetchall()
        connection.execute("BEGIN TRANSACTION")
        try:
            for logical_table, keys_json, hashes_json in rows:
                keys = _json_list(keys_json, "object_keys")
                hashes = [value.lower() for value in _json_list(hashes_json, "object_hashes")]
                if not keys or len(keys) != len(hashes):
                    raise RuntimeError(f"DuckDB replica object bindings are incomplete: {logical_table}")
                for key, object_hash in zip(keys, hashes, strict=True):
                    _resolve_object(object_root, key, object_hash)
                target_paths = [target_object_root.resolve().joinpath(*key.split("/")).resolve() for key in keys]
                path_sql = ", ".join("'" + path.as_posix().replace("'", "''") + "'" for path in target_paths)
                identifier = '"' + str(logical_table).replace('"', '""') + '"'
                connection.execute(
                    f"CREATE OR REPLACE VIEW {identifier} AS "
                    f"SELECT * FROM read_parquet([{path_sql}], union_by_name = true)"
                )
                connection.execute(
                    f'UPDATE "{MANIFEST_TABLE}" SET object_paths_json = ? WHERE logical_table = ?',
                    [json.dumps([path.as_posix() for path in target_paths], separators=(",", ":")), logical_table],
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        connection.execute("CHECKPOINT")
        return {"ok": True, "rebasedReplicaCount": len(rows)}
    finally:
        connection.close()


def materialize_databases(sqlite_source: Path, duckdb_source: Path, sqlite_target: Path, duckdb_target: Path) -> dict[str, Any]:
    if sqlite_target.exists() or duckdb_target.exists():
        raise RuntimeError("Snapshot database targets must not already exist.")
    sqlite_target.parent.mkdir(parents=True, exist_ok=True)
    duckdb_target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{sqlite_source.resolve().as_posix()}?mode=ro", uri=True)
    destination = sqlite3.connect(sqlite_target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    shutil.copyfile(duckdb_source, duckdb_target)
    return {"ok": True, "sqlite": str(sqlite_target), "duckdb": str(duckdb_target)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    lock = subparsers.add_parser("hold-lock")
    lock.add_argument("--path", required=True)
    lock.add_argument("--timeout", type=float, default=60.0)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--sqlite", required=True)
    validate.add_argument("--duckdb", required=True)
    validate.add_argument("--objects", required=True)
    validate.add_argument("--expected-path-root")
    rebase = subparsers.add_parser("rebase")
    rebase.add_argument("--duckdb", required=True)
    rebase.add_argument("--objects", required=True)
    rebase.add_argument("--target-object-root", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--sqlite", required=True)
    materialize.add_argument("--duckdb", required=True)
    materialize.add_argument("--sqlite-out", required=True)
    materialize.add_argument("--duckdb-out", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "hold-lock":
            with workspace_mutation_lock(Path(args.path), timeout_seconds=float(args.timeout)):
                print("LOCKED", flush=True)
                sys.stdin.buffer.read()
            return 0
        if args.command == "validate":
            result = validate_snapshot(
                Path(args.sqlite),
                Path(args.duckdb),
                Path(args.objects),
                expected_path_root=Path(args.expected_path_root) if args.expected_path_root else None,
            )
        elif args.command == "rebase":
            result = rebase_duckdb(Path(args.duckdb), Path(args.objects), Path(args.target_object_root))
        else:
            result = materialize_databases(
                Path(args.sqlite), Path(args.duckdb), Path(args.sqlite_out), Path(args.duckdb_out)
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
