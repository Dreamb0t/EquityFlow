"""
Dashboard tab: growth chart + timeline for a chosen ticker. Includes a
timeframe picker (1 Day / 5 Days / 1 Month / 6 Months / 1 Year / custom N
days) and converts prices into the app's selected display currency.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stockapp.analysis.timeframes import CUSTOM_LABEL, PRESET_TIMEFRAMES
from stockapp.core.models import Ticker
from stockapp.services.app_state import AppState
from stockapp.services.currency_service import CurrencyService
from stockapp.services.dashboard_service import DashboardSeries, DashboardService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService
from stockapp.services.watchlist_service import WatchlistService
from stockapp.ui.desktop.widgets.chart_widget import PriceChartWidget


class DashboardTab(QWidget):
    def __init__(
        self,
        dashboard_service: DashboardService,
        portfolio_service: PortfolioService,
        watchlist_service: WatchlistService,
        scraper_service: ScraperService,
        currency_service: CurrencyService,
        app_state: AppState,
    ):
        super().__init__()
        self._dashboard_service = dashboard_service
        self._portfolio_service = portfolio_service
        self._watchlist_service = watchlist_service
        self._scraper_service = scraper_service
        self._currency_service = currency_service
        self._app_state = app_state

        self._last_series: DashboardSeries | None = None
        self._last_native_currency: str = app_state.display_currency

        self.ticker_select = QComboBox()
        refresh_tickers_button = QPushButton("Reload ticker list")
        refresh_tickers_button.clicked.connect(self.reload_tickers)

        self.timeframe_select = QComboBox()
        self.timeframe_select.addItems(
            [tf.label for tf in PRESET_TIMEFRAMES] + [CUSTOM_LABEL]
        )
        self.timeframe_select.currentTextChanged.connect(self._on_timeframe_changed)

        self.custom_days_input = QSpinBox()
        self.custom_days_input.setRange(1, 3650)
        self.custom_days_input.setValue(23)
        self.custom_days_input.setSuffix(" days")
        self.custom_days_input.setVisible(False)

        fetch_button = QPushButton("Fetch latest data")
        fetch_button.clicked.connect(self._fetch_and_plot)

        self.stats_label = QLabel(
            'Pick a ticker and timeframe, then click "Fetch latest data."'
        )
        self.chart = PriceChartWidget()

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Ticker:"))
        top_row.addWidget(self.ticker_select)
        top_row.addWidget(refresh_tickers_button)
        top_row.addWidget(QLabel("Timeframe:"))
        top_row.addWidget(self.timeframe_select)
        top_row.addWidget(self.custom_days_input)
        top_row.addWidget(fetch_button)
        top_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.chart, 1)  # only the chart absorbs extra space
        self.setLayout(layout)

        self.reload_tickers()
        self._app_state.on_change(self._on_currency_changed)

        # Fetch once on startup so the chart isn't blank until the user
        # clicks the button — but only if there's actually a ticker to plot
        # (an empty portfolio/watchlist would otherwise pop the "no ticker"
        # warning dialog on every launch).
        if self.ticker_select.count() > 0:
            self._fetch_and_plot()

    def reload_tickers(self) -> None:
        tickers = {p.ticker for p in self._portfolio_service.list_positions()}
        tickers |= {w.ticker for w in self._watchlist_service.list()}
        current = self.ticker_select.currentText()
        self.ticker_select.clear()
        self.ticker_select.addItems(sorted(str(t) for t in tickers))
        index = self.ticker_select.findText(current)
        if index >= 0:
            self.ticker_select.setCurrentIndex(index)

    def _current_ticker(self) -> Ticker | None:
        text = self.ticker_select.currentText()
        if not text:
            return None
        if "." in text:
            symbol, exchange = text.split(".", 1)
            return Ticker(symbol, exchange)
        return Ticker(text)

    def _on_timeframe_changed(self, label: str) -> None:
        self.custom_days_input.setVisible(label == CUSTOM_LABEL)

    def _selected_days(self) -> int:
        label = self.timeframe_select.currentText()
        if label == CUSTOM_LABEL:
            return self.custom_days_input.value()
        for tf in PRESET_TIMEFRAMES:
            if tf.label == label:
                return tf.days
        return 365

    def _fetch_and_plot(self) -> None:
        ticker = self._current_ticker()
        if ticker is None:
            QMessageBox.information(
                self, "No ticker", "Add a position or watchlist item first."
            )
            return

        days = self._selected_days()
        intraday = days <= 1

        try:
            if intraday:
                points = self._scraper_service.fetch_intraday(ticker)
                series = self._dashboard_service.series_from_points(
                    ticker, points, intraday=True
                )
            else:
                self._scraper_service.refresh_prices(ticker, lookback_days=days)
                series = self._dashboard_service.get_series(ticker, days=days)
        except Exception as exc:  # scraping is network I/O — surface, don't crash
            QMessageBox.warning(self, "Fetch failed", str(exc))
            return

        try:
            native_currency = self._scraper_service.get_ticker_currency(ticker)
        except Exception:
            native_currency = self._app_state.display_currency

        self._last_series = series
        self._last_native_currency = native_currency
        self._render()

    def _on_currency_changed(self) -> None:
        if self._last_series is not None:
            self._render()

    def _render(self) -> None:
        series = self._last_series
        if series is None:
            return

        if not series.points:
            self.stats_label.setText(f"No price data available yet for {series.ticker}.")
            self.chart.plot_series(series, self._app_state.display_currency)
            return

        display_currency = self._app_state.display_currency
        rate = 1.0
        shown_currency = self._last_native_currency

        if self._last_native_currency != display_currency:
            try:
                rate = self._currency_service.get_rate(
                    self._last_native_currency, display_currency
                )
                shown_currency = display_currency
            except Exception as exc:
                # Don't silently fall back to rate=1.0 while still labeling
                # the axis as the target currency — that's exactly the "title
                # changed but values didn't" bug. Keep showing native prices
                # and say so.
                QMessageBox.warning(
                    self,
                    "Currency conversion failed",
                    f"Could not fetch the {self._last_native_currency}->"
                    f"{display_currency} exchange rate ({exc}). Showing prices "
                    f"in {self._last_native_currency} instead.",
                )

        self.stats_label.setText(
            f"{series.ticker}: {series.total_pct_change:+.1f}% over period · "
            f"volatility {series.volatility_pct:.1f}% · shown in "
            f"{shown_currency} (native: {self._last_native_currency})"
        )
        self.chart.plot_series(series, shown_currency, rate)
