from __future__ import annotations

import json
import os
import shutil
import traceback
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import yaml

from .common import dump_json, now, stable_id
from .http import PublicClient, AccessBlocked
from .state import State
from .quality import validate_directory
from .package import promote
from .train import train


def run(root: Path, state_dir: Path, mode="collect", run_key=None):
    config = yaml.safe_load((root / "config.example.yaml").read_text())
    if config["max_monthly_out_of_pocket_usd"] != 0:
        raise ValueError("This deployment is authorized only for zero paid usage")
    state = State(state_dir)
    run_key = run_key or os.getenv("GITHUB_RUN_ID") or now()
    started = now()
    record = {"run_key": run_key, "started_at": started, "mode": mode,
              "execution_host": "github_actions" if os.getenv("GITHUB_ACTIONS") else "workspace_manual",
              "trigger": os.getenv("GITHUB_EVENT_NAME", "manual"), "sources": [],
              "status": "running", "orders_enabled": False}
    with state.lock():
        if state.data.get("disabled"):
            return {"status": "disabled", "reason": "persistent kill switch"}
        old = state.data["runs"].get(run_key)
        if old and old["status"] in {"completed", "completed_with_source_errors"}:
            return {"status": "duplicate_run_skipped", "run_key": run_key}
        state.data["runs"][run_key] = record
        state.save()
        try:
            if mode in {"collect", "health"}:
                c = config["limits"]
                client = PublicClient(config["collection"]["allowed_hosts"], interval=c["request_interval_seconds"],
                    retries=c["retries"], max_bytes=c["maximum_response_bytes"], max_requests=c["requests_per_run"])
                for source in config["collection"]["sources"]:
                    entry = {"source_id": source["id"], "url": source["url"], "checked_at": now()}
                    try:
                        body, metadata = client.get(source["url"], check_robots=source["robots_required"])
                        html = BeautifulSoup(body, "html.parser")
                        links = []
                        for a in html.select("a[href]"):
                            text = a.get_text(" ", strip=True)
                            href = urljoin(source["url"], a["href"])
                            if ("한국IR" in text or "IR협의회" in text or ".pdf" in href.lower()) and href.startswith("https://"):
                                links.append({"url": href, "title": text[:160], "status": "discovered_not_downloaded_rights_review"})
                        item, version, changed = state.observe(source["url"], metadata["sha256"])
                        state.finish_version(source["url"], metadata["sha256"], "metadata_only", discovered_links=links,
                                             content_archived=False)
                        entry.update(status="metadata_collected", changed=changed, links_discovered=len(links), http_status=metadata["status"])
                    except AccessBlocked as e:
                        entry.update(status="blocked_or_unavailable", error=str(e))
                    record["sources"].append(entry)
                    state.save()  # checkpoint survives a later-source failure
                dump_json(state_dir / "last_http_audit.json", client.audit)
                record["collection_mode"] = config["collection"]["mode"]
                record["new_full_reports"] = 0
                record["explanation"] = "Metadata discovery runs automatically; new full-report extraction requires rights/layout review. Existing pilot facts are revalidated."
            quality = validate_directory(root)
            record["quality"] = {k: v for k, v in quality.items() if k not in {"warnings", "errors"}}
            if mode == "train":
                model = train(root / "data/features.parquet", root / "data/labels.parquet", state_dir / "training/evaluation", config["training"])
                record["training"] = model
            # Initial immutable bundle is durable on the state branch. New releases
            # are published only when curated reports/facts change, not each poll.
            input_hash = stable_id((root / "data/reports.jsonl").read_bytes(), (root / "data/financials.parquet").read_bytes(),
                                   (root / "data/forecasts.parquet").read_bytes())
            if state.data.get("last_validated_input_hash") != input_hash:
                version = "v0.1.0-cloud-" + started[:19].replace(":", "").replace("-", "")
                archive = promote(root, state_dir / "archive", version,
                    max_store_bytes=config["limits"]["maximum_archive_store_bytes"])
                state.data["last_validated_input_hash"] = input_hash
                record["published_archive"] = str(archive.relative_to(state_dir))
            record["status"] = "completed_with_source_errors" if any(s["status"] == "blocked_or_unavailable" for s in record["sources"]) else "completed"
        except Exception as e:
            record.update(status="failed", error_type=type(e).__name__, error=str(e)[:400])
            raise
        finally:
            record["finished_at"] = now()
            state.data["runs"][run_key] = record
            # Keep a bounded checkpoint index; per-run sanitized summaries are durable.
            state.data["runs"] = dict(list(state.data["runs"].items())[-90:])
            state.save()
            dump_json(state_dir / "history" / f"{stable_id(run_key)}.json", record)
            dump_json(state_dir / "last_run.json", record)
    return record
