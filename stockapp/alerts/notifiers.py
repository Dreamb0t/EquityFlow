"""
Notifier implementations. The user wants both in-app and email delivery, so
alert_service (services/alert_service.py) fans each alert out to a list of
Notifier instances — add/remove channels there without touching this file.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from stockapp.config.settings import settings
from stockapp.core.interfaces import Notifier
from stockapp.core.models import Alert


class InAppNotifier(Notifier):
    """Pushes into an in-memory queue the desktop UI polls/subscribes to.
    A web version would replace this with e.g. a websocket push — same
    interface, different implementation."""

    def __init__(self):
        self._queue: list[Alert] = []

    def send(self, alert: Alert) -> None:
        self._queue.append(alert)

    def drain(self) -> list[Alert]:
        pending, self._queue = self._queue, []
        return pending


class EmailNotifier(Notifier):
    def send(self, alert: Alert) -> None:
        if not settings.smtp_host or not settings.alert_email_to:
            raise RuntimeError(
                "Email alerts not configured — set STOCKAPP_SMTP_* and "
                "STOCKAPP_ALERT_EMAIL_TO in .env"
            )

        msg = MIMEText(alert.message)
        msg["Subject"] = f"[stockapp] {alert.severity.value.upper()} — {alert.ticker}"
        msg["From"] = settings.alert_email_from or settings.smtp_username
        msg["To"] = settings.alert_email_to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
