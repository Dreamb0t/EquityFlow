"""
Application-layer service for paper ("Play Trading") positions — simulated
buys added from Guided Trading recommendations, tracked without real money.
The UI layer should only ever call into services/, never into data/ directly.
"""

from __future__ import annotations

from datetime import date

from stockapp.core.interfaces import Repository
from stockapp.core.models import PaperTrade, Ticker


class PaperTradingService:
    def __init__(self, repository: Repository):
        self._repo = repository

    def add_trade(
        self, ticker: Ticker, shares: float, entry_price: float, entry_currency: str
    ) -> int:
        return self._repo.add_paper_trade(
            PaperTrade(
                ticker=ticker,
                shares=shares,
                entry_price=entry_price,
                entry_currency=entry_currency,
                opened_at=date.today(),
            )
        )

    def list_trades(self) -> list[PaperTrade]:
        return self._repo.list_paper_trades()

    def remove_trade(self, trade_id: int) -> None:
        self._repo.remove_paper_trade(trade_id)
