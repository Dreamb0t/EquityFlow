"""
Concrete Repository implementation backed by SQLite/SQLAlchemy.
Everything above this file (services/) talks to the Repository interface only,
never to these ORM rows directly.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable, Optional

from stockapp.core.interfaces import Repository
from stockapp.core.models import (
    Alert,
    AlertSeverity,
    AlertType,
    BalanceSheetSnapshot,
    PaperTrade,
    PricePoint,
    Position,
    Ticker,
    WatchlistItem,
)
from stockapp.data.database import get_session
from stockapp.data.orm_models import (
    AlertRow,
    BalanceSheetRow,
    PaperTradeRow,
    PositionRow,
    PricePointRow,
    WatchlistRow,
)


class SqlRepository(Repository):
    # --- Positions ---
    def add_position(self, position: Position) -> int:
        with get_session() as s:
            row = PositionRow(
                symbol=position.ticker.symbol,
                exchange=position.ticker.exchange,
                shares=position.shares,
                avg_cost=position.avg_cost,
                opened_at=position.opened_at,
                currency=position.currency,
            )
            s.add(row)
            s.flush()
            return row.id

    def update_position(self, position: Position) -> None:
        if position.id is None:
            raise ValueError("update_position requires an id")
        with get_session() as s:
            row = s.get(PositionRow, position.id)
            if row is None:
                raise ValueError(f"No position with id {position.id}")
            row.symbol = position.ticker.symbol
            row.exchange = position.ticker.exchange
            row.shares = position.shares
            row.avg_cost = position.avg_cost
            row.currency = position.currency

    def list_positions(self) -> list[Position]:
        with get_session() as s:
            rows = s.query(PositionRow).all()
            return [
                Position(
                    ticker=Ticker(r.symbol, r.exchange),
                    shares=r.shares,
                    avg_cost=r.avg_cost,
                    opened_at=r.opened_at,
                    currency=r.currency or "USD",
                    id=r.id,
                )
                for r in rows
            ]

    def remove_position(self, position_id: int) -> None:
        with get_session() as s:
            s.query(PositionRow).filter_by(id=position_id).delete()

    # --- Watchlist ---
    def add_watchlist_item(self, item: WatchlistItem) -> int:
        with get_session() as s:
            row = WatchlistRow(
                symbol=item.ticker.symbol,
                exchange=item.ticker.exchange,
                added_at=item.added_at,
                note=item.note,
                target_price=item.target_price,
                currency=item.currency,
            )
            s.add(row)
            s.flush()
            return row.id

    def update_watchlist_item(self, item: WatchlistItem) -> None:
        if item.id is None:
            raise ValueError("update_watchlist_item requires an id")
        with get_session() as s:
            row = s.get(WatchlistRow, item.id)
            if row is None:
                raise ValueError(f"No watchlist item with id {item.id}")
            row.symbol = item.ticker.symbol
            row.exchange = item.ticker.exchange
            row.note = item.note
            row.target_price = item.target_price
            row.currency = item.currency

    def list_watchlist(self) -> list[WatchlistItem]:
        with get_session() as s:
            rows = s.query(WatchlistRow).all()
            return [
                WatchlistItem(
                    ticker=Ticker(r.symbol, r.exchange),
                    added_at=r.added_at,
                    note=r.note,
                    target_price=r.target_price,
                    currency=r.currency or "USD",
                    id=r.id,
                )
                for r in rows
            ]

    def remove_watchlist_item(self, item_id: int) -> None:
        with get_session() as s:
            s.query(WatchlistRow).filter_by(id=item_id).delete()

    # --- Price history (cache of scraped data) ---
    def save_price_points(self, points: Iterable[PricePoint]) -> None:
        with get_session() as s:
            for p in points:
                s.add(
                    PricePointRow(
                        symbol=p.ticker.symbol,
                        exchange=p.ticker.exchange,
                        timestamp=p.timestamp,
                        open=p.open,
                        high=p.high,
                        low=p.low,
                        close=p.close,
                        volume=p.volume,
                    )
                )

    def get_price_history(self, ticker: Ticker, start, end) -> list[PricePoint]:
        # start/end may be plain `date` objects (callers commonly pass
        # date.today()). Comparing a DateTime column against a bare date
        # string is a trap in SQLite: "2026-08-11T00:00:00" sorts AFTER the
        # bare string "2026-08-11", so a same-day timestamp <= date.today()
        # silently evaluates False and today's row vanishes from the range.
        # Normalize to full-day bounds so "today" is actually included.
        start = datetime.combine(start, time.min) if not isinstance(start, datetime) else start
        end = datetime.combine(end, time.max) if not isinstance(end, datetime) else end

        with get_session() as s:
            rows = (
                s.query(PricePointRow)
                .filter(
                    PricePointRow.symbol == ticker.symbol,
                    PricePointRow.exchange == ticker.exchange,
                    PricePointRow.timestamp >= start,
                    PricePointRow.timestamp <= end,
                )
                .order_by(PricePointRow.timestamp)
                .all()
            )
            return [
                PricePoint(
                    ticker=ticker,
                    timestamp=r.timestamp,
                    close=r.close,
                    open=r.open,
                    high=r.high,
                    low=r.low,
                    volume=r.volume,
                )
                for r in rows
            ]

    # --- Balance sheets ---
    def save_balance_sheets(self, snapshots: Iterable[BalanceSheetSnapshot]) -> None:
        with get_session() as s:
            for b in snapshots:
                s.add(
                    BalanceSheetRow(
                        symbol=b.ticker.symbol,
                        exchange=b.ticker.exchange,
                        period_end=b.period_end,
                        total_assets=b.total_assets,
                        total_liabilities=b.total_liabilities,
                        total_equity=b.total_equity,
                        cash_and_equivalents=b.cash_and_equivalents,
                        total_debt=b.total_debt,
                        source=b.source,
                        raw=b.raw,
                    )
                )

    def get_balance_sheet_history(self, ticker: Ticker) -> list[BalanceSheetSnapshot]:
        with get_session() as s:
            rows = (
                s.query(BalanceSheetRow)
                .filter_by(symbol=ticker.symbol, exchange=ticker.exchange)
                .order_by(BalanceSheetRow.period_end)
                .all()
            )
            return [
                BalanceSheetSnapshot(
                    ticker=ticker,
                    period_end=r.period_end,
                    total_assets=r.total_assets,
                    total_liabilities=r.total_liabilities,
                    total_equity=r.total_equity,
                    cash_and_equivalents=r.cash_and_equivalents,
                    total_debt=r.total_debt,
                    source=r.source,
                    raw=r.raw or {},
                )
                for r in rows
            ]

    # --- Alerts ---
    def save_alert(self, alert: Alert) -> None:
        with get_session() as s:
            s.add(
                AlertRow(
                    symbol=alert.ticker.symbol,
                    exchange=alert.ticker.exchange,
                    type=alert.type.value,
                    severity=alert.severity.value,
                    message=alert.message,
                    triggered_at=alert.triggered_at,
                    acknowledged=alert.acknowledged,
                )
            )

    def list_alerts(self, since: Optional[datetime] = None) -> list[Alert]:
        with get_session() as s:
            q = s.query(AlertRow)
            if since:
                q = q.filter(AlertRow.triggered_at >= since)
            rows = q.order_by(AlertRow.triggered_at.desc()).all()
            return [
                Alert(
                    ticker=Ticker(r.symbol, r.exchange),
                    type=AlertType(r.type),
                    severity=AlertSeverity(r.severity),
                    message=r.message,
                    triggered_at=r.triggered_at,
                    acknowledged=r.acknowledged,
                )
                for r in rows
            ]

    # --- Paper trades ("Play Trading") ---
    def add_paper_trade(self, trade: PaperTrade) -> int:
        with get_session() as s:
            row = PaperTradeRow(
                symbol=trade.ticker.symbol,
                exchange=trade.ticker.exchange,
                shares=trade.shares,
                entry_price=trade.entry_price,
                entry_currency=trade.entry_currency,
                opened_at=trade.opened_at,
            )
            s.add(row)
            s.flush()
            return row.id

    def list_paper_trades(self) -> list[PaperTrade]:
        with get_session() as s:
            rows = s.query(PaperTradeRow).all()
            return [
                PaperTrade(
                    ticker=Ticker(r.symbol, r.exchange),
                    shares=r.shares,
                    entry_price=r.entry_price,
                    entry_currency=r.entry_currency or "USD",
                    opened_at=r.opened_at,
                    id=r.id,
                )
                for r in rows
            ]

    def remove_paper_trade(self, trade_id: int) -> None:
        with get_session() as s:
            s.query(PaperTradeRow).filter_by(id=trade_id).delete()
