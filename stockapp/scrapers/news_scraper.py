"""
Could-have feature: news scraper. Interface exists (core/interfaces.py) so this
can be wired into services later without touching other layers.
"""

from __future__ import annotations

from stockapp.core.interfaces import NewsScraper
from stockapp.core.models import Ticker


class StubNewsScraper(NewsScraper):
    def get_recent_headlines(self, ticker: Ticker, limit: int = 10) -> list[dict]:
        raise NotImplementedError("Not yet built — this is a 'Could' feature.")
