"""Feature engineering with FIXED scaling (no statistics are shared between banks)."""

import numpy as np
import pandas as pd

from app.data.generator import CATEGORIES

NUMERIC = [
    "log_amount", "amount_ratio", "hour_sin", "hour_cos", "account_age", "txn_velocity",
    "recency", "failed_logins", "pin_failures", "new_device", "new_beneficiary",
    "collect_request", "weekend", "balance_drain", "dest_empty",
    "amount_moderate", "amount_high", "sender_24h", "same_receiver",
]
# Optional input columns (neutral 0 when absent): populated by the PaySim loader / API.
OPTIONAL = ["balance_drain", "dest_empty", "sender_txn_24h", "same_receiver_24h"]
FEATURES = NUMERIC + [f"cat_{c}" for c in CATEGORIES]

# The conference experiment deliberately uses a compact, fixed 13-value vector.
# Keep it separate from the richer production feature set so the paper preset is
# reproducible without removing the practical extensions used by the app.
PAPER_FEATURES = [
    "log_amount", "amount_ratio", "hour_sin", "hour_cos", "account_age",
    "txn_velocity", "failed_logins", "pin_failures", "new_device",
    "new_beneficiary", "collect_request", "weekend", "merchant_risk",
]

# Human readable label per feature, used for explanations.
LABELS = {
    "log_amount": "High transaction amount",
    "amount_ratio": "Amount far above the user's average",
    "hour_sin": "Unusual hour of day", "hour_cos": "Unusual hour of day",
    "account_age": "Young account", "txn_velocity": "Burst of transactions in the last hour",
    "recency": "Very short gap since previous transaction",
    "failed_logins": "Repeated failed logins", "pin_failures": "UPI PIN failures",
    "new_device": "Payment from a new device", "new_beneficiary": "First payment to this beneficiary",
    "collect_request": "Collect (pull) request", "weekend": "Weekend activity",
    "balance_drain": "Drains most of the sender's balance", "dest_empty": "Beneficiary account was empty",
    "amount_moderate": "Amount in the Rs 70,000-99,999 band", "amount_high": "Amount above Rs 99,999",
    "sender_24h": "Many payments by this user in 24h", "same_receiver": "Repeated payments to the same receiver",
}

REQUIRED = [
    "amount_inr", "amount_to_average_ratio", "transaction_hour", "account_age_days",
    "transactions_last_hour", "minutes_since_last_transaction", "failed_login_attempts_24h",
    "upi_pin_failures_24h", "is_new_device", "is_new_beneficiary", "is_collect_request",
    "is_weekend", "merchant_category",
]


def _opt(df, col):
    return df[col].astype(float).to_numpy() if col in df else np.zeros(len(df))


def transform(df: pd.DataFrame) -> np.ndarray:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    amt = df["amount_inr"].astype(float).to_numpy()
    h = df["transaction_hour"].astype(float).to_numpy() * 2 * np.pi / 24
    cols = {
        "log_amount": np.log1p(df["amount_inr"].astype(float).clip(lower=0)) / 12,
        "amount_ratio": np.log1p(df["amount_to_average_ratio"].astype(float).clip(0, 50)) / 3,
        "hour_sin": np.sin(h), "hour_cos": np.cos(h),
        "account_age": np.log1p(df["account_age_days"].astype(float).clip(lower=0)) / 9,
        "txn_velocity": (df["transactions_last_hour"].astype(float) / 10).clip(0, 1),
        "recency": 1 - np.log1p(df["minutes_since_last_transaction"].astype(float).clip(lower=0)) / 9,
        "failed_logins": (df["failed_login_attempts_24h"].astype(float) / 8).clip(0, 1),
        "pin_failures": (df["upi_pin_failures_24h"].astype(float) / 6).clip(0, 1),
        "new_device": df["is_new_device"].astype(float),
        "new_beneficiary": df["is_new_beneficiary"].astype(float),
        "collect_request": df["is_collect_request"].astype(float),
        "weekend": df["is_weekend"].astype(float),
        "balance_drain": df["balance_drain"].astype(float).clip(0, 1) if "balance_drain" in df else np.zeros(len(df)),
        "dest_empty": df["dest_empty"].astype(float).clip(0, 1) if "dest_empty" in df else np.zeros(len(df)),
        "amount_moderate": ((amt >= 70_000) & (amt < 100_000)).astype(float),
        "amount_high": (amt >= 100_000).astype(float),
        "sender_24h": (_opt(df, "sender_txn_24h") / 10).clip(0, 1),
        "same_receiver": (_opt(df, "same_receiver_24h") / 6).clip(0, 1),
    }
    for c in CATEGORIES:
        cols[f"cat_{c}"] = (df["merchant_category"].astype(str).str.lower() == c).astype(float)
    return np.column_stack([np.asarray(cols[f], dtype=np.float32) for f in FEATURES]).astype(np.float32)


def transform_paper(df: pd.DataFrame) -> np.ndarray:
    """Return the paper's 13-input feature vector with fixed local-safe scaling."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    amount = df["amount_inr"].astype(float).clip(lower=0)
    hour = df["transaction_hour"].astype(float) * 2 * np.pi / 24
    category = df["merchant_category"].astype(str).str.lower()
    merchant_risk = category.map({"p2p": 0.25, "merchant": 0.5, "investment": 1.0}).fillna(0.25)
    cols = {
        "log_amount": np.log1p(amount) / 12,
        "amount_ratio": np.log1p(df["amount_to_average_ratio"].astype(float).clip(0, 50)) / 3,
        "hour_sin": np.sin(hour),
        "hour_cos": np.cos(hour),
        "account_age": np.log1p(df["account_age_days"].astype(float).clip(lower=0)) / 9,
        "txn_velocity": (df["transactions_last_hour"].astype(float) / 10).clip(0, 1),
        "failed_logins": (df["failed_login_attempts_24h"].astype(float) / 8).clip(0, 1),
        "pin_failures": (df["upi_pin_failures_24h"].astype(float) / 6).clip(0, 1),
        "new_device": df["is_new_device"].astype(float),
        "new_beneficiary": df["is_new_beneficiary"].astype(float),
        "collect_request": df["is_collect_request"].astype(float),
        "weekend": df["is_weekend"].astype(float),
        "merchant_risk": merchant_risk.astype(float),
    }
    return np.column_stack([np.asarray(cols[name], dtype=np.float32) for name in PAPER_FEATURES]).astype(np.float32)
