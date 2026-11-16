from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .common import stable_id, timestamp

NUMERIC_FEATURES = ["revenue_growth_pct", "operating_margin_pct", "margin_change_pp",
                    "eps_growth_pct", "per", "pbr", "psr", "ev_ebitda", "roe_pct",
                    "dividend_yield_pct", "debt_to_equity_pct", "revenue_forecast_revision_pct"]


def build_features(reports, facts, tags=()):
    result = []
    previous = {}
    seen_hashes = set()
    reports = sorted(reports, key=lambda r: (r["available_at"], r["stock_code"], r["publication_date"], r["report_id"]))
    for report in reports:
        # Byte-identical copies and translations explicitly mapped to a single family
        # must not become independent signals. Versions are still kept in reports.
        if report["content_version"] in seen_hashes:
            continue
        seen_hashes.add(report["content_version"])
        rows = [f for f in facts if f["report_id"] == report["report_id"] and f["extraction_status"] == "dual_parser_agreed"]
        if not rows:
            continue
        current_year = max(f["fiscal_year"] for f in rows)
        current = {f["metric"]: f for f in rows if f["fiscal_year"] == current_year}
        prior = {f["metric"]: f for f in rows if f["fiscal_year"] == current_year - 1}
        row = {"sample_id": stable_id("features", report["report_id"]),
               **{k: report[k] for k in ["stock_code", "company_name", "report_id", "family_id", "source_id", "available_at", "publication_date"]},
               "signal_id": report["family_id"], "fiscal_year": current_year,
               "value_type": "forecast" if any(f["value_type"] == "forecast" for f in current.values()) else "actual",
               "training_eligible": False, "eligibility_reason": "training_rights_and_financial_validation_pending",
               "business_tags": json.dumps(sorted({t["tag"] for t in tags if t["report_id"] == report["report_id"] and t["kind"] == "business"}), ensure_ascii=False),
               "risk_tags": json.dumps(sorted({t["tag"] for t in tags if t["report_id"] == report["report_id"] and t["kind"] == "risk"}), ensure_ascii=False)}
        used = []
        for metric in NUMERIC_FEATURES:
            row[metric] = current.get(metric, {}).get("value")
            if metric in {"per", "pbr", "psr", "ev_ebitda"} and row[metric] is not None and row[metric] <= 0:
                row[metric] = None  # Source zero remains intact in facts.
            if metric in current:
                used.append(current[metric]["fact_id"])
        a, b = current.get("operating_margin_pct", {}), prior.get("operating_margin_pct", {})
        if a.get("value") is not None and b.get("value") is not None:
            row["margin_change_pp"] = a["value"] - b["value"]
            used.extend([a["fact_id"], b["fact_id"]])
        # Revisions only from a strictly earlier available version of SAME family,
        # SAME target year, currency, unit and statement scope. Historical imports
        # in one batch must never masquerade as a revision time series.
        rev = current.get("revenue", {})
        key = (report["family_id"], current_year, rev.get("currency"), rev.get("statement_scope"), rev.get("unit"))
        prev = previous.get(key)
        if prev and rev.get("value_type") == "forecast" and prev["value_type"] == "forecast" and prev["value"] and prev["value"] > 0:
            if timestamp(prev["available_at"]) < timestamp(report["available_at"]):
                row["revenue_forecast_revision_pct"] = 100 * (rev["value"] / prev["value"] - 1)
                used.extend([rev["fact_id"], prev["fact_id"]])
        if rev:
            previous[key] = rev
        row["source_fact_ids"] = json.dumps(sorted(set(used)))
        row["training_eligible"] = bool(rows) and all(f["training_use_permitted"] and (
            f["value_type"] == "forecast" or f["financial_verification"] == "opendart_matched") for f in rows)
        if row["training_eligible"]:
            row["eligibility_reason"] = "approved"
        result.append(row)
    return pd.DataFrame(result).sort_values(["stock_code", "available_at", "report_id"]).reset_index(drop=True) if result else pd.DataFrame()


def labels_from_prices(features: pd.DataFrame, prices: pd.DataFrame, sessions: pd.DataFrame, *,
                       license_confirmed=False, horizon=20, decision_lag_seconds=60, as_of=None):
    """20 exchange-session open-to-open price return. Never fill missing sessions.

    sessions columns: session_date, open_at (timezone aware).
    prices columns: stock_code, session_date, adjusted_open, tradable, source_id.
    adjusted_open must incorporate split/rights adjustments consistently; cash
    dividends are NOT included. Delisting/missing/halts remain explicit exclusions.
    """
    if not license_confirmed:
        raise PermissionError("A licensed price source is required")
    required = {"stock_code", "session_date", "adjusted_open", "tradable", "source_id"}
    if not required <= set(prices):
        raise ValueError("Incomplete price schema")
    if prices.duplicated(["stock_code", "session_date"]).any():
        raise ValueError("Duplicate price observations")
    if sessions.session_date.duplicated().any():
        raise ValueError("Duplicate exchange sessions")
    if not prices.stock_code.map(lambda x: isinstance(x, str) and len(x) == 6 and x.isdigit()).all():
        raise ValueError("Price stock codes must be strings with leading zeros")
    sessions = sessions.copy().sort_values("session_date").reset_index(drop=True)
    sessions["open_at"] = pd.to_datetime(sessions.open_at.map(lambda v: timestamp(v)), utc=True)
    if not sessions.open_at.is_monotonic_increasing:
        raise ValueError("Non-monotonic calendar")
    observed_at = pd.Timestamp(as_of or pd.Timestamp.now(tz="UTC"))
    out = []
    for sample in features.to_dict("records"):
        cutoff = pd.Timestamp(timestamp(sample["available_at"])) + pd.Timedelta(seconds=decision_lag_seconds)
        eligible = sessions.index[sessions.open_at > cutoff].tolist()
        by_date = prices[prices.stock_code == sample["stock_code"]].set_index("session_date")
        entry = next((i for i in eligible if sessions.iloc[i].session_date in by_date.index
                      and bool(by_date.loc[sessions.iloc[i].session_date, "tradable"])), None)
        base = {"sample_id": sample["sample_id"], "stock_code": sample["stock_code"], "family_id": sample["family_id"],
                "horizon_sessions": horizon, "label": None, "label_status": "no_tradable_entry",
                "entry_at": None, "exit_at": None, "entry_date": None, "exit_date": None, "price_source_id": None}
        if entry is None:
            out.append(base)
            continue
        exit_index = entry + horizon
        base.update(entry_at=sessions.iloc[entry].open_at.isoformat(), entry_date=sessions.iloc[entry].session_date)
        if exit_index >= len(sessions):
            base["label_status"] = "horizon_not_observed"
            out.append(base)
            continue
        exit_session = sessions.iloc[exit_index]
        base.update(exit_at=exit_session.open_at.isoformat(), exit_date=exit_session.session_date)
        if exit_session.open_at > observed_at:
            base["label_status"] = "future_horizon"
        elif exit_session.session_date not in by_date.index or not bool(by_date.loc[exit_session.session_date, "tradable"]):
            base["label_status"] = "exit_missing_halted_or_delisted"
        else:
            p0 = by_date.loc[base["entry_date"]]
            p1 = by_date.loc[base["exit_date"]]
            if pd.isna(p0.adjusted_open) or pd.isna(p1.adjusted_open) or p0.adjusted_open <= 0 or p1.adjusted_open <= 0:
                base["label_status"] = "invalid_price"
            elif p0.source_id != p1.source_id:
                base["label_status"] = "price_source_mismatch"
            else:
                base.update(label=float(p1.adjusted_open / p0.adjusted_open - 1), label_status="valid", price_source_id=p0.source_id)
        out.append(base)
    return pd.DataFrame(out)
