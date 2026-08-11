"""
Wraps an FxRateProvider with a short-lived in-memory cache so switching the
display currency, or re-rendering charts/tables, doesn't hit the network on
every paint. Pure conversion math lives here so it's testable without a real
provider (see tests/test_currency.py, which uses a stub FxRateProvider).
"""

from __future__ import annotations

import time

from stockapp.core.interfaces import FxRateProvider

CACHE_TTL_SECONDS = 15 * 60

# Curated starter list — extend as needed. DKK included per the "should also
# include DKK" requirement.
SUPPORTED_CURRENCIES = ["USD", "EUR", "DKK", "GBP", "SEK", "NOK"]


class CurrencyService:
    def __init__(self, provider: FxRateProvider):
        self._provider = provider
        self._cache: dict[tuple[str, str], tuple[float, float]] = {}

    def get_rate(self, base: str, quote: str) -> float:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0

        key = (base, quote)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[1] < CACHE_TTL_SECONDS:
            return cached[0]

        rate = self._provider.get_rate(base, quote)
        self._cache[key] = (rate, now)
        return rate

    def convert(self, amount: float, base: str, quote: str) -> float:
        return amount * self.get_rate(base, quote)

    def clear_cache(self) -> None:
        self._cache.clear()
