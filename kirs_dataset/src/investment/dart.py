"""Official, documented OpenDART adapter. Authentication is mandatory.

No key is included; use DART_API_KEY from encrypted repository Secrets.
Endpoint/fields checked at DS003 / apiId=2019020 on 2026-11-17 KST.
"""
import os
import time
import requests

from .common import now


def fetch_financials(corp_code: str, year: int, reprt_code="11011", fs_div="CFS"):
    key = os.environ.get("DART_API_KEY")
    if not key:
        return {"status": "not_collected", "reason": "DART_API_KEY missing", "rows": []}
    if len(corp_code) != 8 or not corp_code.isdigit() or fs_div not in {"CFS", "OFS"}:
        raise ValueError("Use official 8-digit corp_code and explicit CFS/OFS")
    if reprt_code not in {"11011", "11012", "11013", "11014"}:
        raise ValueError("Unknown report code")
    for attempt in range(3):
        try:
            response = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
                params={"crtfc_key": key, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div}, timeout=30)
        except requests.RequestException:
            if attempt == 2:
                raise RuntimeError("DART transport failure (URL redacted)") from None
            time.sleep(3 * (attempt + 1))
            continue
        if response.status_code != 200:
            raise RuntimeError(f"DART HTTP {response.status_code} (URL redacted)")
        payload = response.json()
        status = payload.get("status")
        if status == "000":
            return {"status": "collected", "collected_at": now(), "fs_div": fs_div, "corp_code": corp_code,
                    "year": year, "reprt_code": reprt_code, "rows": payload["list"]}
        if status == "013":
            return {"status": "not_available", "reason": "DART 013 no data; not zero", "rows": []}
        # Includes 010/011 authentication, 012 IP, 020 quota: no retry/rotation.
        raise RuntimeError(f"DART application status {status}; stopped")


def compare_amount(report_value_base_units, dart_value, *, same_period, same_scope, same_account, rounding_unit=1e8):
    if not all([same_period, same_scope, same_account]):
        return "not_comparable"
    if report_value_base_units is None or dart_value in {None, "", "-"}:
        return "missing"
    from decimal import Decimal
    difference = abs(Decimal(str(report_value_base_units)) - Decimal(str(dart_value).replace(",", "")))
    return "matched_with_rounding" if difference <= Decimal(str(rounding_unit)) / 2 else "mismatch_review"
