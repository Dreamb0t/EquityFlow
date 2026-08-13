"""
Portfolio tab: positions grouped by stock (one expandable row per ticker,
showing combined shares and profit/loss; expand to see the individual buy
lots), plus a pie chart of allocation by market value. Talks only to
PortfolioService, ScraperService (for live prices) and CurrencyService/
AppState (for display-currency conversion) — no direct DB or scraper access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.analysis.portfolio_analysis import compute_distribution
from stockapp.core.models import Position, SymbolMatch, Ticker
from stockapp.services.app_state import AppState
from stockapp.services.currency_service import SUPPORTED_CURRENCIES, CurrencyService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService
from stockapp.ui.desktop.widgets.pie_chart_widget import PortfolioPieChartWidget

def _normalized_ticker(ticker: Ticker) -> Ticker:
    """Canonical form used for grouping/caching, so two positions in the same
    stock don't fragment into separate rows just because one was typed with
    a differently-cased exchange suffix (e.g. "co" vs "CO")."""
    return Ticker(ticker.symbol.upper(), ticker.exchange.upper() if ticker.exchange else None)


COLUMNS = [
    "Stock",
    "Shares",
    "Avg Cost",
    "Currency",
    "Opened",
    "Profit",
    "Profit %",
]
PROFIT_COLUMN = COLUMNS.index("Profit")
PROFIT_PCT_COLUMN = COLUMNS.index("Profit %")
PROFIT_COLOR = QColor("#2e7d32")
LOSS_COLOR = QColor("#c62828")


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
        self._symbol_matches: list[SymbolMatch] = []

        # Live price/name data, filled in by "Refresh values" — kept separate
        # from _rows (which just mirrors the DB) since fetching them is a
        # network call we don't want to trigger on every routine refresh(),
        # e.g. after every add/edit.
        self._market_prices: dict[Ticker, tuple[float, str]] = {}
        self._names: dict[Ticker, str] = {}

        # --- table: one expandable row per stock, children are buy lots ---
        self.table = QTreeWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)

        # --- add/edit form ---
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("e.g. AAPL or Novo Nordisk")
        self.symbol_input.textEdited.connect(self._on_symbol_text_edited)

        # Debounced so we search on a pause in typing, not every keystroke.
        self._symbol_search_timer = QTimer(self)
        self._symbol_search_timer.setSingleShot(True)
        self._symbol_search_timer.timeout.connect(self._run_symbol_search)

        # Search results, one per matching exchange listing (e.g. a company
        # dual-listed as "NVO" on NYSE and "NOVO-B.CO" on Copenhagen shows up
        # as two separate rows here) — click one to fill in both the symbol
        # and exchange fields correctly instead of guessing a Yahoo suffix.
        self.symbol_suggestions = QListWidget()
        self.symbol_suggestions.setMaximumHeight(110)
        self.symbol_suggestions.setVisible(False)
        self.symbol_suggestions.itemClicked.connect(self._apply_symbol_suggestion)

        symbol_column = QVBoxLayout()
        symbol_column.setContentsMargins(0, 0, 0, 0)
        symbol_column.addWidget(self.symbol_input)
        symbol_column.addWidget(self.symbol_suggestions)
        symbol_field = QWidget()
        symbol_field.setLayout(symbol_column)

        self.exchange_input = QLineEdit()
        self.exchange_input.setPlaceholderText("optional, e.g. CO for Copenhagen")
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
        edit_button = QPushButton("Edit selected lot")
        edit_button.clicked.connect(self._start_edit)
        remove_button = QPushButton("Remove selected lot")
        remove_button.clicked.connect(self._remove_selected)

        form = QFormLayout()
        form.addRow("Symbol", symbol_field)
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
        refresh_values_button = QPushButton("Refresh values (prices, profit & pie chart)")
        refresh_values_button.clicked.connect(self._refresh_market_data)
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

        # Keep whichever stocks were expanded before rebuilding the tree.
        expanded_tickers = {
            self.table.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self.table.topLevelItemCount())
            if self.table.topLevelItem(i).isExpanded()
        }

        groups: dict[Ticker, list[Position]] = {}
        for p in self._rows:
            groups.setdefault(_normalized_ticker(p.ticker), []).append(p)

        self.table.clear()

        for ticker, positions in groups.items():
            total_shares = sum(p.shares for p in positions)
            name = self._names.get(ticker)
            stock_label = f"{name} ({ticker})" if name else str(ticker)
            profit = self._group_profit(positions, display_currency)

            group_item = QTreeWidgetItem(
                [
                    stock_label,
                    f"{total_shares:g}",
                    "",
                    "",
                    "",
                    self._format_signed(profit[0], display_currency) if profit else "—",
                    f"{profit[1]:+.1f}%" if profit else "—",
                ]
            )
            group_item.setData(0, Qt.ItemDataRole.UserRole, ticker)
            self._color_profit_cells(group_item, profit)
            self.table.addTopLevelItem(group_item)
            group_item.setExpanded(ticker in expanded_tickers)

            for p in sorted(positions, key=lambda pos: pos.opened_at):
                child_item = QTreeWidgetItem(
                    [
                        "",
                        f"{p.shares:g}",
                        f"{p.avg_cost:.2f}",
                        p.currency,
                        p.opened_at.isoformat(),
                        "",
                        "",
                    ]
                )
                child_item.setData(0, Qt.ItemDataRole.UserRole, p.id)
                group_item.addChild(child_item)

        for col in range(self.table.columnCount()):
            self.table.resizeColumnToContents(col)

    def _color_profit_cells(
        self, item: QTreeWidgetItem, profit: Optional[tuple[float, float]]
    ) -> None:
        if profit is None:
            return
        color = PROFIT_COLOR if profit[0] >= 0 else LOSS_COLOR
        brush = QBrush(color)
        item.setForeground(PROFIT_COLUMN, brush)
        item.setForeground(PROFIT_PCT_COLUMN, brush)

    def _group_profit(
        self, positions: list[Position], display_currency: str
    ) -> Optional[tuple[float, float]]:
        """Combined profit/loss across every lot of one ticker, in the display
        currency. Cost basis converts from each lot's own recorded currency
        (what the user says they paid); market value converts from the
        ticker's native trading currency — these can differ (see Position's
        docstring on FX-hedged purchases), so each is converted separately."""
        total_market = 0.0
        total_cost = 0.0
        for p in positions:
            market = self._market_prices.get(_normalized_ticker(p.ticker))
            if market is None:
                return None
            price_native, native_currency = market
            try:
                market_rate = self._currency_service.get_rate(native_currency, display_currency)
                cost_rate = self._currency_service.get_rate(p.currency, display_currency)
            except Exception:
                return None
            total_market += price_native * market_rate * p.shares
            total_cost += p.avg_cost * cost_rate * p.shares

        if total_cost <= 0:
            return None
        profit = total_market - total_cost
        return profit, profit / total_cost * 100

    @staticmethod
    def _format_signed(amount: float, currency: str) -> str:
        sign = "+" if amount >= 0 else ""
        return f"{sign}{amount:.2f} {currency}"

    # --- add / edit form ---
    def _submit(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return
        exchange = self.exchange_input.text().strip().upper() or None
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

    def _selected_position(self) -> Optional[Position]:
        """A buy-lot row (child of a stock group) currently selected, or None
        if nothing's selected or a group header is selected — editing/removal
        act on one specific lot, not the aggregated stock."""
        item = self.table.currentItem()
        if item is None or item.parent() is None:
            return None
        position_id = item.data(0, Qt.ItemDataRole.UserRole)
        return next((p for p in self._rows if p.id == position_id), None)

    def _start_edit(self) -> None:
        position = self._selected_position()
        if position is None:
            QMessageBox.information(
                self,
                "Nothing selected",
                "Expand a stock and select one of its buy lots to edit.",
            )
            return
        self._editing_id = position.id
        self.symbol_input.setText(position.ticker.symbol)
        self.exchange_input.setText(position.ticker.exchange or "")
        self.shares_input.setValue(position.shares)
        self.avg_cost_input.setValue(position.avg_cost)
        self.currency_input.setCurrentText(position.currency)
        self.submit_button.setText("Save changes")
        self.cancel_edit_button.setVisible(True)
        self._hide_symbol_suggestions()

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
        self._hide_symbol_suggestions()

    # --- symbol autocomplete ---
    def _on_symbol_text_edited(self, _text: str) -> None:
        # Restart the debounce window on every keystroke; only the last one
        # (350ms after typing pauses) actually triggers a search.
        self._symbol_search_timer.start(350)

    def _run_symbol_search(self) -> None:
        query = self.symbol_input.text().strip()
        if len(query) < 2:
            self._hide_symbol_suggestions()
            return

        try:
            matches = self._scraper_service.search_symbols(query)
        except Exception:
            matches = []  # best-effort — don't interrupt manual entry

        self._symbol_matches = matches
        self.symbol_suggestions.clear()
        for match in matches:
            display = f"{match.symbol}.{match.exchange}" if match.exchange else match.symbol
            label = f"{display}  —  {match.name}"
            if match.exchange_name:
                label += f"  ({match.exchange_name})"
            self.symbol_suggestions.addItem(label)
        self.symbol_suggestions.setVisible(bool(matches))

    def _apply_symbol_suggestion(self, item) -> None:
        row = self.symbol_suggestions.row(item)
        if row < 0 or row >= len(self._symbol_matches):
            return
        match = self._symbol_matches[row]
        self.symbol_input.setText(match.symbol)
        self.exchange_input.setText(match.exchange or "")
        self._hide_symbol_suggestions()

    def _hide_symbol_suggestions(self) -> None:
        self._symbol_search_timer.stop()
        self.symbol_suggestions.clear()
        self.symbol_suggestions.setVisible(False)
        self._symbol_matches = []

    def _remove_selected(self) -> None:
        position = self._selected_position()
        if position is None:
            QMessageBox.information(
                self,
                "Nothing selected",
                "Expand a stock and select one of its buy lots to remove.",
            )
            return
        self._service.remove_position(position.id)
        if self._editing_id == position.id:
            self._cancel_edit()
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        if self._on_change:
            self._on_change()

    # --- market data: live prices + names for profit calc and pie chart ---
    def _refresh_market_data(self) -> None:
        if not self._rows:
            self._market_prices = {}
            self.pie_chart.plot_distribution({})
            self.refresh()
            return

        display_currency = self._app_state.display_currency
        # One representative Ticker per normalized group — enough to make the
        # actual scraper calls, but cached under the normalized key so lots
        # with a differently-cased exchange suffix still share the result.
        tickers: dict[Ticker, Ticker] = {}
        for p in self._rows:
            tickers.setdefault(_normalized_ticker(p.ticker), p.ticker)

        failed: list[str] = []
        for norm_ticker, ticker in tickers.items():
            try:
                latest = self._scraper_service.get_latest_price(ticker)
                native_currency = self._scraper_service.get_ticker_currency(ticker)
                self._market_prices[norm_ticker] = (latest.close, native_currency)
            except Exception:
                failed.append(str(ticker))
            if norm_ticker not in self._names:
                try:
                    self._names[norm_ticker] = self._scraper_service.get_ticker_name(ticker)
                except Exception:
                    pass

        if failed:
            QMessageBox.warning(
                self,
                "Some prices unavailable",
                "Couldn't fetch a live price for: " + ", ".join(failed),
            )

        self.refresh()

        values: dict[str, float] = {}
        for position in self._rows:
            norm_ticker = _normalized_ticker(position.ticker)
            data = self._market_prices.get(norm_ticker)
            if data is None:
                continue
            price, native_currency = data
            try:
                rate = self._currency_service.get_rate(native_currency, display_currency)
            except Exception:
                continue
            label = str(norm_ticker)
            values[label] = values.get(label, 0.0) + price * position.shares * rate

        self.pie_chart.plot_distribution(compute_distribution(values))

    def _on_currency_changed(self) -> None:
        self.currency_input.setCurrentText(self._app_state.display_currency)
        # Profit depends on the display currency, so re-render — no need to
        # refetch prices, just re-convert them.
        self.refresh()
