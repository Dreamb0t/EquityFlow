"""
Basic analysis ("Should" feature): growth metrics and simple stats used by both
the dashboard charts and the alert engine.
"""

from __future__ import annotations

from statistics import mean, pstdev

from stockapp.core.models import PricePoint


def pct_change(points: list[PricePoint]) -> float:
    """Total % change from first to last point in the series."""
    if len(points) < 2:
        return 0.0
    first, last = points[0].close, points[-1].close
    return (last - first) / first * 100 if first else 0.0


def moving_average(points: list[PricePoint], window: int = 20) -> list[float]:
    closes = [p.close for p in points]
    return [
        mean(closes[max(0, i - window + 1) : i + 1]) for i in range(len(closes))
    ]


def volatility(points: list[PricePoint]) -> float:
    """Population stdev of daily % returns — a simple risk proxy."""
    closes = [p.close for p in points]
    if len(closes) < 2:
        return 0.0
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    return pstdev(returns) * 100 if returns else 0.0


def day_over_day_pct_move(latest: PricePoint, previous: PricePoint) -> float:
    if not previous.close:
        return 0.0
    return (latest.close - previous.close) / previous.close * 100
