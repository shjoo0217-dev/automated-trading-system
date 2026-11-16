from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from filelock import FileLock, Timeout

from .common import dump_json, now, stable_id


class State:
    """Checkpoint after every completed URL; remote persistence is separate.

    A native Windows/POSIX file lock protects one machine. GitHub concurrency protects cloud jobs,
    and the state branch update uses a non-force git push for remote CAS.
    """
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "state.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {
            "schema_version": 1, "sources": {}, "runs": {}, "seen_hashes": {}, "disabled": False}

    @contextmanager
    def lock(self):
        lock = FileLock(str(self.directory / ".lock"))
        try:
            lock.acquire(timeout=0)
        except Timeout:
            raise RuntimeError("Already running") from None
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            yield self
        finally:
            lock.release()

    def save(self):
        dump_json(self.path, self.data)

    def observe(self, url, content_hash, *, content=None):
        key = stable_id(url)
        item = self.data["sources"].setdefault(key, {"url": url, "first_seen_at": now(), "versions": []})
        item["last_checked_at"] = now()
        existing = next((v for v in item["versions"] if v["sha256"] == content_hash), None)
        if existing:
            self.save()
            return item, existing, False
        v = {"sha256": content_hash, "first_seen_at": now(), "collected_at": now(), "status": "pending"}
        if content is not None:
            v["content"] = content
        item["versions"].append(v)
        self.save()
        return item, v, True

    def finish_version(self, url, sha256, status, **extra):
        item = self.data["sources"][stable_id(url)]
        version = next(v for v in item["versions"] if v["sha256"] == sha256)
        version.update(status=status, **extra)
        self.save()
