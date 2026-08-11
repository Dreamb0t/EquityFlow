"""
Application-layer service for owned positions. The UI layer (desktop today,
web later) should only ever call into services/, never into data/ or
scrapers/ directly.
"""

from __future__ import annotations

from datetime import date

from stockapp.core.interfaces import Repository
from stockapp.core.models import Position, Ticker


class PortfolioService:
    def __init__(self, repository: Repository):
        self._repo = repository

    def add_position(
        self, symbol: str, shares: float, avg_cost: float, exchange: str | None = None
    ) -> None:
        self._repo.add_position(
            Position(
                ticker=Ticker(symbol, exchange),
                shares=shares,
                avg_cost=avg_cost,
                opened_at=date.today(),
            )
        )

    def remove_position(self, symbol: str, exchange: str | None = None) -> None:
        self._repo.remove_position(Ticker(symbol, exchange))

    def list_positions(self) -> list[Position]:
        return self._repo.list_positions()
