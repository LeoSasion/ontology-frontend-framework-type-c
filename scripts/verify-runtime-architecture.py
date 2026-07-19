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
EXPECTED_DISPATCH_FINGERPRINT = "3a43e99455a255e722d921758bf26c83b0a77ca15ca2b32e38f237a8d5e5f51e"
EXPECTED_USE_CASE_MODULES = {
    "agent_interaction.py",
    "analysis.py",
    "control.py",
    "data.py",
    "delivery.py",
    "lifecycle.py",
}
KERNEL_LINE_BUDGET = 50
AGENT_INTERACTION_LINE_BUDGET = 2349


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


entry_path = TOOLS / "aibi_cli.py"
kernel_path = TOOLS / "aibi_runtime" / "kernel.py"
parser_path = TOOLS / "aibi_runtime" / "parser.py"
use_case_dir = TOOLS / "aibi_runtime" / "use_cases"
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
kernel_tree = ast.parse(kernel_source, filename=str(kernel_path))
kernel_definitions = [
    node.name
    for node in kernel_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
]
kernel_import_modules = {
    str(node.module or "")
    for node in kernel_tree.body
    if isinstance(node, ast.ImportFrom)
}
check(
    "runtime-kernel-is-composition-only",
    not kernel_definitions
    and kernel_import_modules
    == {f"use_cases.{path.removesuffix('.py')}" for path in EXPECTED_USE_CASE_MODULES},
    {"definitions": kernel_definitions, "imports": sorted(kernel_import_modules)},
)
use_case_paths = {
    path.name: path
    for path in use_case_dir.glob("*.py")
    if path.name != "__init__.py"
}
use_case_line_counts = {
    name: len(path.read_text(encoding="utf-8").splitlines())
    for name, path in sorted(use_case_paths.items())
}
check(
    "application-use-case-modules-are-explicit",
    set(use_case_paths) == EXPECTED_USE_CASE_MODULES,
    {"actual": sorted(use_case_paths), "expected": sorted(EXPECTED_USE_CASE_MODULES)},
)
check(
    "agent-interaction-use-case-line-budget",
    use_case_line_counts.get("agent_interaction.py", 0) <= AGENT_INTERACTION_LINE_BUDGET,
    {
        "lineCount": use_case_line_counts.get("agent_interaction.py", 0),
        "budget": AGENT_INTERACTION_LINE_BUDGET,
    },
)
use_case_kernel_imports = [
    name
    for name, path in use_case_paths.items()
    if "aibi_runtime.kernel" in path.read_text(encoding="utf-8")
    or "from .. import kernel" in path.read_text(encoding="utf-8")
    or "from . import kernel" in path.read_text(encoding="utf-8")
]
check("application-use-cases-do-not-import-kernel", not use_case_kernel_imports, use_case_kernel_imports)
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
dispatcher_use_case_mismatches: list[str] = []
for group in registry.groups:
    dispatcher_path = TOOLS / "aibi_runtime" / f"dispatch_{group.name}.py"
    dispatcher_source = dispatcher_path.read_text(encoding="utf-8")
    expected_import = f"from .use_cases import {group.name} as runtime"
    if expected_import not in dispatcher_source or "from . import kernel as runtime" in dispatcher_source:
        dispatcher_use_case_mismatches.append(group.name)
lifecycle_source = (TOOLS / "aibi_runtime" / "dispatch.py").read_text(encoding="utf-8")
if "from .use_cases import lifecycle as runtime" not in lifecycle_source:
    dispatcher_use_case_mismatches.append("lifecycle")
check(
    "dispatchers-depend-on-domain-use-cases",
    not dispatcher_use_case_mismatches,
    dispatcher_use_case_mismatches,
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

kernel_reference_tokens = (
    "aibi_runtime." + "kernel",
    "from aibi_runtime import " + "kernel",
    "from . import " + "kernel",
)
compatibility_kernel_callers: list[str] = []
for base in (ROOT / "server", ROOT / "scripts", ROOT / "tools", ROOT / "src"):
    for path in base.rglob("*.py"):
        if path.resolve() in {Path(__file__).resolve(), kernel_path.resolve()}:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in source for token in kernel_reference_tokens):
            compatibility_kernel_callers.append(str(path.relative_to(ROOT)))
check(
    "no-runtime-callers-use-compatibility-kernel",
    not compatibility_kernel_callers,
    compatibility_kernel_callers,
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-runtime-architecture-verify/v1",
    "commandCount": len(registry.commands),
    "commandGroups": group_sizes,
    "dispatchFingerprint": dispatch_fingerprint,
    "kernelLineCount": len(kernel_source.splitlines()),
    "useCaseLineCounts": use_case_line_counts,
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not failed else 1)
