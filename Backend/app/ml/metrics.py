"""Evaluation helpers for highly imbalanced fraud data."""

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def best_threshold(y, s) -> float:
    """Threshold maximising F1 on validation scores (exact sweep)."""
    order = np.argsort(-s, kind="stable")
    ss, yy = s[order], y[order]
    ends = np.r_[np.flatnonzero(np.diff(ss)), len(y) - 1]
    tp = np.cumsum(yy)[ends]
    f1 = 2 * tp / (ends + 1 + y.sum())
    return float(ss[ends[np.argmax(f1)]])


def evaluate(y, s, thr: float) -> dict:
    y = np.asarray(y).astype(int)
    pred = s >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum()); tn = int((~pred & (y == 0)).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    return {
        "precision": round(prec, 4), "recall": round(rec, 4),
        "f1": round(2 * prec * rec / max(prec + rec, 1e-12), 4),
        "accuracy": round((tp + tn) / len(y), 4),
        "fpr": round(fp / max(fp + tn, 1), 4),
        "roc_auc": round(float(roc_auc_score(y, s)), 4),
        "pr_auc": round(float(average_precision_score(y, s)), 4),
        "threshold": round(float(thr), 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }
