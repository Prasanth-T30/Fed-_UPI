"""Federated training: FedAvg, FedProx and DP-FedAvg (clipping + Gaussian noise).

Only model parameters and sample counts cross the client/server boundary; raw transactions
never leave a bank's `Client`. The server's per-round validation is an evaluation harness
(pooled validation split) used for plots and model selection in this research prototype.

References
- McMahan et al., "Communication-Efficient Learning of Deep Networks from Decentralized Data", AISTATS 2017 (FedAvg)
- Li et al., "Federated Optimization in Heterogeneous Networks", MLSys 2020 (FedProx)
- McMahan et al., "Learning Differentially Private Recurrent Language Models", ICLR 2018 (DP-FedAvg)
"""

from dataclasses import dataclass, asdict
from typing import Callable, Optional

import numpy as np
import torch
from torch import nn

from app.ml import secagg
from app.ml.metrics import best_threshold, evaluate
from app.ml.privacy import epsilon
from app.ml.networks import AutoEncoder, FraudMLP, LogisticFraudClassifier


@dataclass
class FedConfig:
    kind: str = "clf"            # "clf" | "paper_mlp" | "logistic" | "ae"
    algorithm: str = "fedavg"    # "fedavg" | "fedprox"
    rounds: int = 15
    local_epochs: int = 2
    lr: float = 0.01
    batch_size: int = 256
    mu: float = 0.01             # FedProx proximal strength
    dp_clip: float = 0.0         # >0 enables update clipping (L2)
    dp_noise: float = 0.0        # Gaussian noise multiplier z (std = z * clip)
    seed: int = 42
    secure_agg: bool = False     # pairwise-masked aggregation (server sees only the sum)
    dp_delta: float = 1e-5       # delta for the reported (epsilon, delta)

    def dict(self):
        return asdict(self)


def make_model(kind: str, n_in: int):
    if kind == "ae":
        return AutoEncoder(n_in)
    if kind == "logistic":
        return LogisticFraudClassifier(n_in)
    if kind == "paper_mlp":
        return FraudMLP(n_in, hidden=(16,), dropout=0)
    return FraudMLP(n_in)


def _flat(state):
    return torch.cat([v.flatten().float() for v in state.values()])


def scores(model, kind: str, x: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        t = torch.from_numpy(x)
        out = model.error(t) if kind == "ae" else torch.sigmoid(model(t))
    return out.numpy()


class Client:
    """One bank. Holds its private data; exposes only `fit`."""

    def __init__(self, name: str, x: np.ndarray, y: np.ndarray):
        self.name, self.x, self.y = name, x, y

    @property
    def n(self) -> int:
        return len(self.y)

    def fit(self, global_state: dict, cfg: FedConfig, rnd: int) -> dict:
        model = make_model(cfg.kind, self.x.shape[1])
        model.load_state_dict(global_state)
        g = {k: v.clone() for k, v in global_state.items()}
        x, y = self.x, self.y
        if cfg.kind == "ae":                       # learn "normal" behaviour only
            x, y = x[y == 0], y[y == 0]
        if len(y) == 0:
            return {"state": global_state, "n": 0}
        opt = torch.optim.SGD(model.parameters(), lr=cfg.lr, momentum=0.9)
        pos = float(max(y.sum(), 1))
        neg = float(max(len(y) - y.sum(), 1))
        bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(min(neg / pos, 30.0) ** 0.7))
        gen = torch.Generator().manual_seed(cfg.seed * 1000 + rnd)
        xt, yt = torch.from_numpy(x), torch.from_numpy(y.astype(np.float32))
        model.train()
        for _ in range(cfg.local_epochs):
            perm = torch.randperm(len(yt), generator=gen)
            for i in range(0, len(yt), cfg.batch_size):
                idx = perm[i:i + cfg.batch_size]
                opt.zero_grad()
                if cfg.kind != "ae":
                    loss = bce(model(xt[idx]), yt[idx])
                else:
                    loss = model.error(xt[idx]).mean()
                if cfg.algorithm == "fedprox" and cfg.mu > 0:
                    prox = sum(((p - g[k]) ** 2).sum() for k, p in model.named_parameters())
                    loss = loss + 0.5 * cfg.mu * prox
                loss.backward()
                opt.step()
        return {"state": {k: v.detach().clone() for k, v in model.state_dict().items()}, "n": len(y)}


def _secure_average(global_state, deltas, weights, cfg, rng, rnd, stats):
    """Weighted average computed through pairwise-masked uploads. With DP, each bank adds its share
    of the Gaussian noise locally, so the server never sees an un-noised individual update."""
    keys = list(global_state)
    shapes = [tuple(global_state[k].shape) for k in keys]
    m = len(deltas)
    noise_std = cfg.dp_noise * cfg.dp_clip * max(weights) if cfg.dp_clip > 0 else 0.0
    vecs = []
    for w, d in zip(weights, deltas):
        v = np.concatenate([(w * d[k]).numpy().ravel().astype(np.float64) for k in keys])
        if noise_std > 0:
            v = v + rng.normal(0, noise_std / np.sqrt(m), v.shape)
        vecs.append(v)
    uploads = [secagg.client_mask(v, i, m, cfg.seed * 7919 + rnd) for i, v in enumerate(vecs)]
    total = secagg.server_sum(uploads)
    stats["secagg_max_error"] = max(stats.get("secagg_max_error", 0.0), float(np.abs(total - np.sum(vecs, axis=0)).max()))
    stats["masked_upload_looks_random"] = bool(abs(np.corrcoef(uploads[0].astype(np.float64), vecs[0])[0, 1]) < 0.05)
    out, pos = {}, 0
    for k, shp in zip(keys, shapes):
        size = int(np.prod(shp)) if shp else 1
        out[k] = torch.from_numpy(total[pos:pos + size].reshape(shp).astype(np.float32))
        pos += size
    return out


def aggregate(global_state: dict, updates: list, cfg: FedConfig, rng: np.random.Generator,
              rnd: int = 0, stats: Optional[dict] = None) -> dict:
    """Weighted FedAvg on parameter deltas, with optional DP clipping/noise and secure aggregation."""
    total = float(sum(u["n"] for u in updates))
    weights = [u["n"] / total for u in updates]
    new = {}
    deltas = []
    for u in updates:
        d = {k: u["state"][k].float() - global_state[k].float() for k in global_state}
        if cfg.dp_clip > 0:
            norm = float(_flat(d).norm())
            scale = min(1.0, cfg.dp_clip / (norm + 1e-12))
            d = {k: v * scale for k, v in d.items()}
        deltas.append(d)
    if cfg.secure_agg:
        avg = _secure_average(global_state, deltas, weights, cfg, rng, rnd, stats if stats is not None else {})
        return {k: (global_state[k].float() + avg[k]).to(global_state[k].dtype) for k in global_state}
    for k in global_state:
        avg = sum(w * d[k] for w, d in zip(weights, deltas))
        if cfg.dp_clip > 0 and cfg.dp_noise > 0:
            std = cfg.dp_noise * cfg.dp_clip * max(weights)
            avg = avg + torch.from_numpy(rng.normal(0, std, size=tuple(avg.shape)).astype(np.float32))
        new[k] = (global_state[k].float() + avg).to(global_state[k].dtype)
    return new


def run_federation(
    clients: list,
    x_val: np.ndarray,
    y_val: np.ndarray,
    cfg: FedConfig,
    on_round: Optional[Callable[[dict], None]] = None,
):
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)
    n_in = clients[0].x.shape[1]
    model = make_model(cfg.kind, n_in)
    state = {k: v.clone() for k, v in model.state_dict().items()}
    n_params = sum(p.numel() for p in model.parameters())
    history = []
    stats: dict = {}
    for r in range(1, cfg.rounds + 1):
        updates = [c.fit(state, cfg, r) for c in clients]
        updates = [u for u in updates if u["n"] > 0]
        state = aggregate(state, updates, cfg, rng, r, stats)
        model.load_state_dict(state)
        s = scores(model, cfg.kind, x_val)
        thr = best_threshold(y_val, s)
        m = evaluate(y_val, s, thr)
        row = {"round": r, "f1": m["f1"], "pr_auc": m["pr_auc"], "roc_auc": m["roc_auc"],
               "precision": m["precision"], "recall": m["recall"],
               "upload_kb": round(len(updates) * n_params * 4 / 1024, 1)}
        if cfg.dp_clip > 0 and cfg.dp_noise > 0:
            row["epsilon"] = round(epsilon(cfg.dp_noise, r, cfg.dp_delta), 2)
        history.append(row)
        if on_round:
            on_round(row)
    model.load_state_dict(state)
    model.fed_stats = stats
    return model, history
