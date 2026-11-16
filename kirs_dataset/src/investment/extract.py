"""Two observed KIRS layouts. Unknown layouts go to review, never guessed.

Only tabular facts and short metadata are emitted. Full PDF/text is not retained
unless separately licensed. OCR and LLM suggestions are NOT treated as labels.
"""
from __future__ import annotations

import calendar
import io
import re
from decimal import Decimal, InvalidOperation

import pdfplumber
import pymupdf

from .common import available_at, digest, stable_id
from .schema import validate_fact

SUMMARY = [
    ("매출액(억원)", "revenue", "KRW_100M"),
    ("YoY(%)", "revenue_growth_pct", "percent"),
    ("영업이익(억원)", "operating_profit", "KRW_100M"),
    ("OP마진(%)", "operating_margin_pct", "percent"),
    ("지배주주순이익(억원)", "net_income_parent", "KRW_100M"),
    ("EPS(원)", "eps", "KRW_per_share"),
    ("YoY(%)", "eps_growth_pct", "percent"),
    ("PER(배)", "per", "multiple"), ("PSR(배)", "psr", "multiple"),
    ("EV/EBITDA(배)", "ev_ebitda", "multiple"),
    ("PBR(배)", "pbr", "multiple"), ("ROE(%)", "roe_pct", "percent"),
    ("배당수익률(%)", "dividend_yield_pct", "percent"),
]
APPENDIX = {
    "자산총계": ("assets", "KRW_100M"), "부채총계": ("liabilities", "KRW_100M"),
    "자본총계": ("equity", "KRW_100M"), "당기순이익": ("net_income", "KRW_100M"),
    "영업활동으로인한현금흐름": ("operating_cash_flow", "KRW_100M"),
    "유형자산의증가(CAPEX)": ("capex_cash_flow_signed", "KRW_100M"),
    "부채비율": ("debt_to_equity_pct", "percent"),
}
OUTSOURCE = [
    ("매출액", "revenue", "KRW_100M"), ("증감", "revenue_growth_pct", "percent"),
    ("영업이익", "operating_profit", "KRW_100M"), ("이익률", "operating_margin_pct", "percent"),
    ("순이익", "net_income", "KRW_100M"), ("이익률", "net_margin_pct", "percent"),
    ("ROE", "roe_pct", "percent"), ("ROA", "roa_pct", "percent"),
    ("부채비율", "debt_to_equity_pct", "percent"), ("EPS", "eps", "KRW_per_share"),
    ("BPS", "bps", "KRW_per_share"), ("PER", "per", "multiple"), ("PBR", "pbr", "multiple"),
]


def norm(text):
    return re.sub(r"\s+", "", text.replace("\x00", "").replace("\x01", "").replace("−", "-"))


def numeric(token):
    clean = norm(token).replace(",", "")
    if clean in {"N/A", "NA", "-", "–", "—", "", "적지", "적전", "흑전", "흑지"}:
        return None, "source_non_numeric:" + clean
    try:
        if clean.startswith("(") and clean.endswith(")"):
            clean = "-" + clean[1:-1]
        number = Decimal(clean)
        if not number.is_finite():
            raise InvalidOperation
        return number, None
    except InvalidOperation:
        return None, "unreadable_token"


def box(words):
    return [min(w["x0"] for w in words), min(w["top"] for w in words),
            max(w["x1"] for w in words), max(w["bottom"] for w in words)]


def word_rows(page, x0=0, x1=None, min_y=0):
    groups = []
    for w in sorted(page.extract_words(x_tolerance=1, y_tolerance=2), key=lambda w: (w["top"], w["x0"])):
        if w["x0"] < x0 or (x1 is not None and w["x1"] > x1) or w["top"] < min_y:
            continue
        match = next((g for g in groups[-3:] if abs(g[0]["top"] - w["top"]) < 2), None)
        if match is None:
            groups.append([w])
        else:
            match.append(w)
    return [sorted(g, key=lambda w: w["x0"]) for g in groups]


def report_metadata(spec, pdf, observed):
    first = pdf[0].get_text(sort=True)
    second = pdf[1].get_text(sort=True)
    code = re.search(r"\((\d{6})\)", first)
    if not code or code.group(1) != spec["stock_code"]:
        raise ValueError("Company/code mismatch between discovery record and PDF")
    if norm(spec["company_name"]) not in norm(first):
        raise ValueError("Company name mismatch")
    dt = re.search(r"(20\d{2})\.(\d{2})\.(\d{2})", first)
    if not dt:
        raise ValueError("Publication date absent on PDF cover")
    publication_date = "-".join(dt.groups())
    analyst = re.search(r"Analyst\s+(\S+)", second)
    source_id = stable_id(spec["url"])
    report_id = stable_id(source_id, observed["sha256"])
    # Conservative over-grouping of same issuer+publication date is intentional.
    family = spec.get("family_id") or stable_id("KIRS", spec["stock_code"], publication_date)
    return {
        "report_id": report_id, "source_id": source_id, "family_id": family,
        "content_version": observed["sha256"], "company_name": spec["company_name"],
        "stock_code": spec["stock_code"], "market": spec.get("market"), "industry": spec.get("industry"),
        "title": spec["title"], "publisher": spec.get("publisher", "한국IR협의회 기업리서치센터"),
        "commissioner": "한국IR협의회", "authors": spec.get("authors") or ([analyst.group(1)] if analyst else []),
        "language": "ko", "report_type": spec["layout"], "publication_date": publication_date,
        "published_at": None, "public_time_precision": "date_only_pdf_cover",
        "issuer_posted_date": spec.get("issuer_posted_date"), "first_seen_at": observed["first_seen_at"],
        "collected_at": observed["collected_at"], "available_at": available_at(observed["first_seen_at"], None),
        "availability_rule": "first_observed_current_bytes; never backdate historical imports",
        "source_url": spec["url"], "discovery_url": spec["discovery_url"],
        "source_host_role": "issuer_ir_copy_of_kirs_report", "page_count": len(pdf),
        "target_price": None, "recommendation": None,
        "target_price_status": "not_collected_no_explicit_target_verified",
        "translation_of": None, "supersedes": None, "relationship_status": "no_verified_link",
        "raw_retained": False, "raw_retention_reason": "No permission for full PDF redistribution; metadata only",
        "training_use_permitted": False, "rights_status": "limited_fact_pilot; bulk_or_model_training_needs_clearance",
        "metadata_evidence": {"identity_page": 1, "date_page": 1, "author_page": 2 if analyst else 1,
                              "title_page": 1 if spec["layout"] == "kirs_summary_v1" else 2},
        "extraction_status": "pending", "fiscal_calendar_note": spec.get("fiscal_calendar_note"),
    }


def make_fact(report, fitz_page, *, metric, unit, raw_word, label_words, period_words, year_label,
              page, table, row_label, scope="unknown", scope_evidence=None, fiscal_end_month=None):
    raw = raw_word["text"]
    value, missing = numeric(raw)
    bbox = box([raw_word])
    # A second parser re-reads exactly this geometric cell.
    second_words = [w for w in fitz_page.get_text("words")
                    if bbox[0] - .8 <= (w[0] + w[2]) / 2 <= bbox[2] + .8
                    and bbox[1] <= (w[1] + w[3]) / 2 <= bbox[3]]
    second = norm("".join(w[4] for w in sorted(second_words, key=lambda w: w[0])))
    agreement = second == norm(raw)
    year = int(year_label[:4])
    kind = "forecast" if year_label.endswith(("F", "E")) else "preliminary" if year_label.endswith("P") else "actual"
    multiplier = 1e8 if unit == "KRW_100M" else 1.0
    currency = "KRW" if unit.startswith("KRW") else None
    start = end = mapping = None
    if fiscal_end_month == 2:
        start = f"{year}-03-01"
        end = f"{year+1}-02-{calendar.monthrange(year+1, 2)[1]:02}"
        mapping = "PDF page 2: 2월 결산법인; FY2024 = 2024-03 through 2025-02"
    row = {
        "fact_id": stable_id(report["report_id"], table, metric, year_label),
        **{k: report[k] for k in ["report_id", "source_id", "content_version", "family_id", "stock_code", "company_name"]},
        "metric": metric, "value": float(value) if value is not None else None,
        "value_decimal": str(value) if value is not None else None,
        "value_base_units": float(value * Decimal(str(multiplier))) if value is not None else None,
        "raw_value": raw, "missing_reason": missing, "unit": unit, "unit_multiplier": multiplier,
        "currency": currency, "fiscal_year": year, "fiscal_period": "FY" + str(year),
        "period_start": start, "period_end": end, "period_mapping_evidence": mapping,
        "value_type": kind, "estimate_owner": "research_publisher" if kind == "forecast" else None,
        "statement_scope": scope, "scope_evidence": scope_evidence,
        "reference_date": None, "reference_date_text": None,
        "source_url": report["source_url"], "page": page,
        "printed_page": str(page if report["report_type"] == "kirs_summary_v1" else page - 1),
        "table": table, "row_label": row_label, "column_label": year_label,
        "bbox": bbox, "label_bbox": box(label_words), "period_bbox": box(period_words),
        "parser_agreement": agreement,
        "extraction_status": "dual_parser_agreed" if agreement and missing != "unreadable_token" else "needs_review",
        "financial_verification": "not_reconciled_with_opendart",
        **{k: report[k] for k in ["first_seen_at", "collected_at", "published_at", "available_at", "training_use_permitted"]},
    }
    validate_fact(row)
    return row


def extract(spec: dict, pdf_bytes: bytes, observed: dict):
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Not a PDF")
    observed = {**observed, "sha256": digest(pdf_bytes)}
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as fp, pdfplumber.open(io.BytesIO(pdf_bytes)) as pp:
        if len(fp) < 2:
            raise ValueError("Insufficient pages")
        report = report_metadata(spec, fp, observed)
        if len(fp[1].get_text().strip()) < 100:
            raise ValueError("OCR required; excluded until manually reviewed")
        result = []
        if spec["layout"] == "kirs_summary_v1":
            # Observed five-column table; stop on any change in headers/column count.
            rows = word_rows(pp.pages[1], x1=370, min_y=400)
            header = next((r for r in rows if len([w for w in r if re.fullmatch(r"20\d\d[FEP]?", w["text"])]) == 5), None)
            if not header:
                raise ValueError("Unrecognized summary header; requires layout review")
            periods = [w for w in header if re.fullmatch(r"20\d\d[FEP]?", w["text"])]
            sequence = 0
            for row in rows:
                if row[0]["top"] <= header[0]["top"]:
                    continue
                labels = [w for w in row if w["x0"] < 140]
                values = [w for w in row if w["x0"] >= 140]
                if sequence >= len(SUMMARY):
                    break
                expected, metric, unit = SUMMARY[sequence]
                label = norm("".join(w["text"] for w in labels))
                # Preserve the original typo EV/EBIDA, but normalize the metric name.
                if label == "EV/EBIDA(배)":
                    normalized_label = "EV/EBITDA(배)"
                else:
                    normalized_label = label
                if normalized_label != expected:
                    continue
                if len(values) != 5:
                    raise ValueError(f"Wrong column count: {metric}")
                for period, v in zip(periods, values):
                    result.append(make_fact(report, fp[1], metric=metric, unit=unit, raw_word=v,
                        label_words=labels, period_words=[period], year_label=period["text"], page=2,
                        table="Forecast earnings & Valuation", row_label=label,
                        fiscal_end_month=spec.get("fiscal_end_month")))
                sequence += 1
            if sequence != len(SUMMARY):
                raise ValueError(f"Only {sequence} of {len(SUMMARY)} summary rows recognized")
            appendix_index = len(pp.pages) - 2
            appendix = pp.pages[appendix_index]
            if "재무상태표" not in (appendix.extract_text() or ""):
                raise ValueError("Appendix layout not recognized")
            extracted = set()
            for side, (x0, x1) in enumerate([(45, 306), (306, 560)]):
                for words in word_rows(appendix, x0=x0, x1=x1):
                    for n in range(1, min(len(words), 7)):
                        label = norm("".join(w["text"] for w in words[:n]))
                        if label not in APPENDIX or label in extracted:
                            continue
                        vals = words[n:]
                        if len(vals) != 5:
                            continue
                        metric, unit = APPENDIX[label]
                        # Re-read this page's own fiscal headers, never borrow cell locations.
                        local_rows = word_rows(appendix, x0=x0, x1=x1)
                        candidates = [[w for w in r if re.fullmatch(r"20\d\d[FEP]?", w["text"])] for r in local_rows]
                        local_periods = next((c for c in candidates if len(c) == 5), None)
                        if not local_periods or [w["text"] for w in local_periods] != [w["text"] for w in periods]:
                            raise ValueError("Appendix periods disagree with summary")
                        for period, v in zip(local_periods, vals):
                            result.append(make_fact(report, fp[appendix_index], metric=metric, unit=unit,
                                raw_word=v, label_words=words[:n], period_words=[period], year_label=period["text"],
                                page=appendix_index+1, table="Financial statements appendix", row_label=label,
                                fiscal_end_month=spec.get("fiscal_end_month")))
                        extracted.add(label)
            if extracted != set(APPENDIX):
                raise ValueError("Missing appendix rows: " + str(sorted(set(APPENDIX)-extracted)))
        elif spec["layout"] == "ktc_summary_v1":
            rows = word_rows(pp.pages[1], min_y=700)
            header = next((r for r in rows if norm(r[0]["text"]) == "매출액" and len(r) == 13), None)
            if not header:
                raise ValueError("Outsourcing header not recognized")
            for row in rows:
                if len(row) != 14 or not re.fullmatch(r"20\d{2}", row[0]["text"]):
                    continue
                for v, h, (label, metric, unit) in zip(row[1:], header, OUTSOURCE):
                    if norm(h["text"]) != label:
                        raise ValueError("Outsourcing metric header differs")
                    result.append(make_fact(report, fp[1], metric=metric, unit=unit, raw_word=v,
                        label_words=[h], period_words=[row[0]], year_label=row[0]["text"], page=2,
                        table="요약 투자지표", row_label=label, scope="consolidated",
                        scope_evidence="PDF page 2: K-IFRS 연결 기준"))
            if len(result) != 39:
                raise ValueError("Outsourcing expected 3 years x 13 metrics")
        else:
            raise ValueError("Unsupported layout; needs review")
        report["extraction_status"] = "parsed_with_quarantine" if any(r["extraction_status"] == "needs_review" for r in result) else "dual_parser_agreed"
        return report, result
