"""Price estimation: median with IQR outlier rejection and an explicit sample-size floor."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median, quantiles


@dataclass(frozen=True)
class Estimate:
    median_minor: int | None
    n: int
    n_used: int
    status: str  # "ok" | "insufficient_data"


def estimate(prices_minor: list[int], min_samples: int = 3) -> Estimate:
    n = len(prices_minor)
    if n < min_samples:
        return Estimate(None, n, 0, "insufficient_data")
    q1, _, q3 = quantiles(prices_minor, n=4, method="inclusive")
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    kept = [p for p in prices_minor if lo <= p <= hi]
    if len(kept) < min_samples:
        return Estimate(None, n, len(kept), "insufficient_data")
    return Estimate(int(median(kept)), n, len(kept), "ok")
