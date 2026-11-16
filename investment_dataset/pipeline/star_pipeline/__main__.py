import argparse, json, os, shutil
from pathlib import Path
from .core import LocalState, GitHubState, dump, now, emit
from .collect import metadata_run
from .package import build, manifest, archive
from .train import train


def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['collect','train','package','extract'])
    p.add_argument('--root',default='investment_dataset'); p.add_argument('--state',default='/tmp/star-checkpoint.json')
    p.add_argument('--github-state',action='store_true'); p.add_argument('--max-posts',type=int,default=350)
    p.add_argument('--max-pages',type=int,default=40); p.add_argument('--max-requests',type=int,default=450)
    p.add_argument('--pdf'); p.add_argument('--report-json'); p.add_argument('--ocr',action='store_true')
    args=p.parse_args(); root=Path(args.root); policy=json.loads((root/'pipeline/source_policy.json').read_text())
    if args.command=='extract':
        from .extract import licensed_extract
        report=json.loads(Path(args.report_json).read_text())
        result=licensed_extract(args.pdf,report,policy,args.ocr)
        dump(root/'data'/('extraction-'+result['file_sha256']+'.json'),result)
        return
    if args.command=='collect':
        store=GitHubState(os.environ['GITHUB_REPOSITORY']) if args.github_state else LocalState(args.state)
        state,run=metadata_run(store,policy,args.max_posts,args.max_pages,args.max_requests)
        audit_path=root/'quality/yesti_audit.json'; audit=json.loads(audit_path.read_text()) if audit_path.exists() else None
        build(root,state,run,audit)
        emit('collection_complete',successes=run['successes'],failures=run['failures'],pending=run['pending'])
        # Persist checkpoint even if partial; mark job failure after packaging by workflow validation.
    if args.command in ('collect','train'):
        result=train(root,json.loads((root/'pipeline/training_config.json').read_text()),policy)
        emit('training_gate',status=result['status'],reasons=result.get('reasons',[]))
    if args.command in ('collect','train','package'):
        deployment_path=root/'operations/deployment_status.json'
        deployment=json.loads(deployment_path.read_text()) if deployment_path.exists() else {'status':'not_deployed','version_suffix':'pilot'}
        if os.environ.get('GITHUB_RUN_ID'):
            deployment.update(status='github_job_running_snapshot',run_id=os.environ['GITHUB_RUN_ID'],
                              run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
                              version_suffix=os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1'))
        dump(deployment_path,deployment); manifest(root,deployment)
        archive(root,root.parent/'investment_dataset.zip')

if __name__=='__main__': main()
