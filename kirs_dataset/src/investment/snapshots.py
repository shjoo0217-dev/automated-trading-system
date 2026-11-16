import io
import re

import pdfplumber

from .extract import word_rows, norm, box
from .common import stable_id


def company_snapshots(report, data):
    specs = [("현재주가", "price", "KRW", 1), ("현재가(원)", "price", "KRW", 1),
             ("시가총액", "market_cap", "KRW", 1e8), ("발행주식수", "shares_outstanding", "shares", 1),
             ("일평균거래량", "average_volume_60d", "shares_per_day", 1),
             ("외국인지분율", "foreign_ownership_pct", "percent", 1)]
    output = []
    outsourcing = report["report_type"] == "ktc_summary_v1"
    with pdfplumber.open(io.BytesIO(data)) as doc:
        rows = word_rows(doc.pages[1], x0=25 if outsourcing else 380, x1=220 if outsourcing else 560, min_y=120)
        for row in rows:
            text = norm("".join(w["text"] for w in row))
            for prefix, metric, unit, scale in specs:
                if not text.startswith(prefix):
                    continue
                m = re.search(r"(-?[\d,]+(?:\.\d+)?)(백만주|만주|억원|억|원|%|주)?$", text)
                if not m:
                    continue
                if m[2] == "백만주": scale = 1e6
                elif m[2] == "만주": scale = 1e4
                date = re.search(r"\((\d{1,2}/\d{1,2})\)", text)
                output.append({"snapshot_id": stable_id(report["report_id"], metric),
                    **{k: report[k] for k in ["report_id", "source_id", "stock_code", "available_at", "source_url"]},
                    "metric": metric, "value": float(m[1].replace(",", "")), "unit": unit,
                    "multiplier": float(scale), "value_base_units": float(m[1].replace(",", "")) * scale,
                    "reference_date": "2024-08-22" if outsourcing else None,
                    "reference_date_text": "2024.08.22 기준" if outsourcing else (date[1] if date else None),
                    "date_status": "explicit" if outsourcing else "partial_or_unspecified; do_not_infer_exact_date",
                    "page": 2, "table": "시세정보" if outsourcing else "Company Data", "row_label": prefix,
                    "raw_value": m[0], "bbox": box(row), "extraction_status": "rule_parsed_review_sample",
                    "price_use": "report_snapshot_only; not licensed daily market data"})
                break
    return output
