import pyarrow as pa

FACT_SCHEMA = pa.schema([
    ("fact_id", pa.string()), ("report_id", pa.string()), ("source_id", pa.string()),
    ("content_version", pa.string()), ("family_id", pa.string()), ("stock_code", pa.string()),
    ("company_name", pa.string()), ("metric", pa.string()), ("value", pa.float64()),
    ("value_decimal", pa.string()), ("value_base_units", pa.float64()), ("raw_value", pa.string()),
    ("missing_reason", pa.string()), ("unit", pa.string()), ("unit_multiplier", pa.float64()),
    ("currency", pa.string()), ("fiscal_year", pa.int32()), ("fiscal_period", pa.string()),
    ("period_start", pa.string()), ("period_end", pa.string()), ("period_mapping_evidence", pa.string()),
    ("value_type", pa.string()), ("estimate_owner", pa.string()), ("statement_scope", pa.string()),
    ("scope_evidence", pa.string()), ("reference_date", pa.string()), ("reference_date_text", pa.string()),
    ("source_url", pa.string()), ("page", pa.int32()), ("printed_page", pa.string()),
    ("table", pa.string()), ("row_label", pa.string()), ("column_label", pa.string()),
    ("bbox", pa.list_(pa.float64())), ("label_bbox", pa.list_(pa.float64())),
    ("period_bbox", pa.list_(pa.float64())), ("parser_agreement", pa.bool_()),
    ("extraction_status", pa.string()), ("financial_verification", pa.string()),
    ("first_seen_at", pa.string()), ("collected_at", pa.string()), ("published_at", pa.string()),
    ("available_at", pa.string()), ("training_use_permitted", pa.bool_()),
])


def write_facts(path, rows):
    import pyarrow.parquet as pq
    table = pa.Table.from_pylist(rows, schema=FACT_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd")


def validate_fact(row):
    import math
    import re
    if not re.fullmatch(r"\d{6}", row["stock_code"] or ""):
        raise ValueError("stock_code must be a six-character string")
    if row["page"] < 1 or not row["bbox"] or not row["source_url"]:
        raise ValueError("Missing page/cell provenance")
    if row["value"] is not None and not math.isfinite(row["value"]):
        raise ValueError("Non-finite numeric value")
    if row["value"] is None and not row["missing_reason"]:
        raise ValueError("Null must have a missing reason")
    if row["value_type"] == "forecast" and row["estimate_owner"] not in {"research_publisher", "company"}:
        raise ValueError("Unknown forecast owner")
    if row["value_type"] not in {"actual", "preliminary", "forecast", "unknown"}:
        raise ValueError("Invalid value type")
