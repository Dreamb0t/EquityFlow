"""
Background scheduling so alerts fire even while the desktop app is just sitting
open (or, later, while a web server is running). APScheduler runs in-process —
good enough for a single-user desktop app; a web deployment would likely move
this to Celery beat or a cron-triggered endpoint, but the job functions below
don't change either way since they just call services/.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from stockapp.config.settings import settings
from stockapp.services.alert_service import AlertService
from stockapp.services.container import get_container
from stockapp.services.scraper_service import ScraperService


def refresh_and_check() -> None:
    c = get_container()
    scraper_service = ScraperService(c.repository, c.price_scraper, c.balance_sheet_scraper)
    alert_service = AlertService(c.repository, c.notifiers)

    scraper_service.refresh_all()
    alert_service.evaluate_all(scraper_service.tracked_tickers())


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_and_check,
        "interval",
        minutes=settings.alert_check_interval_minutes,
        id="refresh_and_check",
        next_run_time=None,  # first run scheduled by caller / on demand
    )
    scheduler.start()
    return scheduler
