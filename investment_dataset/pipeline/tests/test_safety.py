"""Synthetic fixtures ONLY. These values are never written to the delivered dataset."""
import json
from pathlib import Path
import pandas as pd
import pytest
from star_pipeline.extract import number, target_conflicts, target_candidates
from star_pipeline.core import LocalState, require_permission, digest
from star_pipeline.market import available_session, asof_facts, excess_20
from star_pipeline.train import purged_splits, check_sample
from star_pipeline.collect import parse_post, parse_listing

@pytest.mark.parametrize('raw,unit,value', [('1,234','억원',123400000000),('(4)','억원',-400000000),('0','원',0),('11.2','%',.112),('N/A','원',None),('', '원',None),('12','천원',12000),('2','백만원',2000000)])
def test_unit_conversion(raw,unit,value):
    if value is None: assert number(raw,unit) is None
    else: assert number(raw,unit)==pytest.approx(value)

def test_ambiguous_not_guessed():
    for raw,unit in [('871\n38','억원'),('1.2x','원'),('12','unknown'),('NaN','원')]:
        with pytest.raises(ValueError): number(raw,unit)

def test_rights_gate():
    with pytest.raises(PermissionError): require_permission({'permissions':{}},'model_training')
    with pytest.raises(PermissionError): require_permission({'permissions':{'model_training':{'allowed':True}}},'model_training')

def test_same_date_target_conflict_not_old_history():
    pages=[{'page':1,'text':'목표주가\n42,800'}, {'page':28,'text':'투자의견 및 목표주가 변동내역\n2026.08.14\nBUY\n40,800'}]
    v=target_candidates(pages,'test-only','a'*64)
    assert len(target_conflicts(v,'2026-08-14'))==1
    assert not target_conflicts(v,'2025-01-01')

def test_calendar_no_weekday_guess():
    s=pd.DataFrame({'session':['2026-11-16','2026-11-19'],'open_at':['2026-11-16T09:00:00+09:00','2026-11-19T09:00:00+09:00']})
    assert available_session('2026-11-16T15:31:00Z',s)=='2026-11-19T09:00:00+09:00'
    assert available_session('2027-01-01T00:00:00Z',s) is None

def test_asof_restatement_filter():
    f=pd.DataFrame([dict(ticker='000001',metric='revenue',period_end='2025-12-31',consolidation='C',known_at=k,value=v) for k,v in [('2026-01-01T00:00Z',1),('2026-03-01T00:00Z',2)]])
    assert asof_facts(f,'2026-02-01T00:00Z').iloc[0]['value']==1

def sample(sid,doc,sha,t,end):
    return {'sample_id':sid,'report_id':doc,'file_sha256':sha,'available_at':t,'labels':{'exit_at':end}}

def test_purge_group_and_transitive_hash():
    data=[sample('a','doc1','sha1','2026-01-01T00:00Z','2026-01-31T00:00Z'),
          sample('b','doc1','sha2','2026-02-10T00:00Z','2026-02-25T00:00Z'),
          sample('c','doc2','sha2','2026-04-01T00:00Z','2026-04-25T00:00Z'),
          sample('d','doc3','sha3','2026-02-20T00:00Z','2026-03-05T00:00Z'),
          sample('e','doc4','sha4','2026-01-01T00:00Z','2026-01-25T00:00Z')]
    s=purged_splits(data,'2026-02-01T00:00Z','2026-03-01T00:00Z')
    assert all(s['assignments'][x]=='excluded' for x in ['a','b','c','d'])
    assert s['assignments']['e']=='train'

def test_labels_exact_20_sessions_and_costs():
    days=pd.bdate_range('2026-01-01',periods=21).strftime('%Y-%m-%d').tolist() # Synthetic calendar ONLY.
    sessions=pd.DataFrame({'session':days,'open_at':[d+'T09:00:00+09:00' for d in days],'close_at':[d+'T15:30:00+09:00' for d in days]})
    def prices(close): return pd.DataFrame({'session':days,'ticker':'000001','adjusted_open':100,'adjusted_close':close,'tradable':True,'source_id':'synthetic','adjustment_method':'forward_total_return_anchor_entry'})
    r=excess_20('000001',sessions.iloc[0].open_at,sessions,prices(110),prices(102),'SYNTHETIC',30)
    assert r['exit_session']==days[19]; assert r['excess_return_20d']==pytest.approx(.08)
    assert r['net_excess_return_20d']==pytest.approx(.077)
    bad=prices(110); bad.loc[19,'tradable']=False
    assert excess_20('000001',sessions.iloc[0].open_at,sessions,bad,prices(102),'SYNTHETIC')['status']=='missing_or_untradable_prices'

def test_missing_horizon_never_fabricated():
    s=pd.DataFrame({'session':['2026-01-01'],'open_at':['2026-01-01T09:00:00+09:00']})
    assert excess_20('000001','2026-01-01T09:00:00+09:00',s,None,None,'X')['excess_return_20d'] is None

def test_future_features_rejected():
    r={'quality_status':'passed','training_eligible':True,'ticker':'000001','available_at':'2026-01-01T00:00Z',
       'labels':{'status':'observed','excess_return_20d':.01,'entry_at':'2026-01-01T00:00Z','exit_at':'2026-02-01T00:00Z','adjustment_method':'forward_total_return_anchor_entry'},
       'features':{'target_gap_at_entry':{'value':1,'known_at':'2026-01-02T00:00Z','evidence_ids':['x']}}}
    with pytest.raises(ValueError,match='future_feature'): check_sample(r)

def test_state_idempotent_and_no_overwrite(tmp_path):
    store=LocalState(tmp_path/'s.json'); d={'reports':{'a':{'version':1}}}; store.save(d); store.save(d); assert store.load()==d

def test_stable_metadata_and_date_sources():
    body='<div class="view_tit"><h3>테스트, 제목 (발간일: 260814)</h3><p>관리자 / 2026-09-09</p></div><div class="view_cont">내용</div><div class="extra_cont"><a href="/fileRequest/download?file=x.pdf">PDF</a></div>'
    a=parse_post(body+'<script>time=1</script>','http://starskku.com/board/board_view?code=research&no=1')
    b=parse_post(body+'<script>time=2</script>','http://starskku.com/board/board_view?code=research&no=1')
    assert a['metadata_sha256']==b['metadata_sha256']; assert a['posted_date']=='2026-09-09'; assert a['publication_date']=='2026-08-14'
    assert a['ticker'] is None

def test_feature_missing_units_future_and_negative_base():
    from star_pipeline.features import ratio_feature
    a={'value':120,'unit':'KRW','quality_status':'passed','known_at':'2026-01-01T00:00Z','evidence_id':'a'}
    b={**a,'value':100,'evidence_id':'b'}
    assert ratio_feature(a,b,'2026-01-02T00:00Z',True)['value']==pytest.approx(.2)
    assert ratio_feature(a,{**b,'unit':'USD'},'2026-01-02T00:00Z')['value'] is None
    assert ratio_feature(a,{**b,'value':-100},'2026-01-02T00:00Z')['value'] is None
    assert ratio_feature(a,b,'2025-01-02T00:00Z')['value'] is None

def test_actual_release_records_schema():
    from star_pipeline.validate import validate_bundle
    root=Path(__file__).resolve().parents[2]
    if (root/'schema.json').exists(): assert validate_bundle(root,verify_hashes=False)['status']=='passed'

def test_dates_are_compared_without_backdating():
    from star_pipeline.quality import date_issues
    r={'report_id':'test','publication_date':'2026-08-14','posted_date':'2026-09-09','posted_time':None}
    issues=date_issues(r)
    assert issues[0]['code']=='publication_posting_gap';assert '26일' in issues[0]['detail']
    assert issues[1]['code']=='posting_time_missing'

def test_financial_conflicts_keep_input_provenance():
    from star_pipeline.quality import numeric_issues
    base={'report_id':'test','period_year':2026,'period_quarter':None,'estimate_type':'forecast','consolidation':'C','business_segment':None,'currency':'KRW'}
    fs=[{**base,'fact_id':i,'metric':m,'value':v,'unit':u} for i,m,v,u in [('a','revenue',100,'KRW'),('b','net_income',10,'KRW'),('c','net_margin',.2,'ratio')]]
    issue=numeric_issues(fs)[0]
    assert issue['code']=='margin_arithmetic_conflict';assert issue['input_fact_ids']==['a','b','c']

def test_inline_images_are_hashed_never_stored():
    body='<div class="view_tit"><h3>test, title (발간일: 260101)</h3><p>admin / 2026-01-02</p></div><div class="view_cont"><img src="data:image/png;base64,AAAABBBB"/><img src="/upload/x.jpg"/></div>'
    r=parse_post(body,'http://starskku.com/board/board_view?code=research&no=1')
    assert r['embedded_image_urls']==['http://starskku.com/upload/x.jpg']
    assert r['inline_image_count']==1
    assert 'AAAABBBB' not in json.dumps(r)
    assert len(r['inline_image_sha256'][0])==64
