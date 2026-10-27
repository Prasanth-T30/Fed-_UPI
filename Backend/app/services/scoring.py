"""Loads the trained federated model and scores transactions with explanations."""

import json
import threading

import numpy as np
import pandas as pd
import torch

from app.config import META_PATH, MODEL_PATH, MODEL_VERSION
from app.data.features import FEATURES, LABELS, PAPER_FEATURES, transform, transform_paper
from app.ml.explain import attributions
from app.ml import policy
from app.ml.federated import make_model, scores


def _describe(feature: str, row: pd.Series) -> str:
    amt = f"Rs {row['amount_inr']:,.0f}"
    return {
        "log_amount": f"Large amount ({amt})",
        "amount_ratio": f"Amount is {row['amount_to_average_ratio']:.1f}x the user's average",
        "hour_sin": f"Unusual hour ({int(row['transaction_hour']):02d}:00)",
        "hour_cos": f"Unusual hour ({int(row['transaction_hour']):02d}:00)",
        "account_age": f"Young account ({int(row['account_age_days'])} days old)",
        "txn_velocity": f"{int(row['transactions_last_hour'])} transactions in the last hour",
        "recency": f"Only {row['minutes_since_last_transaction']:.1f} min since previous transaction",
        "failed_logins": f"{int(row['failed_login_attempts_24h'])} failed logins in 24h",
        "pin_failures": f"{int(row['upi_pin_failures_24h'])} UPI PIN failures in 24h",
        "new_device": "Payment initiated from a new device",
        "new_beneficiary": "First payment to this beneficiary",
        "collect_request": "Collect (pull) request instead of a push payment",
        "weekend": "Weekend activity",
        "balance_drain": f"Moves {row.get('balance_drain', 0) * 100:.0f}% of the sender's balance",
        "dest_empty": "Beneficiary account was empty before this payment",
    }.get(feature, LABELS.get(feature, feature))


class ModelService:
    def __init__(self):
        self.lock = threading.Lock()
        self.ready = False
        self.meta: dict = {}
        self.load()

    def load(self) -> bool:
        if not (MODEL_PATH.exists() and META_PATH.exists()):
            self.ready = False
            return False
        with self.lock:
            self.meta = json.loads(META_PATH.read_text())
            state = torch.load(MODEL_PATH, map_location="cpu")
            n = self.meta["n_features"]
            model_kind = self.meta.get("model_kind", "clf")
            self.mlp, self.ae = make_model(model_kind, n), make_model("ae", n)
            self.mlp.load_state_dict(state["mlp"])
            self.ae.load_state_dict(state["ae"])
            self.mlp.eval()
            self.ae.eval()
            self.ready = True
        return True

    def score(self, df: pd.DataFrame, explain: bool = True) -> list:
        if not self.ready:
            raise RuntimeError("Model not trained yet. Run backend.ps1 (it trains on first start) or use the Federated Lab.")
        df = df.reset_index(drop=True)
        paper_profile = self.meta.get("feature_profile") == "paper"
        x = transform_paper(df) if paper_profile else transform(df)
        feature_names = PAPER_FEATURES if paper_profile else FEATURES
        w, scale = self.meta["ensemble_weight"], self.meta["ae_scale"]
        p = scores(self.mlp, "clf", x)
        a = np.clip(scores(self.ae, "ae", x) / scale, 0, 1)
        s = (1 - w) * p + w * a
        thr = self.meta["threshold"]
        amount = df["amount_inr"].astype(float).to_numpy()
        recv = df["same_receiver_24h"].astype(float).to_numpy() if "same_receiver_24h" in df else np.zeros(len(df))
        vel = df["transactions_last_hour"].astype(float).to_numpy()
        level, trig = policy.tiers(amount, recv, vel, s, thr)
        risk = policy.risk_percent(level, s, thr)
        attr = attributions(self.mlp, x) if explain else None
        out = []
        for i, (_, row) in enumerate(df.iterrows()):
            name = policy.LEVELS[level[i]]
            rules, reasons = [], []
            if trig["high_amount"][i]:
                rules.append("high_amount")
                reasons.append({"reason": f"Amount Rs {amount[i]:,.0f} is above Rs 99,999 (high-value rule)", "weight": None})
            elif trig["moderate_amount"][i]:
                rules.append("moderate_amount")
                reasons.append({"reason": f"Amount Rs {amount[i]:,.0f} is in the Rs 70,000-99,999 band (moderate-value rule)", "weight": None})
            if trig["repeat"][i]:
                rules.append("repeat_receiver")
                reasons.append({"reason": f"Payment #{int(recv[i]) + 1} to the same receiver within 24 hours", "weight": None})
            if trig["burst"][i]:
                rules.append("burst")
                reasons.append({"reason": f"{int(vel[i])} earlier payments by this user in the last hour", "weight": None})
            if trig["model"][i]:
                rules.append("model")
            if explain and level[i] > 0:
                merged = {}
                for f, v in zip(feature_names, attr[i]):
                    if f.startswith("cat_") or v <= 0 or f in ("amount_moderate", "amount_high", "same_receiver", "sender_24h"):
                        continue
                    key = "hour" if f.startswith("hour_") else f
                    merged[key] = (merged.get(key, (0.0, f))[0] + float(v), f)
                top = sorted(merged.values(), key=lambda t: -t[0])[:4]
                tot = sum(v for v, _ in top) or 1
                reasons += [{"reason": _describe(f, row), "weight": round(v / tot, 3)} for v, f in top if v / tot > 0.05]
            out.append({
                "risk_score": float(risk[i]), "model_score": round(float(s[i]) * 100, 1),
                "classifier_score": round(float(p[i]) * 100, 1), "anomaly_score": round(float(a[i]) * 100, 1),
                "risk_level": name, "decision": policy.DECISIONS[name], "reasons": reasons, "rules": rules,
                "model_version": MODEL_VERSION,
            })
        return out


service = ModelService()
