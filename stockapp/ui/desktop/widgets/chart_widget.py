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

from datetime import timedelta

import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator
from PyQt6.QtWidgets import QSizePolicy

from stockapp.services.dashboard_service import DashboardSeries

# Assumed length of a trading session, for spanning the intraday x-axis
# across a full day even before the session has finished.
INTRADAY_SESSION = timedelta(hours=8)
INTRADAY_TICK_COUNT = 5

# Yahoo Finance-style dark theme: black background, green close line.
BACKGROUND_COLOR = "#000000"
GRID_COLOR = "#2a2a2a"
TEXT_COLOR = "#e0e0e0"
CLOSE_COLOR = "#00c805"
MOVING_AVG_COLOR = "#8a8d93"


class PriceChartWidget(FigureCanvasQTAgg):
    def __init__(self):
        self._figure = Figure(figsize=(6, 4))
        self._figure.patch.set_facecolor(BACKGROUND_COLOR)
        super().__init__(self._figure)
        self._ax = self._figure.add_subplot(111)
        # Claim any extra space in the parent layout instead of staying at
        # its small default size hint — otherwise a tall window leaves the
        # chart squeezed and dead space collects around the other widgets.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _apply_theme(self) -> None:
        self._ax.set_facecolor(BACKGROUND_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.6)
        for spine in self._ax.spines.values():
            spine.set_color(GRID_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.xaxis.label.set_color(TEXT_COLOR)
        self._ax.yaxis.label.set_color(TEXT_COLOR)
        self._ax.title.set_color(TEXT_COLOR)

    def plot_series(self, series: DashboardSeries, currency_code: str, rate: float = 1.0) -> None:
        self._ax.clear()
        self._apply_theme()

        if not series.points:
            self._ax.set_title(f"{series.ticker} — no data")
            self.draw()
            return

        timestamps = [p.timestamp for p in series.points]
        closes = [p.close * rate for p in series.points]
        moving_avg = [m * rate for m in series.moving_avg]

        ticker_label = str(series.ticker)
        self._ax.plot(
            timestamps, closes, label=f"{ticker_label} Close", color=CLOSE_COLOR, linewidth=1.6
        )
        if moving_avg:
            self._ax.plot(
                timestamps,
                moving_avg,
                label=f"{ticker_label} Moving avg",
                linestyle="--",
                color=MOVING_AVG_COLOR,
                linewidth=1.0,
            )

        self._ax.set_title(f"{series.ticker} — {series.total_pct_change:+.1f}%")
        self._ax.set_ylabel(currency_code)
        self._ax.legend(facecolor=BACKGROUND_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

        if series.intraday:
            # Plot every 5-minute point for a precise curve, but keep the
            # x-axis readable with a handful of marks spanning a full
            # session rather than one per point.
            #
            # Anchored to the first point's own timestamp (when the stock
            # actually started trading today) rather than a fixed clock
            # hour — pre-market/exchange-hours vary by ticker, and the
            # session may still be in progress, so we can't know "now" is
            # the close. Spanning a full assumed session from that anchor,
            # rather than autoscaling to whatever's been plotted so far,
            # keeps all tick labels visible even mid-session.
            session_start = timestamps[0]
            tz = session_start.tzinfo
            # tz must be passed explicitly — otherwise matplotlib formats
            # labels in UTC and the displayed hours drift.
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=tz))
            ticks = [
                mdates.date2num(
                    session_start + INTRADAY_SESSION * i / (INTRADAY_TICK_COUNT - 1)
                )
                for i in range(INTRADAY_TICK_COUNT)
            ]
            self._ax.xaxis.set_major_locator(FixedLocator(ticks))
            self._ax.set_xlim(ticks[0], ticks[-1])
        else:
            span_days = (timestamps[-1] - timestamps[0]).days
            date_format = "%b %d" if span_days <= 400 else "%b %Y"
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
            self._ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))

        self._figure.autofmt_xdate()
        self.draw()
