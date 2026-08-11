"""
Matplotlib-in-Qt chart for the growth/timeline dashboard requirement. Kept as a
standalone widget so it's easy to reuse (or reimplement with a JS charting lib)
in the future web UI.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from stockapp.services.dashboard_service import DashboardSeries


class PriceChartWidget(FigureCanvasQTAgg):
    def __init__(self):
        self._figure = Figure(figsize=(6, 4))
        super().__init__(self._figure)
        self._ax = self._figure.add_subplot(111)

    def plot_series(self, series: DashboardSeries) -> None:
        self._ax.clear()
        timestamps = [p.timestamp for p in series.points]
        closes = [p.close for p in series.points]

        self._ax.plot(timestamps, closes, label="Close")
        if series.moving_avg_20d:
            self._ax.plot(timestamps, series.moving_avg_20d, label="20d MA", linestyle="--")

        self._ax.set_title(f"{series.ticker} — {series.total_pct_change:+.1f}%")
        self._ax.legend()
        self._figure.autofmt_xdate()
        self.draw()
