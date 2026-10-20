"""Explainability: gradient x input attribution on the federated MLP (per-transaction)."""

import numpy as np
import torch


def attributions(model, x: np.ndarray) -> np.ndarray:
    """Signed contribution of every input feature to the fraud logit."""
    model.eval()
    t = torch.from_numpy(np.atleast_2d(x).astype(np.float32)).requires_grad_(True)
    model(t).sum().backward()
    return (t.grad * t).detach().numpy()
