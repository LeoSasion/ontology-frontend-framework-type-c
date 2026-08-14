from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sqlite3
from typing import Any, Callable


PLAN_SCHEMA = "aibi-metric-contract-plan/v2"
CONTRACT_SCHEMA = "aibi-metric-contract/v2"
REPLAY_SCHEMA = "aibi-metric-contract-replay/v1"
ALLOWED_NULL_POLICIES = {"exclude", "zero", "error"}
ALLOWED_DIRECTIONS = {"neutral", "increase", "decrease"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _workspace_id(connection: sqlite3.Connection, args: argparse.Namespace, active_workspace_id: Callable[[sqlite3.Connection], str]) -> str:
    requested = str(getattr(args, "workspace", "") or "").strip()
    workspace_id = requested or active_workspace_id(connection)
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _request_key(args: argparse.Namespace) -> str:
    value = str(getattr(args, "request_key", "") or "").strip()
    if len(value) < 8 or len(value) > 200:
        raise ValueError("Metric Contract requires a requestKey between 8 and 200 characters.")
    return value


def _metric_row(connection: sqlite3.Connection, workspace_id: str, metric_ref: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT m.*, t.data_version, t.row_count
        FROM metric_definitions m
        JOIN table_registry t ON t.workspace_id=m.workspace_id AND t.table_key=m.table_key
        WHERE m.workspace_id=? AND (m.metric_key=? OR m.label=?) AND m.enabled=1
        ORDER BY CASE WHEN m.metric_key=? THEN 0 ELSE 1 END LIMIT 1
        """,
        (workspace_id, metric_ref, metric_ref, metric_ref),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown active metric: {metric_ref}")
    return row


def _definition(row: sqlite3.Row, args: argparse.Namespace | None = None) -> dict[str, Any]:
    stored_filters = json.loads(str(row["filters_json"] or "[]"))
    definition = {
        "metricKey": str(row["metric_key"]),
        "label": str(row["label"]),
        "tableKey": str(row["table_key"]),
        "metricType": str(row["metric_type"] or "basic"),
        "measure": str(row["measure"] or "*"),
        "aggregation": str(row["aggregation"]),
        "formulaText": str(row["formula_text"] or ""),
        "dependencies": json.loads(str(row["dependencies_json"] or "[]")),
        "defaultDimension": str(row["dimension"] or ""),
        "timeField": str(row["time_field"] or ""),
        "filters": stored_filters,
        "valueFormat": str(row["value_format"] or "auto"),
        "description": str(row["description"] or ""),
    }
    if args is not None:
        null_policy = str(getattr(args, "null_policy", "exclude") or "exclude")
        direction = str(getattr(args, "direction", "neutral") or "neutral")
        if null_policy not in ALLOWED_NULL_POLICIES:
            raise ValueError("Metric Contract nullPolicy must be exclude, zero, or error.")
        if direction not in ALLOWED_DIRECTIONS:
            raise ValueError("Metric Contract direction must be neutral, increase, or decrease.")
        definition["contract"] = {
            "population": str(getattr(args, "population", "") or "All rows after saved metric filters").strip()[:500],
            "grain": str(getattr(args, "grain", "") or row["dimension"] or "workspace-total").strip()[:160],
            "unit": str(getattr(args, "unit", "") or row["value_format"] or "auto").strip()[:80],
            "nullPolicy": null_policy,
            "dedupKey": str(getattr(args, "dedup_key", "") or "").strip()[:160],
            "direction": direction,
            "owner": str(getattr(args, "owner", "") or "workspace-owner").strip()[:160],
        }
    return definition


def _binding(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "tableKey": str(row["table_key"]),
        "dataVersion": int(row["data_version"] or 0),
        "rowCount": int(row["row_count"] or 0),
    }


def _parse_scenarios(args: argparse.Namespace) -> list[dict[str, Any]]:
    raw = getattr(args, "scenario_json", []) or []
    if isinstance(raw, str):
        raw = [raw]
    if not raw:
        return [{"name": "All data", "groups": [], "filters": [], "limit": 50}]
    if len(raw) > 12:
        raise ValueError("Metric Contract supports at most 12 replay scenarios.")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for value in raw:
        try:
            item = json.loads(str(value))
        except json.JSONDecodeError as error:
            raise ValueError("Metric Contract scenario must be valid JSON.") from error
        if not isinstance(item, dict):
            raise ValueError("Metric Contract scenario must be an object.")
        name = str(item.get("name") or "").strip()[:80]
        groups = [str(group).strip() for group in item.get("groups", []) if str(group).strip()]
        filters = item.get("filters", [])
        limit = int(item.get("limit") or 50)
        if not name or name in names or len(groups) > 5 or not isinstance(filters, list) or len(filters) > 10 or limit < 1 or limit > 200:
            raise ValueError("Metric Contract scenario violates name, group, filter, or limit bounds.")
        normalized_filters = []
        for entry in filters:
            if not isinstance(entry, dict) or not str(entry.get("field") or "").strip() or not str(entry.get("operator") or "").strip():
                raise ValueError("Metric Contract filters require field and operator.")
            normalized_filters.append({
                "field": str(entry["field"]).strip(),
                "operator": str(entry["operator"]).strip(),
                "value": str(entry.get("value") or ""),
            })
        names.add(name)
        result.append({"name": name, "groups": groups, "filters": normalized_filters, "limit": limit})
    return result


def _filter_cli(filters: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in filters:
        value = str(item.get("value") or "")
        values.append(f"{item['field']}:{item['operator']}:{value}" if value else f"{item['field']}:{item['operator']}")
    return values


def _run_scenario(
    query_metric: Callable[[argparse.Namespace], dict[str, Any]],
    workspace_id: str,
    metric_key: str,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    payload = query_metric(argparse.Namespace(
        workspace=workspace_id,
        metric=metric_key,
        group=list(scenario["groups"]),
        filter=_filter_cli(list(scenario["filters"])),
        sort="",
        limit=int(scenario["limit"]),
    ))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    result_fingerprint = _fingerprint(rows)
    scalar = None
    if len(rows) == 1 and isinstance(rows[0], dict):
        numeric = [value for value in rows[0].values() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if len(numeric) == 1:
            scalar = float(numeric[0])
    return {
        "resultFingerprint": result_fingerprint,
        "rowCount": len(rows),
        "columnCount": len(rows[0]) if rows and isinstance(rows[0], dict) else 0,
        "scalar": scalar,
    }


def _public_scenario(scenario: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "name": scenario["name"],
        "groups": list(scenario["groups"]),
        "filters": [
            {
                "field": item["field"],
                "operator": item["operator"],
                "hasValue": bool(item.get("value")),
                "valueFingerprint": hashlib.sha256(str(item.get("value") or "").encode("utf-8")).hexdigest() if item.get("value") else "",
            }
            for item in scenario["filters"]
        ],
        "limit": scenario["limit"],
    }
    if baseline is not None:
        result["baseline"] = baseline
    return result


def _diff(left: dict[str, Any] | None, right: dict[str, Any]) -> list[dict[str, Any]]:
    if not left:
        return [{"field": "contract", "kind": "created"}]
    result = []
    for field in sorted(set(left) | set(right)):
        if _fingerprint(left.get(field)) != _fingerprint(right.get(field)):
            result.append({"field": field, "kind": "changed"})
    return result


def _latest_contract(connection: sqlite3.Connection, workspace_id: str, metric_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM metric_contract_versions WHERE workspace_id=? AND metric_key=? ORDER BY version DESC LIMIT 1",
        (workspace_id, metric_key),
    ).fetchone()


def _build_plan(connection: sqlite3.Connection, args: argparse.Namespace, workspace_id: str, query_metric: Callable[[argparse.Namespace], dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    request_key = _request_key(args)
    row = _metric_row(connection, workspace_id, str(getattr(args, "metric", "") or ""))
    definition = _definition(row, args)
    binding = _binding(row)
    scenarios = _parse_scenarios(args)
    evaluated = [
        {"scenario": item, "baseline": _run_scenario(query_metric, workspace_id, str(row["metric_key"]), item)}
        for item in scenarios
    ]
    latest = _latest_contract(connection, workspace_id, str(row["metric_key"]))
    previous_definition = json.loads(str(latest["definition_json"])) if latest else None
    private = {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
        "metricKey": str(row["metric_key"]),
        "version": int(latest["version"] if latest else 0) + 1,
        "definition": definition,
        "binding": binding,
        "scenarios": evaluated,
        "changes": _diff(previous_definition, definition),
    }
    private["planFingerprint"] = _fingerprint(private)
    public = {key: value for key, value in private.items() if key != "scenarios"}
    public["scenarios"] = [_public_scenario(item["scenario"], item["baseline"]) for item in evaluated]
    public["readyToPublish"] = True
    return public, private


def metric_contract_preview_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], query_metric: Callable[[argparse.Namespace], dict[str, Any]]) -> dict[str, Any]:
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        plan, _private = _build_plan(connection, args, workspace_id, query_metric)
    return {"ok": True, "dryRun": True, "requiresConfirmation": True, "metricContractPlan": plan}


def _contract_key(workspace_id: str, metric_key: str, version: int, plan_fingerprint: str) -> str:
    return "metric_contract_" + hashlib.sha256(f"{workspace_id}\0{metric_key}\0{version}\0{plan_fingerprint}".encode("utf-8")).hexdigest()[:20]


def _contract_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    definition = json.loads(str(row["definition_json"]))
    binding = json.loads(str(row["binding_json"]))
    scenarios = json.loads(str(row["scenarios_json"]))
    current_row = _metric_row(connection, str(row["workspace_id"]), str(row["metric_key"]))
    current_definition = _definition(current_row, None)
    stored_core = {key: value for key, value in definition.items() if key != "contract"}
    definition_current = _fingerprint(stored_core) == _fingerprint(current_definition)
    current_binding = _binding(current_row)
    binding_current = current_binding == binding
    return {
        "schema": CONTRACT_SCHEMA,
        "contractKey": str(row["contract_key"]),
        "workspaceId": str(row["workspace_id"]),
        "metricKey": str(row["metric_key"]),
        "version": int(row["version"]),
        "label": str(row["label"]),
        "status": "current" if definition_current else "stale",
        "definition": definition,
        "definitionFingerprint": str(row["definition_fingerprint"]),
        "binding": binding,
        "bindingFingerprint": str(row["binding_fingerprint"]),
        "freshness": {
            "definitionCurrent": definition_current,
            "bindingCurrent": binding_current,
            "replayRecommended": not binding_current,
            "mismatches": ([] if definition_current else ["metric-definition-changed"]) + ([] if binding_current else ["data-version-changed"]),
        },
        "scenarios": [_public_scenario(item["scenario"], item["baseline"]) for item in scenarios],
        "planFingerprint": str(row["plan_fingerprint"]),
        "publishedAt": str(row["published_at"]),
    }


def metric_contract_publish_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], query_metric: Callable[[argparse.Namespace], dict[str, Any]], now_iso: Callable[[], str]) -> dict[str, Any]:
    if not bool(getattr(args, "yes", False)):
        raise ValueError("Metric Contract publish requires --yes after preview.")
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if len(expected) != 64:
        raise ValueError("Metric Contract publish requires the exact preview fingerprint.")
    request_key = _request_key(args)
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        existing = connection.execute("SELECT * FROM metric_contract_versions WHERE workspace_id=? AND request_key=?", (workspace_id, request_key)).fetchone()
        if existing:
            if str(existing["plan_fingerprint"]) != expected:
                raise ValueError("requestKey is already bound to a different Metric Contract plan.")
            return {"ok": True, "confirmed": True, "changed": False, "idempotentReplay": True, "metricContract": _contract_payload(connection, existing)}
        public, private = _build_plan(connection, args, workspace_id, query_metric)
        if expected != private["planFingerprint"]:
            raise ValueError("Metric Contract changed after preview; preview it again.")
        timestamp = now_iso()
        version = int(private["version"])
        key = _contract_key(workspace_id, private["metricKey"], version, expected)
        definition = private["definition"]
        binding = private["binding"]
        connection.execute(
            """INSERT INTO metric_contract_versions(contract_key,workspace_id,metric_key,version,request_key,label,status,definition_json,definition_fingerprint,binding_json,binding_fingerprint,scenarios_json,plan_fingerprint,published_at)
               VALUES(?,?,?,?,?,?, 'published',?,?,?,?,?,?,?)""",
            (key, workspace_id, private["metricKey"], version, request_key, str(getattr(args, "label", "") or definition["label"])[:160], _canonical(definition), _fingerprint(definition), _canonical(binding), _fingerprint(binding), _canonical(private["scenarios"]), expected, timestamp),
        )
        connection.execute("INSERT INTO metric_contract_events(workspace_id,contract_key,event_type,payload_json,created_at) VALUES(?,?, 'published', ?, ?)", (workspace_id, key, _canonical({"planFingerprint": expected, "scenarioCount": len(private["scenarios"])}), timestamp))
        connection.commit()
        saved = connection.execute("SELECT * FROM metric_contract_versions WHERE workspace_id=? AND contract_key=?", (workspace_id, key)).fetchone()
        payload = _contract_payload(connection, saved)
    return {"ok": True, "confirmed": True, "changed": True, "idempotentReplay": False, "metricContract": payload, "metricContractPlan": public}


def metric_contracts_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        contract_key = str(getattr(args, "contract", "") or "").strip()
        if contract_key:
            row = connection.execute("SELECT * FROM metric_contract_versions WHERE workspace_id=? AND contract_key=?", (workspace_id, contract_key)).fetchone()
            if not row:
                raise ValueError("Unknown Metric Contract")
            return {"ok": True, "workspaceId": workspace_id, "metricContract": _contract_payload(connection, row)}
        metric_ref = str(getattr(args, "metric", "") or "").strip()
        params: list[Any] = [workspace_id]
        clause = ""
        if metric_ref:
            metric = _metric_row(connection, workspace_id, metric_ref)
            clause = " AND metric_key=?"
            params.append(str(metric["metric_key"]))
        limit = max(1, min(int(getattr(args, "limit", 50) or 50), 100))
        params.append(limit)
        rows = connection.execute(f"SELECT * FROM metric_contract_versions WHERE workspace_id=?{clause} ORDER BY published_at DESC LIMIT ?", params).fetchall()
        contracts = [_contract_payload(connection, row) for row in rows]
    return {"ok": True, "workspaceId": workspace_id, "metricContracts": contracts, "count": len(contracts)}


def metric_contract_replay_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], query_metric: Callable[[argparse.Namespace], dict[str, Any]]) -> dict[str, Any]:
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        contract_key = str(getattr(args, "contract", "") or "").strip()
        row = connection.execute("SELECT * FROM metric_contract_versions WHERE workspace_id=? AND contract_key=?", (workspace_id, contract_key)).fetchone()
        if not row:
            raise ValueError("Unknown Metric Contract")
        contract = _contract_payload(connection, row)
        scenarios = json.loads(str(row["scenarios_json"]))
    comparisons = []
    for item in scenarios:
        try:
            current = _run_scenario(query_metric, workspace_id, str(row["metric_key"]), item["scenario"])
            baseline = item["baseline"]
            scalar_delta = None
            if baseline.get("scalar") is not None and current.get("scalar") is not None:
                scalar_delta = float(current["scalar"]) - float(baseline["scalar"])
            comparisons.append({
                "name": item["scenario"]["name"],
                "status": "passed" if current["resultFingerprint"] == baseline["resultFingerprint"] else "changed",
                "baseline": baseline,
                "current": current,
                "scalarDelta": scalar_delta,
            })
        except Exception as error:
            comparisons.append({"name": item["scenario"]["name"], "status": "blocked", "errorCode": type(error).__name__})
    changed = sum(1 for item in comparisons if item["status"] == "changed")
    blocked = sum(1 for item in comparisons if item["status"] == "blocked")
    return {
        "ok": blocked == 0,
        "schema": REPLAY_SCHEMA,
        "workspaceId": workspace_id,
        "contractKey": contract_key,
        "metricKey": str(row["metric_key"]),
        "status": "blocked" if blocked else "changed" if changed else "passed",
        "attribution": "definition-and-data-changed" if not contract["freshness"]["definitionCurrent"] and not contract["freshness"]["bindingCurrent"] else "definition-changed" if not contract["freshness"]["definitionCurrent"] else "data-changed" if not contract["freshness"]["bindingCurrent"] else "no-drift",
        "freshness": contract["freshness"],
        "comparisons": comparisons,
        "summary": {"total": len(comparisons), "passed": len(comparisons) - changed - blocked, "changed": changed, "blocked": blocked},
    }
