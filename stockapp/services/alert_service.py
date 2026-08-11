"""
Ties scraping -> analysis -> alert_engine -> notifiers together. This is what
the scheduler calls periodically, and what the desktop UI can also call
on-demand (e.g. a "Check now" button).
"""

from __future__ import annotations

from stockapp.alerts import alert_engine
from stockapp.core.interfaces import Notifier, Repository
from stockapp.core.models import Ticker


class AlertService:
    def __init__(self, repository: Repository, notifiers: list[Notifier]):
        self._repo = repository
        self._notifiers = notifiers

    def evaluate_ticker(self, ticker: Ticker) -> None:
        alerts = []

        prices = self._repo.get_price_history(
            ticker, *_last_two_days_range()
        )
        if len(prices) >= 2:
            price_alert = alert_engine.check_price_move(ticker, prices[-1], prices[-2])
            if price_alert:
                alerts.append(price_alert)

        bs_history = self._repo.get_balance_sheet_history(ticker)
        alerts.extend(alert_engine.check_balance_sheet(ticker, bs_history))

        for alert in alerts:
            self._repo.save_alert(alert)
            for notifier in self._notifiers:
                notifier.send(alert)

    def evaluate_all(self, tickers: list[Ticker]) -> None:
        for ticker in tickers:
            self.evaluate_ticker(ticker)

    def list_alerts(self):
        return self._repo.list_alerts()


def _last_two_days_range():
    from datetime import date, timedelta

    return date.today() - timedelta(days=7), date.today()
