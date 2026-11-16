from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

from .common import digest, dump_json, now, read_jsonl
from .quality import validate_directory

ALLOWED_DIRS = {"src", "data", "raw", "models", "evaluation", "cloud", "config", "tests", ".github", "windows"}
ALLOWED_FILES = {"README.md", "CODEX_HANDOFF.md", "DATA_DICTIONARY.md", "manifest.json", "requirements.txt",
                 "requirements-dev.txt", "pyproject.toml", "config.example.yaml", ".gitignore", "VERSION", "LICENSE"}


def included(root):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or p.is_symlink() or "__pycache__" in rel.parts or any(x.endswith(".egg-info") for x in rel.parts):
            continue
        if rel.parts[0] not in ALLOWED_DIRS and str(rel) not in ALLOWED_FILES:
            continue
        if any(x in p.name.lower() for x in ["credentials", "token", "secret", ".env"]) or p.suffix in {".pem", ".pyc"}:
            continue
        yield p


def row_count(path):
    if path.suffix == ".jsonl":
        return len(read_jsonl(path))
    if path.suffix == ".parquet":
        return pq.read_metadata(path).num_rows
    if path.suffix == ".csv":
        import csv
        with path.open(encoding="utf-8-sig", newline="") as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)
    if path.suffix == ".sqlite":
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as c:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            return {t: c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}
    return None


def manifest(root: Path, version: str):
    quality = validate_directory(root)
    reports = read_jsonl(root / "data/reports.jsonl")
    created = now()
    files = []
    for p in included(root):
        if p.name == "manifest.json":
            continue  # Self-checksum is circular; ZIP checksum is external.
        files.append({"path": str(p.relative_to(root)), "bytes": p.stat().st_size,
                      "rows": row_count(p), "sha256": digest(p.read_bytes()), "status": "generated"})
    missing = [
        {"path": "data/labels.parquet", "status": "not_generated", "reason": "No licensed price history; future 20-session horizon unobserved"},
        {"path": "models/ridge_pipeline.joblib", "status": "not_generated", "reason": "No eligible labels; insufficient companies/time span; training rights unconfirmed"},
        {"path": "raw/original_pdfs", "status": "not_retained", "reason": "Full-text redistribution permission not secured"},
        {"path": "data/english_reports.jsonl", "status": "not_generated", "reason": "KIRS English source unavailable (HTTP 503)"},
        {"path": "data/dart_verified.parquet", "status": "not_generated", "reason": "OpenDART API key absent"},
    ]
    missing = [m for m in missing if not (root / m["path"]).exists()]
    value = {"dataset_version": version, "schema_version": "1.0", "generated_at": created, "timezone": "Asia/Seoul",
        "validation_status": quality["status"], "validation_scope": "Schema, numeric extraction agreement, arithmetic and PIT rules; NOT DART verification or training-rights clearance",
        "report_publication_period": {"start": min(r["publication_date"] for r in reports), "end": max(r["publication_date"] for r in reports)},
        "collection_period": {"start": min(r["collected_at"] for r in reports), "end": max(r["collected_at"] for r in reports)},
        "company_count": quality["companies"], "report_count": quality["reports"],
        "sources": sorted({r["source_url"] for r in reports}), "source_registry": "data/sources.csv",
        "files": files, "unavailable": missing,
        "contains_secrets": False, "raw_document_policy": "metadata_only_in_distributed_bundle",
        "current_cloud_status_file": "cloud/deployment_status.json"}
    dump_json(root / "manifest.json", value)
    return value


def verify_manifest(root):
    value = json.loads((root / "manifest.json").read_text())
    for row in value["files"]:
        p = root / row["path"]
        if not p.exists() or digest(p.read_bytes()) != row["sha256"]:
            raise ValueError("Checksum mismatch: " + row["path"])
    return True


def bundle(root: Path, output: Path, version: str):
    manifest(root, version)
    verify_manifest(root)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"investment_dataset_{version}.zip"
    if path.exists():
        raise FileExistsError("Immutable archive already exists; choose a new version")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in included(root):
            z.write(p, "investment_dataset/" + str(p.relative_to(root)))
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
    checksum = digest(path.read_bytes())
    (output / (path.name + ".sha256")).write_text(checksum + "  " + path.name + "\n")
    return path, checksum


def promote(candidate: Path, store: Path, version: str, *, max_store_bytes=100_000_000):
    # Complete validation precedes ANY latest-pointer update.
    validate_directory(candidate)
    tmp = store / "staging" / version
    tmp.mkdir(parents=True, exist_ok=True)
    archive, sha = bundle(candidate, tmp, version)
    used = sum(p.stat().st_size for p in (store / "versions").glob("*.zip"))
    if used + archive.stat().st_size > max_store_bytes:
        raise RuntimeError("Archive capacity guard; previous latest preserved")
    dest = store / "versions" / archive.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError("Immutable version already exists")
    shutil.move(archive, dest)
    shutil.move(str(archive) + ".sha256", str(dest) + ".sha256")
    dump_json(store / "latest_validated.json", {"version": version, "path": str(dest.relative_to(store)), "sha256": sha, "promoted_at": now()})
    return dest
