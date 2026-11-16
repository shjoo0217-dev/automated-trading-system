"""Numerical, evidence-backed features only. Missing/conflicting inputs stay null."""
import math
import pandas as pd


def ratio_feature(numerator, denominator, available_at, minus_one=False):
    inputs=[numerator,denominator]
    formula='numerator / denominator' + (' - 1' if minus_one else '')
    evidence=[x['evidence_id'] for x in inputs if x and x.get('evidence_id')]
    empty={'value':None,'known_at':None,'evidence_ids':evidence,'formula':formula}
    if any(not x or x.get('value') is None or x.get('quality_status')!='passed' for x in inputs): return empty
    if numerator.get('unit')!=denominator.get('unit'): return {**empty,'reason':'unit_mismatch'}
    if any(not x.get('known_at') or pd.Timestamp(x['known_at']) > pd.Timestamp(available_at) for x in inputs):
        return {**empty,'reason':'input_not_available'}
    if denominator['value']<=0: return {**empty,'reason':'nonpositive_denominator_requires_separate_growth_definition'}
    v=numerator['value']/denominator['value']-(1 if minus_one else 0)
    if not math.isfinite(v): return {**empty,'reason':'nonfinite'}
    return {'value':v,'known_at':max(pd.Timestamp(x['known_at']) for x in inputs).isoformat(),'evidence_ids':evidence,'formula':formula}


def growth_feature(current, previous, available_at):
    # Matching business periods and estimate kinds must be verified before comparison.
    if not current or not previous: return ratio_feature(None,None,available_at,True)
    keys=['metric','currency','consolidation','business_segment','period_quarter','estimate_type']
    if any(current.get(k)!=previous.get(k) for k in keys):
        return {'value':None,'known_at':None,'evidence_ids':[],'reason':'incomparable_period_basis'}
    if current.get('period_year',0)!=previous.get('period_year',0)+1:
        return {'value':None,'known_at':None,'evidence_ids':[],'reason':'not_year_over_year'}
    return ratio_feature(current,previous,available_at,True)
