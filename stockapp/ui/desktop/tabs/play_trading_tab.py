"""
Play Trading tab: simulated positions added from Guided Trading, tracked
against live prices to see how well the recommendation would have performed
— no real money involved. Talks only to PaperTradingService, ScraperService
(live prices) and CurrencyService/AppState (display-currency conversion).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.core.models import PaperTrade
from stockapp.services.app_state import AppState
from stockapp.services.currency_service import CurrencyService
from stockapp.services.paper_trading_service import PaperTradingService
from stockapp.services.scraper_service import ScraperService

COLUMNS = [
    "Name",
    "Symbol",
    "Shares",
    "Entry Price",
    "Entry Currency",
    "Current Price",
    "Profit",
    "Profit %",
    "Opened",
]
PROFIT_COLUMN = COLUMNS.index("Profit")
PROFIT_PCT_COLUMN = COLUMNS.index("Profit %")
PROFIT_COLOR = QColor("#2e7d32")
LOSS_COLOR = QColor("#c62828")


class PlayTradingTab(QWidget):
    def __init__(
        self,
        paper_trading_service: PaperTradingService,
        scraper_service: ScraperService,
        currency_service: CurrencyService,
        app_state: AppState,
    ):
        super().__init__()
        self._service = paper_trading_service
        self._scraper_service = scraper_service
        self._currency_service = currency_service
        self._app_state = app_state

        self._rows: list[PaperTrade] = []
        # Live price data, filled in by "Refresh values" — a network call we
        # don't want to trigger on every routine refresh() (e.g. after a
        # remove), same pattern as PortfolioTab.
        self._market_prices: dict[tuple[str, Optional[str]], tuple[float, str]] = {}
        self._names: dict[tuple[str, Optional[str]], str] = {}

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        refresh_button = QPushButton("Refresh values")
        refresh_button.clicked.connect(self._refresh_market_data)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._remove_selected)

        # Combined total across every simulated position — sum of current
        # position value and sum of profit, not just per-row figures.
        self.summary_label = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.summary_label)
        layout.addWidget(refresh_button)
        layout.addWidget(remove_button)
        self.setLayout(layout)

        self._app_state.on_change(self.refresh)
        self.refresh()

    @staticmethod
    def _key(trade: PaperTrade) -> tuple[str, Optional[str]]:
        return (trade.ticker.symbol.upper(), trade.ticker.exchange.upper() if trade.ticker.exchange else None)

    def refresh(self) -> None:
        self._rows = self._service.list_trades()
        display_currency = self._app_state.display_currency

        self.table.setRowCount(len(self._rows))
        for row, trade in enumerate(self._rows):
            key = self._key(trade)
            name = self._names.get(key, str(trade.ticker))
            profit = self._trade_profit(trade, display_currency)
            market = self._market_prices.get(key)
            current_price = f"{market[0]:.2f} {market[1]}" if market else "—"

            values = [
                name,
                str(trade.ticker),
                f"{trade.shares:g}",
                f"{trade.entry_price:.2f}",
                trade.entry_currency,
                current_price,
                self._format_signed(profit[0], display_currency) if profit else "—",
                f"{profit[1]:+.1f}%" if profit else "—",
                trade.opened_at.isoformat(),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (PROFIT_COLUMN, PROFIT_PCT_COLUMN) and profit:
                    color = PROFIT_COLOR if profit[0] >= 0 else LOSS_COLOR
                    item.setForeground(QBrush(color))
                self.table.setItem(row, col, item)

        self._update_summary(display_currency)

    def _trade_value(
        self, trade: PaperTrade, display_currency: str
    ) -> Optional[tuple[float, float]]:
        """(market_value, cost_value) in the display currency, or None if the
        live price hasn't been fetched yet or a conversion rate failed."""
        market = self._market_prices.get(self._key(trade))
        if market is None:
            return None
        price_native, native_currency = market
        try:
            market_rate = self._currency_service.get_rate(native_currency, display_currency)
            cost_rate = self._currency_service.get_rate(trade.entry_currency, display_currency)
        except Exception:
            return None
        market_value = price_native * market_rate * trade.shares
        cost_value = trade.entry_price * cost_rate * trade.shares
        return market_value, cost_value

    def _trade_profit(
        self, trade: PaperTrade, display_currency: str
    ) -> Optional[tuple[float, float]]:
        values = self._trade_value(trade, display_currency)
        if values is None:
            return None
        market_value, cost_value = values
        if cost_value <= 0:
            return None
        profit = market_value - cost_value
        return profit, profit / cost_value * 100

    def _update_summary(self, display_currency: str) -> None:
        if not self._rows:
            self.summary_label.setText("No simulated positions yet.")
            self.summary_label.setStyleSheet("")
            return

        total_market = 0.0
        total_cost = 0.0
        priced_count = 0
        for trade in self._rows:
            values = self._trade_value(trade, display_currency)
            if values is None:
                continue
            priced_count += 1
            total_market += values[0]
            total_cost += values[1]

        if priced_count == 0 or total_cost <= 0:
            self.summary_label.setText(
                f'{len(self._rows)} position(s) — click "Refresh values" for totals.'
            )
            self.summary_label.setStyleSheet("")
            return

        total_profit = total_market - total_cost
        total_profit_pct = total_profit / total_cost * 100
        priced_note = "" if priced_count == len(self._rows) else f" ({priced_count}/{len(self._rows)} priced)"
        self.summary_label.setText(
            f"Total position value: {total_market:.2f} {display_currency}  ·  "
            f"Total profit: {self._format_signed(total_profit, display_currency)} "
            f"({total_profit_pct:+.1f}%){priced_note}"
        )
        color = PROFIT_COLOR if total_profit >= 0 else LOSS_COLOR
        self.summary_label.setStyleSheet(f"color: {color.name()}; font-weight: bold;")

    @staticmethod
    def _format_signed(amount: float, currency: str) -> str:
        sign = "+" if amount >= 0 else ""
        return f"{sign}{amount:.2f} {currency}"

    def _refresh_market_data(self) -> None:
        if not self._rows:
            self.refresh()
            return

        tickers = {self._key(t): t.ticker for t in self._rows}
        failed: list[str] = []
        for key, ticker in tickers.items():
            try:
                latest = self._scraper_service.get_latest_price(ticker)
                native_currency = self._scraper_service.get_ticker_currency(ticker)
                self._market_prices[key] = (latest.close, native_currency)
            except Exception:
                failed.append(str(ticker))
            if key not in self._names:
                try:
                    self._names[key] = self._scraper_service.get_ticker_name(ticker)
                except Exception:
                    pass

        if failed:
            QMessageBox.warning(
                self,
                "Some prices unavailable",
                "Couldn't fetch a live price for: " + ", ".join(failed),
            )

        self.refresh()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "Nothing selected", "Select a trade first.")
            return
        trade = self._rows[row]
        self._service.remove_trade(trade.id)
        self.refresh()
