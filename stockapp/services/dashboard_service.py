"""
Aggregates data for the dashboard: growth charts + timeline for a ticker,
combining cached price history with the analysis layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from stockapp.analysis.growth_analysis import moving_average, pct_change, volatility
from stockapp.core.interfaces import Repository
from stockapp.core.models import PricePoint, Ticker


@dataclass
class DashboardSeries:
    ticker: Ticker
    points: list[PricePoint]
    moving_avg_20d: list[float]
    total_pct_change: float
    volatility_pct: float


class DashboardService:
    def __init__(self, repository: Repository):
        self._repo = repository

    def get_series(self, ticker: Ticker, lookback_days: int = 365) -> DashboardSeries:
        start = date.today() - timedelta(days=lookback_days)
        points = self._repo.get_price_history(ticker, start, date.today())
        return DashboardSeries(
            ticker=ticker,
            points=points,
            moving_avg_20d=moving_average(points, window=20),
            total_pct_change=pct_change(points),
            volatility_pct=volatility(points),
        )
