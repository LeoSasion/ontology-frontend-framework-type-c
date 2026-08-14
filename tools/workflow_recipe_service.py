from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sqlite3
from typing import Any, Callable

from bi_cli_contracts import command_semantics
from capability_contract_service import build_capability_contract, validate_capability_invocation
from workflow_stage_service import build_workflow_stage


PLAN_SCHEMA = "aibi-workflow-recipe-plan/v1"
RECIPE_SCHEMA = "aibi-workflow-recipe/v1"
RUN_SCHEMA = "aibi-workflow-recipe-instantiation/v1"
PLACEHOLDER = re.compile(r"^\$\{([A-Za-z][A-Za-z0-9_.-]{0,63})\}$")
URL_LITERAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*://|www\.)", re.IGNORECASE)
SQL_LITERAL = re.compile(r"^(?:select|insert|update|delete|merge|drop|alter|create|with|pragma|attach|detach)\b", re.IGNORECASE)
CODE_LITERAL = re.compile(r"^(?:(?:python|node|powershell|cmd|bash|sh)\s+|(?:eval|exec)\s*\(|```)", re.IGNORECASE)
SECRET_DESTINATIONS = {"password", "token", "access_token", "api_key", "secret", "client_secret"}
PATH_DESTINATIONS = {"path", "file", "folder", "source_path", "output", "output_path", "package", "database", "root"}
FRESH_BINDING_DESTINATIONS = {"request_key", "expected_plan"}
FORBIDDEN_CONTROL_DESTINATIONS = {"workspace", "yes", "confirm", "confirmed"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _workspace(connection: sqlite3.Connection, args: argparse.Namespace, active_workspace_id: Callable[[sqlite3.Connection], str]) -> str:
    workspace_id = str(getattr(args, "workspace", "") or "").strip() or active_workspace_id(connection)
    if not connection.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _request_key(args: argparse.Namespace) -> str:
    key = str(getattr(args, "request_key", "") or "").strip()
    if len(key) < 8 or len(key) > 200:
        raise ValueError("Workflow Recipe requires a requestKey between 8 and 200 characters.")
    return key


def _subparser(parser: argparse.ArgumentParser, command: str) -> argparse.ArgumentParser | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(command)
    return None


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item[:1].upper() + item[1:] for item in tail)


def _input_contract(command_parser: argparse.ArgumentParser) -> tuple[dict[str, str], set[str]]:
    aliases: dict[str, str] = {}
    required: set[str] = set()
    for action in command_parser._actions:
        destination = str(getattr(action, "dest", "") or "")
        if not destination or destination == "help" or destination == argparse.SUPPRESS:
            continue
        for alias in {destination, _camel_case(destination)}:
            aliases[alias] = destination
        for option in getattr(action, "option_strings", []):
            normalized = str(option).lstrip("-").replace("-", "_")
            aliases[normalized] = destination
            aliases[_camel_case(normalized)] = destination
        if bool(getattr(action, "required", False)):
            required.add(destination)
    return aliases, required


def _validate_literal(value: Any, *, destination: str, publication: bool) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _validate_literal(item, destination=destination, publication=publication)
        return
    if isinstance(value, list):
        for item in value:
            _validate_literal(item, destination=destination, publication=publication)
        return
    if not isinstance(value, str) or PLACEHOLDER.fullmatch(value):
        return
    normalized = value.strip()
    if destination in SECRET_DESTINATIONS:
        raise ValueError(f"Workflow Recipe cannot carry secret input: {destination}")
    if publication and (destination in PATH_DESTINATIONS or destination in FRESH_BINDING_DESTINATIONS):
        raise ValueError(f"Workflow Recipe input must use a fresh placeholder: {destination}")
    if URL_LITERAL.match(normalized) or SQL_LITERAL.match(normalized) or CODE_LITERAL.match(normalized):
        raise ValueError(f"Workflow Recipe rejects URL, SQL, or code literals in input: {destination}")


def _validate_stage_inputs(command_parser: argparse.ArgumentParser, inputs: dict[str, Any], *, publication: bool) -> dict[str, str]:
    aliases, required = _input_contract(command_parser)
    destinations: dict[str, str] = {}
    for key, value in inputs.items():
        normalized_key = str(key)
        destination = aliases.get(normalized_key)
        if destination is None:
            raise ValueError(f"Workflow Recipe stage uses an unknown capability input: {normalized_key}")
        if destination in FORBIDDEN_CONTROL_DESTINATIONS:
            raise ValueError(f"Workflow Recipe cannot freeze authorization or workspace input: {normalized_key}")
        _validate_literal(value, destination=destination, publication=publication)
        destinations[normalized_key] = destination
    missing = sorted(required - set(destinations.values()))
    if missing:
        raise ValueError(f"Workflow Recipe stage is missing required capability inputs: {', '.join(missing)}")
    return destinations


def _public_resolved_inputs(inputs: dict[str, Any], destinations: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in inputs.items():
        destination = destinations[key]
        if destination in PATH_DESTINATIONS or destination == "request_key":
            result[key] = {
                "bound": not (isinstance(value, str) and PLACEHOLDER.fullmatch(value)),
                "valueFingerprint": _fingerprint(value),
            }
        else:
            result[key] = value
    return result


def _stages(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    raw = getattr(args, "stage_json", []) or []
    if isinstance(raw, str):
        raw = [raw]
    if not 1 <= len(raw) <= 12:
        raise ValueError("Workflow Recipe requires between 1 and 12 stages.")
    result = []
    for index, value in enumerate(raw, start=1):
        try:
            item = json.loads(str(value))
        except json.JSONDecodeError as error:
            raise ValueError("Workflow Recipe stage must be valid JSON.") from error
        if not isinstance(item, dict):
            raise ValueError("Workflow Recipe stage must be an object.")
        command = str(item.get("command") or "").strip()
        command_parser = _subparser(parser, command)
        if not command_parser or command in {"workflow-recipe-preview", "workflow-recipe-publish", "workflow-recipe-plan"}:
            raise ValueError(f"Workflow Recipe stage uses an unsupported capability: {command}")
        inputs = item.get("input") if isinstance(item.get("input"), dict) else {}
        if len(_canonical(inputs)) > 8_000:
            raise ValueError("Workflow Recipe stage input is too large.")
        _validate_stage_inputs(command_parser, inputs, publication=True)
        semantics = command_semantics(command, command_parser)
        capability = build_capability_contract(command, semantics)
        result.append({
            "sequence": index,
            "label": str(item.get("label") or command).strip()[:120],
            "command": command,
            "capabilityId": capability["capabilityId"],
            "input": inputs,
            "requiresConfirmation": bool(capability["confirmation"]["required"]),
            "mutationMode": capability["mutationMode"],
        })
    return result


def _build_plan(connection: sqlite3.Connection, args: argparse.Namespace, parser: argparse.ArgumentParser, active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    workspace_id = _workspace(connection, args, active_workspace_id)
    request_key = _request_key(args)
    name = str(getattr(args, "name", "") or "").strip()[:160]
    if not name:
        raise ValueError("Workflow Recipe name is required.")
    stages = _stages(args, parser)
    previous = connection.execute("SELECT version FROM workflow_recipes WHERE workspace_id=? AND name=? ORDER BY version DESC LIMIT 1", (workspace_id, name)).fetchone()
    material = {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
        "name": name,
        "description": str(getattr(args, "description", "") or "").strip()[:500],
        "version": int(previous["version"] if previous else 0) + 1,
        "stages": stages,
        "confirmationStageCount": sum(1 for stage in stages if stage["requiresConfirmation"]),
    }
    material["planFingerprint"] = _fingerprint(material)
    material["readyToPublish"] = True
    return material


def workflow_recipe_preview_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with contextlib.closing(open_db()) as connection:
        plan = _build_plan(connection, args, parser, active_workspace_id)
    return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workflowRecipePlan": plan}


def _recipe_key(workspace_id: str, name: str, version: int, plan_fingerprint: str) -> str:
    return "recipe_" + hashlib.sha256(f"{workspace_id}\0{name}\0{version}\0{plan_fingerprint}".encode("utf-8")).hexdigest()[:20]


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    stages = json.loads(str(row["stages_json"]))
    return {
        "schema": RECIPE_SCHEMA,
        "recipeKey": str(row["recipe_key"]),
        "workspaceId": str(row["workspace_id"]),
        "name": str(row["name"]),
        "description": str(row["description"]),
        "version": int(row["version"]),
        "status": str(row["status"]),
        "stages": stages,
        "stageCount": len(stages),
        "confirmationStageCount": sum(1 for stage in stages if stage.get("requiresConfirmation")),
        "planFingerprint": str(row["plan_fingerprint"]),
        "publishedAt": str(row["published_at"]),
    }


def workflow_recipe_publish_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    if not bool(getattr(args, "yes", False)):
        raise ValueError("Workflow Recipe publish requires --yes after preview.")
    request_key = _request_key(args)
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if len(expected) != 64:
        raise ValueError("Workflow Recipe publish requires the exact preview fingerprint.")
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace(connection, args, active_workspace_id)
        existing = connection.execute("SELECT * FROM workflow_recipes WHERE workspace_id=? AND request_key=?", (workspace_id, request_key)).fetchone()
        if existing:
            if str(existing["plan_fingerprint"]) != expected:
                raise ValueError("requestKey is already bound to another Workflow Recipe plan.")
            return {"ok": True, "confirmed": True, "changed": False, "idempotentReplay": True, "workflowRecipe": _payload(existing)}
        plan = _build_plan(connection, args, parser, active_workspace_id)
        if plan["planFingerprint"] != expected:
            raise ValueError("Workflow Recipe changed after preview; preview it again.")
        key = _recipe_key(workspace_id, plan["name"], plan["version"], expected)
        timestamp = now_iso()
        connection.execute("INSERT INTO workflow_recipes(recipe_key,workspace_id,name,description,version,request_key,status,stages_json,plan_fingerprint,published_at) VALUES(?,?,?,?,?,?, 'published', ?,?,?)", (key, workspace_id, plan["name"], plan["description"], plan["version"], request_key, _canonical(plan["stages"]), expected, timestamp))
        connection.execute("INSERT INTO workflow_recipe_events(workspace_id,recipe_key,event_type,payload_json,created_at) VALUES(?,?, 'published', ?,?)", (workspace_id, key, _canonical({"planFingerprint": expected, "stageCount": len(plan["stages"])}), timestamp))
        connection.commit()
        saved = connection.execute("SELECT * FROM workflow_recipes WHERE workspace_id=? AND recipe_key=?", (workspace_id, key)).fetchone()
        payload = _payload(saved)
    return {"ok": True, "confirmed": True, "changed": True, "idempotentReplay": False, "workflowRecipe": payload}


def workflow_recipes_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace(connection, args, active_workspace_id)
        recipe_key = str(getattr(args, "recipe", "") or "").strip()
        if recipe_key:
            row = connection.execute("SELECT * FROM workflow_recipes WHERE workspace_id=? AND recipe_key=?", (workspace_id, recipe_key)).fetchone()
            if not row:
                raise ValueError("Unknown Workflow Recipe")
            return {"ok": True, "workspaceId": workspace_id, "workflowRecipe": _payload(row)}
        rows = connection.execute("SELECT * FROM workflow_recipes WHERE workspace_id=? ORDER BY published_at DESC LIMIT ?", (workspace_id, max(1, min(int(getattr(args, "limit", 50) or 50), 100)))).fetchall()
        recipes = [_payload(row) for row in rows]
    return {"ok": True, "workspaceId": workspace_id, "workflowRecipes": recipes, "count": len(recipes)}


def _resolve(value: Any, bindings: dict[str, Any], required: set[str]) -> Any:
    if isinstance(value, dict):
        return {str(key): _resolve(item, bindings, required) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, bindings, required) for item in value]
    if isinstance(value, str):
        match = PLACEHOLDER.fullmatch(value)
        if match:
            key = match.group(1)
            required.add(key)
            return bindings.get(key, value)
    return value


def workflow_recipe_plan_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    try:
        bindings = json.loads(str(getattr(args, "bindings_json", "{}") or "{}"))
    except json.JSONDecodeError as error:
        raise ValueError("bindings-json must be an object.") from error
    if not isinstance(bindings, dict) or len(_canonical(bindings)) > 8_000:
        raise ValueError("Workflow Recipe bindings must be a bounded object.")
    with contextlib.closing(open_db()) as connection:
        workspace_id = _workspace(connection, args, active_workspace_id)
        row = connection.execute("SELECT * FROM workflow_recipes WHERE workspace_id=? AND recipe_key=?", (workspace_id, str(args.recipe))).fetchone()
        if not row:
            raise ValueError("Unknown Workflow Recipe")
        recipe = _payload(row)
    required: set[str] = set()
    stages = []
    blockers = []
    for item in recipe["stages"]:
        command = str(item["command"])
        command_parser = _subparser(parser, command)
        semantics = command_semantics(command, command_parser)
        capability = build_capability_contract(command, semantics)
        resolved = _resolve(item.get("input", {}), bindings, required)
        input_destinations = _validate_stage_inputs(command_parser, resolved, publication=False)
        public_resolved = _public_resolved_inputs(resolved, input_destinations)
        missing = sorted(key for key in required if key not in bindings)
        # A Recipe freezes the canonical CLI capability contract but never
        # invokes it. Runtime/API entrypoint authorization is rechecked only
        # when the user executes the stage in its owning product surface.
        stage_blockers = validate_capability_invocation(capability, entrypoint="cli", confirmed=False, workspace_id=workspace_id)
        stage_result = {"ok": not stage_blockers, "requiresConfirmation": item["requiresConfirmation"], "evidence": []}
        stage = build_workflow_stage(command=command, args=public_resolved, result=stage_result, capability=capability, status="waiting-confirmation" if item["requiresConfirmation"] else "planned")
        stage["label"] = item["label"]
        stage["blockers"] = stage_blockers
        stages.append(stage)
        blockers.extend(stage_blockers)
    missing = sorted(key for key in required if key not in bindings)
    blockers.extend(f"missing-binding:{key}" for key in missing)
    return {
        "ok": True,
        "schema": RUN_SCHEMA,
        "workspaceId": workspace_id,
        "recipe": recipe,
        "bindingsFingerprint": _fingerprint(bindings),
        "requiredBindings": sorted(required),
        "missingBindings": missing,
        "stages": stages,
        "confirmationStageCount": sum(1 for stage in stages if stage["requiresConfirmation"]),
        "blockers": sorted(set(blockers)),
        "readyToProceed": not blockers,
        "executesAutomatically": False,
    }
