"""Write ready-to-upload example datasets into ../samples (never seen during training: different seeds).

    python scripts/make_datasets.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.data.generator import generate  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "samples"
OUT.mkdir(exist_ok=True)

# 1) Mixed realistic traffic from all five banks (unseen seed), in three formats
mixed = generate(seed=777, scale=0.04)
mixed.to_csv(OUT / "upi_test_transactions.csv", index=False)
mixed.to_excel(OUT / "upi_test_transactions.xlsx", index=False)
mixed.to_json(OUT / "upi_test_transactions.json", orient="records", indent=1)

# 2) Larger training-style dataset (CSV) to inspect, or to retrain on
generate(seed=42).to_csv(OUT / "upi_training_dataset.csv", index=False)

# 3) Hand-written rules demo: every amount band, repeat payments, bursts, classic scams
base = dict(amount_to_average_ratio=1.0, account_age_days=900, transactions_last_hour=0, minutes_since_last_transaction=600,
            failed_login_attempts_24h=0, upi_pin_failures_24h=0, is_new_device=0, is_new_beneficiary=0,
            is_collect_request=0, is_weekend=0, transaction_hour=14, bank="Bank A", scenario="demo", is_fraud=0)
rows = []


def add(sender, receiver, ts, amount, cat="p2p", **kw):
    rows.append({**base, "sender_id": sender, "receiver_id": receiver, "timestamp": ts, "amount_inr": amount,
                 "merchant_category": cat, **kw})


# amount bands (each a different user, so only the amount differs)
for i, amt in enumerate([500, 25_000, 69_999, 70_000, 85_000, 99_999, 100_000, 150_000, 199_000]):
    add(f"A-BAND{i}", f"R-BAND{i}", f"2026-08-01 11:{i:02d}:00", amt, cat=["p2p", "merchant", "investment"][i % 3])
# same user paying the same receiver repeatedly within 2 hours (structuring / split payments)
for k, m in enumerate([0, 12, 25, 41, 58, 80]):
    add("A-REPEAT1", "R-SUSPECT", f"2026-08-02 09:{m % 60:02d}:00" if m < 60 else f"2026-08-02 10:{m - 60:02d}:00",
        24_500 + 300 * k, cat="p2p", is_new_beneficiary=int(k == 0), scenario="repeat_receiver", is_fraud=int(k >= 2))
# normal user paying a friend twice in a day (genuine, should stay low)
add("A-FRIEND", "R-FRIEND", "2026-08-02 13:00:00", 800); add("A-FRIEND", "R-FRIEND", "2026-08-02 19:30:00", 650)
# burst of payments to many different receivers within an hour (mule behaviour)
for k in range(7):
    add("B-BURST", f"R-MULE{k}", f"2026-08-03 02:{k * 6:02d}:00", 9_000 + 400 * k, is_new_beneficiary=1,
        transaction_hour=2, scenario="mule_account", is_fraud=int(k >= 3))
# classic scams (small amounts: can reach MODERATE but never HIGH under the policy)
add("C-COLLECT", "R-SCAM1", "2026-08-04 15:10:00", 9_500, is_collect_request=1, is_new_beneficiary=1,
    amount_to_average_ratio=4.2, upi_pin_failures_24h=1, scenario="collect_scam", is_fraud=1)
add("C-SIM", "R-SCAM2", "2026-08-04 03:05:00", 48_000, is_new_device=1, is_new_beneficiary=1, failed_login_attempts_24h=4,
    amount_to_average_ratio=6.0, transaction_hour=3, scenario="sim_swap", is_fraud=1)
# ordinary traffic
for i in range(12):
    add(f"D-USER{i}", f"R-SHOP{i % 4}", f"2026-08-05 1{i % 10}:{(i * 7) % 60:02d}:00", 300 + 150 * i, cat="merchant")
demo = pd.DataFrame(rows)
demo.insert(0, "transaction_id", [f"DEMO{i:04d}" for i in range(len(demo))])
demo.to_csv(OUT / "policy_rules_demo.csv", index=False)
demo.to_excel(OUT / "policy_rules_demo.xlsx", index=False)
print({p.name: p.stat().st_size // 1024 for p in OUT.iterdir() if p.suffix in (".csv", ".xlsx", ".json")})
