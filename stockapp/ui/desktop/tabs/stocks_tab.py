"""
Stocks tab: search for a stock (autocomplete over ticker/company name, same
as Guided Trading's add flow) and add it — to Portfolio (real), Play Trading
(simulated), or both at once. This is the only place new stocks get added;
Portfolio only views/edits/removes what's already there. Talks only to
ScraperService (symbol search), PortfolioService and PaperTradingService —
no direct DB/scraper access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stockapp.core.models import SymbolMatch, Ticker
from stockapp.services.app_state import AppState
from stockapp.services.currency_service import SUPPORTED_CURRENCIES
from stockapp.services.paper_trading_service import PaperTradingService
from stockapp.services.portfolio_service import PortfolioService
from stockapp.services.scraper_service import ScraperService


class StocksTab(QWidget):
    def __init__(
        self,
        scraper_service: ScraperService,
        portfolio_service: PortfolioService,
        paper_trading_service: PaperTradingService,
        app_state: AppState,
        on_portfolio_change: Optional[Callable[[], None]] = None,
        on_play_trading_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._scraper_service = scraper_service
        self._portfolio_service = portfolio_service
        self._paper_trading_service = paper_trading_service
        self._app_state = app_state
        self._on_portfolio_change = on_portfolio_change
        self._on_play_trading_change = on_play_trading_change

        self._symbol_matches: list[SymbolMatch] = []

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
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.0001, 1_000_000_000)
        self.price_input.setDecimals(2)
        self.currency_input = QComboBox()
        self.currency_input.addItems(SUPPORTED_CURRENCIES)

        self.portfolio_checkbox = QCheckBox("Portfolio")
        self.play_trading_checkbox = QCheckBox("Play Trading")

        destination_row = QHBoxLayout()
        destination_row.addWidget(self.portfolio_checkbox)
        destination_row.addWidget(self.play_trading_checkbox)
        destination_row.addStretch()

        form = QFormLayout()
        form.addRow("Symbol", symbol_field)
        form.addRow("Exchange (optional)", self.exchange_input)
        form.addRow("Shares", self.shares_input)
        form.addRow("Price", self.price_input)
        form.addRow("Currency", self.currency_input)
        form.addRow("Add to", destination_row)

        add_button = QPushButton("Add stock")
        add_button.clicked.connect(self._add_stock)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(add_button)
        layout.addStretch()
        self.setLayout(layout)

        self.currency_input.setCurrentText(self._app_state.display_currency)
        self._app_state.on_change(self._on_currency_changed)

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

    # --- add ---
    def _add_stock(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Missing symbol", "Enter a ticker symbol.")
            return

        to_portfolio = self.portfolio_checkbox.isChecked()
        to_play_trading = self.play_trading_checkbox.isChecked()
        if not to_portfolio and not to_play_trading:
            QMessageBox.warning(
                self, "Nothing to do", "Check Portfolio, Play Trading, or both."
            )
            return

        exchange = self.exchange_input.text().strip().upper() or None
        shares = self.shares_input.value()
        price = self.price_input.value()
        currency = self.currency_input.currentText()

        destinations = []
        if to_portfolio:
            self._portfolio_service.add_position(symbol, shares, price, currency, exchange)
            destinations.append("Portfolio")
            if self._on_portfolio_change:
                self._on_portfolio_change()
        if to_play_trading:
            self._paper_trading_service.add_trade(
                Ticker(symbol, exchange), shares, price, currency
            )
            destinations.append("Play Trading")
            if self._on_play_trading_change:
                self._on_play_trading_change()

        ticker_label = f"{symbol}.{exchange}" if exchange else symbol
        QMessageBox.information(
            self,
            "Added",
            f"Added {shares:g} shares of {ticker_label} at {price:.2f} {currency} to "
            + " and ".join(destinations)
            + ".",
        )
        self._clear_form()

    def _clear_form(self) -> None:
        self.symbol_input.clear()
        self.exchange_input.clear()
        self.shares_input.setValue(self.shares_input.minimum())
        self.price_input.setValue(self.price_input.minimum())
        self.currency_input.setCurrentText(self._app_state.display_currency)
        self.portfolio_checkbox.setChecked(False)
        self.play_trading_checkbox.setChecked(False)
        self._hide_symbol_suggestions()

    def _on_currency_changed(self) -> None:
        self.currency_input.setCurrentText(self._app_state.display_currency)
