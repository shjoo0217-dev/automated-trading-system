"""Generate schedules from explicit KST/UTC config; fail on mismatched conversion."""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml
from croniter import croniter


def verify_schedules(config):
    base = datetime(2026, 11, 17, tzinfo=timezone.utc)
    for name in ["collect", "train"]:
        local = croniter(config["schedules"][name+"_cron_kst"], base.astimezone(ZoneInfo(config["timezone"])))
        utc = croniter(config["schedules"][name+"_cron_utc"], base)
        for _ in range(10):
            if local.get_next(datetime).astimezone(timezone.utc) != utc.get_next(datetime):
                raise ValueError("KST and UTC schedules do not agree")


def main():
    p = argparse.ArgumentParser();p.add_argument("--config",type=Path,default=Path("config.example.yaml"));p.add_argument("--output",type=Path,default=Path(".github/workflows/investment-pipeline.yml"))
    a=p.parse_args();c=yaml.safe_load(a.config.read_text());verify_schedules(c)
    template=(Path(__file__).parent/"workflow.template.yml").read_text()
    for name in ["collect", "train"]:template=template.replace("__"+name.upper()+"_CRON__",c["schedules"][name+"_cron_utc"])
    template=template.replace("__TIMEOUT__",str(c["limits"]["timeout_minutes"]))
    if not c.get("execution", {}).get("cloud_schedules_enabled", False):
        template=re.sub(r"on:\n[\s\S]*?\npermissions:", "on:\n  workflow_dispatch:\n    inputs:\n      mode:\n        type: choice\n        options: [collect, train, health]\n        default: collect\npermissions:", template)
        template=template.replace("if: ${{ vars.PIPELINE_DISABLED != 'true' }}", "if: ${{ vars.KIRS_CLOUD_ENABLED == 'true' && vars.PIPELINE_DISABLED != 'true' }}")
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(template)


if __name__ == "__main__": main()
