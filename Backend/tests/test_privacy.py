import math

import numpy as np
import torch

from app.ml import secagg
from app.ml.federated import FedConfig, aggregate
from app.ml.privacy import epsilon, noise_for_target


def test_secagg_sum_exact_and_individual_uploads_masked():
    rng = np.random.default_rng(0)
    vecs = [rng.normal(0, 0.1, 500) for _ in range(5)]
    ups = [secagg.client_mask(v, i, 5, 99) for i, v in enumerate(vecs)]
    assert np.abs(secagg.server_sum(ups) - np.sum(vecs, axis=0)).max() < 1e-5
    assert abs(np.corrcoef(ups[0].astype(float), vecs[0])[0, 1]) < 0.2   # looks random
    assert not np.allclose(secagg.server_sum(ups[:4]), np.sum(vecs[:4], axis=0), atol=1e-3)  # missing bank breaks cancel


def test_secure_aggregate_matches_plain():
    g = {"w": torch.zeros(6), "b": torch.zeros(2, 3)}
    ups = [{"state": {"w": torch.randn(6) * .1, "b": torch.randn(2, 3) * .1}, "n": n} for n in (10, 30, 60)]
    plain = aggregate(g, ups, FedConfig(), np.random.default_rng(0))
    sec = aggregate(g, ups, FedConfig(secure_agg=True), np.random.default_rng(0), 1, {})
    for k in g:
        assert torch.allclose(plain[k], sec[k], atol=1e-4)


def test_epsilon_properties():
    assert math.isinf(epsilon(0, 10))
    assert epsilon(2.0, 10) < epsilon(1.0, 10) < epsilon(0.5, 10)       # more noise -> smaller eps
    assert epsilon(1.0, 5) < epsilon(1.0, 20)                             # more rounds -> larger eps
    assert epsilon(1.0, 10, 1e-3) < epsilon(1.0, 10, 1e-8)
    # Gaussian mechanism, 1 step, z=1, delta=1e-5: known eps is roughly 4-5.
    assert 3.5 < epsilon(1.0, 1) < 5.5


def test_noise_for_target_roundtrip():
    z = noise_for_target(8.0, 15)
    assert abs(epsilon(z, 15) - 8.0) < 0.05
