from __future__ import annotations
import json, platform, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from .core import now, digest, dump, require_permission

FEATURES = ['target_gap_at_entry', 'forecast_revenue_growth', 'forecast_profit_growth',
            'forecast_vs_consensus', 'target_revision_rate', 'risk_event_count']


def purged_splits(samples, validation_start, test_start):
    """Drop every connected document/hash group crossing temporal boundaries."""
    val, test = pd.Timestamp(validation_start), pd.Timestamp(test_start)
    if val >= test: raise ValueError('invalid_split_boundaries')
    parent = list(range(len(samples)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    keys = {}
    for i, row in enumerate(samples):
        for key in [('report', row['report_id']), ('sha', row.get('file_sha256'))]:
            if not key[1]: continue
            if key in keys: parent[find(i)] = find(keys[key])
            else: keys[key] = i
    assignments, reasons, groups = {}, {}, {}
    for i, row in enumerate(samples):
        t = pd.Timestamp(row['available_at']); end = pd.Timestamp(row['labels']['exit_at'])
        name = 'train' if t < val else 'validation' if t < test else 'test'
        groups.setdefault(find(i), set()).add(name)
        if (name == 'train' and end >= val) or (name == 'validation' and end >= test):
            assignments[row['sample_id']] = 'excluded'; reasons[row['sample_id']] = 'label_window_crosses_boundary'
        else: assignments[row['sample_id']] = name
    for i, row in enumerate(samples):
        if len(groups[find(i)]) > 1:
            assignments[row['sample_id']] = 'excluded'; reasons[row['sample_id']] = 'document_or_duplicate_crosses_splits'
    return {'assignments': assignments, 'exclusions': reasons, 'validation_start': validation_start,
            'test_start': test_start, 'method': 'chronological_connected_document_groups_purged_horizon'}


def check_sample(row):
    if row.get('quality_status') != 'passed' or not row.get('training_eligible'): return False
    if not row.get('ticker') or not row.get('available_at'): return False
    label = row.get('labels', {})
    if label.get('status') != 'observed' or label.get('excess_return_20d') is None: return False
    if label.get('adjustment_method') != 'forward_total_return_anchor_entry': return False
    if pd.Timestamp(label['entry_at']) < pd.Timestamp(row['available_at']): raise ValueError('label_entry_precedes_availability')
    if pd.Timestamp(label['exit_at']) <= pd.Timestamp(label['entry_at']): raise ValueError('invalid_label_period')
    for feature in row['features'].values():
        if feature.get('value') is not None:
            if not feature.get('evidence_ids') or not feature.get('known_at'): raise ValueError('feature_missing_provenance')
            if pd.Timestamp(feature['known_at']) > pd.Timestamp(row['available_at']): raise ValueError('future_feature')
    return True


def train(root, config, policy):
    root = Path(root); out = root / 'evaluation'
    samples = [json.loads(x) for x in (root / 'data/training_samples.jsonl').read_text().splitlines() if x.strip()]
    usable = [r for r in samples if check_sample(r)]
    reasons = []
    try: require_permission(policy, 'model_training')
    except PermissionError: reasons.append('source_training_permission_missing')
    if len(usable) < config['min_samples']: reasons.append('insufficient_labeled_samples')
    if len({r['ticker'] for r in usable}) < config['min_tickers']: reasons.append('insufficient_ticker_diversity')
    if not config.get('validation_start') or not config.get('test_start'): reasons.append('time_boundaries_unconfigured')
    if reasons:
        result = {'status': 'not_run', 'trained': False, 'reasons': reasons, 'eligible_samples': len(usable),
                  'input_records': len(samples), 'metrics': None, 'checked_at': now()}
        dump(out/'metrics.json', result); dump(root/'data/splits.json', {'status':'not_created','reasons':reasons,'assignments':{}})
        return result
    split = purged_splits(usable, config['validation_start'], config['test_start']); dump(root/'data/splits.json', split)
    parts = {k: [r for r in usable if split['assignments'][r['sample_id']] == k] for k in ['train','validation','test']}
    if any(len(parts[k]) < config['min_per_split'][k] for k in parts):
        result = {'status':'not_run','trained':False,'reasons':['insufficient_samples_after_purge'],
                  'split_counts':{k:len(v) for k,v in parts.items()},'metrics':None}; dump(out/'metrics.json',result); return result
    def xy(rows):
        return (np.array([[r['features'].get(k,{}).get('value') if r['features'].get(k,{}).get('value') is not None else np.nan for k in FEATURES] for r in rows],dtype=float),
                np.array([r['labels']['excess_return_20d'] for r in rows], dtype=float))
    xtr,ytr=xy(parts['train']); xv,yv=xy(parts['validation']); xt,yt=xy(parts['test'])
    if not np.isfinite(ytr).all() or not np.isfinite(yv).all() or not np.isfinite(yt).all(): raise ValueError('nonfinite_labels')
    if not np.isfinite(xtr).any(): raise ValueError('no_observed_training_features')
    # All preprocessing is fitted exclusively on training rows; validation selects alpha.
    candidates=[]
    for alpha in [1.0,10.0,100.0]:
        model=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                        ('scale',StandardScaler()),('model',Ridge(alpha=alpha))])
        model.fit(xtr,ytr); candidates.append((mean_absolute_error(yv,model.predict(xv)),alpha,model))
    _,alpha,model=min(candidates,key=lambda r:r[0]); pred=model.predict(xt)
    baseline=DummyRegressor(strategy='mean').fit(xtr,ytr).predict(xt)
    costs=config['roundtrip_bps']/10000; selected=pred>costs
    result={'status':'trained','trained':True,'checked_at':now(),'seed':config['seed'],'alpha':alpha,
            'split_counts':{k:len(v) for k,v in parts.items()},'mae':float(mean_absolute_error(yt,pred)),
            'mse':float(mean_squared_error(yt,pred)),'historical_mean_baseline_mae':float(mean_absolute_error(yt,baseline)),
            'zero_excess_baseline_mae':float(mean_absolute_error(yt,np.zeros_like(yt))),
            'selected_count':int(selected.sum()),'selected_mean_net_excess':float((yt[selected]-costs).mean()) if selected.any() else None,
            'all_long_mean_net_excess':float((yt-costs).mean()),'no_trade_return':0,
            'roundtrip_bps':config['roundtrip_bps'], 'evaluation_scope':'per-report diagnostics, not a portfolio backtest; overlapping holdings not aggregated',
            'data_sha256':digest((root/'data/training_samples.jsonl').read_bytes())}
    version=digest({'data':result['data_sha256'],'config':config,'features':FEATURES})[:16]
    dest=root/'models'/version; dest.mkdir(parents=True,exist_ok=False)
    joblib.dump(model,dest/'ridge.joblib'); dump(dest/'config.json',config); dump(dest/'metrics.json',result)
    dump(dest/'features.json',FEATURES)
    (dest/'libraries.txt').write_text(subprocess.check_output(['python','-m','pip','freeze'],text=True))
    dump(out/'metrics.json',result); return result
