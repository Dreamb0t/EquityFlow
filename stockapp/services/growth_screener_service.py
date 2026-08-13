"""
Wraps a StockScreener with a short-lived cache, mirroring CurrencyService's
pattern — screening hits a market-wide Yahoo endpoint, so opening/refreshing
the Guided Trading tab shouldn't trigger a fresh network call every time.
"""

from __future__ import annotations

import time

from stockapp.core.interfaces import StockScreener
from stockapp.core.models import GrowthCandidate

CACHE_TTL_SECONDS = 15 * 60


class GrowthScreenerService:
    def __init__(self, screener: StockScreener):
        self._screener = screener
        self._cache: list[GrowthCandidate] = []
        self._cached_at: float = 0.0

    def get_recommendations(
        self, limit: int = 20, force_refresh: bool = False
    ) -> list[GrowthCandidate]:
        now = time.monotonic()
        if not force_refresh and self._cache and now - self._cached_at < CACHE_TTL_SECONDS:
            return self._cache[:limit]

        candidates = self._screener.find_growth_candidates(limit=limit)
        if candidates:
            self._cache = candidates
            self._cached_at = now
        return self._cache[:limit]
