"""Synthetic UPI transaction generator: P2P, merchant and investment payments across five banks.

No public labelled real UPI fraud dataset exists (banks cannot share one - the reason for federated
learning). This generator simulates UPI fraud typologies and, importantly, produces sender/receiver
identifiers and timestamps so that repeat-payment behaviour (same user, same receiver, time window)
is computed from real history instead of being typed in:

  collect_scam, sim_swap, qr_phishing, account_takeover  - single suspicious payments
  mule_account      - burst of many payments by one user inside an hour
  repeat_receiver   - the same user paying the same receiver again and again (structuring / split payments)
  stealth           - fraud with only a faint signal
Legitimate traffic includes hard negatives: new-phone payments, big purchases and genuine double payments.
"""

import numpy as np
import pandas as pd

from app.data.behavior import compute

CATEGORIES = ["p2p", "merchant", "investment"]
SCENARIOS = ["collect_scam", "sim_swap", "mule_account", "qr_phishing", "account_takeover", "repeat_receiver", "stealth"]
START = pd.Timestamp("2026-07-01", tz="UTC")
MAX_AMOUNT = 200_000

# bank -> (rows, fraud rate, amount multiplier, scenario weights in SCENARIOS order)
BANK_PROFILES = {
    "Bank A": (14000, 0.030, 1.0, [0.22, 0.12, 0.08, 0.15, 0.12, 0.21, 0.10]),
    "Bank B": (12000, 0.045, 0.8, [0.35, 0.08, 0.08, 0.08, 0.08, 0.23, 0.10]),
    "Bank C": (10000, 0.025, 1.4, [0.08, 0.25, 0.15, 0.08, 0.15, 0.19, 0.10]),
    "Bank D": (9000, 0.060, 1.1, [0.10, 0.08, 0.32, 0.10, 0.08, 0.22, 0.10]),
    "Bank E": (7000, 0.020, 0.6, [0.15, 0.08, 0.05, 0.32, 0.12, 0.18, 0.10]),
}
COLUMNS = [
    "transaction_id", "timestamp", "bank", "sender_id", "receiver_id", "merchant_category", "amount_inr",
    "amount_to_average_ratio", "transaction_hour", "account_age_days", "transactions_last_hour",
    "minutes_since_last_transaction", "sender_txn_24h", "same_receiver_24h", "failed_login_attempts_24h",
    "upi_pin_failures_24h", "is_new_device", "is_new_beneficiary", "is_collect_request", "is_weekend",
    "scenario", "is_fraud",
]
CAT_SCALE = {"p2p": 1.0, "merchant": 0.8, "investment": 8.0}


def _legit(rng, n, mult):
    cat = rng.choice(CATEGORIES, n, p=[0.50, 0.38, 0.12])
    avg = rng.lognormal(np.log(1500 * mult), 0.7, n) * np.array([CAT_SCALE[c] for c in cat])
    ratio = rng.lognormal(0.0, 0.55, n).clip(0.05, 12)
    hour = np.clip(rng.normal(15, 5, n), 0, 23.99).astype(int)
    night = rng.random(n) < 0.08
    hour[night] = rng.integers(0, 6, night.sum())
    amount = avg * ratio
    big = rng.random(n) < 0.012                       # genuine big payments: rent, gold, fund purchases
    amount[big] = rng.uniform(70_000, 190_000, big.sum())
    ratio[big] = amount[big] / avg[big]
    new_p = np.where(cat == "p2p", 0.20, 0.10)
    d = {
        "merchant_category": cat, "amount_inr": amount.clip(10, MAX_AMOUNT).round(2),
        "amount_to_average_ratio": ratio.clip(0.05, 50).round(3), "transaction_hour": hour,
        "account_age_days": rng.integers(30, 3500, n),
        "failed_login_attempts_24h": rng.poisson(0.12, n), "upi_pin_failures_24h": rng.poisson(0.08, n),
        "is_new_device": (rng.random(n) < 0.04).astype(int),
        "is_new_beneficiary": (rng.random(n) < new_p).astype(int),
        "is_collect_request": (rng.random(n) < np.where(cat == "p2p", 0.02, 0.06)).astype(int),
        "scenario": "legit", "is_fraud": 0,
    }
    d = pd.DataFrame(d)
    hard = rng.random(n) < 0.03                       # legit but suspicious-looking
    d.loc[hard, ["is_new_device", "is_new_beneficiary"]] = 1
    d.loc[hard, "amount_to_average_ratio"] = rng.uniform(2, 6, hard.sum()).round(3)
    return d


def _fraud(rng, n, mult, weights):
    scen = rng.choice(SCENARIOS, n, p=np.array(weights) / np.sum(weights))
    f = _legit(rng, n, mult)
    f["scenario"], f["is_fraud"], f["is_new_beneficiary"] = scen, 1, 1
    u = lambda lo, hi, k: rng.uniform(lo, hi, k)
    for s in SCENARIOS:
        m = scen == s
        k = int(m.sum())
        if not k:
            continue
        if s == "collect_scam":
            f.loc[m, "is_collect_request"] = 1; f.loc[m, "merchant_category"] = "p2p"
            f.loc[m, "amount_to_average_ratio"] = u(1.5, 6, k); f.loc[m, "upi_pin_failures_24h"] = rng.poisson(0.8, k)
        elif s == "sim_swap":
            f.loc[m, "is_new_device"] = 1; f.loc[m, "failed_login_attempts_24h"] = rng.integers(1, 7, k)
            f.loc[m, "amount_to_average_ratio"] = u(2, 8, k); f.loc[m, "transaction_hour"] = rng.integers(0, 6, k)
        elif s == "mule_account":
            f.loc[m, "amount_to_average_ratio"] = u(2.0, 8, k)
        elif s == "qr_phishing":
            f.loc[m, "merchant_category"] = rng.choice(["merchant", "investment"], k)
            f.loc[m, "amount_to_average_ratio"] = u(1.2, 4.5, k); f.loc[m, "upi_pin_failures_24h"] = rng.poisson(0.5, k)
        elif s == "account_takeover":
            f.loc[m, "failed_login_attempts_24h"] = rng.integers(3, 9, k)
            f.loc[m, "upi_pin_failures_24h"] = rng.integers(2, 6, k)
            f.loc[m, "is_new_device"] = (rng.random(k) < 0.6).astype(int); f.loc[m, "transaction_hour"] = rng.integers(0, 6, k)
            f.loc[m, "amount_to_average_ratio"] = u(1.5, 7, k)
        elif s == "repeat_receiver":
            f.loc[m, "amount_to_average_ratio"] = u(1.0, 4.0, k)
        else:
            f.loc[m, "amount_to_average_ratio"] = u(0.8, 2.2, k)
    avg = rng.lognormal(np.log(1500 * mult), 0.7, n) * np.array([CAT_SCALE[c] for c in f["merchant_category"]])
    amount = avg * f["amount_to_average_ratio"].to_numpy()
    hv = rng.random(n) < 0.12                           # some fraud is high value
    amount[hv] = rng.uniform(70_000, 195_000, hv.sum())
    f["amount_inr"] = amount.clip(10, MAX_AMOUNT).round(2)
    return f


def _assign_identity(rng, df, bank_code, n_users):
    """Sender / receiver ids and timestamps, including fraud bursts and genuine double payments."""
    n = len(df)
    senders = np.array([f"{bank_code}-U{i:05d}" for i in range(n_users)])
    fav = {s: rng.integers(0, 60000, 4) for s in senders}
    sid = rng.choice(senders, n, p=_zipf(rng, n_users))
    df["sender_id"] = sid
    df["receiver_id"] = [f"R{rng.integers(0, 60000):05d}" if new else f"R{rng.choice(fav[s]):05d}"
                         for s, new in zip(sid, df["is_new_beneficiary"])]
    day = rng.integers(0, 30, n)
    sec = rng.integers(0, 3600, n)
    df["timestamp"] = [START + pd.Timedelta(days=int(d), hours=int(h), seconds=int(s))
                       for d, h, s in zip(day, df["transaction_hour"], sec)]
    # fraud bursts: group repeat_receiver / mule rows into bursts that share sender (and receiver)
    for scen in ("repeat_receiver", "mule_account"):
        idx = df.index[df["scenario"] == scen].to_numpy().copy()
        rng.shuffle(idx)
        pos = 0
        while pos < len(idx):
            size = int(rng.integers(3, 8)) if scen == "repeat_receiver" else int(rng.integers(4, 10))
            grp = idx[pos:pos + size]; pos += size
            base = START + pd.Timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)), minutes=int(rng.integers(0, 60)))
            span = 150 if scen == "repeat_receiver" else 50
            offs = np.sort(rng.integers(0, span, len(grp)))
            df.loc[grp, "sender_id"] = f"{bank_code}-U{rng.integers(0, n_users):05d}"
            if scen == "repeat_receiver":
                rcv = f"R{rng.integers(0, 60000):05d}"
                df.loc[grp, "receiver_id"] = rcv
                base_amt = rng.uniform(8_000, 68_000)
                df.loc[grp, "amount_inr"] = (base_amt * rng.uniform(0.85, 1.15, len(grp))).round(2)
                df.loc[grp[1:], "is_new_beneficiary"] = 0
            df.loc[grp, "timestamp"] = [base + pd.Timedelta(minutes=int(o)) for o in offs]
    return df


def _zipf(rng, k):
    w = 1 / np.arange(1, k + 1) ** 0.35
    rng.shuffle(w)
    return w / w.sum()


def _double_payments(rng, legit):
    """Genuine repeat payments (splitting a bill, paying twice by mistake): hard negatives for the repeat rule."""
    pick = legit.sample(frac=0.015, random_state=int(rng.integers(1 << 30))).copy()
    pick["timestamp"] = pick["timestamp"] + pd.to_timedelta(rng.integers(5, 200, len(pick)), unit="m")
    pick["amount_inr"] = (pick["amount_inr"] * rng.uniform(0.3, 1.0, len(pick))).round(2)
    pick["is_new_beneficiary"] = 0
    return pick


def generate(seed: int = 42, scale: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for bank, (rows, rate, mult, weights) in BANK_PROFILES.items():
        rows = int(rows * scale)
        n_fraud = max(10, int(rows * rate))
        legit, fraud = _legit(rng, rows - n_fraud, mult), _fraud(rng, n_fraud, mult, weights)
        df = pd.concat([legit, fraud], ignore_index=True)
        df = _assign_identity(rng, df, bank[-1], max(50, rows // 6))
        dbl = _double_payments(rng, df[df.is_fraud == 0])
        df = pd.concat([df, dbl], ignore_index=True)
        df.insert(0, "bank", bank)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = compute(out)                                  # repeat / velocity features from real history
    out = out.sort_values("timestamp", kind="stable").reset_index(drop=True)
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out.insert(0, "transaction_id", [f"UPI{i:07d}" for i in range(len(out))])
    out["is_weekend"] = out["is_weekend"].astype(int)
    return out[COLUMNS]
