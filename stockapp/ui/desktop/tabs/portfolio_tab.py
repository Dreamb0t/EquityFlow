"""
Portfolio tab: positions grouped by stock (one expandable row per ticker,
showing combined shares and profit/loss; expand to see the individual buy
lots), plus a pie chart of allocation by market value. Adding new stocks
lives in the Stocks tab (search + choose Portfolio/Play Trading/both) — this
tab only views, edits and removes positions that are already there. Talks
only to PortfolioService, ScraperService (for live prices) and
CurrencyService/AppState (for display-currency conversion) — no direct DB or
scraper access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.analysis.portfolio_analysis import compute_distribution
from stockapp.core.models import Position, Ticker
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

        # Live price/name data, filled in by "Refresh values" — kept separate
        # from _rows (which just mirrors the DB) since fetching them is a
        # network call we don't want to trigger on every routine refresh(),
        # e.g. after every edit.
        self._market_prices: dict[Ticker, tuple[float, str]] = {}
        self._names: dict[Ticker, str] = {}

        # --- table: one expandable row per stock, children are buy lots ---
        self.table = QTreeWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)

        # --- edit form: hidden until "Edit selected lot" is clicked. New
        # positions are added from the Stocks tab, not here. ---
        self.symbol_input = QLineEdit()
        self.exchange_input = QLineEdit()
        self.shares_input = QDoubleSpinBox()
        self.shares_input.setRange(0.0001, 1_000_000_000)
        self.shares_input.setDecimals(4)
        self.avg_cost_input = QDoubleSpinBox()
        self.avg_cost_input.setRange(0.0001, 1_000_000_000)
        self.avg_cost_input.setDecimals(2)
        self.currency_input = QComboBox()
        self.currency_input.addItems(SUPPORTED_CURRENCIES)

        form = QFormLayout()
        form.addRow("Symbol", self.symbol_input)
        form.addRow("Exchange (optional)", self.exchange_input)
        form.addRow("Shares", self.shares_input)
        form.addRow("Avg cost", self.avg_cost_input)
        form.addRow("Currency", self.currency_input)

        self.save_button = QPushButton("Save changes")
        self.save_button.clicked.connect(self._save_changes)
        self.cancel_edit_button = QPushButton("Cancel edit")
        self.cancel_edit_button.clicked.connect(self._cancel_edit)

        edit_button_row = QHBoxLayout()
        edit_button_row.addWidget(self.save_button)
        edit_button_row.addWidget(self.cancel_edit_button)
        edit_button_row.addStretch()

        self.edit_panel = QWidget()
        edit_panel_layout = QVBoxLayout()
        edit_panel_layout.setContentsMargins(0, 0, 0, 0)
        edit_panel_layout.addLayout(form)
        edit_panel_layout.addLayout(edit_button_row)
        self.edit_panel.setLayout(edit_panel_layout)
        self.edit_panel.setVisible(False)

        edit_button = QPushButton("Edit selected lot")
        edit_button.clicked.connect(self._start_edit)
        remove_button = QPushButton("Remove selected lot")
        remove_button.clicked.connect(self._remove_selected)

        action_button_row = QHBoxLayout()
        action_button_row.addWidget(edit_button)
        action_button_row.addWidget(remove_button)
        action_button_row.addStretch()

        left = QVBoxLayout()
        left.addWidget(self.table)
        left.addWidget(self.edit_panel)
        left.addLayout(action_button_row)
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

        self._add_total_row(display_currency)

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

    def _position_value(
        self, position: Position, display_currency: str
    ) -> Optional[tuple[float, float]]:
        """(market_value, cost_value) for one lot, in the display currency, or
        None if its live price hasn't been fetched yet or a conversion rate
        failed. Cost basis converts from the lot's own recorded currency
        (what the user says they paid); market value converts from the
        ticker's native trading currency — these can differ (see Position's
        docstring on FX-hedged purchases), so each is converted separately."""
        market = self._market_prices.get(_normalized_ticker(position.ticker))
        if market is None:
            return None
        price_native, native_currency = market
        try:
            market_rate = self._currency_service.get_rate(native_currency, display_currency)
            cost_rate = self._currency_service.get_rate(position.currency, display_currency)
        except Exception:
            return None
        market_value = price_native * market_rate * position.shares
        cost_value = position.avg_cost * cost_rate * position.shares
        return market_value, cost_value

    def _group_profit(
        self, positions: list[Position], display_currency: str
    ) -> Optional[tuple[float, float]]:
        """Combined profit/loss across every lot of one ticker, in the display
        currency."""
        total_market = 0.0
        total_cost = 0.0
        for p in positions:
            values = self._position_value(p, display_currency)
            if values is None:
                return None
            total_market += values[0]
            total_cost += values[1]

        if total_cost <= 0:
            return None
        profit = total_market - total_cost
        return profit, profit / total_cost * 100

    def _add_total_row(self, display_currency: str) -> None:
        """A trailing row summing every position — same columns as the rest
        of the table. "Avg Cost"/"Currency" are repurposed here for the
        combined money spent (in the display currency, since it's summed
        across lots that may each be in a different native currency)."""
        if not self._rows:
            return

        total_market = 0.0
        total_cost = 0.0
        priced_count = 0
        for position in self._rows:
            values = self._position_value(position, display_currency)
            if values is None:
                continue
            priced_count += 1
            total_market += values[0]
            total_cost += values[1]

        total_shares = sum(p.shares for p in self._rows)
        has_totals = priced_count > 0 and total_cost > 0
        profit = None
        if has_totals:
            profit_amount = total_market - total_cost
            profit = (profit_amount, profit_amount / total_cost * 100)

        total_item = QTreeWidgetItem(
            [
                "Total",
                f"{total_shares:g}",
                f"{total_cost:.2f}" if priced_count > 0 else "—",
                display_currency if priced_count > 0 else "",
                "",
                self._format_signed(profit[0], display_currency) if profit else "—",
                f"{profit[1]:+.1f}%" if profit else "—",
            ]
        )
        bold_font = total_item.font(0)
        bold_font.setBold(True)
        for col in range(len(COLUMNS)):
            total_item.setFont(col, bold_font)
        self._color_profit_cells(total_item, profit)
        self.table.addTopLevelItem(total_item)

    @staticmethod
    def _format_signed(amount: float, currency: str) -> str:
        sign = "+" if amount >= 0 else ""
        return f"{sign}{amount:.2f} {currency}"

    # --- edit form ---
    def _save_changes(self) -> None:
        if self._editing_id is None:
            return  # the panel is only ever shown while editing a lot
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return
        exchange = self.exchange_input.text().strip().upper() or None
        shares = self.shares_input.value()
        avg_cost = self.avg_cost_input.value()
        currency = self.currency_input.currentText()

        existing = next((p for p in self._rows if p.id == self._editing_id), None)
        opened_at = existing.opened_at if existing else None
        self._service.update_position(
            self._editing_id, symbol, shares, avg_cost, currency, exchange, opened_at
        )
        self._cancel_edit()
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
        self.edit_panel.setVisible(True)

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self.edit_panel.setVisible(False)

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
        # Profit depends on the display currency, so re-render — no need to
        # refetch prices, just re-convert them.
        self.refresh()
