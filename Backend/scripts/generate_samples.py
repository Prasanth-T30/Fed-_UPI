"""Generate deterministic sample datasets required by integration and model-quality tests."""

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from app.data.behavior import compute  # noqa: E402
from app.data.generator import COLUMNS, generate  # noqa: E402


def row(transaction_id, timestamp, sender, receiver, amount, *, fraud=0, scenario="legit"):
    return {
        "transaction_id": transaction_id,
        "timestamp": timestamp,
        "bank": "Bank A",
        "sender_id": sender,
        "receiver_id": receiver,
        "merchant_category": "p2p",
        "amount_inr": amount,
        "amount_to_average_ratio": 0.8,
        "transaction_hour": int(timestamp[11:13]),
        "account_age_days": 1200,
        "transactions_last_hour": 0,
        "minutes_since_last_transaction": 300,
        "sender_txn_24h": 0,
        "same_receiver_24h": 0,
        "failed_login_attempts_24h": 0,
        "upi_pin_failures_24h": 0,
        "is_new_device": 0,
        "is_new_beneficiary": 0,
        "is_collect_request": 0,
        "is_weekend": 0,
        "scenario": scenario,
        "is_fraud": fraud,
    }


def policy_demo():
    rows = []
    amounts = [500, 69_999, 70_000, 99_999, 100_000, 199_000]
    for index, amount in enumerate(amounts):
        rows.append(row(
            f"BAND-{index + 1}", f"2026-08-01 {8 + index:02d}:00:00",
            f"A-BAND-{index + 1}", f"R-BAND-{index + 1}", amount,
            fraud=int(amount >= 70_000), scenario="amount_band",
        ))

    for index in range(3):
        rows.append(row(
            f"REPEAT-{index + 1}", f"2026-08-02 10:{index * 10:02d}:00",
            "A-REPEAT1", "R-REPEAT1", 9_000 + index * 250,
            fraud=int(index == 2), scenario="repeat_receiver",
        ))

    for index in range(3):
        rows.append(row(
            f"FRIEND-{index + 1}", f"2026-08-03 {8 + index * 3:02d}:00:00",
            "A-FRIEND", f"R-FRIEND-{index + 1}", 400 + index * 50,
        ))

    for index in range(6):
        rows.append(row(
            f"BURST-{index + 1}", f"2026-08-04 11:{index * 8:02d}:00",
            "A-BURST1", f"R-BURST-{index + 1}", 2_000 + index * 100,
            fraud=int(index >= 4), scenario="mule_account",
        ))

    for index in range(3):
        rows.append(row(
            f"MODERATE-{index + 1}", f"2026-08-05 {10 + index:02d}:00:00",
            f"A-MODERATE-{index + 1}", f"R-MODERATE-{index + 1}", 75_000 + index * 2_000,
            fraud=1, scenario="amount_band",
        ))

    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = compute(frame).sort_values("timestamp", kind="stable")
    frame["timestamp"] = frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return frame[COLUMNS]


def main():
    output = ROOT / "samples"
    output.mkdir(parents=True, exist_ok=True)
    policy_demo().to_csv(output / "policy_rules_demo.csv", index=False)
    generate(seed=2026, scale=0.05).to_csv(output / "upi_test_transactions.csv", index=False)
    print(f"Generated integration fixtures in {output}")


if __name__ == "__main__":
    main()
