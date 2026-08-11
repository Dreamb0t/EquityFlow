"""
Matplotlib-in-Qt chart for the growth/timeline dashboard requirement. Kept as a
standalone widget so it's easy to reuse (or reimplement with a JS charting lib)
in the future web UI.

x-axis format depends on the timeframe: intraday (1-day) views show only
times, multi-day views show dates — set via DashboardSeries.intraday.
Currency conversion is a simple multiply — pass the already-looked-up rate,
this widget doesn't know about FX.
"""

from __future__ import annotations

import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from stockapp.services.dashboard_service import DashboardSeries


class PriceChartWidget(FigureCanvasQTAgg):
    def __init__(self):
        self._figure = Figure(figsize=(6, 4))
        super().__init__(self._figure)
        self._ax = self._figure.add_subplot(111)

    def plot_series(self, series: DashboardSeries, currency_code: str, rate: float = 1.0) -> None:
        self._ax.clear()

        if not series.points:
            self._ax.set_title(f"{series.ticker} — no data")
            self.draw()
            return

        timestamps = [p.timestamp for p in series.points]
        closes = [p.close * rate for p in series.points]
        moving_avg = [m * rate for m in series.moving_avg]

        self._ax.plot(timestamps, closes, label="Close")
        if moving_avg:
            self._ax.plot(timestamps, moving_avg, label="Moving avg", linestyle="--")

        self._ax.set_title(f"{series.ticker} — {series.total_pct_change:+.1f}%")
        self._ax.set_ylabel(currency_code)
        self._ax.legend()

        if series.intraday:
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            self._ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
        else:
            span_days = (timestamps[-1] - timestamps[0]).days
            date_format = "%b %d" if span_days <= 400 else "%b %Y"
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
            self._ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))

        self._figure.autofmt_xdate()
        self.draw()
