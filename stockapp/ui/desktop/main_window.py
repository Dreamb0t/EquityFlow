"""
Main window: Dashboard, Portfolio, Watchlist, Alerts (Must/Should features),
Stocks (search + add to Portfolio/Play Trading/both — the only place new
stocks are added; Portfolio itself is view/edit/remove only), plus Guided
Trading and Play Trading (growth-stock recommendations and a paper-trading
sandbox to try them out) — and a global currency selector in the toolbar
that every tab reacts to via AppState. Every tab talks only to services/,
never to data/, scrapers/, or alerts/ directly — that boundary is what makes
a future web UI a matter of writing new views against the same services.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLabel, QMainWindow, QTabWidget, QToolBar

from stockapp.services.alert_service import AlertService
from stockapp.services.container import Container
from stockapp.services.currency_service import SUPPORTED_CURRENCIES
from stockapp.services.dashboard_service import DashboardService
from stockapp.services.growth_screener_service import GrowthScreenerService
from stockapp.services.paper_trading_service import PaperTradingService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService
from stockapp.services.watchlist_service import WatchlistService
from stockapp.ui.desktop.tabs.alerts_tab import AlertsTab
from stockapp.ui.desktop.tabs.dashboard_tab import DashboardTab
from stockapp.ui.desktop.tabs.guided_trading_tab import GuidedTradingTab
from stockapp.ui.desktop.tabs.play_trading_tab import PlayTradingTab
from stockapp.ui.desktop.tabs.portfolio_tab import PortfolioTab
from stockapp.ui.desktop.tabs.stocks_tab import StocksTab
from stockapp.ui.desktop.tabs.watchlist_tab import WatchlistTab


class MainWindow(QMainWindow):
    def __init__(self, container: Container):
        super().__init__()
        self.setWindowTitle("Stock App")
        self.resize(1200, 750)

        # Services — the only thing tabs are allowed to depend on.
        self.dashboard_service = DashboardService(container.repository)
        self.portfolio_service = PortfolioService(container.repository)
        self.watchlist_service = WatchlistService(container.repository)
        self.scraper_service = ScraperService(
            container.repository,
            container.price_scraper,
            container.balance_sheet_scraper,
        )
        self.alert_service = AlertService(container.repository, container.notifiers)
        self.in_app_notifier = container.in_app_notifier
        self.currency_service = container.currency_service
        self.app_state = container.app_state
        self.paper_trading_service = PaperTradingService(container.repository)
        self.growth_screener_service = GrowthScreenerService(container.growth_screener)

        self._build_currency_toolbar()

        # Dashboard first so its reload_tickers can be handed to the other
        # tabs as an on_change callback.
        self.dashboard_tab = DashboardTab(
            self.dashboard_service,
            self.portfolio_service,
            self.watchlist_service,
            self.scraper_service,
            self.currency_service,
            self.app_state,
        )
        self.portfolio_tab = PortfolioTab(
            self.portfolio_service,
            self.scraper_service,
            self.currency_service,
            self.app_state,
            on_change=self.dashboard_tab.reload_tickers,
        )
        self.watchlist_tab = WatchlistTab(
            self.watchlist_service,
            self.currency_service,
            self.app_state,
            on_change=self.dashboard_tab.reload_tickers,
        )
        self.alerts_tab = AlertsTab(
            self.alert_service, self.scraper_service, self.in_app_notifier
        )

        # Play Trading first so its refresh can be handed to Guided Trading
        # as an on_change callback (adding a recommendation should update it
        # immediately), matching the dashboard_tab.reload_tickers pattern.
        self.play_trading_tab = PlayTradingTab(
            self.paper_trading_service,
            self.scraper_service,
            self.currency_service,
            self.app_state,
        )
        self.guided_trading_tab = GuidedTradingTab(
            self.growth_screener_service,
            self.paper_trading_service,
            self.portfolio_service,
            on_play_trading_change=self.play_trading_tab.refresh,
            on_portfolio_change=self._on_portfolio_added,
        )
        self.stocks_tab = StocksTab(
            self.scraper_service,
            self.portfolio_service,
            self.paper_trading_service,
            self.app_state,
            on_portfolio_change=self._on_portfolio_added,
            on_play_trading_change=self.play_trading_tab.refresh,
        )

        tabs = QTabWidget()
        tabs.addTab(self.dashboard_tab, "Dashboard")
        tabs.addTab(self.stocks_tab, "Stocks")
        tabs.addTab(self.portfolio_tab, "Portfolio")
        tabs.addTab(self.watchlist_tab, "Watchlist")
        tabs.addTab(self.alerts_tab, "Alerts")
        tabs.addTab(self.guided_trading_tab, "Guided Trading")
        tabs.addTab(self.play_trading_tab, "Play Trading")
        self.setCentralWidget(tabs)

    def _on_portfolio_added(self) -> None:
        """A new position landed in the DB from outside PortfolioTab (Stocks
        or Guided Trading) — refresh its table and the Dashboard's ticker
        dropdown, which both only read the DB on demand."""
        self.portfolio_tab.refresh()
        self.dashboard_tab.reload_tickers()

    def _build_currency_toolbar(self) -> None:
        toolbar = QToolBar("Currency")
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel(" Display currency: "))

        self.currency_selector = QComboBox()
        self.currency_selector.addItems(SUPPORTED_CURRENCIES)
        self.currency_selector.setCurrentText(self.app_state.display_currency)
        self.currency_selector.currentTextChanged.connect(
            self.app_state.set_display_currency
        )
        toolbar.addWidget(self.currency_selector)
        self.addToolBar(toolbar)
