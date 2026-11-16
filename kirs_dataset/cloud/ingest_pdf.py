"""Create an isolated candidate from an authorized local PDF; never auto-promote."""
import argparse,json,sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from investment.common import read_jsonl,write_jsonl,now,dump_json
from investment.extract import extract
from investment.lineage import apply_lineage
from investment.schema import write_facts
from investment.features import build_features
from investment.quality import validate_directory,create_database
from investment.package import included
from investment.examples import examples_from_facts

def main():
    p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path,required=True);p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--facts-only-use-reviewed',action='store_true');a=p.parse_args()
    if not a.facts_only_use_reviewed: p.error('Confirm applicable rights before ingestion; full PDF is never archived here')
    if a.candidate.exists(): p.error('Candidate must be a new directory')
    spec=json.loads(a.spec.read_text());observed=now()
    r,rows=extract(spec,a.pdf.read_bytes(),{'first_seen_at':observed,'collected_at':observed})
    reports=read_jsonl(a.root/'data/reports.jsonl');facts=read_jsonl(a.root/'data/facts_seed.jsonl')
    if any(x['content_version']==r['content_version'] for x in reports):
        print('Exact duplicate bytes; no independent signal added');return
    previous=[x for x in reports if x['source_id']==r['source_id']]
    relationships=[]
    if previous:
        prev=max(previous,key=lambda x:x['available_at'])
        relationships=[{'report_id':r['report_id'],'related_report_id':prev['report_id'],'kind':'supersedes','status':'verified','evidence':'Same source URL, different bytes; current observation only'}]
    reports=apply_lineage(reports+[r],relationships);families={x['report_id']:x['family_id'] for x in reports}
    facts+=rows
    for f in facts:f['family_id']=families[f['report_id']]
    for src in included(a.root):
        dst=a.candidate/src.relative_to(a.root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    business=read_jsonl(a.root/'data/business_risks.jsonl')
    write_jsonl(a.candidate/'data/reports.jsonl',reports);write_jsonl(a.candidate/'data/facts_seed.jsonl',facts)
    actual=[f for f in facts if f['value_type']!='forecast'];forecast=[f for f in facts if f['value_type']=='forecast']
    write_facts(a.candidate/'data/financials.parquet',actual);write_facts(a.candidate/'data/forecasts.parquet',forecast)
    build_features(reports,facts,business).to_parquet(a.candidate/'data/features.parquet',index=False)
    write_jsonl(a.candidate/'data/research_examples.jsonl',examples_from_facts(reports,facts))
    create_database(a.candidate,reports,actual,forecast,business)
    quality=validate_directory(a.candidate)
    dump_json(a.candidate/'evaluation/candidate_status.json',{'status':'review_required','quality':quality,'new_report_id':r['report_id'],'latest_pointer_changed':False,'note':'Review metadata, lineage, auxiliary tables and rights before versioned promotion; prior bundle untouched'})
    print('Candidate created and checked; latest unchanged')

if __name__=='__main__': main()
