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
        self, ticker: Ticker, start: date, end: date
    ) -> list[PricePoint]: ...


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

    # Positions (owned stocks)
    @abstractmethod
    def add_position(self, position: Position) -> None: ...

    @abstractmethod
    def list_positions(self) -> list[Position]: ...

    @abstractmethod
    def remove_position(self, ticker: Ticker) -> None: ...

    # Watchlist
    @abstractmethod
    def add_watchlist_item(self, item: WatchlistItem) -> None: ...

    @abstractmethod
    def list_watchlist(self) -> list[WatchlistItem]: ...

    @abstractmethod
    def remove_watchlist_item(self, ticker: Ticker) -> None: ...

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
