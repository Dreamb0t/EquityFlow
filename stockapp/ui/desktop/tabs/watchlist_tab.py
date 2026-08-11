"""
Watchlist tab: tracked tickers not necessarily owned, each with an optional
note and target price. Talks only to WatchlistService.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.services.watchlist_service import WatchlistService

COLUMNS = ["Symbol", "Exchange", "Note", "Target Price", "Added"]


class WatchlistTab(QWidget):
    def __init__(
        self,
        watchlist_service: WatchlistService,
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._service = watchlist_service
        self._on_change = on_change

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("e.g. MSFT")
        self.exchange_input = QLineEdit()
        self.exchange_input.setPlaceholderText("optional")
        self.note_input = QLineEdit()
        self.target_price_input = QLineEdit()
        self.target_price_input.setPlaceholderText("optional")

        add_button = QPushButton("Add to watchlist")
        add_button.clicked.connect(self._add_item)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._remove_selected)

        form = QFormLayout()
        form.addRow("Symbol", self.symbol_input)
        form.addRow("Exchange (optional)", self.exchange_input)
        form.addRow("Note", self.note_input)
        form.addRow("Target price", self.target_price_input)

        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(button_row)
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
        items = self._service.list()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.ticker.symbol,
                item.ticker.exchange or "",
                item.note,
                f"{item.target_price:.2f}" if item.target_price is not None else "",
                item.added_at.isoformat(),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _add_item(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return
        exchange = self.exchange_input.text().strip() or None

        target_price = None
        raw_target = self.target_price_input.text().strip()
        if raw_target:
            try:
                target_price = float(raw_target)
            except ValueError:
                QMessageBox.warning(self, "Invalid target price", "Enter a number.")
                return

        self._service.add(symbol, exchange, self.note_input.text().strip(), target_price)
        self.symbol_input.clear()
        self.exchange_input.clear()
        self.note_input.clear()
        self.target_price_input.clear()
        self._changed()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        symbol = self.table.item(row, 0).text()
        exchange = self.table.item(row, 1).text() or None
        self._service.remove(symbol, exchange)
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        if self._on_change:
            self._on_change()
