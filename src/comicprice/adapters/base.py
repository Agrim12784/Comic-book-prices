from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from ..models import PriceType


@dataclass(frozen=True)
class RawListing:
    source: str
    source_id: str
    title: str
    price: Decimal
    currency: str
    price_type: PriceType
    url: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def price_minor(self) -> int:
        return int((self.price * 100).to_integral_value())


class RateLimiter:
    """Minimum-interval limiter. Simple and predictable beats clever for API quotas."""

    def __init__(self, min_interval_s: float, clock=time.monotonic, sleep=time.sleep):
        self.min_interval_s, self._clock, self._sleep = min_interval_s, clock, sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            delay = self.min_interval_s - (now - self._last)
            if delay > 0:
                self._sleep(delay)
        self._last = self._clock()


class SourceAdapter(ABC):
    """One adapter per data source. Fetching and normalization stay inside the adapter;
    matching and storage are source-agnostic and live in ingest.py."""

    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 50) -> Iterator[RawListing]:
        ...
