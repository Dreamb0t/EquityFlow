"""
Portfolio tab: table of owned positions + a form to add new ones.
Talks only to PortfolioService — no direct DB/scraper access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
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

from stockapp.services.portfolio_service import PortfolioService

COLUMNS = ["Symbol", "Exchange", "Shares", "Avg Cost", "Opened"]


class PortfolioTab(QWidget):
    def __init__(
        self,
        portfolio_service: PortfolioService,
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._service = portfolio_service
        self._on_change = on_change

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("e.g. AAPL")
        self.exchange_input = QLineEdit()
        self.exchange_input.setPlaceholderText("optional")
        self.shares_input = QDoubleSpinBox()
        self.shares_input.setRange(0.0001, 1_000_000_000)
        self.shares_input.setDecimals(4)
        self.avg_cost_input = QDoubleSpinBox()
        self.avg_cost_input.setRange(0.0001, 1_000_000_000)
        self.avg_cost_input.setDecimals(2)
        self.avg_cost_input.setPrefix("$ ")

        add_button = QPushButton("Add position")
        add_button.clicked.connect(self._add_position)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._remove_selected)

        form = QFormLayout()
        form.addRow("Symbol", self.symbol_input)
        form.addRow("Exchange (optional)", self.exchange_input)
        form.addRow("Shares", self.shares_input)
        form.addRow("Avg cost", self.avg_cost_input)

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
        positions = self._service.list_positions()
        self.table.setRowCount(len(positions))
        for row, p in enumerate(positions):
            values = [
                p.ticker.symbol,
                p.ticker.exchange or "",
                f"{p.shares:g}",
                f"{p.avg_cost:.2f}",
                p.opened_at.isoformat(),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _add_position(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return
        exchange = self.exchange_input.text().strip() or None
        self._service.add_position(
            symbol, self.shares_input.value(), self.avg_cost_input.value(), exchange
        )
        self.symbol_input.clear()
        self.exchange_input.clear()
        self.shares_input.setValue(self.shares_input.minimum())
        self.avg_cost_input.setValue(self.avg_cost_input.minimum())
        self._changed()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        symbol = self.table.item(row, 0).text()
        exchange = self.table.item(row, 1).text() or None
        self._service.remove_position(symbol, exchange)
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        if self._on_change:
            self._on_change()
