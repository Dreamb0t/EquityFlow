"""
Dashboard tab: growth chart + timeline for a chosen ticker. Pulls the ticker
list from both services (owned + watchlist) and lets the user trigger a fresh
scrape when no cached price data exists yet.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stockapp.core.models import Ticker
from stockapp.services.dashboard_service import DashboardService
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
    ):
        super().__init__()
        self._dashboard_service = dashboard_service
        self._portfolio_service = portfolio_service
        self._watchlist_service = watchlist_service
        self._scraper_service = scraper_service

        self.ticker_select = QComboBox()
        refresh_tickers_button = QPushButton("Reload ticker list")
        refresh_tickers_button.clicked.connect(self.reload_tickers)

        fetch_button = QPushButton("Fetch latest data")
        fetch_button.clicked.connect(self._fetch_and_plot)

        self.stats_label = QLabel('Pick a ticker and click "Fetch latest data."')
        self.chart = PriceChartWidget()

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Ticker:"))
        top_row.addWidget(self.ticker_select)
        top_row.addWidget(refresh_tickers_button)
        top_row.addWidget(fetch_button)
        top_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.chart)
        self.setLayout(layout)

        self.reload_tickers()

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

    def _fetch_and_plot(self) -> None:
        ticker = self._current_ticker()
        if ticker is None:
            QMessageBox.information(
                self, "No ticker", "Add a position or watchlist item first."
            )
            return

        try:
            self._scraper_service.refresh_prices(ticker)
        except Exception as exc:  # scraping is network I/O — surface, don't crash
            QMessageBox.warning(self, "Fetch failed", str(exc))

        series = self._dashboard_service.get_series(ticker)
        if not series.points:
            self.stats_label.setText(f"No price data available yet for {ticker}.")
            return

        self.stats_label.setText(
            f"{ticker}: {series.total_pct_change:+.1f}% over period · "
            f"volatility {series.volatility_pct:.1f}%"
        )
        self.chart.plot_series(series)
