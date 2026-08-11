"""
Aggregates data for the dashboard: growth chart + timeline for a ticker,
combining price history with the analysis layer. Currency conversion is
deliberately NOT done here — stats (% change, volatility) are scale-invariant
ratios, so they're computed in the ticker's native currency; only the raw
price values shown on the chart need converting, and that's the UI layer's
job (it has the user's selected display currency).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from stockapp.analysis.growth_analysis import moving_average, pct_change, volatility
from stockapp.analysis.timeframes import is_intraday, moving_average_window
from stockapp.core.interfaces import Repository
from stockapp.core.models import PricePoint, Ticker


@dataclass
class DashboardSeries:
    ticker: Ticker
    points: list[PricePoint]
    moving_avg: list[float]
    total_pct_change: float
    volatility_pct: float
    intraday: bool


class DashboardService:
    def __init__(self, repository: Repository):
        self._repo = repository

    def get_series(self, ticker: Ticker, days: int = 365) -> DashboardSeries:
        """Reads cached daily bars from the repository. Not used for the
        1-day/intraday view — see series_from_points for that."""
        start = date.today() - timedelta(days=days)
        points = self._repo.get_price_history(ticker, start, date.today())
        return self._build(ticker, points, intraday=is_intraday(days))

    def series_from_points(
        self, ticker: Ticker, points: list[PricePoint], intraday: bool
    ) -> DashboardSeries:
        """Builds a series from points fetched directly from a scraper
        (used for intraday data, which isn't cached in the repository)."""
        return self._build(ticker, points, intraday)

    def _build(self, ticker: Ticker, points: list[PricePoint], intraday: bool) -> DashboardSeries:
        window = moving_average_window(len(points))
        return DashboardSeries(
            ticker=ticker,
            points=points,
            moving_avg=moving_average(points, window=window),
            total_pct_change=pct_change(points),
            volatility_pct=volatility(points),
            intraday=intraday,
        )
