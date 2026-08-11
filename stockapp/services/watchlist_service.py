from __future__ import annotations

from datetime import date

from stockapp.core.interfaces import Repository
from stockapp.core.models import Ticker, WatchlistItem


class WatchlistService:
    def __init__(self, repository: Repository):
        self._repo = repository

    def add(
        self,
        symbol: str,
        exchange: str | None = None,
        note: str = "",
        target_price: float | None = None,
    ) -> None:
        self._repo.add_watchlist_item(
            WatchlistItem(
                ticker=Ticker(symbol, exchange),
                added_at=date.today(),
                note=note,
                target_price=target_price,
            )
        )

    def remove(self, symbol: str, exchange: str | None = None) -> None:
        self._repo.remove_watchlist_item(Ticker(symbol, exchange))

    def list(self) -> list[WatchlistItem]:
        return self._repo.list_watchlist()
