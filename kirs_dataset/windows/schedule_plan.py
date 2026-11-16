"""Read configurable simple KST schedules for native Windows Task Scheduler."""
import argparse,json,re
from pathlib import Path
import yaml


def plan(config):
    if config['timezone']!='Asia/Seoul':
        raise ValueError('This Windows task installer requires Asia/Seoul')
    cm,ch,cd,cmo,cw=config['schedules']['collect_cron_kst'].split()
    tm,th,td,tmo,tw=config['schedules']['train_cron_kst'].split()
    if (cd,cmo,cw)!=('*','*','*') or not cm.isdigit() or not re.fullmatch(r'\d+(,\d+)*',ch):
        raise ValueError('Collect schedule must be daily: minute hour[,hour] * * *')
    if (td,tmo)!=('*','*') or not all(x.isdigit() for x in [tm,th,tw]):
        raise ValueError('Train schedule must be weekly: minute hour * * day_number')
    hours=[int(x) for x in ch.split(',')]
    if not (0<=int(cm)<60 and all(0<=h<24 for h in hours) and 0<=int(tm)<60 and 0<=int(th)<24 and 0<=int(tw)<=6):
        raise ValueError('Invalid schedule time')
    return {'collect_times':[f'{h:02d}:{int(cm):02d}' for h in hours],
            'train_time':f'{int(th):02d}:{int(tm):02d}',
            'train_day':['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][int(tw)],
            'timeout_minutes':config['limits']['timeout_minutes']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    print(json.dumps(plan(yaml.safe_load((a.root/'config.example.yaml').read_text(encoding='utf-8')))))
