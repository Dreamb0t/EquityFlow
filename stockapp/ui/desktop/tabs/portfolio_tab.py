"""
Portfolio tab: editable table of owned positions, plus a pie chart of
allocation by market value (what % of the portfolio each holding is). Talks
only to PortfolioService, ScraperService (for live prices) and
CurrencyService/AppState (for display-currency conversion) — no direct DB or
scraper access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.analysis.portfolio_analysis import compute_distribution
from stockapp.core.models import Position
from stockapp.services.app_state import AppState
from stockapp.services.currency_service import SUPPORTED_CURRENCIES, CurrencyService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService
from stockapp.ui.desktop.widgets.pie_chart_widget import PortfolioPieChartWidget

COLUMNS = ["Symbol", "Exchange", "Shares", "Avg Cost", "Currency", "Avg Cost (display)", "Opened"]


class PortfolioTab(QWidget):
    def __init__(
        self,
        portfolio_service: PortfolioService,
        scraper_service: ScraperService,
        currency_service: CurrencyService,
        app_state: AppState,
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._service = portfolio_service
        self._scraper_service = scraper_service
        self._currency_service = currency_service
        self._app_state = app_state
        self._on_change = on_change

        self._rows: list[Position] = []
        self._editing_id: Optional[int] = None

        # --- table ---
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # --- add/edit form ---
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
        self.currency_input = QComboBox()
        self.currency_input.addItems(SUPPORTED_CURRENCIES)

        self.submit_button = QPushButton("Add position")
        self.submit_button.clicked.connect(self._submit)
        self.cancel_edit_button = QPushButton("Cancel edit")
        self.cancel_edit_button.clicked.connect(self._cancel_edit)
        self.cancel_edit_button.setVisible(False)
        edit_button = QPushButton("Edit selected")
        edit_button.clicked.connect(self._start_edit)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._remove_selected)

        form = QFormLayout()
        form.addRow("Symbol", self.symbol_input)
        form.addRow("Exchange (optional)", self.exchange_input)
        form.addRow("Shares", self.shares_input)
        form.addRow("Avg cost", self.avg_cost_input)
        form.addRow("Currency", self.currency_input)

        button_row = QHBoxLayout()
        button_row.addWidget(self.submit_button)
        button_row.addWidget(self.cancel_edit_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()

        left = QVBoxLayout()
        left.addWidget(self.table)
        left.addLayout(form)
        left.addLayout(button_row)
        left_widget = QWidget()
        left_widget.setLayout(left)

        # --- allocation pie chart ---
        self.pie_chart = PortfolioPieChartWidget()
        refresh_values_button = QPushButton("Refresh values (updates pie chart)")
        refresh_values_button.clicked.connect(self._refresh_distribution)
        right = QVBoxLayout()
        right.addWidget(refresh_values_button)
        right.addWidget(self.pie_chart)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        self._app_state.on_change(self._on_currency_changed)
        self.currency_input.setCurrentText(self._app_state.display_currency)
        self.refresh()

    # --- table population ---
    def refresh(self) -> None:
        self._rows = self._service.list_positions()
        display_currency = self._app_state.display_currency
        self.table.setRowCount(len(self._rows))
        for row, p in enumerate(self._rows):
            converted = self._safe_convert(p.avg_cost, p.currency, display_currency)
            values = [
                p.ticker.symbol,
                p.ticker.exchange or "",
                f"{p.shares:g}",
                f"{p.avg_cost:.2f}",
                p.currency,
                f"{converted:.2f} {display_currency}" if converted is not None else "—",
                p.opened_at.isoformat(),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _safe_convert(self, amount: float, base: str, quote: str) -> Optional[float]:
        try:
            return self._currency_service.convert(amount, base, quote)
        except Exception:
            return None

    # --- add / edit form ---
    def _submit(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return
        exchange = self.exchange_input.text().strip() or None
        shares = self.shares_input.value()
        avg_cost = self.avg_cost_input.value()
        currency = self.currency_input.currentText()

        if self._editing_id is None:
            self._service.add_position(symbol, shares, avg_cost, currency, exchange)
        else:
            existing = next((p for p in self._rows if p.id == self._editing_id), None)
            opened_at = existing.opened_at if existing else None
            self._service.update_position(
                self._editing_id, symbol, shares, avg_cost, currency, exchange, opened_at
            )
            self._cancel_edit()

        self._clear_form()
        self._changed()

    def _start_edit(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "Nothing selected", "Select a position first.")
            return
        position = self._rows[row]
        self._editing_id = position.id
        self.symbol_input.setText(position.ticker.symbol)
        self.exchange_input.setText(position.ticker.exchange or "")
        self.shares_input.setValue(position.shares)
        self.avg_cost_input.setValue(position.avg_cost)
        self.currency_input.setCurrentText(position.currency)
        self.submit_button.setText("Save changes")
        self.cancel_edit_button.setVisible(True)

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self.submit_button.setText("Add position")
        self.cancel_edit_button.setVisible(False)
        self._clear_form()

    def _clear_form(self) -> None:
        self.symbol_input.clear()
        self.exchange_input.clear()
        self.shares_input.setValue(self.shares_input.minimum())
        self.avg_cost_input.setValue(self.avg_cost_input.minimum())
        self.currency_input.setCurrentText(self._app_state.display_currency)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        position = self._rows[row]
        self._service.remove_position(position.id)
        if self._editing_id == position.id:
            self._cancel_edit()
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        if self._on_change:
            self._on_change()

    # --- pie chart / allocation ---
    def _refresh_distribution(self) -> None:
        if not self._rows:
            self.pie_chart.plot_distribution({})
            return

        display_currency = self._app_state.display_currency
        values: dict[str, float] = {}
        failed: list[str] = []
        for position in self._rows:
            try:
                latest = self._scraper_service.get_latest_price(position.ticker)
                native_currency = self._scraper_service.get_ticker_currency(position.ticker)
                rate = self._currency_service.get_rate(native_currency, display_currency)
                market_value = latest.close * position.shares * rate
            except Exception:
                failed.append(str(position.ticker))
                continue
            label = str(position.ticker)
            values[label] = values.get(label, 0.0) + market_value

        if failed:
            QMessageBox.warning(
                self,
                "Some prices unavailable",
                "Couldn't fetch a live price for: " + ", ".join(failed),
            )

        self.pie_chart.plot_distribution(compute_distribution(values))

    def _on_currency_changed(self) -> None:
        self.currency_input.setCurrentText(self._app_state.display_currency)
        # The "Avg Cost (display)" column depends on the display currency, so
        # re-render it. The pie chart doesn't need refreshing: converting
        # every position through the same target currency scales every slice
        # by the same factor, so allocation percentages are unchanged.
        self.refresh()
