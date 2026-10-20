"""Behavioural features derived from transaction history: repeated payments by the same user and to
the same receiver inside a time window. Used for training data, uploaded files and (via the database)
single-transaction scoring.
"""

import numpy as np
import pandas as pd

H1, H24 = 3600, 86400
MAX_GAP_MIN = 10080.0   # one week


def _prior_in_window(t_sorted: np.ndarray, window: int) -> np.ndarray:
    """For each element of a time-sorted array: how many EARLIER elements lie within `window` seconds."""
    left = np.searchsorted(t_sorted, t_sorted - window, side="left")
    return np.arange(len(t_sorted)) - left


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Fill transactions_last_hour, minutes_since_last_transaction, sender_txn_24h, same_receiver_24h.

    Needs sender_id, receiver_id and timestamp columns; returns df unchanged if they are missing.
    Counts are of PRIOR transactions only (the current one is excluded), so scoring a transaction in
    real time and re-scoring it from a file give identical features.
    """
    if not {"sender_id", "receiver_id", "timestamp"} <= set(df.columns):
        return df
    out = df.copy()
    ts = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    if ts.isna().any():
        raise ValueError("Some timestamps could not be read; use a format like 2026-07-01 14:30:00.")
    t = (ts - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().to_numpy()
    n = len(out)
    last_hour, last_day, same_recv, gap = (np.zeros(n, dtype=int), np.zeros(n, dtype=int),
                                           np.zeros(n, dtype=int), np.full(n, MAX_GAP_MIN))
    order = np.argsort(t, kind="stable")
    sender = out["sender_id"].astype(str).to_numpy()[order]
    recv = out["receiver_id"].astype(str).to_numpy()[order]
    ts_sorted = t[order]
    keys = pd.Series(np.arange(n))
    for _, idx in keys.groupby(sender).groups.items():
        idx = np.asarray(idx); tt = ts_sorted[idx]
        last_hour[order[idx]] = _prior_in_window(tt, H1)
        last_day[order[idx]] = _prior_in_window(tt, H24)
        if len(idx) > 1:
            gap[order[idx[1:]]] = np.minimum(np.diff(tt) / 60.0, MAX_GAP_MIN)
    pair = pd.Series(sender) + "->" + pd.Series(recv)
    for _, idx in keys.groupby(pair.to_numpy()).groups.items():
        idx = np.asarray(idx)
        same_recv[order[idx]] = _prior_in_window(ts_sorted[idx], H24)
    out["transactions_last_hour"] = last_hour
    out["sender_txn_24h"] = last_day
    out["same_receiver_24h"] = same_recv
    out["minutes_since_last_transaction"] = gap.round(1)
    out["transaction_hour"] = ts.dt.hour.to_numpy()
    out["is_weekend"] = (ts.dt.weekday >= 5).astype(int).to_numpy()
    return out
