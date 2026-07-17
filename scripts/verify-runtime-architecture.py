from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aibi_runtime.parser import build_parser  # noqa: E402
from aibi_runtime.registry import build_command_registry  # noqa: E402


checks: list[dict[str, object]] = []
EXPECTED_COMMAND_COUNT = 171
EXPECTED_GROUP_SIZES = {
    "control": 36,
    "analysis": 38,
    "data": 66,
    "delivery": 31,
}
EXPECTED_DISPATCH_FINGERPRINT = "5cffc55c7b1b01ffc91e0e30c353ea36d3f1031b7956d4c4b5e9cb9a53a5fa2e"
KERNEL_LINE_BUDGET = 2816


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


entry_path = TOOLS / "aibi_cli.py"
kernel_path = TOOLS / "aibi_runtime" / "kernel.py"
parser_path = TOOLS / "aibi_runtime" / "parser.py"
entry_source = entry_path.read_text(encoding="utf-8")
kernel_source = kernel_path.read_text(encoding="utf-8")

legacy_entry_name = "bi_" + "cli.py"
check("legacy-monolithic-entry-removed", not (TOOLS / legacy_entry_name).exists())
check("legacy-parser-location-removed", not (TOOLS / "bi_cli_parser.py").exists())
check(
    "public-cli-is-a-thin-adapter",
    "from aibi_runtime.dispatch import main" in entry_source and len(entry_source.splitlines()) <= 10,
    {"lineCount": len(entry_source.splitlines())},
)
check("runtime-kernel-does-not-own-process-entry", "def main(" not in kernel_source)
check(
    "runtime-kernel-line-budget",
    len(kernel_source.splitlines()) <= KERNEL_LINE_BUDGET,
    {"lineCount": len(kernel_source.splitlines()), "budget": KERNEL_LINE_BUDGET},
)
check("runtime-parser-moved-behind-package-boundary", parser_path.exists())

registry = build_command_registry()
parser = build_parser()
try:
    registry.validate_parser(parser)
except Exception as error:  # pragma: no cover - verifier failure detail
    check("parser-and-command-registry-match", False, str(error))
else:
    check("parser-and-command-registry-match", True)

group_names = [group.name for group in registry.groups]
group_sizes = {group.name: len(group.commands) for group in registry.groups}
check(
    "runtime-dispatch-is-domain-partitioned",
    group_names == ["control", "analysis", "data", "delivery"] and group_sizes == EXPECTED_GROUP_SIZES,
    {"groups": group_names, "sizes": group_sizes},
)
check(
    "runtime-command-inventory-size",
    len(registry.commands) == EXPECTED_COMMAND_COUNT,
    {"commandCount": len(registry.commands), "expected": EXPECTED_COMMAND_COUNT},
)


def command_names_from_test(test: ast.expr) -> list[str]:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return []
    left = test.left
    if not (
        isinstance(left, ast.Attribute)
        and left.attr == "command"
        and isinstance(left.value, ast.Name)
        and left.value.id == "args"
    ):
        return []
    comparator = test.comparators[0]
    if isinstance(test.ops[0], ast.Eq) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
        return [comparator.value]
    if isinstance(test.ops[0], ast.In) and isinstance(comparator, (ast.Set, ast.Tuple, ast.List)):
        return sorted(
            item.value
            for item in comparator.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    return []


def dispatcher_inventory(group) -> dict[str, str]:
    source_path = Path(group.handler.__code__.co_filename).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    dispatch_function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "dispatch"
    )
    branch = next((node for node in dispatch_function.body if isinstance(node, ast.If)), None)
    inventory: dict[str, str] = {}
    while isinstance(branch, ast.If):
        branch_commands = command_names_from_test(branch.test)
        body_fingerprint_input = ast.dump(
            ast.Module(body=branch.body, type_ignores=[]),
            annotate_fields=True,
            include_attributes=False,
        )
        for command in branch_commands:
            inventory[command] = body_fingerprint_input
        branch = branch.orelse[0] if len(branch.orelse) == 1 and isinstance(branch.orelse[0], ast.If) else None
    return inventory


dispatch_inventory: dict[str, dict[str, str]] = {}
dispatch_mismatches: dict[str, dict[str, list[str]]] = {}
for group in registry.groups:
    inventory = dispatcher_inventory(group)
    dispatch_inventory[group.name] = inventory
    registered = set(group.commands)
    implemented = set(inventory)
    if registered != implemented:
        dispatch_mismatches[group.name] = {
            "missingBranches": sorted(registered - implemented),
            "unregisteredBranches": sorted(implemented - registered),
        }
check("registry-and-dispatch-branches-match", not dispatch_mismatches, dispatch_mismatches)

dispatch_fingerprint = hashlib.sha256(
    json.dumps(dispatch_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
check(
    "runtime-dispatch-mapping-fingerprint",
    dispatch_fingerprint == EXPECTED_DISPATCH_FINGERPRINT,
    {"actual": dispatch_fingerprint, "expected": EXPECTED_DISPATCH_FINGERPRINT},
)

old_entry_pattern = re.compile(r"(?<![A-Za-z0-9_])bi_cli\.py")
stale_references: list[str] = []
for base in (ROOT / "server", ROOT / "scripts", ROOT / "tools", ROOT / "src", ROOT / "docs"):
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".mjs", ".js", ".ts", ".tsx", ".md"}:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if old_entry_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            stale_references.append(str(path.relative_to(ROOT)))
for path in (ROOT / "package.json", ROOT / "README.md"):
    if path.exists() and old_entry_pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
        stale_references.append(str(path.relative_to(ROOT)))
check("no-callers-use-retired-entry-name", not stale_references, stale_references)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-runtime-architecture-verify/v1",
    "commandCount": len(registry.commands),
    "commandGroups": group_sizes,
    "dispatchFingerprint": dispatch_fingerprint,
    "kernelLineCount": len(kernel_source.splitlines()),
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not failed else 1)
