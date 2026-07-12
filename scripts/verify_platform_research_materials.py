from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from relationship_tools import build_relationship_preview  # noqa: E402


WORKBOOKS = {
    "douyin_order_logistics_synthetic.xlsx": {
        "订单商品明细": "douyin_orders_synthetic.xlsx",
        "售后明细": "douyin_aftersales_synthetic.xlsx",
        "物流明细": "douyin_logistics_synthetic.xlsx",
    },
    "taobao_order_logistics_synthetic.xlsx": {
        "交易主单": "taobao_trades_synthetic.xlsx",
        "子订单": "taobao_order_items_synthetic.xlsx",
        "退款单": "taobao_refunds_synthetic.xlsx",
        "物流单": "taobao_logistics_synthetic.xlsx",
    },
    "jushuitan_order_logistics_synthetic.xlsx": {
        "订单版本流": "jushuitan_orders_versioned_synthetic.xlsx",
        "订单商品": "jushuitan_order_items_synthetic.xlsx",
        "销售出库": "jushuitan_outbounds_synthetic.xlsx",
        "售后单": "jushuitan_aftersales_synthetic.xlsx",
        "物流同步": "jushuitan_logistics_synthetic.xlsx",
    },
}

REQUIRED_DOCS = [
    "README.md",
    "notes/case_library.md",
    "notes/closed_loop_test_plan.md",
    "notes/field_mapping.md",
    "notes/platform_pitfalls.md",
    "sources/douyin/official_notes.md",
    "sources/taobao/official_notes.md",
    "sources/jushuitan/official_notes.md",
]


def frame_equal(left: pd.DataFrame, right: pd.DataFrame) -> tuple[bool, str]:
    try:
        pd.testing.assert_frame_equal(
            left.reset_index(drop=True),
            right.reset_index(drop=True),
            check_dtype=False,
            check_like=False,
        )
        return True, ""
    except AssertionError as error:
        return False, str(error).splitlines()[0]


def relation_receipt(
    name: str,
    left: pd.DataFrame,
    right: pd.DataFrame,
    keys: list[str],
) -> dict[str, Any]:
    left_keys = left[keys].astype("string").fillna("")
    right_keys = right[keys].astype("string").fillna("")
    left_key = left_keys.agg("\x1f".join, axis=1)
    right_key = right_keys.agg("\x1f".join, axis=1)
    right_counts = right_key.value_counts()
    joined_rows = int(left_key.map(right_counts).fillna(1).sum())
    matched_rows = int(left_key.isin(set(right_key)).sum())
    empty_left_keys = int(left_keys.eq("").any(axis=1).sum())
    empty_right_keys = int(right_keys.eq("").any(axis=1).sum())
    duplicate_right_keys = int(right_key[right_key.duplicated(keep=False)].nunique())
    return {
        "name": name,
        "keys": keys,
        "leftRows": len(left),
        "rightRows": len(right),
        "matchedLeftRows": matched_rows,
        "unmatchedLeftRows": len(left) - matched_rows,
        "emptyLeftKeyRows": empty_left_keys,
        "emptyRightKeyRows": empty_right_keys,
        "duplicateRightKeys": duplicate_right_keys,
        "joinedRows": joined_rows,
        "rowExpansion": round(joined_rows / len(left), 6) if len(left) else 0,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    templates = root / "templates"
    checks: list[dict[str, Any]] = []

    standalone: dict[str, pd.DataFrame] = {}
    for mapping in WORKBOOKS.values():
        for filename in mapping.values():
            standalone[filename] = pd.read_excel(templates / filename)

    for combined_name, mapping in WORKBOOKS.items():
        workbook = pd.read_excel(templates / combined_name, sheet_name=None)
        expected_sheets = [*mapping, "说明与验收"]
        checks.append({
            "id": f"{combined_name}:sheet-set",
            "ok": list(workbook) == expected_sheets,
            "actual": list(workbook),
            "expected": expected_sheets,
        })
        for sheet_name, standalone_name in mapping.items():
            ok, error = frame_equal(workbook[sheet_name], standalone[standalone_name])
            checks.append({
                "id": f"{combined_name}:{sheet_name}:standalone-parity",
                "ok": ok,
                "rows": len(workbook[sheet_name]),
                "columns": len(workbook[sheet_name].columns),
                "standalone": standalone_name,
                "error": error,
            })

    for relative in REQUIRED_DOCS:
        path = root / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        requires_source_link = relative == "notes/case_library.md" or relative.startswith("sources/")
        checks.append({
            "id": f"documentation:{relative}",
            "ok": bool(text.strip()) and (not requires_source_link or "http" in text),
            "bytes": len(text.encode("utf-8")),
        })

    douyin_orders = standalone["douyin_orders_synthetic.xlsx"]
    douyin_aftersales = standalone["douyin_aftersales_synthetic.xlsx"]
    douyin_logistics = standalone["douyin_logistics_synthetic.xlsx"]
    taobao_trades = standalone["taobao_trades_synthetic.xlsx"]
    taobao_items = standalone["taobao_order_items_synthetic.xlsx"]
    taobao_refunds = standalone["taobao_refunds_synthetic.xlsx"]
    taobao_logistics = standalone["taobao_logistics_synthetic.xlsx"]
    jst_orders_raw = standalone["jushuitan_orders_versioned_synthetic.xlsx"]
    jst_orders = jst_orders_raw.sort_values("ts").drop_duplicates("o_id", keep="last")
    jst_items = standalone["jushuitan_order_items_synthetic.xlsx"]
    jst_outbounds = standalone["jushuitan_outbounds_synthetic.xlsx"]
    jst_aftersales = standalone["jushuitan_aftersales_synthetic.xlsx"]
    jst_logistics = standalone["jushuitan_logistics_synthetic.xlsx"]

    relationships = [
        relation_receipt("douyin-order-aftersales", douyin_orders, douyin_aftersales, ["主订单编号", "商品ID", "商家编码"]),
        relation_receipt("douyin-order-logistics", douyin_orders, douyin_logistics, ["主订单编号", "子订单编号"]),
        relation_receipt("taobao-trade-items", taobao_trades, taobao_items, ["tid"]),
        relation_receipt("taobao-item-refunds", taobao_items, taobao_refunds, ["tid", "oid"]),
        relation_receipt("taobao-trade-logistics", taobao_trades, taobao_logistics, ["tid"]),
        relation_receipt("jst-order-items", jst_orders, jst_items, ["o_id"]),
        relation_receipt("jst-order-outbounds", jst_orders, jst_outbounds, ["o_id"]),
        relation_receipt("jst-order-aftersales", jst_orders, jst_aftersales, ["o_id"]),
        relation_receipt("jst-order-logistics", jst_orders, jst_logistics, ["o_id"]),
    ]
    expected_expansion = {
        "douyin-order-aftersales": 1.1,
        "douyin-order-logistics": 1.1,
        "taobao-trade-items": 1.375,
        "taobao-item-refunds": 1.0,
        "taobao-trade-logistics": 1.125,
        "jst-order-items": 1.5,
        "jst-order-outbounds": 1.25,
        "jst-order-aftersales": 1.0,
        "jst-order-logistics": 1.25,
    }
    for relation in relationships:
        expected = expected_expansion[relation["name"]]
        checks.append({
            "id": f"relationship:{relation['name']}:row-expansion",
            "ok": abs(relation["rowExpansion"] - expected) < 1e-9,
            "actual": relation["rowExpansion"],
            "expected": expected,
        })

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    taobao_trades.to_sql("trades", connection, index=False)
    taobao_items.to_sql("items", connection, index=False)
    relationship_runtime = build_relationship_preview(
        connection,
        "trades",
        "items",
        list(taobao_trades.columns),
        list(taobao_items.columns),
        [{"leftField": "tid", "rightField": "tid"}],
        join_type="left",
        sample_limit=5,
        quote_identifier=lambda name: '"' + str(name).replace('"', '""') + '"',
    )
    connection.close()
    checks.append({
        "id": "relationship-runtime:output-rows-and-expansion",
        "ok": relationship_runtime["metrics"].get("outputRows") == 11
        and relationship_runtime["metrics"].get("rowExpansion") == 1.375
        and any("1.38 倍" in warning for warning in relationship_runtime["warnings"]),
        "metrics": relationship_runtime["metrics"],
        "warnings": relationship_runtime["warnings"],
    })

    failed = [check for check in checks if not check["ok"]]
    receipt = {
        "ok": not failed,
        "schema": "aibi-platform-research-materials-verify/v1",
        "researchRoot": str(root),
        "combinedWorkbooks": len(WORKBOOKS),
        "standaloneTables": len(standalone),
        "documents": len(REQUIRED_DOCS),
        "checks": len(checks),
        "failed": failed,
        "relationships": relationships,
        "relationshipRuntime": relationship_runtime,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
