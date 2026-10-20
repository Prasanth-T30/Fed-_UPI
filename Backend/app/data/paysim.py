"""Loader for the real public PaySim dataset (Lopez-Rojas et al., EMSS 2016; Kaggle `ealaxi/paysim1`).

PaySim is a simulator calibrated on real mobile-money logs from an African operator - public, but NOT
Indian UPI data. Only PRE-transaction signals are used (post-transaction balances leak the label).

Mapping into the FedUPI schema (anything PaySim does not record gets a neutral constant, which
makes that feature uninformative rather than invented):

  amount                      -> amount_inr
  amount / mean(type amount)  -> amount_to_average_ratio       (population proxy, no per-user history)
  step % 24                   -> transaction_hour
  (step // 24) % 7 >= 5       -> is_weekend                    (day-of-week is arbitrary in PaySim)
  txns of nameOrig in step    -> transactions_last_hour
  TRANSFER / CASH_OUT         -> merchant_category p2p / merchant
  amount / oldbalanceOrg      -> balance_drain                  (extra feature, strongest PaySim signal)
  oldbalanceDest == 0         -> dest_empty                     (extra feature)
  account_age, logins, PIN failures, new device/beneficiary, collect flag -> neutral constants

Banks: PaySim has none, so rows are hash-partitioned by nameOrig into five simulated banks (IID).
Legitimate rows are down-sampled (all fraud kept) so the demo stays fast; this raises prevalence.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import DATA_DIR

RAW_ZIP = DATA_DIR / "raw" / "paysim.zip"
RAW_CSV = DATA_DIR / "raw" / "paysim.csv"
SAMPLE_PATH = DATA_DIR / "paysim_transactions.csv"
BANKS = ["Bank A", "Bank B", "Bank C", "Bank D", "Bank E"]
USECOLS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "oldbalanceDest", "isFraud"]


def _read_raw() -> pd.DataFrame:
    if RAW_CSV.exists():
        return pd.read_csv(RAW_CSV, usecols=USECOLS)
    if RAW_ZIP.exists():
        with zipfile.ZipFile(RAW_ZIP) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(member) as f:
                return pd.read_csv(f, usecols=USECOLS)
    raise FileNotFoundError(
        "PaySim not found. Download https://www.kaggle.com/datasets/ealaxi/paysim1 and place the CSV at "
        f"{RAW_CSV} (or the zip at {RAW_ZIP})."
    )


def load_paysim(max_rows: int = 150_000, seed: int = 42) -> pd.DataFrame:
    raw = _read_raw()
    raw = raw[raw["type"].isin(["TRANSFER", "CASH_OUT"]) & (raw["amount"] > 0)].copy()
    raw = raw.drop_duplicates(subset=["step", "type", "amount", "nameOrig", "oldbalanceOrg", "oldbalanceDest"])
    fraud = raw[raw.isFraud == 1]
    legit = raw[raw.isFraud == 0]
    n_legit = max(0, max_rows - len(fraud))
    legit = legit.sample(min(n_legit, len(legit)), random_state=seed)
    df = pd.concat([fraud, legit]).sample(frac=1, random_state=seed).reset_index(drop=True)

    type_mean = raw.groupby("type")["amount"].mean()
    ratio = (df["amount"] / df["type"].map(type_mean)).clip(0, 50)
    orig_hash = pd.util.hash_array(df["nameOrig"].to_numpy().astype(object)) % len(BANKS)
    same_step = df.groupby(["nameOrig", "step"])["amount"].transform("size") - 1
    out = pd.DataFrame({
        "transaction_id": [f"PS{i:07d}" for i in range(len(df))],
        "bank": np.array(BANKS)[orig_hash.astype(int)],
        "merchant_category": np.where(df["type"] == "TRANSFER", "p2p", "merchant"),
        "amount_inr": df["amount"].round(2),
        "amount_to_average_ratio": ratio.round(3),
        "transaction_hour": (df["step"] % 24).astype(int),
        "account_age_days": 365,
        "transactions_last_hour": same_step.astype(int),
        "minutes_since_last_transaction": 1440.0,
        "failed_login_attempts_24h": 0,
        "upi_pin_failures_24h": 0,
        "is_new_device": 0,
        "is_new_beneficiary": 0,
        "is_collect_request": 0,
        "is_weekend": (((df["step"] // 24) % 7) >= 5).astype(int),
        "balance_drain": np.where(df["oldbalanceOrg"] > 0, (df["amount"] / df["oldbalanceOrg"]).clip(0, 1), 0.0).round(4),
        "dest_empty": ((df["oldbalanceDest"] == 0) & (df["amount"] > 0)).astype(int),
        "scenario": np.where(df["isFraud"] == 1, "paysim_fraud", "legit"),
        "is_fraud": df["isFraud"].astype(int),
    })
    return out


def prepare(max_rows: int = 150_000, seed: int = 42) -> Path:
    df = load_paysim(max_rows, seed)
    df.to_csv(SAMPLE_PATH, index=False)
    return SAMPLE_PATH
