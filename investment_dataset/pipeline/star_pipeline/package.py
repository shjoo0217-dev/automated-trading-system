from __future__ import annotations
import csv, json, shutil, zipfile
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from .core import dump, digest, now

FINANCIAL_SCHEMA = pa.schema([
    ('fact_id',pa.string()),('report_id',pa.string()),('ticker',pa.string()),('file_sha256',pa.string()),
    ('metric',pa.string()),('period_year',pa.int32()),('period_quarter',pa.int8()),('estimate_type',pa.string()),
    ('currency',pa.string()),('raw_value',pa.string()),('raw_unit',pa.string()),('value',pa.float64()),('unit',pa.string()),
    ('consolidation',pa.string()),('business_segment',pa.string()),('page',pa.int32()),
    ('source_url',pa.string()),('formula',pa.string()),('input_evidence_ids',pa.list_(pa.string())),
    ('quality_status',pa.string()),('training_eligible',pa.bool_())])
VALUATION_SCHEMA = pa.schema([
    ('evidence_id',pa.string()),('report_id',pa.string()),('ticker',pa.string()),('file_sha256',pa.string()),
    ('field',pa.string()),('raw_value',pa.string()),('value',pa.float64()),('raw_unit',pa.string()),('unit',pa.string()),
    ('page',pa.int32()),('role',pa.string()),('effective_date',pa.string()),('opinion_raw',pa.string()),
    ('source_url',pa.string()),('observed_at',pa.string()),('quality_status',pa.string()),('training_eligible',pa.bool_())])


def csv_write(path, rows, fields=None):
    fields=fields or sorted(set(k for r in rows for k in r))
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items() if k in fields})


def jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows),encoding='utf-8')


def build(root, state, run, audit=None):
    root=Path(root); (root/'data').mkdir(parents=True,exist_ok=True)
    reports=list(state.get('reports',{}).values())
    if audit:
        for r in reports:
            if r['report_id']==audit['report_id']:
                r.update(ticker=audit['ticker'],market=audit['market'],identity_status='report_claim_not_master_verified',
                         publication_date=audit['publication_date'],publication_date_source='pdf_page_1_and_post_title',
                         file_sha256=audit['file_sha256'],file_hash_verified_at=audit['observed_at'],
                         document_version='sha256:'+audit['file_sha256'],quality_status='quarantined_conflict_and_rights',
                         pdf_current_version_verified=False)
    csv_write(root/'data/reports.csv',reports,fields=sorted(set(k for r in reports for k in r)) if reports else ['report_id'])
    jsonl(root/'data/report_versions.jsonl',state.get('history',[]))
    jsonl(root/'data/tombstones.jsonl',state.get('tombstones',[]))
    values=audit['valuations'] if audit else []
    pq.write_table(pa.Table.from_pylist(values,schema=VALUATION_SCHEMA),root/'data/valuations.parquet')
    pq.write_table(pa.Table.from_pylist([],schema=FINANCIAL_SCHEMA),root/'data/financials.parquet')
    jsonl(root/'data/events.jsonl',[])
    samples=[]
    if audit:
        samples=[{'sample_id':audit['report_id']+':'+audit['file_sha256'][:12], 'report_id':audit['report_id'],
                  'file_sha256':audit['file_sha256'],'ticker':audit['ticker'],'available_at':None,
                  'available_not_before':audit['observed_at'],
                  'features':{'target_gap_at_entry':{'value':None,'known_at':None,'evidence_ids':[]}},
                  'labels':{'status':'unavailable','excess_return_20d':None,'net_excess_return_20d':None},
                  'evidence':[{'evidence_id':v['evidence_id'],'page':v['page'],'source_url':v['source_url']} for v in values],
                  'quality_status':'quarantined_conflict_and_rights','training_eligible':False,'split':'excluded',
                  'record_kind':'real_source_audit_not_training_eligible'}]
    jsonl(root/'data/training_samples.jsonl',samples)
    issues=[]
    if audit:
        issues=[{'issue_id':'STAR340-DATE','report_id':'star-340','severity':'info','code':'publication_posting_gap',
                 'detail':'2026-08-14 발간 / 2026-09-09 게시: 26일 차이. 날짜 오류로 단정하지 않음.','pages':'1;website','training_action':'do_not_backdate'},
                {'issue_id':'STAR340-TP','report_id':'star-340','severity':'error','code':'target_price_conflict',
                 'detail':'42,800 KRW (1쪽) / 40,800 KRW (28쪽, 동일 발간일). 자동 선택 금지.','pages':'1;28','training_action':'exclude'},
                {'issue_id':'STAR340-RIGHTS','report_id':'star-340','severity':'blocker','code':'permission_required',
                 'detail':'28쪽 무단 변형·복제·배포·전송 금지. 원문·전문·학습 허가 미확보.','pages':'28','training_action':'exclude'},
                {'issue_id':'STAR340-TABLE','report_id':'star-340','severity':'error','code':'merged_table_cell',
                 'detail':'1쪽 재무표 2025년 열에 여러 행이 하나의 셀로 추출됨. 금액을 임의 배분하지 않음.','pages':'1','training_action':'manual_review'},
                {'issue_id':'STAR340-PIT','report_id':'star-340','severity':'blocker','code':'historical_version_not_proven',
                 'detail':'현재 PDF 버전의 과거 공개 증거 없음. 최초 관측 이전 사용 금지. 거래일 달력 미연결.','pages':'1;28','training_action':'exclude'}]
    issues += [{'issue_id':'DATA-LABELS','report_id':'*','severity':'blocker','code':'market_labels_missing',
                'detail':'검증된 가격·거래일·배당·분할·상장폐지·지수 데이터 미연결. 미래 수익률 null.','pages':'','training_action':'exclude'}]
    csv_write(root/'quality/issues.csv',issues)
    dump(root/'operations/collection_run.json',run)
    dump(root/'operations/checkpoint_summary.json',{'reports':len(reports),'pending':len(state.get('pending_urls',[])),
          'last_run_at':state.get('last_run_at'),'scan_completed_at':state.get('scan_completed_at'),
          'metadata_only':True,'pdf_redistribution':False})
    dump(root/'data/splits.json',{'status':'not_created','assignments':{},'reason':'no_eligible_observed_labels'})
    return reports


def manifest(root, deployment):
    root=Path(root); files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or '.pytest_cache' in p.parts or p.name=='manifest.json': continue
        rel=p.relative_to(root).as_posix(); rows=None
        if p.suffix=='.parquet': rows=pq.read_metadata(p).num_rows
        elif p.suffix=='.jsonl': rows=len(p.read_text().splitlines())
        elif p.suffix=='.csv':
            with p.open(encoding='utf-8-sig',newline='') as f: rows=sum(1 for _ in csv.DictReader(f))
        files.append({'path':rel,'bytes':p.stat().st_size,'rows':rows,'sha256':digest(p.read_bytes())})
    run=json.loads((root/'operations/collection_run.json').read_text())
    value={'dataset_version':'0.1.0+'+deployment['version_suffix'],'generated_at':now(),'timezone':'Asia/Seoul',
           'source':'http://starskku.com/board/board_list?code=research','data_as_of':run['completed_at'],
           'collection':{k:run.get(k) for k in ['kind','successes','failures','source_requests','source_bytes','pending','listed_total']},
           'pdf_inspected':1,'pdf_included':0,'eligible_training_samples':0,
           'rights':json.loads((root/'pipeline/source_policy.json').read_text()),
           'deployment':deployment,'files':files,'self_hash_policy':'manifest excluded from its own file hashes; zip hash in delivery receipt'}
    dump(root/'manifest.json',value); return value


def archive(root, path):
    root=Path(root)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts:
                z.write(p,Path('investment_dataset')/p.relative_to(root))
