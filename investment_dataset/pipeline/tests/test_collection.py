"""Synthetic network fixtures exercise resume, revisions and exclusion behavior."""
from copy import deepcopy
import pytest
from star_pipeline import collect
from star_pipeline.core import LocalState, digest

TERM=b'<div id="content">synthetic terms</div>'
LIST=b'<div class="bbs_num"><strong>1</strong></div><table class="bbs_list"><tr><td class="board_tit"><a href="/board/board_view?code=research&no=1">x</a></td></tr></table>'
POST='<div class="view_tit"><h3>test, {title} (발간일: 260101)</h3><p>admin / 2026-01-02</p></div><div class="view_cont">body</div>'

class FakeClient:
    title='first'
    def __init__(self,**kwargs): self.requests=self.bytes=self.failures=0;self.receipts=[]
    def check_robots(self): return {'synthetic':True}
    def get(self,url):
        self.requests+=1
        if 'agreement' in url:return TERM
        if 'board_list' in url:return LIST
        return POST.format(title=self.title).encode()


def test_rerun_idempotency_and_revision_retention(tmp_path,monkeypatch):
    monkeypatch.setattr(collect,'BoundedClient',FakeClient)
    store=LocalState(tmp_path/'state.json')
    policy={'permissions':{'metadata':{'allowed':True,'evidence':'synthetic test'}},'agreement_text_sha256':digest(b'synthetic terms')}
    a,_=collect.metadata_run(store,policy)
    first=deepcopy(a['reports']['star-1'])
    b,run=collect.metadata_run(store,policy)
    assert run['changed']==0;assert b['reports']['star-1']['metadata_version']==1;assert not b['history']
    monkeypatch.setattr(FakeClient,'title','revised')
    c,run=collect.metadata_run(store,policy)
    assert c['reports']['star-1']['metadata_version']==2;assert len(c['history'])==1
    assert c['reports']['star-1']['first_collected_at']==first['first_collected_at']
    assert c['reports']['star-1']['available_at'] is None
    assert c['history'][0]['metadata_sha256']==first['metadata_sha256']


def test_terms_change_stops_before_posts(tmp_path,monkeypatch):
    monkeypatch.setattr(collect,'BoundedClient',FakeClient)
    with pytest.raises(PermissionError,match='terms_changed'):
        collect.metadata_run(LocalState(tmp_path/'s.json'),{'permissions':{'metadata':{'allowed':True,'evidence':'x'}},'agreement_text_sha256':'different'})


def test_resume_pending_url_without_duplicating(tmp_path,monkeypatch):
    monkeypatch.setattr(collect,'BoundedClient',FakeClient)
    store=LocalState(tmp_path/'state.json')
    url='http://starskku.com/board/board_view?code=research&no=1'
    store.save({'pending_urls':[url],'scan_urls':[url],'scan_listing_complete':True})
    policy={'permissions':{'metadata':{'allowed':True,'evidence':'synthetic test'}},'agreement_text_sha256':digest(b'synthetic terms')}
    s,r=collect.metadata_run(store,policy)
    assert not s['pending_urls'];assert len(s['reports'])==1;assert r['successes']==1
