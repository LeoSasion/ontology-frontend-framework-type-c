from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from evidence_profile_runtime.semantic_text import SEMANTIC_ALIASES

DEFAULT_DOMAIN_PACK_RUNTIME: dict[str, Any] = {
    "version": 2,
    "domainPackId": "aibi-generic-tabular",
    "ontologyDomain": "generic-tabular",
    "label": "Generic tabular data / 通用表格数据",
    "generatedBy": "tools/evidence_profile_runtime/domain_pack_runtime.py",
    "loadStatus": "fallback_static",
    "semanticHints": [
        {"semantic": semantic, "aliases": aliases[:8]}
        for semantic, aliases in sorted(SEMANTIC_ALIASES.items())
    ],
    "runtimeUse": {
        "semanticScorer": "Field names, table names, and value shapes produce explainable candidates.",
        "relationshipDiscovery": "Identity-like fields and overlapping samples create non-writing relationship evidence.",
        "metricCompiler": "Only metrics backed by detected fields produce executable result samples.",
    },
}

SOURCE_PIPELINE_CONTRACT: dict[str, Any] = {
    "version": 2,
    "status": "ready",
    "generatedBy": "tools/source_evidence_engine.py",
    "stages": [
        {"id": "reader", "outputEvidence": ["source-profile-generic.json"]},
        {"id": "profiler", "outputEvidence": ["source-profile-generic.json"]},
        {"id": "semantic_scorer", "outputEvidence": ["semantic-field-candidates.json", "semantic-confirmation-draft.json"]},
        {"id": "relationship_discovery", "outputEvidence": ["relationship-discovery.json", "relationship-coverage-matrix.json"]},
        {"id": "diagnostics", "outputEvidence": ["data-gap-diagnostics.json", "source-readiness-diagnostics.json", "source-quality-diagnostics.json"]},
        {"id": "metric_compiler", "outputEvidence": ["metric-sql-compiler.json"]},
        {"id": "query_runtime", "outputEvidence": ["metric-query-results.json"]},
        {"id": "artifact_contract", "outputEvidence": ["analysis-requirement-catalog.json"]},
    ],
    "guardrails": [
        "Source files are read-only.",
        "Generated SQL is evidence; writes still require a separate confirmation boundary.",
        "Low confidence semantics remain reviewable instead of silently becoming business truth.",
    ],
}


def load_domain_pack_runtime(
    domain_pack_runtime_path: Path | None,
    *,
    default_runtime_file: dict[str, Any] | None = None,
    rel_path: Callable[[Path], str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if domain_pack_runtime_path and domain_pack_runtime_path.exists():
        try:
            loaded = json.loads(domain_pack_runtime_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                runtime = {**DEFAULT_DOMAIN_PACK_RUNTIME, **loaded, "loadedFrom": str(domain_pack_runtime_path)}
                return runtime, {**SOURCE_PIPELINE_CONTRACT, "domainPackRuntime": runtime}
        except (OSError, json.JSONDecodeError):
            pass
    runtime = dict(default_runtime_file or DEFAULT_DOMAIN_PACK_RUNTIME)
    runtime.setdefault("loadedFrom", None)
    return runtime, {**SOURCE_PIPELINE_CONTRACT, "domainPackRuntime": runtime}


def merge_semantic_catalog_with_domain_pack(catalog: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    merged = dict(catalog)
    for item in runtime.get("semanticHints", []):
        if isinstance(item, dict) and item.get("semantic"):
            merged.setdefault(str(item["semantic"]), {}).setdefault("aliases", item.get("aliases", []))
    return merged
