"""
Domain models — plain dataclasses with no dependency on UI, DB, or scraping code.

These are the shapes that flow between every layer. Keeping them framework-free
is what lets the same core/ and services/ code power a desktop UI today and a
web UI later without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class AlertType(str, Enum):
    PRICE_MOVE = "price_move"
    BALANCE_SHEET_IRREGULARITY = "balance_sheet_irregularity"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Ticker:
    symbol: str
    exchange: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.symbol}.{self.exchange}" if self.exchange else self.symbol


@dataclass
class PricePoint:
    ticker: Ticker
    timestamp: datetime
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None


@dataclass
class BalanceSheetSnapshot:
    """One period (e.g. one fiscal quarter) of balance sheet data for a company."""

    ticker: Ticker
    period_end: date
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    total_debt: Optional[float] = None
    source: str = "unknown"
    raw: dict = field(default_factory=dict)  # unparsed fields kept for future analysis


@dataclass
class Position:
    """A stock the user actually owns.

    `currency` is the ISO code `avg_cost` is denominated in — set by the user
    at entry time (defaults to the app's display currency), not auto-detected,
    since what a broker actually charged can differ from a ticker's home
    exchange currency (e.g. FX-hedged purchases).
    """

    ticker: Ticker
    shares: float
    avg_cost: float
    opened_at: date
    currency: str = "USD"
    id: Optional[int] = None


@dataclass
class WatchlistItem:
    ticker: Ticker
    added_at: date
    note: str = ""
    target_price: Optional[float] = None
    currency: str = "USD"
    id: Optional[int] = None


@dataclass
class Alert:
    ticker: Ticker
    type: AlertType
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    acknowledged: bool = False
