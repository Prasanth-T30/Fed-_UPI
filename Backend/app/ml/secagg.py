"""Secure aggregation by pairwise additive masking (Bonawitz et al., CCS 2017, simplified).

Each pair of banks (i<j) agrees on a secret seed; bank i adds the PRG mask, bank j subtracts it.
Updates are fixed-point encoded in the ring Z_(2^40), so the server only ever sees values that look
uniformly random individually, yet the masks cancel exactly in the sum.

Simplifications (documented, not hidden): the pairwise seeds are derived from a simulated key
agreement (no real Diffie-Hellman), there is no dropout recovery (all banks must report), and the
server is assumed honest-but-curious rather than malicious.
"""

import hashlib

import numpy as np

MOD = 1 << 40
SCALE = 1 << 20          # fixed-point resolution ~1e-6
HALF = MOD // 2


def _seed(round_seed: int, i: int, j: int) -> int:
    h = hashlib.sha256(f"fedupi-secagg|{round_seed}|{i}|{j}".encode()).digest()
    return int.from_bytes(h[:8], "little")


def _mask(round_seed: int, i: int, j: int, dim: int) -> np.ndarray:
    return np.random.default_rng(_seed(round_seed, i, j)).integers(0, MOD, dim, dtype=np.int64)


def encode(v: np.ndarray) -> np.ndarray:
    if np.abs(v).max(initial=0) * SCALE >= HALF / 64:
        raise ValueError("Update too large for fixed-point range; clip updates first.")
    return np.mod(np.rint(v * SCALE).astype(np.int64), MOD)


def client_mask(vec: np.ndarray, idx: int, n: int, round_seed: int) -> np.ndarray:
    """What bank `idx` uploads: its encoded update plus pairwise masks."""
    out = encode(vec)
    for j in range(n):
        if j == idx:
            continue
        m = _mask(round_seed, min(idx, j), max(idx, j), len(vec))
        out = out + m if idx < j else out - m
    return np.mod(out, MOD)


def server_sum(masked: list) -> np.ndarray:
    """Server-side: sum masked uploads mod 2^40 and decode. Reveals only the aggregate."""
    total = np.mod(np.sum(np.stack(masked), axis=0), MOD)
    signed = np.where(total >= HALF, total - MOD, total)
    return signed.astype(np.float64) / SCALE
