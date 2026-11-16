#!/usr/bin/env bash
set -euo pipefail
# Run from the directory containing investment_dataset; this is an interactive/local process.
python3 -m venv .star-venv
.star-venv/bin/python -m pip install -r investment_dataset/pipeline/requirements.lock.txt
export PYTHONPATH=investment_dataset/pipeline
.star-venv/bin/python investment_dataset/pipeline/run_direct.py --state investment_dataset/data/checkpoint.json --max-cycles 5 --posts-per-cycle 60
