"""
Orchestrates scraping + caching: pulls fresh data via the scraper interfaces
and persists it through the repository, for whatever tickers the user tracks
(positions + watchlist).
"""

from __future__ import annotations

from datetime import date, timedelta

from stockapp.core.interfaces import BalanceSheetScraper, PriceScraper, Repository
from stockapp.core.models import PricePoint, Ticker


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
        self._currency_cache: dict[Ticker, str] = {}

    def tracked_tickers(self) -> list[Ticker]:
        positions = {p.ticker for p in self._repo.list_positions()}
        watchlist = {w.ticker for w in self._repo.list_watchlist()}
        return list(positions | watchlist)

    def refresh_prices(self, ticker: Ticker, lookback_days: int = 5) -> None:
        start = date.today() - timedelta(days=lookback_days)
        points = self._price_scraper.get_price_history(
            ticker, start, date.today(), interval="1d"
        )
        self._repo.save_price_points(points)

    def fetch_intraday(self, ticker: Ticker, interval: str = "5m") -> list[PricePoint]:
        """Live minute-level bars for today. Deliberately NOT cached in the
        repository — price_points there holds daily bars, and mixing
        granularities in one table would corrupt the daily-based analytics
        (moving averages, day-over-day alerts)."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        return self._price_scraper.get_price_history(
            ticker, today, tomorrow, interval=interval
        )

    def get_latest_price(self, ticker: Ticker):
        """Live quote passthrough — kept on this service (rather than handing
        tabs the price_scraper directly) so the UI layer never talks to
        scrapers/ directly, matching the rest of the app's layering."""
        return self._price_scraper.get_latest_price(ticker)

    def get_ticker_currency(self, ticker: Ticker) -> str:
        """The currency a ticker actually trades in, cached for the process
        lifetime (a company's listing currency doesn't change)."""
        if ticker not in self._currency_cache:
            self._currency_cache[ticker] = self._price_scraper.get_currency(ticker)
        return self._currency_cache[ticker]

    def refresh_balance_sheet(self, ticker: Ticker) -> None:
        snapshots = self._bs_scraper.get_balance_sheet_history(ticker)
        self._repo.save_balance_sheets(snapshots)

    def refresh_all(self) -> None:
        for ticker in self.tracked_tickers():
            self.refresh_prices(ticker)
            self.refresh_balance_sheet(ticker)
