import json
from pathlib import Path
from decimal import Decimal

import pandas as pd
import pytest

from investment.common import available_at, dump_json
from investment.dart import compare_amount, fetch_financials
from investment.extract import numeric
from investment.features import labels_from_prices
from investment.http import PublicClient, AccessBlocked
from investment.package import promote
from investment.state import State
from investment.train import time_split, train
from investment.examples import to_chat_examples


def test_missing_and_literal_zero_are_different():
    assert numeric("0.0") == (Decimal("0.0"), None)
    assert numeric("N/A")[0] is None
    assert numeric("흑전")[0] is None
    assert numeric("(1,234)")[0] == Decimal("-1234")


def test_historical_import_never_backdated_without_version_evidence():
    assert available_at("2026-11-17T01:00:00+09:00", "2023-11-17T09:00:00+09:00") == "2026-11-16T16:00:00+00:00"
    with pytest.raises(ValueError): available_at("2026-01-01T12:00:00", None)


def test_resume_preserves_original_observation_and_versions(tmp_path):
    s = State(tmp_path)
    _, version, changed = s.observe("https://example.com/report", "a")
    first = version["first_seen_at"]
    s.finish_version("https://example.com/report", "a", "parsed")
    s2 = State(tmp_path)
    _, v2, changed = s2.observe("https://example.com/report", "a")
    assert changed is False and v2["first_seen_at"] == first and v2["status"] == "parsed"
    item, v3, changed = s2.observe("https://example.com/report", "b")
    assert changed and len(item["versions"]) == 2


def test_concurrent_local_run_rejected(tmp_path):
    with State(tmp_path).lock():
        with pytest.raises(RuntimeError, match="Already running"):
            with State(tmp_path).lock(): pass


def test_telegram_never_requested(monkeypatch):
    c = PublicClient(["t.me"])
    monkeypatch.setattr(c.session, "get", lambda *a, **k: pytest.fail("network must not be called"))
    with pytest.raises(AccessBlocked, match="licensing"):
        c.get("https://t.me/s/kirsofficial")


def calendar_fixture():
    days = pd.bdate_range("2024-01-01", periods=50)
    sessions = pd.DataFrame({"session_date": days.strftime("%Y-%m-%d"),
                             "open_at": [d.strftime("%Y-%m-%dT09:00:00+09:00") for d in days]})
    prices = pd.DataFrame({"stock_code": "001234", "session_date": sessions.session_date,
                           "adjusted_open": range(100, 150), "tradable": True, "source_id": "synthetic_test_only"})
    f = pd.DataFrame([{"sample_id": "test1", "stock_code": "001234", "family_id": "family1",
                       "available_at": "2024-01-01T09:01:00+09:00"}])
    return f, prices, sessions


def test_entry_after_information_and_exact_twenty_exchange_sessions():
    f, p, c = calendar_fixture()
    result = labels_from_prices(f,p,c,license_confirmed=True,as_of="2025-01-01T00:00:00Z")
    assert result.iloc[0].entry_date == c.iloc[1].session_date
    assert result.iloc[0].exit_date == c.iloc[21].session_date
    assert result.iloc[0].label == pytest.approx(121/101-1)


def test_missing_exit_not_forward_filled_or_horizon_extended():
    f,p,c = calendar_fixture()
    p = p.drop(index=21)
    r = labels_from_prices(f,p,c,license_confirmed=True,as_of="2025-01-01T00:00:00Z")
    assert r.iloc[0].label is None
    assert r.iloc[0].label_status == "exit_missing_halted_or_delisted"


def test_halted_entry_waits_but_future_label_remains_absent():
    f,p,c = calendar_fixture()
    p.loc[1, "tradable"] = False
    r = labels_from_prices(f,p,c,license_confirmed=True,as_of="2024-01-03T01:00:00Z")
    assert r.iloc[0].entry_date == c.iloc[2].session_date
    assert r.iloc[0].label_status == "future_horizon"


def test_price_license_and_duplicate_keys_gate():
    f,p,c = calendar_fixture()
    with pytest.raises(PermissionError): labels_from_prices(f,p,c)
    with pytest.raises(ValueError,match="Duplicate price"):
        labels_from_prices(f,pd.concat([p,p.iloc[:1]]),c,license_confirmed=True)


def test_temporal_split_purges_overlap_and_translation_families():
    dates = pd.date_range("2020-01-01", periods=100, freq="7D", tz="UTC")
    f = pd.DataFrame({"sample_id": [str(i) for i in range(100)], "family_id": [str(i) for i in range(100)],
        "available_at": dates, "entry_at": dates+pd.Timedelta(days=1), "exit_at": dates+pd.Timedelta(days=30)})
    f.loc[90, "family_id"] = "1"
    a,b,c = time_split(f)
    assert a.exit_at.max() < b.available_at.min()
    assert b.exit_at.max() < c.available_at.min()
    assert not set(a.family_id) & set(c.family_id)
    assert "90" not in set(c.sample_id)


def test_failed_candidate_cannot_replace_latest(tmp_path,monkeypatch):
    store=tmp_path/"store";store.mkdir()
    dump_json(store/"latest_validated.json",{"version":"old"})
    monkeypatch.setattr("investment.package.validate_directory", lambda p: (_ for _ in ()).throw(ValueError("invalid candidate")))
    with pytest.raises(ValueError): promote(tmp_path/"bad",store,"new")
    assert json.loads((store/"latest_validated.json").read_text())["version"] == "old"


def test_dart_scope_period_rounding_and_no_key(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    assert fetch_financials("00123456",2023)["status"] == "not_collected"
    assert compare_amount(100000000, "100,000,001", same_scope=True,same_period=True,same_account=True) == "matched_with_rounding"
    assert compare_amount(0, 100, same_scope=False,same_period=True,same_account=True) == "not_comparable"


def test_no_fake_model_when_labels_missing(tmp_path):
    r=train(tmp_path/"features.parquet",tmp_path/"labels.parquet",tmp_path/"evaluation",{"min_samples":500})
    assert r["actually_trained"] is False and r["metrics"] is None
    assert not (tmp_path/"models/ridge_pipeline.joblib").exists()


def test_unreviewed_examples_cannot_be_exported_for_training():
    with pytest.raises(PermissionError): list(to_chat_examples([]))


def test_transitive_lineage_and_cross_company_rejection():
    from investment.lineage import apply_lineage
    r=[{'report_id':x,'stock_code':'001234','family_id':x,'content_version':x} for x in ['a','b','c']]
    links=[{'report_id':'b','related_report_id':'a','kind':'translation_of','status':'verified','evidence':'reviewed translation'},
           {'report_id':'c','related_report_id':'b','kind':'supersedes','status':'verified','evidence':'reviewed correction'}]
    assert len({x['family_id'] for x in apply_lineage(r,links)})==1
    r[2]['stock_code']='006789'
    with pytest.raises(ValueError,match='cross-company'):apply_lineage(r,links)


def test_uncertain_tradability_and_nonfinite_exit_cannot_create_a_label():
    f,p,c=calendar_fixture()
    p["tradable"]=p.tradable.astype("boolean")
    p.loc[1,"tradable"]=pd.NA
    with pytest.raises(ValueError,match="Tradability"):
        labels_from_prices(f,p,c,license_confirmed=True)
    p.loc[1,"tradable"]=True
    p["adjusted_open"]=p.adjusted_open.astype(float)
    p.loc[21,"adjusted_open"]=float("inf")
    r=labels_from_prices(f,p,c,license_confirmed=True,as_of="2025-01-01T00:00:00Z")
    assert r.iloc[0].label_status=="invalid_price" and r.iloc[0].label is None


def test_deferred_retraining_preserves_previous_successful_evaluation(tmp_path):
    out=tmp_path/"evaluation";out.mkdir()
    dump_json(out/"model_evaluation.json",{"actually_trained":True,"status":"trained","metrics":{"test":{"mae":0.1}}})
    result=train(tmp_path/"features.parquet",tmp_path/"labels.parquet",out,{"min_samples":500})
    assert result["status"]=="deferred"
    assert json.loads((out/"model_evaluation.json").read_text())["actually_trained"] is True
    assert json.loads((out/"last_training_attempt.json").read_text())["actually_trained"] is False
