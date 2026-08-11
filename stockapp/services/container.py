"""
Composition root: the ONE place concrete implementations get wired to
interfaces. Every other module depends on abstractions (core/interfaces.py) or
on this container — never on a concrete class directly.

To port to the web app later: build a parallel container (or reuse this one)
and hand it to FastAPI route handlers instead of to the desktop UI. Nothing in
services/ needs to change.
"""

from __future__ import annotations

from functools import lru_cache

from stockapp.alerts.notifiers import EmailNotifier, InAppNotifier
from stockapp.config.settings import settings
from stockapp.data.repository import SqlRepository
from stockapp.scrapers.balance_sheet_scraper import YFinanceBalanceSheetScraper
from stockapp.scrapers.price_scraper import YFinancePriceScraper


class Container:
    def __init__(self):
        self.repository = SqlRepository()
        self.price_scraper = YFinancePriceScraper()
        self.balance_sheet_scraper = YFinanceBalanceSheetScraper()
        self.in_app_notifier = InAppNotifier()
        self.notifiers = [self.in_app_notifier]

        # Email is opt-in: only wire it up if SMTP + a recipient are set in
        # .env. Without this, the app (and alerts) work fine using in-app
        # notifications only — no credentials required to run.
        self.email_notifier: EmailNotifier | None = None
        if settings.smtp_host and settings.alert_email_to:
            self.email_notifier = EmailNotifier()
            self.notifiers.append(self.email_notifier)


@lru_cache
def get_container() -> Container:
    return Container()
