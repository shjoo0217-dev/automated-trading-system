"""Cross-field checks preserve conflicts and never select a preferred source value."""
from datetime import date


def date_issues(report):
    pub, posted = report.get('publication_date'), report.get('posted_date')
    result=[]
    if pub and posted:
        gap=(date.fromisoformat(posted)-date.fromisoformat(pub)).days
        if gap:
            result.append({'issue_id':report['report_id']+'-DATE','report_id':report['report_id'],
                           'severity':'info' if gap>0 else 'error','code':'publication_posting_gap',
                           'detail':f'발간 {pub}; 게시 {posted}; 차이 {gap}일. 가용시점 소급 금지.',
                           'pages':'post_title;website','training_action':'do_not_backdate'})
    if report.get('posted_time') is None:
        result.append({'issue_id':report['report_id']+'-TIME','report_id':report['report_id'],
                       'severity':'info','code':'posting_time_missing','detail':'게시 시각 미표시. 검증된 다음 거래 세션 규칙 적용.',
                       'pages':'website','training_action':'calendar_required'})
    return result


def numeric_issues(facts,tolerance=.002):
    groups={};result=[]
    keys=['report_id','period_year','period_quarter','estimate_type','consolidation','business_segment']
    for f in facts:
        if f.get('value') is None:continue
        groups.setdefault(tuple(f.get(k) for k in keys),{}).setdefault(f['metric'],[]).append(f)
    for group,metrics in groups.items():
        for name,rows in metrics.items():
            if len({(r['value'],r.get('unit')) for r in rows})>1:
                result.append({'code':'conflicting_financial_values','metric':name,'fact_ids':[r['fact_id'] for r in rows]})
        for profit,margin in [('operating_income','operating_margin'),('net_income','net_margin')]:
            if not all(k in metrics and len(metrics[k])==1 for k in ['revenue',profit,margin]):continue
            sales,earnings,reported=[metrics[k][0] for k in ['revenue',profit,margin]]
            if sales['value']==0 or sales.get('unit')!=earnings.get('unit') or reported.get('unit')!='ratio':continue
            # Only compare explicitly matched consolidation and currency bases.
            if sales.get('consolidation') is None or sales.get('currency')!=earnings.get('currency'):continue
            calc=earnings['value']/sales['value']
            if abs(calc-reported['value'])>tolerance:
                result.append({'code':'margin_arithmetic_conflict','metric':margin,'calculated_value':calc,
                               'formula':profit+'/revenue','reported_value':reported['value'],
                               'input_fact_ids':[sales['fact_id'],earnings['fact_id'],reported['fact_id']]})
    return result
