"""Rebuild factual storage from the included canonical facts; no web calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from investment.common import read_jsonl
from investment.schema import write_facts
from investment.features import build_features
from investment.quality import validate_directory,create_database

root=Path(__file__).resolve().parents[1]
facts=read_jsonl(root/"data/facts_seed.jsonl")
reports=read_jsonl(root/"data/reports.jsonl")
business=read_jsonl(root/"data/business_risks.jsonl")
actual=[f for f in facts if f['value_type']!='forecast'];forecast=[f for f in facts if f['value_type']=='forecast']
write_facts(root/"data/financials.parquet",actual);write_facts(root/"data/forecasts.parquet",forecast)
build_features(reports,facts,business).to_parquet(root/"data/features.parquet",index=False)
create_database(root,reports,actual,forecast,business)
print(validate_directory(root)['status'])
