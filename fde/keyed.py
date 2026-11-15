"""Keyed randomness: every draw is a hash of (seed, purpose, ids), so every design meets the same luck."""

from __future__ import annotations

import hashlib
import math


class Keyed:
    def __init__(self, seed: str) -> None:
        self.seed = seed

    def u(self, purpose: str, *ids: object) -> float:
        """A uniform draw in [0, 1)."""
        key = "|".join([self.seed, purpose, *map(str, ids)]).encode()
        h = hashlib.sha256(key).digest()
        return int.from_bytes(h[:7], "big") / float(1 << 56)

    def chance(self, p: float, purpose: str, *ids: object) -> bool:
        return self.u(purpose, *ids) < p

    def pick(self, n: int, purpose: str, *ids: object) -> int:
        return min(n - 1, int(self.u(purpose, *ids) * n))

    def between(self, lo: int, hi: int, purpose: str, *ids: object) -> int:
        return lo + min(hi - lo, int(self.u(purpose, *ids) * (hi - lo + 1)))

    def lognormal(self, sigma: float, purpose: str, *ids: object) -> float:
        """A multiplicative overrun factor with median 1 (Box-Muller from two keyed draws)."""
        u1 = max(1e-12, self.u(purpose + ":1", *ids))
        u2 = self.u(purpose + ":2", *ids)
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return math.exp(sigma * z)
