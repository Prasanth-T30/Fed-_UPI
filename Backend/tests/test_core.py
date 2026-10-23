import numpy as np
import pytest
import torch

from app.data.features import FEATURES, transform
from app.data.generator import generate
from app.ml.federated import Client, FedConfig, aggregate, make_model, run_federation
from app.ml.metrics import best_threshold, evaluate, paper_threshold, recall_threshold


@pytest.fixture(scope="module")
def df():
    return generate(seed=1, scale=0.1)


def test_generator_shape_and_banks(df):
    assert df.bank.nunique() == 5 and 0.01 < df.is_fraud.mean() < 0.08
    assert transform(df).shape == (len(df), len(FEATURES))


def test_aggregate_is_weighted_average():
    cfg = FedConfig()
    g = {"w": torch.zeros(2)}
    ups = [{"state": {"w": torch.ones(2)}, "n": 1}, {"state": {"w": torch.full((2,), 4.0)}, "n": 3}]
    out = aggregate(g, ups, cfg, np.random.default_rng(0))
    assert torch.allclose(out["w"], torch.full((2,), 3.25))


def test_dp_clip_bounds_update():
    cfg = FedConfig(dp_clip=0.5)
    g = {"w": torch.zeros(4)}
    out = aggregate(g, [{"state": {"w": torch.full((4,), 10.0)}, "n": 5}], cfg, np.random.default_rng(0))
    assert float(out["w"].norm()) <= 0.5 + 1e-5


def test_federation_learns(df):
    x, y = transform(df), df.is_fraud.to_numpy()
    idx = np.array_split(np.arange(len(df)), 3)
    clients = [Client(f"c{i}", x[i], y[i]) for i in idx]
    model, hist = run_federation(clients, x, y, FedConfig(rounds=12))
    assert hist[-1]["pr_auc"] > hist[0]["pr_auc"] and hist[-1]["pr_auc"] > 5 * y.mean()


def test_metrics():
    y = np.array([0, 0, 1, 1])
    s = np.array([0.1, 0.4, 0.35, 0.8])
    m = evaluate(y, s, best_threshold(y, s))
    assert 0 <= m["f1"] <= 1 and m["tp"] + m["fn"] == 2


def test_research_paper_models_and_threshold_grid():
    logistic = make_model("logistic", 13)
    paper_mlp = make_model("paper_mlp", 13)
    assert logistic.linear.in_features == 13
    assert paper_mlp.net[0].in_features == 13
    assert paper_mlp.net[0].out_features == 16
    assert paper_mlp.net[-1].out_features == 1

    y = np.array([0, 0, 1, 1])
    scores = np.array([0.05, 0.25, 0.55, 0.90])
    threshold = paper_threshold(y, scores)
    assert 0.10 <= threshold <= 0.95
    assert round(threshold, 2) == threshold


def test_recall_threshold_meets_target_and_prefers_highest_cutoff():
    y = np.array([1, 0, 1, 1, 0])
    s = np.array([0.9, 0.8, 0.7, 0.4, 0.2])
    threshold = recall_threshold(y, s, minimum_recall=2 / 3)
    assert threshold == 0.7
    assert (y[s >= threshold].sum() / y.sum()) >= 2 / 3





def test_policy_tiers_and_risk_percent():
    from app.ml import policy
    amt = np.array([500, 69_999, 70_000, 99_999, 100_000, 50_000])
    lvl, _ = policy.tiers(amt, [0, 0, 0, 0, 0, 2], [0] * 6, np.zeros(6), 0.8)
    assert lvl.tolist() == [0, 0, 1, 1, 2, 1]                       # repeat receiver -> MODERATE, never HIGH
    lvl2, _ = policy.tiers([50_000], [0], [0], np.array([0.99]), 0.8)
    assert lvl2.tolist() == [1]                                      # model alone cannot reach HIGH
    pct = policy.risk_percent(np.array([0, 1, 2]), np.array([0.5, 0.5, 0.5]), 0.8)
    assert pct[0] < 40 <= pct[1] < 80 <= pct[2] < 100


def test_behavior_features():
    import pandas as pd
    from app.data.behavior import compute
    df = pd.DataFrame({"sender_id": ["a"] * 4 + ["b"], "receiver_id": ["r"] * 3 + ["x", "r"],
                       "timestamp": ["2026-08-01 10:00:00", "2026-08-01 10:30:00", "2026-08-01 11:00:00",
                                     "2026-08-03 10:00:00", "2026-08-01 10:10:00"]})
    out = compute(df)
    assert out["same_receiver_24h"].tolist() == [0, 1, 2, 0, 0]
    assert out["transactions_last_hour"].tolist() == [0, 1, 2, 0, 0] and out["sender_txn_24h"].tolist() == [0, 1, 2, 0, 0]
