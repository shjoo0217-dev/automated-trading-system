import csv,json,hashlib
from pathlib import Path
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator,FormatChecker
from .core import digest


def validate_bundle(root, verify_hashes=True):
    root=Path(root); schema=json.loads((root/'schema.json').read_text()); checked={}
    for name,file,kind in [('training_sample','data/training_samples.jsonl','jsonl'),('event','data/events.jsonl','jsonl'),
                           ('valuation','data/valuations.parquet','parquet'),('financial','data/financials.parquet','parquet')]:
        rows=[json.loads(l) for l in (root/file).read_text().splitlines() if l.strip()] if kind=='jsonl' else pq.read_table(root/file).to_pylist()
        validator=Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=FormatChecker())
        for row in rows: validator.validate(row)
        checked[file]=len(rows)
    with (root/'data/reports.csv').open(encoding='utf-8-sig',newline='') as f: reports=list(csv.DictReader(f))
    ids=[r['report_id'] for r in reports]
    if len(ids)!=len(set(ids)): raise ValueError('duplicate_report_ids')
    for r in reports:
        if r.get('ticker') and (len(r['ticker'])!=6 or not r['ticker'].isdigit()): raise ValueError('invalid_ticker')
        if r.get('training_eligible')=='True' and not r.get('available_at'): raise ValueError('eligible_without_availability')
    checked['data/reports.csv']=len(reports)
    if verify_hashes:
        manifest=json.loads((root/'manifest.json').read_text())
        for f in manifest['files']:
            p=root/f['path']
            if root.resolve() not in p.resolve().parents: raise ValueError('unsafe_manifest_path')
            if digest(p.read_bytes())!=f['sha256']: raise ValueError('hash_mismatch:'+f['path'])
    return {'status':'passed','schema_rows':checked,'training_eligible':sum(r.get('training_eligible')=='True' for r in reports)}


def restore_training_data(archive,root):
    """Restore only data/model files from a chosen private release, never execute archive code."""
    import zipfile
    root=Path(root)
    with zipfile.ZipFile(archive) as z:
        info=json.loads(z.read('investment_dataset/manifest.json'))
        selected=[f for f in info['files'] if f['path'].startswith(('data/','models/'))]
        if sum(f['bytes'] for f in selected)>500_000_000: raise ValueError('training_import_size_limit')
        for f in selected:
            p=root/f['path']
            if root.resolve() not in p.resolve().parents: raise ValueError('unsafe_import_path')
            b=z.read('investment_dataset/'+f['path'])
            if digest(b)!=f['sha256']: raise ValueError('training_import_hash_mismatch')
            p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
    return info['dataset_version']
