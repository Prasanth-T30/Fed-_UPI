"""End-to-end experiment pipeline: split -> federate -> baselines -> report + artifacts."""

import time
from typing import Callable, Optional

import numpy as np
import pandas as pd
import torch 
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve

from app.data.features import FEATURES, transform
from app.ml.explain import attributions
from app.ml.federated import Client, FedConfig, run_federation, scores
from app.ml.metrics import best_threshold, evaluate, recall_threshold
from app.ml import policy
from app.ml.privacy import epsilon

Progress = Optional[Callable[[dict], None]]


def split_by_bank(df: pd.DataFrame, seed: int):
    parts = {"train": [], "val": [], "test": []}
    for bank, g in df.groupby("bank", sort=True):
        tr, rest = train_test_split(g, test_size=0.30, stratify=g.is_fraud, random_state=seed)
        va, te = train_test_split(rest, test_size=0.5, stratify=rest.is_fraud, random_state=seed)
        for k, v in zip(parts, (tr, va, te)):
            parts[k].append(v.assign(bank=bank))
    return {k: pd.concat(v, ignore_index=True) for k, v in parts.items()}


def _xy(df):
    return transform(df), df.is_fraud.to_numpy(dtype=np.int64)


def ae_normaliser(model, x_val, y_val):
    err = scores(model, "ae", x_val[y_val == 0])
    return float(np.percentile(err, 95)) * 4 + 1e-9


def ae_norm(model, x, scale):
    return np.clip(scores(model, "ae", x) / scale, 0, 1)


def run_pipeline(df: pd.DataFrame, cfg: FedConfig, progress: Progress = None, full: bool = True):
    """full=True runs every baseline (for the research report); False = fast federated run."""
    t0 = time.time()
    say = lambda stage, **kw: progress and progress({"stage": stage, **kw})
    sp = split_by_bank(df, cfg.seed)
    xtr, ytr = _xy(sp["train"]); xva, yva = _xy(sp["val"]); xte, yte = _xy(sp["test"])
    clients = []
    for bank, g in sp["train"].groupby("bank", sort=True):
        x, y = _xy(g)
        clients.append(Client(bank, x, y))

    def fed(c_list, **over):
        c = FedConfig(**{**cfg.dict(), **over})
        return run_federation(c_list, xva, yva, c, on_round=lambda r: say(f"{c.algorithm}/{c.kind}", **r))

    def test_metrics(model, kind="clf"):
        thr = best_threshold(yva, scores(model, kind, xva))
        return evaluate(yte, scores(model, kind, xte), thr)

    experiments = {}
    # --- main federated supervised model -------------------------------------------------
    say("federated-main", note=f"{cfg.algorithm} x {len(clients)} banks")
    main_model, main_hist = fed(clients)
    experiments["federated"] = {"label": f"Federated {cfg.algorithm.upper()}", "metrics": test_metrics(main_model),
                                "history": main_hist}
    # --- federated unsupervised autoencoder + ensemble -----------------------------------
    say("federated-autoencoder")
    ae_model, ae_hist = fed(clients, kind="ae", algorithm="fedavg", lr=0.05, local_epochs=5, rounds=max(cfg.rounds, 20))
    scale = ae_normaliser(ae_model, xva, yva)
    p_va, a_va = scores(main_model, "clf", xva), ae_norm(ae_model, xva, scale)
    best_w, best_f = 0.0, -1.0
    for w in (0.0, 0.1, 0.2, 0.3):
        s = (1 - w) * p_va + w * a_va
        f = evaluate(yva, s, best_threshold(yva, s))["f1"]
        if f > best_f + 1e-9:
            best_w, best_f = w, f
    ens = lambda x: (1 - best_w) * scores(main_model, "clf", x) + best_w * ae_norm(ae_model, x, scale)
    # Keep a validation margin so recall remains robust on unseen bank/upload distributions.
    thr = recall_threshold(yva, ens(xva), minimum_recall=0.75)
    experiments["ensemble"] = {"label": "Federated MLP + Autoencoder", "metrics": evaluate(yte, ens(xte), thr)}
    ae_only_thr = best_threshold(yva, scores(ae_model, "ae", xva))
    experiments["autoencoder"] = {"label": "Federated Autoencoder (unsupervised)",
                                  "metrics": evaluate(yte, scores(ae_model, "ae", xte), ae_only_thr), "history": ae_hist}
    if full:
        say("federated-fedprox")
        m, h = fed(clients, algorithm="fedprox")
        experiments["fedprox"] = {"label": "Federated FedProx", "metrics": test_metrics(m), "history": h}
        say("federated-dp")
        for key, label, over in (
            ("fedavg_secagg", "Federated FedAvg + Secure Aggregation", dict(secure_agg=True)),
            ("fedavg_dp", "Federated FedAvg + DP (clip 1.0, z 0.3)", dict(dp_clip=1.0, dp_noise=0.3)),
            ("fedavg_dp_secagg", "Federated FedAvg + DP + SecAgg (clip 1.0, z 1.0)",
             dict(dp_clip=1.0, dp_noise=1.0, secure_agg=True)),
        ):
            m, h = fed(clients, algorithm="fedavg", **over)
            c = FedConfig(**{**cfg.dict(), **over})
            entry = {"label": label, "metrics": test_metrics(m), "history": h}
            if c.dp_noise > 0:
                entry["epsilon"] = round(epsilon(c.dp_noise, c.rounds, c.dp_delta), 2)
            if c.secure_agg:
                entry["secagg"] = m.fed_stats
            experiments[key] = entry
        say("centralized")
        m, h = fed([Client("all", xtr, ytr)], algorithm="fedavg")
        experiments["centralized_mlp"] = {"label": "Centralized MLP (all data pooled)", "metrics": test_metrics(m)}
        gb = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1, random_state=cfg.seed, class_weight="balanced")
        gb.fit(xtr, ytr)
        gthr = best_threshold(yva, gb.predict_proba(xva)[:, 1])
        experiments["centralized_gbm"] = {"label": "Centralized Gradient Boosting",
                                          "metrics": evaluate(yte, gb.predict_proba(xte)[:, 1], gthr)}
        say("local-only")
        locs = []
        for c in clients:
            m, _ = fed([c], algorithm="fedavg")
            locs.append({"bank": c.name, **test_metrics(m)})
        keys = ["precision", "recall", "f1", "roc_auc", "pr_auc", "accuracy", "fpr"]
        avg = {k: round(float(np.mean([l[k] for l in locs])), 4) for k in keys}
        experiments["local_only"] = {"label": "Local-only (each bank alone, mean)", "metrics": avg, "per_bank": locs}

    # --- final model analytics -----------------------------------------------------------
    final_scores = ens(xte)
    review_thr = round(thr * 0.5, 4)
    prec, rec, _ = precision_recall_curve(yte, final_scores)
    step = max(1, len(prec) // 60)
    per_bank = []
    for bank, g in sp["test"].groupby("bank", sort=True):
        idx = g.index.to_numpy()
        per_bank.append({"bank": bank, "rows": len(g), "fraud": int(g.is_fraud.sum()),
                         **{k: v for k, v in evaluate(yte[idx], final_scores[idx], thr).items()
                            if k in ("precision", "recall", "f1", "pr_auc")}})
    test = sp["test"].reset_index(drop=True)
    flagged = final_scores >= thr
    by_scenario = []
    for s, g in test[test.is_fraud == 1].groupby("scenario"):
        by_scenario.append({"scenario": s, "count": len(g), "recall": round(float(flagged[g.index].mean()), 4)})
    lvl, trig = policy.tiers(test["amount_inr"], test.get("same_receiver_24h", 0), test.get("transactions_last_hour", 0), final_scores, thr)
    risk = policy.risk_percent(lvl, final_scores, thr)
    fl = lvl >= 1
    tp = int((fl & (yte == 1)).sum())
    pol = {
        "rules": {"high_min": policy.HIGH_MIN, "moderate_min": policy.MODERATE_MIN,
                  "repeat_receiver_prior_payments": policy.REPEAT_RECEIVER_MIN, "burst_prior_payments_1h": policy.BURST_PER_HOUR_MIN},
        "tiers": [{"tier": name, "transactions": int((lvl == i).sum()), "fraud": int(((lvl == i) & (yte == 1)).sum()),
                   "mean_risk_pct": round(float(risk[lvl == i].mean()), 1) if (lvl == i).any() else None}
                  for i, name in enumerate(policy.LEVELS)],
        "flagged_precision": round(tp / max(int(fl.sum()), 1), 4), "flagged_recall": round(tp / max(int((yte == 1).sum()), 1), 4),
        "triggers": {k: {"flagged": int(v.sum()), "fraud": int((v & (yte == 1)).sum())} for k, v in trig.items()},
        "high_amount_legit": int((trig["high_amount"] & (yte == 0)).sum()),
        "repeat_receiver_note": "Repeat = 2+ earlier payments to the same receiver by the same user within 24h.",
    }
    fraud_x = xte[yte == 1][:400]
    importance = np.abs(attributions(main_model, fraud_x)).mean(axis=0)
    imp = _merge_importance(importance)
    hist_bins = np.linspace(0, 1, 21)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec": round(time.time() - t0, 1),
        "config": cfg.dict(),
        "dataset": {
            "rows": len(df), "fraud_rows": int(df.is_fraud.sum()), "fraud_rate": round(float(df.is_fraud.mean()), 4),
            "train": len(sp["train"]), "val": len(sp["val"]), "test": len(sp["test"]),
            "banks": [{"bank": c.name, "rows": c.n, "fraud": int(c.y.sum()),
                       "fraud_rate": round(float(c.y.mean()), 4)} for c in clients],
            "note": "Metrics are calculated from the explicitly supplied labelled training dataset.",
        },
        "experiments": experiments,
        "final": {
            "threshold": round(thr, 4), "review_threshold": review_thr, "ensemble_weight": best_w,
            "metrics": evaluate(yte, final_scores, thr),
            "pr_curve": [{"recall": round(float(r), 4), "precision": round(float(p), 4)}
                         for p, r in zip(prec[::step], rec[::step])],
            "per_bank": per_bank, "by_scenario": by_scenario, "importance": imp, "policy": pol,
            "score_hist": {
                "bins": [round(float(b), 2) for b in hist_bins[:-1]],
                "legit": np.histogram(final_scores[yte == 0], hist_bins)[0].tolist(),
                "fraud": np.histogram(final_scores[yte == 1], hist_bins)[0].tolist(),
            },
        },
        "privacy": {
            "raw_rows_sent_to_server": 0,
            "params_per_update": sum(p.numel() for p in main_model.parameters()),
            "secure_aggregation": cfg.secure_agg,
            "dp": {"enabled": cfg.dp_clip > 0 and cfg.dp_noise > 0, "clip": cfg.dp_clip, "noise_multiplier": cfg.dp_noise,
                   "delta": cfg.dp_delta, "rounds": cfg.rounds,
                   "epsilon": round(epsilon(cfg.dp_noise, cfg.rounds, cfg.dp_delta), 2) if cfg.dp_clip > 0 and cfg.dp_noise > 0 else None},
            "secagg_stats": getattr(main_model, "fed_stats", {}) if cfg.secure_agg else None,
            "note": ("Client-level (eps, delta)-DP via an RDP accountant, all banks every round, no subsampling; "
                     "epsilon covers the training rounds of the supervised model only. Secure aggregation is pairwise "
                     "masking with simulated key agreement and no dropout recovery."),
        },
    }
    artifacts = {"mlp": main_model.state_dict(), "ae": ae_model.state_dict(),
                 "meta": {"threshold": float(thr), "review_threshold": review_thr, "ensemble_weight": best_w,
                          "ae_scale": scale, "n_features": len(FEATURES)}}
    return report, artifacts


def _merge_importance(imp: np.ndarray):
    from app.data.features import LABELS
    merged = {}
    for f, v in zip(FEATURES, imp):
        label = LABELS.get(f)
        if label:
            merged[label] = merged.get(label, 0.0) + float(v)
    tot = sum(merged.values()) or 1.0
    items = sorted(merged.items(), key=lambda kv: -kv[1])[:10]
    return [{"feature": k, "importance": round(v / tot, 4)} for k, v in items]
