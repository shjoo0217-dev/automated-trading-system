from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from .common import dump_json, read_jsonl, timestamp
from .schema import validate_fact


def assess(reports, facts):
    errors, warnings = [], []
    report_ids = {r["report_id"] for r in reports}
    ids = set()
    for r in reports:
        if timestamp(r["available_at"]) < timestamp(r["first_seen_at"]) and r.get("availability_rule", "").startswith("first_observed"):
            errors.append({"report_id": r["report_id"], "error": "backdated_availability"})
    for f in facts:
        try:
            validate_fact(f)
        except ValueError as e:
            errors.append({"fact_id": f.get("fact_id"), "error": str(e)})
        if f["fact_id"] in ids or f["report_id"] not in report_ids:
            errors.append({"fact_id": f["fact_id"], "error": "duplicate_or_orphan_fact"})
        ids.add(f["fact_id"])
        if f["extraction_status"] == "needs_review":
            warnings.append({"fact_id": f["fact_id"], "warning": "parser_disagreement"})
        if f["value"] == 0 and f["metric"] in {"per", "pbr", "psr"}:
            warnings.append({"fact_id": f["fact_id"], "warning": "zero_valuation_preserved_as_printed; do_not_use_as_cheap_signal"})
    groups = {}
    for f in facts:
        groups.setdefault((f["report_id"], f["fiscal_year"], f["statement_scope"]), {})[f["metric"]] = f
    for key, g in groups.items():
        if all(k in g and g[k]["value"] is not None for k in ["assets", "liabilities", "equity"]):
            delta = abs(g["assets"]["value"] - g["liabilities"]["value"] - g["equity"]["value"])
            if delta > 2:  # up to three independently rounded hundred-million KRW values
                errors.append({"report_id": key[0], "year": key[1], "error": "balance_identity_outside_rounding", "difference": delta})
        if all(k in g and g[k]["value"] is not None for k in ["revenue", "operating_profit", "operating_margin_pct"]) and g["revenue"]["value"]:
            diff = abs(100 * g["operating_profit"]["value"] / g["revenue"]["value"] - g["operating_margin_pct"]["value"])
            # Very small sales / large negative earnings amplify integer rounding.
            tolerance = 0.1 + 50 / abs(g["revenue"]["value"]) + 50 * abs(g["operating_profit"]["value"]) / g["revenue"]["value"] ** 2
            if diff > tolerance:
                errors.append({"report_id": key[0], "year": key[1], "error": "margin_mismatch", "difference_pp": diff})
    return {"status": "failed" if errors else "passed_with_limitations", "errors": errors, "warnings": warnings,
            "reports": len(reports), "companies": len({r["stock_code"] for r in reports}), "facts": len(facts),
            "null_facts": sum(f["value"] is None for f in facts),
            "parser_agreement_facts": sum(f["parser_agreement"] for f in facts),
            "unknown_statement_scope_facts": sum(f["statement_scope"] == "unknown" for f in facts),
            "dart_reconciled_facts": sum(f["financial_verification"] == "opendart_matched" for f in facts)}


def create_database(root: Path, reports, financials, forecasts, business):
    path = root / "data" / "investment.sqlite"
    tmp = path.with_suffix(".tmp.sqlite")
    if tmp.exists():
        tmp.unlink()
    with sqlite3.connect(tmp) as conn:
        def write(name, rows):
            if not rows:
                return
            flattened = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows]
            pd.DataFrame(flattened).to_sql(name, conn, index=False)
        write("reports", reports)
        write("financials", financials)
        write("forecasts", forecasts)
        write("business_risks", business)
        for name in ["financials", "forecasts"]:
            conn.execute(f"CREATE UNIQUE INDEX {name}_fact_id ON {name}(fact_id)")
            conn.execute(f"CREATE INDEX {name}_point_in_time ON {name}(stock_code,available_at,fiscal_year,metric)")
        conn.execute("CREATE UNIQUE INDEX reports_id ON reports(report_id)")
        conn.execute("CREATE INDEX report_family ON reports(family_id,available_at)")
    tmp.replace(path)


def validate_directory(root: Path):
    reports = read_jsonl(root / "data/reports.jsonl")
    facts = []
    for name in ["financials", "forecasts"]:
        p = root / f"data/{name}.parquet"
        if p.exists():
            import pyarrow.parquet as pq
            facts.extend(pq.read_table(p).to_pylist())
    result = assess(reports, facts)
    dump_json(root / "evaluation/quality_checks.json", result)
    if result["errors"]:
        raise ValueError("Dataset validation failed; latest pointer must not change")
    return result
