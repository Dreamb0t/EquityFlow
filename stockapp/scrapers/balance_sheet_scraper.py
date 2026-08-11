"""
Balance sheet scraper — the "Must" feature that needs a concrete source picked.

Two implementations are sketched:

1. YFinanceBalanceSheetScraper — uses yfinance's built-in financials endpoints.
   Fastest to ship; covers most public companies; not really "web scraping" but
   satisfies the requirement with the least maintenance burden.

2. HtmlBalanceSheetScraper — a requests + BeautifulSoup scraper stub against a
   named source URL, for when a specific site's data is wanted instead
   (or as a fallback / cross-check against #1). Fill in _parse() once a target
   site is chosen.

Both implement the same BalanceSheetScraper interface, so services/ doesn't care
which one is wired in (see services/scraper_service.py).
"""

from __future__ import annotations

from datetime import datetime

from stockapp.core.interfaces import BalanceSheetScraper
from stockapp.core.models import BalanceSheetSnapshot, Ticker


class YFinanceBalanceSheetScraper(BalanceSheetScraper):
    def get_balance_sheet_history(
        self, ticker: Ticker, periods: int = 8
    ) -> list[BalanceSheetSnapshot]:
        import yfinance as yf

        bs = yf.Ticker(str(ticker)).quarterly_balance_sheet
        snapshots = []
        for period_end in list(bs.columns)[:periods]:
            col = bs[period_end]
            snapshots.append(
                BalanceSheetSnapshot(
                    ticker=ticker,
                    period_end=period_end.date(),
                    total_assets=col.get("Total Assets"),
                    total_liabilities=col.get("Total Liabilities Net Minority Interest"),
                    total_equity=col.get("Stockholders Equity"),
                    cash_and_equivalents=col.get("Cash And Cash Equivalents"),
                    total_debt=col.get("Total Debt"),
                    source="yfinance",
                    raw=col.dropna().to_dict(),
                )
            )
        return snapshots


class HtmlBalanceSheetScraper(BalanceSheetScraper):
    """Skeleton for scraping a specific site directly. Pick a source and fill in
    _build_url / _parse — layout below assumes a per-ticker financials page."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_balance_sheet_history(
        self, ticker: Ticker, periods: int = 8
    ) -> list[BalanceSheetSnapshot]:
        import requests
        from bs4 import BeautifulSoup

        from stockapp.config.settings import settings

        url = self._build_url(ticker)
        resp = requests.get(
            url,
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=settings.request_timeout_seconds,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._parse(ticker, soup)[:periods]

    def _build_url(self, ticker: Ticker) -> str:
        return f"{self.base_url}/{ticker.symbol}/balance-sheet"

    def _parse(self, ticker: Ticker, soup) -> list[BalanceSheetSnapshot]:
        # TODO: implement once a target site is chosen — table structure is
        # site-specific. Return [] for now so callers don't break.
        raise NotImplementedError(
            "Choose a source site and implement table parsing for its layout."
        )
