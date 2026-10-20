"""Business risk policy layered on the federated model.

Tiers (user-defined policy):
  HIGH      amount above Rs 99,999 (i.e. >= Rs 1,00,000) - the ONLY way to reach HIGH
  MODERATE  amount Rs 70,000 - 99,999, OR the model flags the transaction, OR repeated payments to the
            same receiver / a burst of payments by the same user inside the time window
  LOW       everything else

The model can therefore never mark a payment below Rs 1,00,000 as HIGH; fraud signals on smaller payments
become MODERATE (step-up authentication). Risk % is tier-consistent: LOW 0-39, MODERATE 40-79, HIGH 80-99,
with the model's fraud score deciding the position inside the band.
"""

import numpy as np

HIGH_MIN = 100_000          # > 99,999
MODERATE_MIN = 70_000       # 70,000 - 99,999
REPEAT_RECEIVER_MIN = 2     # 2 earlier payments to the same receiver in 24h  -> this is the 3rd
BURST_PER_HOUR_MIN = 4      # 4 earlier payments by the same user in 1h
LEVELS = ["LOW", "MODERATE", "HIGH"]
DECISIONS = {"LOW": "ALLOW", "MODERATE": "STEP_UP_AUTH", "HIGH": "BLOCK"}


def tiers(amount, same_receiver_24h, txn_last_hour, model_score, model_threshold):
    """Vectorised tier index (0 LOW, 1 MODERATE, 2 HIGH) and boolean masks of the triggers."""
    amount = np.asarray(amount, dtype=float)
    model_flag = np.asarray(model_score) >= model_threshold
    repeat = np.asarray(same_receiver_24h) >= REPEAT_RECEIVER_MIN
    burst = np.asarray(txn_last_hour) >= BURST_PER_HOUR_MIN
    mod_amt = (amount >= MODERATE_MIN) & (amount < HIGH_MIN)
    high_amt = amount >= HIGH_MIN
    level = np.zeros(len(amount), dtype=int)
    level[model_flag | repeat | burst | mod_amt] = 1
    level[high_amt] = 2
    return level, {"model": model_flag, "repeat": repeat, "burst": burst, "moderate_amount": mod_amt, "high_amount": high_amt}


def risk_percent(level, model_score, model_threshold):
    """Tier-consistent percentage (see module docstring)."""
    s = np.clip(np.asarray(model_score, dtype=float), 0, 1)
    low = np.clip(s / max(model_threshold, 1e-9), 0, 1) * 39.0
    return np.where(level == 2, 80 + 19 * s, np.where(level == 1, 40 + 39 * s, low)).round(1)
