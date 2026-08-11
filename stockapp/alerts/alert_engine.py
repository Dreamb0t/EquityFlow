"""
Evaluates price moves and balance-sheet irregularities into Alert objects.
Pure logic — no I/O, no scraping, no persistence — so it's trivially unit
testable in isolation.
"""

from __future__ import annotations

from datetime import datetime

from stockapp.analysis import irregularity_detector
from stockapp.analysis.growth_analysis import day_over_day_pct_move
from stockapp.config.settings import settings
from stockapp.core.models import (
    Alert,
    AlertSeverity,
    AlertType,
    BalanceSheetSnapshot,
    PricePoint,
    Ticker,
)


def check_price_move(
    ticker: Ticker, latest: PricePoint, previous: PricePoint
) -> Alert | None:
    move = day_over_day_pct_move(latest, previous)
    if abs(move) >= settings.price_move_alert_pct:
        direction = "up" if move > 0 else "down"
        return Alert(
            ticker=ticker,
            type=AlertType.PRICE_MOVE,
            severity=AlertSeverity.WARNING if abs(move) < 10 else AlertSeverity.CRITICAL,
            message=f"{ticker} moved {direction} {abs(move):.1f}% (threshold "
            f"{settings.price_move_alert_pct}%)",
            triggered_at=datetime.now(),
        )
    return None


def check_balance_sheet(
    ticker: Ticker, history: list[BalanceSheetSnapshot]
) -> list[Alert]:
    findings = irregularity_detector.detect(history)
    now = datetime.now()
    return [
        Alert(
            ticker=ticker,
            type=AlertType.BALANCE_SHEET_IRREGULARITY,
            severity=AlertSeverity(f.severity),
            message=f.description,
            triggered_at=now,
        )
        for f in findings
    ]
