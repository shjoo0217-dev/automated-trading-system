import argparse
import json
from pathlib import Path
import yaml

from .common import read_jsonl, now
from .quality import validate_directory
from .package import bundle, verify_manifest
from .pipeline import run
from .train import train


def main():
    p = argparse.ArgumentParser(description="KIRS investment dataset; never places orders")
    p.add_argument("command", choices=["validate", "verify", "package", "run", "train"])
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--state", type=Path, default=Path(".runtime"))
    p.add_argument("--mode", choices=["collect", "train", "health"], default="collect")
    p.add_argument("--version", default=None)
    p.add_argument("--output", type=Path, default=Path("dist"))
    a = p.parse_args()
    if a.command == "validate": result = validate_directory(a.root)
    elif a.command == "verify": result = {"checksums_valid": verify_manifest(a.root)}
    elif a.command == "package":
        if not a.version: p.error("--version required for immutable packaging")
        archive, sha = bundle(a.root, a.output, a.version)
        result = {"archive": str(archive), "sha256": sha}
    elif a.command == "train":
        config = yaml.safe_load((a.root / "config.example.yaml").read_text())
        result = train(a.root / "data/features.parquet", a.root / "data/labels.parquet", a.root / "evaluation", config["training"])
    else: result = run(a.root, a.state, a.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
