from __future__ import annotations

from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .common import dump_json, now
from .features import NUMERIC_FEATURES


def record_evaluation(output, result):
    """A deferred attempt must not erase the last successfully trained result."""
    dump_json(output / "last_training_attempt.json", result)
    latest = output / "model_evaluation.json"
    previous = json.loads(latest.read_text()) if latest.exists() else {}
    if result["actually_trained"] or not previous.get("actually_trained"):
        dump_json(latest, result)
    return result


def time_split(frame):
    f = frame.copy().sort_values(["available_at", "sample_id"])
    for c in ["available_at", "entry_at", "exit_at"]:
        f[c] = pd.to_datetime(f[c], utc=True)
    times = sorted(f.available_at.unique())
    if len(times) < 10:
        raise ValueError("Insufficient unique availability times")
    val_start, test_start = times[int(len(times) * .6)], times[int(len(times) * .8)]
    tr = f[(f.available_at < val_start) & (f.exit_at < val_start)].copy()
    va = f[(f.available_at >= val_start) & (f.available_at < test_start) & (f.exit_at < test_start)].copy()
    te = f[f.available_at >= test_start].copy()
    # If a family occurs across boundaries, keep it in its earliest split only.
    # This protects translation and revision groups without revising past inputs.
    earliest = f.groupby("family_id").available_at.min()
    tr = tr[tr.family_id.map(earliest) < val_start]
    va = va[(va.family_id.map(earliest) >= val_start) & (va.family_id.map(earliest) < test_start)]
    te = te[te.family_id.map(earliest) >= test_start]
    for x in [tr, va, te]:
        x.drop_duplicates("family_id", keep="first", inplace=True)
    return tr, va, te


def train(features_path: Path, labels_path: Path, output: Path, settings: dict):
    output.mkdir(parents=True, exist_ok=True)
    result = {"status": "deferred", "actually_trained": False, "evaluated_at": now(),
              "target": "20_exchange_session_open_to_open_price_return", "metrics": None,
              "cost_assumptions": {"trading_backtest_performed": False, "fees": None, "tax": None,
                                   "slippage": None, "liquidity_filter": None},
              "resume_conditions": settings}
    if not features_path.exists() or not labels_path.exists():
        result["reason"] = "Licensed prices/labels not available; no fabricated labels or evaluation"
        return record_evaluation(output, result)
    f = pd.read_parquet(features_path)
    labels = pd.read_parquet(labels_path)
    if labels.duplicated("sample_id").any() or f.duplicated("sample_id").any():
        raise ValueError("Duplicate sample IDs")
    frame = f[f.training_eligible].merge(labels[labels.label_status == "valid"], on="sample_id", validate="one_to_one", suffixes=("", "_label"))
    result["valid_samples"] = len(frame)
    result["companies"] = int(frame.stock_code.nunique())
    months = 0 if frame.empty else (pd.to_datetime(frame.available_at, utc=True).max() - pd.to_datetime(frame.available_at, utc=True).min()).days / 30.4375
    seen_path = output.parent / "models" / "trained_sample_ids.json"
    trained_ids = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()
    new_count = len(set(frame.sample_id) - trained_ids)
    result["new_valid_samples"] = new_count
    if (len(frame) < settings["min_samples"] or frame.stock_code.nunique() < settings["min_companies"]
            or months < settings["min_months"] or new_count < settings["min_new_samples"]):
        result["reason"] = "Insufficient licensed, validated, time-separated new observations"
        return record_evaluation(output, result)
    tr, va, te = time_split(frame)
    if min(map(len, [tr, va, te])) < settings["min_split_samples"]:
        result["reason"] = "Too few samples after family grouping and label-overlap purging"
        return record_evaluation(output, result)
    # Fit all transforms on TRAIN ONLY. Fixed alpha: no test-set tuning.
    model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler(), Ridge(alpha=1.0))
    baseline = DummyRegressor(strategy="mean")
    model.fit(tr[NUMERIC_FEATURES], tr.label)
    baseline.fit(tr[NUMERIC_FEATURES], tr.label)
    scores = {}
    for name, data in [("train", tr), ("validation", va), ("test", te)]:
        p, b = model.predict(data[NUMERIC_FEATURES]), baseline.predict(data[NUMERIC_FEATURES])
        scores[name] = {"samples": len(data), "companies": int(data.stock_code.nunique()),
            "availability_start": data.available_at.min().isoformat(), "availability_end": data.available_at.max().isoformat(),
            "label_end": data.exit_at.max().isoformat(), "mae": float(mean_absolute_error(data.label, p)),
            "rmse": float(mean_squared_error(data.label, p) ** .5), "r2": float(r2_score(data.label, p)),
            "baseline_mae": float(mean_absolute_error(data.label, b)), "baseline_rmse": float(mean_squared_error(data.label, b) ** .5)}
    model_dir = output.parent / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / "ridge_pipeline.joblib")
    joblib.dump(baseline, model_dir / "mean_baseline.joblib")
    dump_json(model_dir / "training_config.json", {"features": NUMERIC_FEATURES, "ridge_alpha": 1.0, "settings": settings,
        "train_sample_ids": tr.sample_id.tolist(), "validation_sample_ids": va.sample_id.tolist(), "test_sample_ids": te.sample_id.tolist()})
    dump_json(seen_path, sorted(set(frame.sample_id)))
    result.update(status="trained", actually_trained=True, reason=None, metrics=scores)
    return record_evaluation(output, result)
