"""
Main window: four tabs matching the Must/Should features — Dashboard,
Portfolio, Watchlist, Alerts. Every tab talks only to services/, never to
data/, scrapers/, or alerts/ directly — that boundary is what makes a future
web UI a matter of writing new views against the same services.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QTabWidget

from stockapp.services.alert_service import AlertService
from stockapp.services.container import Container
from stockapp.services.dashboard_service import DashboardService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService
from stockapp.services.watchlist_service import WatchlistService
from stockapp.ui.desktop.tabs.alerts_tab import AlertsTab
from stockapp.ui.desktop.tabs.dashboard_tab import DashboardTab
from stockapp.ui.desktop.tabs.portfolio_tab import PortfolioTab
from stockapp.ui.desktop.tabs.watchlist_tab import WatchlistTab


class MainWindow(QMainWindow):
    def __init__(self, container: Container):
        super().__init__()
        self.setWindowTitle("Stock App")
        self.resize(1100, 700)

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

        # Dashboard first so its reload_tickers can be handed to the other
        # tabs as an on_change callback.
        self.dashboard_tab = DashboardTab(
            self.dashboard_service,
            self.portfolio_service,
            self.watchlist_service,
            self.scraper_service,
        )
        self.portfolio_tab = PortfolioTab(
            self.portfolio_service, on_change=self.dashboard_tab.reload_tickers
        )
        self.watchlist_tab = WatchlistTab(
            self.watchlist_service, on_change=self.dashboard_tab.reload_tickers
        )
        self.alerts_tab = AlertsTab(
            self.alert_service, self.scraper_service, self.in_app_notifier
        )

        tabs = QTabWidget()
        tabs.addTab(self.dashboard_tab, "Dashboard")
        tabs.addTab(self.portfolio_tab, "Portfolio")
        tabs.addTab(self.watchlist_tab, "Watchlist")
        tabs.addTab(self.alerts_tab, "Alerts")
        self.setCentralWidget(tabs)
