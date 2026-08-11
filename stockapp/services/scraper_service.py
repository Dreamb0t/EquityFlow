"""
Orchestrates scraping + caching: pulls fresh data via the scraper interfaces
and persists it through the repository, for whatever tickers the user tracks
(positions + watchlist).
"""

from __future__ import annotations

from datetime import date, timedelta

from stockapp.core.interfaces import BalanceSheetScraper, PriceScraper, Repository
from stockapp.core.models import Ticker


class ScraperService:
    def __init__(
        self,
        repository: Repository,
        price_scraper: PriceScraper,
        balance_sheet_scraper: BalanceSheetScraper,
    ):
        self._repo = repository
        self._price_scraper = price_scraper
        self._bs_scraper = balance_sheet_scraper

    def tracked_tickers(self) -> list[Ticker]:
        positions = {p.ticker for p in self._repo.list_positions()}
        watchlist = {w.ticker for w in self._repo.list_watchlist()}
        return list(positions | watchlist)

    def refresh_prices(self, ticker: Ticker, lookback_days: int = 5) -> None:
        start = date.today() - timedelta(days=lookback_days)
        points = self._price_scraper.get_price_history(ticker, start, date.today())
        self._repo.save_price_points(points)

    def refresh_balance_sheet(self, ticker: Ticker) -> None:
        snapshots = self._bs_scraper.get_balance_sheet_history(ticker)
        self._repo.save_balance_sheets(snapshots)

    def refresh_all(self) -> None:
        for ticker in self.tracked_tickers():
            self.refresh_prices(ticker)
            self.refresh_balance_sheet(ticker)
