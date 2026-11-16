"""Optional OpenDART adapter. No credentials or external financials are bundled."""
import os, time
import requests
from .core import now


def filings(corp_code, start, end, pages=1):
    if pages > 5: raise ValueError('dart_page_budget')
    key = os.environ['DART_API_KEY']  # Inject from GitHub Actions Secrets / Secret Manager.
    result=[]
    for page in range(1,pages+1):
        # Avoid response.raise_for_status(): its exception can expose the query-string API key.
        r=requests.get('https://opendart.fss.or.kr/api/list.json', params={
            'crtfc_key':key,'corp_code':corp_code,'bgn_de':start,'end_de':end,'page_no':page,'page_count':100},timeout=30)
        if r.status_code!=200: raise RuntimeError('dart_http_failure')
        data=r.json()
        if data.get('status')=='013': break
        if data.get('status')!='000': raise RuntimeError('dart_api_failure')
        for item in data['list']:
            result.append({**item,'first_observed_at':now(),'known_at':now(),
                           'availability_rule':'first_observed_conservative; receipt_date_alone_not_intraday_proof'})
        if page>=data.get('total_page',0): break
        time.sleep(1)
    return result
