"""
Alerts tab: history of triggered alerts plus a manual "check now" that runs
the same evaluation the background scheduler does. Also polls the in-app
notifier queue so alerts fired by the scheduler thread show up without a
manual refresh.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.alerts.notifiers import InAppNotifier
from stockapp.services.alert_service import AlertService
from stockapp.services.scraper_service import ScraperService

COLUMNS = ["Time", "Ticker", "Severity", "Type", "Message"]


class AlertsTab(QWidget):
    def __init__(
        self,
        alert_service: AlertService,
        scraper_service: ScraperService,
        in_app_notifier: InAppNotifier,
    ):
        super().__init__()
        self._alert_service = alert_service
        self._scraper_service = scraper_service
        self._in_app_notifier = in_app_notifier

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        check_button = QPushButton("Check now")
        check_button.clicked.connect(self._check_now)

        button_row = QHBoxLayout()
        button_row.addWidget(check_button)
        button_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(button_row)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.refresh()

        # The scheduler runs on a background thread; poll for anything it
        # pushed into the in-app queue so this tab stays current without the
        # user needing to click anything.
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._drain_notifier)
        self._poll_timer.start(5000)

    def refresh(self) -> None:
        self._render(self._alert_service.list_alerts())

    def _render(self, alerts) -> None:
        self.table.setRowCount(len(alerts))
        for row, a in enumerate(alerts):
            values = [
                a.triggered_at.strftime("%Y-%m-%d %H:%M"),
                str(a.ticker),
                a.severity.value,
                a.type.value,
                a.message,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _check_now(self) -> None:
        try:
            self._alert_service.evaluate_all(self._scraper_service.tracked_tickers())
        except Exception as exc:
            QMessageBox.warning(self, "Check failed", str(exc))
        self.refresh()

    def _drain_notifier(self) -> None:
        if self._in_app_notifier.drain():
            self.refresh()
