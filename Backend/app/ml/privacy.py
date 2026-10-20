"""Renyi-DP accountant for the Gaussian mechanism applied once per federated round.

Client-level (user-level) DP: all banks participate in every round (no subsampling), each update is
clipped to L2 norm C and the aggregate gets Gaussian noise with std z*C*max_weight, i.e. noise
multiplier z relative to the per-bank sensitivity. RDP of the Gaussian mechanism at order a is
a / (2 z^2) per round and composes additively over rounds (Mironov 2017). Conversion to (eps, delta)
uses the tighter bound of Balle et al. 2020 / Opacus:
    eps = rdp + log((a-1)/a) - (log(delta) + log(a)) / (a-1)
"""

import math

ORDERS = [1 + x / 10 for x in range(1, 100)] + list(range(12, 64)) + [128, 256, 512]


def epsilon(noise_multiplier: float, rounds: int, delta: float = 1e-5) -> float:
    """Smallest eps over RDP orders; inf when no noise is added."""
    if noise_multiplier <= 0 or rounds <= 0:
        return math.inf if rounds > 0 else 0.0
    best = math.inf
    for a in ORDERS:
        rdp = rounds * a / (2 * noise_multiplier ** 2)
        eps = rdp + math.log((a - 1) / a) - (math.log(delta) + math.log(a)) / (a - 1)
        best = min(best, eps)
    return max(best, 0.0)


def noise_for_target(target_eps: float, rounds: int, delta: float = 1e-5) -> float:
    """Smallest noise multiplier achieving target_eps over `rounds` (bisection)."""
    lo, hi = 0.05, 500.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if epsilon(mid, rounds, delta) > target_eps:
            lo = mid
        else:
            hi = mid
    return round(hi, 3)
