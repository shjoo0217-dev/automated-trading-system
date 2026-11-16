"""Direct execution alternative to GitHub Actions; completed files must be exported.
This process depends on its active execution environment. It is not a persistent scheduler.
"""
import argparse,json,time,uuid
from pathlib import Path
from star_pipeline.core import LocalState,dump,now,emit
from star_pipeline.collect import metadata_run
from star_pipeline.package import build,manifest,archive
from star_pipeline.train import train

p=argparse.ArgumentParser();p.add_argument('--root',default='investment_dataset')
p.add_argument('--state',required=True);p.add_argument('--max-cycles',type=int,default=4)
p.add_argument('--posts-per-cycle',type=int,default=60);args=p.parse_args()
root=Path(args.root);policy=json.loads((root/'pipeline/source_policy.json').read_text())
store=LocalState(args.state);run_id='direct-'+now().replace(':','').replace('+','_')+'-'+uuid.uuid4().hex[:6]
runs=[];start=now()
for cycle in range(args.max_cycles):
    state,run=metadata_run(store,policy,max_posts=args.posts_per_cycle,max_pages=40,max_requests=450)
    run['execution_id']=run_id;run['cycle']=cycle+1;runs.append(run)
    dump(root/'operations/direct_runs.json',{'execution_id':run_id,'started_at':start,'runs':runs})
    emit('direct_checkpoint',execution_id=run_id,cycle=cycle+1,reports=len(state['reports']),pending=len(state['pending_urls']))
    if not state['pending_urls']:break
    # A per-run budget stop is resumable; a new cycle retains the same source rate limit.
    time.sleep(3)
summary={'kind':'metadata','execution_id':run_id,'execution_environment':'Codex managed workspace direct process',
         'coverage_status':'partial' if state['pending_urls'] else 'scan_complete','successes':sum(r['successes'] for r in runs),
         'failures':sum(r['failures'] for r in runs),'source_requests':sum(r['source_requests'] for r in runs),
         'source_bytes':sum(r['source_bytes'] for r in runs),'pending':len(state['pending_urls']),
         'listed_total':runs[-1]['listed_total'],'completed_at':now(),'cycles':len(runs),
         'note':'Continues a checkpoint initially created on GitHub; successes here count only this direct process.'}
audit=json.loads((root/'quality/yesti_audit.json').read_text())
build(root,state,summary,audit)
result=train(root,json.loads((root/'pipeline/training_config.json').read_text()),policy)
deployment={'status':'github_collection_paused_direct_execution_completed','version_suffix':run_id,
            'scheduler_state':'disabled_manually','next_scheduled_execution':None,
            'direct_execution_id':run_id,'long_lived_independence_required':False}
dump(root/'operations/deployment_status.json',deployment)
manifest(root,deployment);archive(root,root.parent/'investment_dataset.zip')
emit('direct_complete',execution_id=run_id,reports=len(state['reports']),pending=len(state['pending_urls']),training_status=result['status'])
