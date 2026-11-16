"""Task Scheduler entry point. Local UTF-8 logs; never logs secret values."""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--mode',choices=['collect','train','health'],default='collect')
    a=p.parse_args(); root=a.root.resolve()
    cfg=yaml.safe_load((root/'config.example.yaml').read_text(encoding='utf-8'))
    logs=root/'.runtime/logs'; logs.mkdir(parents=True,exist_ok=True)
    log=logs/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+a.mode+'.log')
    env={**os.environ,'PYTHONUTF8':'1'}
    cmd=[sys.executable,'-X','utf8','-m','investment.cli','run','--root',str(root),'--state',str(root/'.runtime'),'--mode',a.mode]
    with log.open('w',encoding='utf-8') as output:
        try:
            r=subprocess.run(cmd,cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT,
                             timeout=cfg['limits']['timeout_minutes']*60)
            code=r.returncode
        except subprocess.TimeoutExpired:
            output.write('\nJob exceeded configured time limit; checkpoints are retained.\n')
            code=124
    print('Log: '+str(log))
    return code


if __name__=='__main__':sys.exit(main())
