"""Conservative candidate extraction. Unresolved layout/semantics are quarantined."""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from datetime import date
from .core import digest, require_permission

FACTORS = {'원': 1, '천원': 1000, '백만원': 1_000_000, '억원': 100_000_000,
           '%': .01, '배': 1, '주': 1, '개월': 1}
NULLS = {'', '-', '—', 'N/A', 'NA', 'n/a', 'null'}
METRICS = {'매출액': 'revenue', '영업이익': 'operating_income', '순이익': 'net_income',
           '영업이익률': 'operating_margin', '순이익률': 'net_margin', 'EPS': 'eps', 'PER': 'per'}


def number(raw, unit):
    if raw is None or str(raw).strip() in NULLS: return None
    text = str(raw).strip().replace(',', '').replace('−', '-')
    if '\n' in text: raise ValueError('merged_cell')
    if text.startswith('(') and text.endswith(')'): text = '-' + text[1:-1]
    text = text.removesuffix('%').strip()
    if unit not in FACTORS: raise ValueError('unknown_unit')
    try:
        result = Decimal(text) * Decimal(str(FACTORS[unit]))
        if not result.is_finite(): raise ValueError('nonfinite_number')
        return float(result)
    except InvalidOperation: raise ValueError('ambiguous_number') from None


def read_pdf(path, ocr=False, max_pages=100):
    import pymupdf
    doc = pymupdf.open(path)
    if len(doc) > max_pages: raise ValueError('page_budget_exceeded')
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text(); method = 'embedded_text'
        if len(text.strip()) < 30 and page.get_images():
            if ocr:
                text = page.get_text(textpage=page.get_textpage_ocr(language='kor+eng', dpi=200, full=True))
                method = 'ocr'; tables = []  # OCR tables require manual alignment review.
            else: method = 'ocr_required'; tables = []
        else:
            tables = [{'bbox': list(t.bbox), 'cells': t.extract()} for t in page.find_tables().tables]
        pages.append({'page': i + 1, 'text': text, 'method': method, 'tables': tables})
    doc.close()
    return pages


def target_candidates(pages, report_id, file_sha):
    result = []
    for p in pages:
        text = p['text']
        # Isolated cover value, not every occurrence in a discussion of prior targets.
        if p['page'] == 1:
            m = re.search(r'목표주가\s*\n?\s*([\d,]+)', text)
            if m:
                result.append({'field': 'target_price', 'raw_value': m[1], 'value': number(m[1], '원'),
                               'raw_unit': '원', 'unit': 'KRW', 'page': 1, 'role': 'cover', 'effective_date': None})
        if '투자의견 및 목표주가 변동내역' in text:
            for m in re.finditer(r'(20\d{2}[.\-/]\d{2}[.\-/]\d{2})\s*\n\s*(CONVICTION BUY|BUY|HOLD|SELL)\s*\n\s*([\d,]+)', text):
                result.append({'field': 'target_price', 'raw_value': m[3], 'value': number(m[3], '원'),
                               'raw_unit': '원', 'unit': 'KRW', 'page': p['page'], 'role': 'target_history',
                               'effective_date': m[1].replace('.', '-').replace('/', '-'), 'opinion_raw': m[2]})
    for r in result:
        r.update(report_id=report_id, file_sha256=file_sha,
                 evidence_id=digest([report_id, file_sha, r['page'], r['field'], r['role']]),
                 quality_status='needs_review', training_eligible=False)
    return result


def target_conflicts(values, publication_date):
    current = [v for v in values if v['role'] == 'cover' or v.get('effective_date') == publication_date]
    prices = sorted(set(v['value'] for v in current if v['value'] is not None))
    return [{'code': 'target_price_conflict', 'values': prices, 'evidence_ids': [v['evidence_id'] for v in current]}] if len(prices) > 1 else []


def financial_candidates(pages, report_id, sha, publication_date):
    out, issues = [], []
    for page in pages:
        for table_index, table in enumerate(page['tables']):
            cells = table['cells']
            if not cells: continue
            header = cells[0]
            years = []
            for col, cell in enumerate(header):
                m = re.fullmatch(r'\s*(20\d{2})([FEA]?)\s*', cell or '')
                if m: years.append((col, int(m[1]), m[2]))
            for row_index, row in enumerate(cells[1:], 1):
                label = (row[0] or '').replace(' ', '') if row else ''
                metric = next((METRICS[k] for k in sorted(METRICS, key=len, reverse=True) if label.startswith(k)), None)
                if not metric: continue
                unit = next((x for x in ['억원','백만원','천원','원','%','배'] if x in label), None)
                if metric == 'per' and not unit: unit = '배'
                for col, year, suffix in years:
                    raw = row[col] if col < len(row) else None
                    try: value = number(raw, unit) if raw is not None else None
                    except ValueError as e:
                        issues.append({'code': str(e), 'page': page['page'], 'table': table_index, 'row': row_index, 'col': col}); value = None
                    # An unqualified historical report value is not an audited statement.
                    kind = 'society_forecast_candidate' if suffix in ('F','E') else 'historical_reported_unverified' if year < int(publication_date[:4]) else 'unknown'
                    out.append({'fact_id': digest([sha, page['page'], table_index, row_index, col]), 'report_id': report_id,
                                'file_sha256': sha, 'metric': metric, 'period_year': year, 'period_quarter': None,
                                'estimate_type': kind, 'currency': 'KRW' if unit and '원' in unit else None,
                                'raw_value': raw, 'raw_unit': unit, 'value': value,
                                'unit': 'ratio' if unit == '%' else 'KRW' if unit and '원' in unit else unit,
                                'consolidation': None, 'business_segment': None, 'page': page['page'],
                                'table_index': table_index, 'row_index': row_index, 'column_index': col,
                                'source_url': None, 'formula': None, 'input_evidence_ids': [],
                                'quality_status': 'needs_review', 'training_eligible': False})
    return out, issues


def licensed_extract(path, report, policy, ocr=False):
    require_permission(policy, 'pdf_processing'); require_permission(policy, 'derived_storage')
    pages = read_pdf(path, ocr=ocr)
    sha = digest(open(path, 'rb').read())
    values = target_candidates(pages, report['report_id'], sha)
    facts, issues = financial_candidates(pages, report['report_id'], sha, report['publication_date'])
    issues += target_conflicts(values, report['publication_date'])
    from .quality import numeric_issues
    issues += numeric_issues(facts)
    # Events and industry metrics require evidence-backed manual annotation of candidates;
    # a broad regex is not allowed to invent subjects, event dates or period semantics.
    return {'file_sha256': sha, 'pages': len(pages), 'valuations': values, 'financials': facts,
            'issues': issues, 'quality_status': 'needs_review', 'training_eligible': False}
