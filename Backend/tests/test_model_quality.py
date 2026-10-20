"""Model and data checks on data the model never saw during training."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from app.data.behavior import compute
from app.data.generator import CATEGORIES, generate
from app.ml.policy import tiers
from app.services.scoring import service

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
pytestmark = pytest.mark.skipif(not service.ready, reason="model not trained")


@pytest.fixture(scope="module")
def unseen():
    df = pd.read_csv(SAMPLES / "upi_test_transactions.csv")
    res = service.score(df, explain=False)
    df["risk"] = [r["risk_score"] for r in res]; df["model"] = [r["model_score"] for r in res]; df["decision"] = [r["decision"] for r in res]
    return df


def test_generator_is_deterministic_and_in_scope():
    a, b = generate(3, 0.02), generate(3, 0.02)
    pd.testing.assert_frame_equal(a, b)
    assert set(a.merchant_category) <= set(CATEGORIES) and a.amount_inr.max() <= 200_000 and a.amount_inr.min() >= 10
    assert 0.01 < a.is_fraud.mean() < 0.08 and a.bank.nunique() == 5


def test_history_features_match_a_second_implementation():
    df = generate(4, 0.02)
    out = compute(df.copy())
    sample = out.sample(60, random_state=1)
    ts = pd.to_datetime(out.timestamp, utc=True)
    for i, row in sample.iterrows():
        prior = out[(out.sender_id == row.sender_id) & ((ts < ts[i]) | ((ts == ts[i]) & (out.index < i)))]
        w24 = prior[ts[prior.index] >= ts[i] - pd.Timedelta(hours=24)]
        assert row.sender_txn_24h == len(w24)
        assert row.same_receiver_24h == (w24.receiver_id == row.receiver_id).sum()
        assert row.transactions_last_hour == (ts[w24.index] >= ts[i] - pd.Timedelta(hours=1)).sum()


def test_model_ranks_fraud_above_legitimate_on_unseen_data(unseen):
    y = unseen.is_fraud
    assert roc_auc_score(y, unseen.model) > 0.95
    assert average_precision_score(y, unseen.model) > 0.5
    assert unseen.model[y == 1].median() > unseen.model[y == 0].median() + 30


def test_flagged_recall_and_precision_on_unseen_data(unseen):
    y, flag = unseen.is_fraud == 1, unseen.decision != "ALLOW"
    assert (flag & y).sum() / y.sum() > 0.6            # recall of Moderate + High
    assert (flag & y).sum() / flag.sum() > 0.35        # precision of Moderate + High


def test_policy_invariants_hold_for_every_unseen_payment(unseen):
    assert (unseen[unseen.amount_inr >= 100_000].decision == "BLOCK").all()
    assert (unseen[unseen.amount_inr < 100_000].decision != "BLOCK").all()
    mid = unseen[(unseen.amount_inr >= 70_000) & (unseen.amount_inr < 100_000)]
    assert (mid.decision != "ALLOW").all()
    assert unseen[unseen.decision == "ALLOW"].risk.max() < 40
    assert unseen[unseen.decision == "STEP_UP_AUTH"].risk.between(40, 79.9).all()
    assert unseen[unseen.decision == "BLOCK"].risk.between(80, 99).all()


def test_scoring_is_deterministic_and_batch_equals_single():
    df = generate(9, 0.02).head(40)
    batch = service.score(df, explain=False)
    again = service.score(df, explain=False)
    assert [r["risk_score"] for r in batch] == [r["risk_score"] for r in again]
    singles = [service.score(df.iloc[[i]], explain=False)[0]["model_score"] for i in range(10)]
    assert np.allclose([r["model_score"] for r in batch[:10]], singles, atol=0.05)


def test_explanations_are_present_for_flagged_payments_only():
    df = generate(10, 0.02).head(300)
    res = service.score(df, explain=True)
    assert all(r["reasons"] for r in res if r["decision"] != "ALLOW")
    assert all(not r["reasons"] for r in res if r["decision"] == "ALLOW")
    assert all(0 <= x["weight"] <= 1 for r in res for x in r["reasons"] if x["weight"] is not None)


def test_report_matches_active_model():
    rep = json.loads((Path(__file__).resolve().parents[1] / "artifacts" / "report.json").read_text())
    assert abs(rep["final"]["threshold"] - service.meta["threshold"]) < 1e-3
    assert rep["privacy"]["raw_rows_sent_to_server"] == 0 and rep["privacy"]["secure_aggregation"] is True
    assert rep["experiments"]["fedavg_secagg"]["secagg"]["secagg_max_error"] < 1e-4
    assert rep["experiments"]["federated"]["metrics"]["pr_auc"] > rep["experiments"]["local_only"]["metrics"]["pr_auc"]


def test_tiers_function_edges():
    lvl, _ = tiers([99_999, 100_000, 70_000, 69_999], [0, 0, 0, 0], [0, 0, 0, 0], np.zeros(4), 0.8)
    assert lvl.tolist() == [1, 2, 1, 0]
