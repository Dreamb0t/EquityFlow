"""Smoke tests for the pure-logic layers (no DB, no network)."""

from datetime import date, datetime

from stockapp.alerts import alert_engine
from stockapp.analysis import irregularity_detector
from stockapp.analysis.growth_analysis import day_over_day_pct_move, pct_change
from stockapp.core.models import BalanceSheetSnapshot, PricePoint, Ticker

TICKER = Ticker("AAPL")


def _pp(close: float, day: int) -> PricePoint:
    return PricePoint(ticker=TICKER, timestamp=datetime(2026, 1, day), close=close)


def test_pct_change():
    points = [_pp(100, 1), _pp(110, 2)]
    assert pct_change(points) == 10.0


def test_day_over_day_move_triggers_alert():
    latest, previous = _pp(110, 2), _pp(100, 1)
    assert day_over_day_pct_move(latest, previous) == 10.0
    alert = alert_engine.check_price_move(TICKER, latest, previous)
    assert alert is not None
    assert alert.ticker == TICKER


def test_no_alert_below_threshold():
    latest, previous = _pp(101, 2), _pp(100, 1)
    assert alert_engine.check_price_move(TICKER, latest, previous) is None


def test_equity_drop_flagged():
    prev = BalanceSheetSnapshot(
        ticker=TICKER, period_end=date(2025, 12, 31), total_equity=1000, total_debt=100
    )
    latest = BalanceSheetSnapshot(
        ticker=TICKER, period_end=date(2026, 3, 31), total_equity=700, total_debt=110
    )
    findings = irregularity_detector.detect([prev, latest])
    assert any("equity" in f.description.lower() for f in findings)
