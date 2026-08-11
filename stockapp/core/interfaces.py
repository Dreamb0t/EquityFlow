"""
Abstract interfaces (ports) that every outer layer depends on instead of on each
other directly. This is the piece that makes the desktop-to-web migration cheap:

    UI (desktop today, web later) --> services --> these interfaces
                                                        ^
                                                        |
                                        concrete implementations (scrapers/, data/, alerts/)

Swap an implementation (e.g. SQLite -> Postgres repository, or desktop notifier ->
web push notifier) without touching services/ or the other implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Iterable, Optional

from stockapp.core.models import (
    Alert,
    BalanceSheetSnapshot,
    PricePoint,
    Position,
    Ticker,
    WatchlistItem,
)


class PriceScraper(ABC):
    @abstractmethod
    def get_latest_price(self, ticker: Ticker) -> PricePoint: ...

    @abstractmethod
    def get_price_history(
        self, ticker: Ticker, start: date, end: date, interval: str = "1d"
    ) -> list[PricePoint]:
        """interval follows yfinance conventions: '1d' for daily bars, '5m'/'1m'
        for intraday (only available for recent dates)."""
        ...

    @abstractmethod
    def get_currency(self, ticker: Ticker) -> str:
        """ISO currency code the ticker actually trades in (e.g. 'USD', 'DKK') —
        used to convert live/historical prices into the user's display currency."""
        ...


class FxRateProvider(ABC):
    @abstractmethod
    def get_rate(self, base: str, quote: str) -> float:
        """Units of `quote` equal to 1 unit of `base` (e.g. base='USD',
        quote='DKK' -> ~6.9)."""
        ...


class BalanceSheetScraper(ABC):
    @abstractmethod
    def get_balance_sheet_history(
        self, ticker: Ticker, periods: int = 8
    ) -> list[BalanceSheetSnapshot]: ...


class NewsScraper(ABC):
    """Could-have: scrape news for a ticker. Defined now so the interface exists
    even before an implementation is built."""

    @abstractmethod
    def get_recent_headlines(self, ticker: Ticker, limit: int = 10) -> list[dict]: ...


class Notifier(ABC):
    @abstractmethod
    def send(self, alert: Alert) -> None: ...


class Repository(ABC):
    """Persistence port. Concrete implementation lives in data/ (SQLite now,
    swappable for Postgres later with no change to services/)."""

    # Positions (owned stocks) — identified by db row id so a symbol/exchange
    # can be edited without losing identity.
    @abstractmethod
    def add_position(self, position: Position) -> int: ...

    @abstractmethod
    def update_position(self, position: Position) -> None: ...

    @abstractmethod
    def list_positions(self) -> list[Position]: ...

    @abstractmethod
    def remove_position(self, position_id: int) -> None: ...

    # Watchlist
    @abstractmethod
    def add_watchlist_item(self, item: WatchlistItem) -> int: ...

    @abstractmethod
    def update_watchlist_item(self, item: WatchlistItem) -> None: ...

    @abstractmethod
    def list_watchlist(self) -> list[WatchlistItem]: ...

    @abstractmethod
    def remove_watchlist_item(self, item_id: int) -> None: ...

    # Cached market data
    @abstractmethod
    def save_price_points(self, points: Iterable[PricePoint]) -> None: ...

    @abstractmethod
    def get_price_history(
        self, ticker: Ticker, start: date, end: date
    ) -> list[PricePoint]: ...

    @abstractmethod
    def save_balance_sheets(self, snapshots: Iterable[BalanceSheetSnapshot]) -> None: ...

    @abstractmethod
    def get_balance_sheet_history(self, ticker: Ticker) -> list[BalanceSheetSnapshot]: ...

    # Alerts
    @abstractmethod
    def save_alert(self, alert: Alert) -> None: ...

    @abstractmethod
    def list_alerts(self, since: Optional[datetime] = None) -> list[Alert]: ...
