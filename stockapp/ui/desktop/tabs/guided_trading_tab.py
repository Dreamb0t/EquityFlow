"""
Guided Trading tab: recommends stocks screened for strong growth indicators
(recent momentum + sustained 52-week appreciation), and lets the user add
them to Play Trading (simulated) or Portfolio (real) to try them out. Talks
only to GrowthScreenerService, PaperTradingService and PortfolioService — no
direct scraper/DB access.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stockapp.core.models import GrowthCandidate
from stockapp.services.growth_screener_service import GrowthScreenerService
from stockapp.services.paper_trading_service import PaperTradingService
from stockapp.services.portfolio_service import PortfolioService

COLUMNS = ["Name", "Symbol", "Price", "Currency", "1D %", "52W %", "Growth score"]
BULK_SHARES = 10


class GuidedTradingTab(QWidget):
    def __init__(
        self,
        screener_service: GrowthScreenerService,
        paper_trading_service: PaperTradingService,
        portfolio_service: PortfolioService,
        on_play_trading_change: Optional[Callable[[], None]] = None,
        on_portfolio_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._screener_service = screener_service
        self._paper_trading_service = paper_trading_service
        self._portfolio_service = portfolio_service
        self._on_play_trading_change = on_play_trading_change
        self._on_portfolio_change = on_portfolio_change

        self._candidates: list[GrowthCandidate] = []

        intro = QLabel(
            "Stocks screened for strong growth indicators (52-week appreciation, "
            "weighted above today's move). Add the selected stock to Play Trading "
            "(simulated, no real money) or Portfolio (real), or bulk-add every "
            "recommendation to Play Trading at once."
        )
        intro.setWordWrap(True)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        refresh_button = QPushButton("Refresh recommendations")
        refresh_button.clicked.connect(self._refresh)

        self.shares_input = QDoubleSpinBox()
        self.shares_input.setRange(0.0001, 1_000_000_000)
        self.shares_input.setDecimals(4)
        self.shares_input.setValue(1)
        self.shares_input.valueChanged.connect(self._update_button_labels)

        form = QFormLayout()
        form.addRow("Shares (X)", self.shares_input)

        # Selected-row actions.
        self.add_selected_play_button = QPushButton()
        self.add_selected_play_button.clicked.connect(self._add_selected_to_play_trading)
        self.add_selected_portfolio_button = QPushButton()
        self.add_selected_portfolio_button.clicked.connect(self._add_selected_to_portfolio)

        # Bulk actions — every current recommendation at once.
        self.add_bulk_fixed_button = QPushButton(
            f"Add {BULK_SHARES} of all to Play Trading"
        )
        self.add_bulk_fixed_button.clicked.connect(
            lambda: self._add_all_to_play_trading(BULK_SHARES)
        )
        self.add_bulk_x_button = QPushButton()
        self.add_bulk_x_button.clicked.connect(
            lambda: self._add_all_to_play_trading(self.shares_input.value())
        )

        buttons = QGridLayout()
        buttons.addWidget(refresh_button, 0, 0)
        buttons.addWidget(self.add_selected_play_button, 0, 1)
        buttons.addWidget(self.add_selected_portfolio_button, 0, 2)
        buttons.addWidget(self.add_bulk_x_button, 1, 0)
        buttons.addWidget(self.add_bulk_fixed_button, 1, 1)

        layout = QVBoxLayout()
        layout.addWidget(intro)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

        self._update_button_labels()
        self._populate(self._screener_service.get_recommendations())

    def _update_button_labels(self) -> None:
        shares = f"{self.shares_input.value():g}"
        self.add_selected_play_button.setText(f"Add {shares} to Play Trading")
        self.add_selected_portfolio_button.setText(f"Add {shares} to Portfolio")
        self.add_bulk_x_button.setText(f"Add {shares} of all to Play Trading")

    def _refresh(self) -> None:
        try:
            candidates = self._screener_service.get_recommendations(force_refresh=True)
        except Exception as exc:
            QMessageBox.warning(self, "Refresh failed", str(exc))
            return
        if not candidates:
            QMessageBox.information(
                self, "No recommendations", "Couldn't fetch any growth candidates right now."
            )
        self._populate(candidates)

    def _populate(self, candidates: list[GrowthCandidate]) -> None:
        self._candidates = candidates
        self.table.setRowCount(len(candidates))
        for row, c in enumerate(candidates):
            values = [
                c.name,
                str(c.ticker),
                f"{c.price:.2f}",
                c.currency,
                f"{c.day_change_pct:+.1f}%",
                f"{c.year_change_pct:+.1f}%",
                f"{c.growth_score:+.1f}",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _selected_candidate(self) -> Optional[GrowthCandidate]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._candidates):
            QMessageBox.information(
                self, "Nothing selected", "Select a recommended stock first."
            )
            return None
        return self._candidates[row]

    # --- selected-row actions ---
    def _add_selected_to_play_trading(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        shares = self.shares_input.value()
        self._paper_trading_service.add_trade(
            candidate.ticker, shares, candidate.price, candidate.currency
        )
        QMessageBox.information(
            self,
            "Added to Play Trading",
            f"Added {shares:g} simulated shares of {candidate.ticker} at "
            f"{candidate.price:.2f} {candidate.currency}.",
        )
        if self._on_play_trading_change:
            self._on_play_trading_change()

    def _add_selected_to_portfolio(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        shares = self.shares_input.value()
        self._portfolio_service.add_position(
            candidate.ticker.symbol,
            shares,
            candidate.price,
            candidate.currency,
            candidate.ticker.exchange,
        )
        QMessageBox.information(
            self,
            "Added to Portfolio",
            f"Added {shares:g} shares of {candidate.ticker} at "
            f"{candidate.price:.2f} {candidate.currency} to your portfolio.",
        )
        if self._on_portfolio_change:
            self._on_portfolio_change()

    # --- bulk actions ---
    def _add_all_to_play_trading(self, shares: float) -> None:
        if not self._candidates:
            QMessageBox.information(
                self, "No recommendations", "Refresh recommendations first."
            )
            return
        reply = QMessageBox.question(
            self,
            "Add all recommendations?",
            f"Add {shares:g} simulated shares of all {len(self._candidates)} "
            "recommended stocks to Play Trading?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for candidate in self._candidates:
            self._paper_trading_service.add_trade(
                candidate.ticker, shares, candidate.price, candidate.currency
            )
        QMessageBox.information(
            self,
            "Added to Play Trading",
            f"Added {shares:g} simulated shares of {len(self._candidates)} stocks.",
        )
        if self._on_play_trading_change:
            self._on_play_trading_change()
