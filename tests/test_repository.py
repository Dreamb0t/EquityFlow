"""
Integration tests for the SQLite repository's id-based CRUD (positions +
watchlist), including the currency field. Uses a throwaway DB file per test
run via STOCKAPP_DATABASE_URL, set before stockapp.config.settings loads.
"""

import os
import tempfile
from datetime import date

import pytest


@pytest.fixture()
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["STOCKAPP_DATABASE_URL"] = f"sqlite:///{path}"

    # Settings/engine are created at import time, so make sure we get fresh
    # modules bound to this test's DB file rather than a cached one.
    import sys

    for mod in list(sys.modules):
        if mod.startswith("stockapp.config") or mod.startswith("stockapp.data"):
            del sys.modules[mod]

    from stockapp.data.database import init_db
    from stockapp.data.repository import SqlRepository

    init_db()
    yield SqlRepository()

    os.remove(path)


def test_add_and_list_position_round_trips_currency_and_id(repo):
    from stockapp.core.models import Position, Ticker

    position_id = repo.add_position(
        Position(
            ticker=Ticker("AAPL"),
            shares=10,
            avg_cost=150.0,
            opened_at=date.today(),
            currency="USD",
        )
    )
    positions = repo.list_positions()
    assert len(positions) == 1
    assert positions[0].id == position_id
    assert positions[0].currency == "USD"


def test_update_position_by_id(repo):
    from stockapp.core.models import Position, Ticker

    position_id = repo.add_position(
        Position(ticker=Ticker("AAPL"), shares=10, avg_cost=150.0, opened_at=date.today())
    )
    repo.update_position(
        Position(
            id=position_id,
            ticker=Ticker("AAPL"),
            shares=20,
            avg_cost=160.0,
            opened_at=date.today(),
            currency="DKK",
        )
    )
    positions = repo.list_positions()
    assert len(positions) == 1
    assert positions[0].shares == 20
    assert positions[0].avg_cost == 160.0
    assert positions[0].currency == "DKK"


def test_remove_position_by_id_only_removes_that_row(repo):
    from stockapp.core.models import Position, Ticker

    id_a = repo.add_position(
        Position(ticker=Ticker("AAPL"), shares=1, avg_cost=1, opened_at=date.today())
    )
    id_b = repo.add_position(
        Position(ticker=Ticker("AAPL"), shares=2, avg_cost=2, opened_at=date.today())
    )
    repo.remove_position(id_a)
    remaining = repo.list_positions()
    assert [p.id for p in remaining] == [id_b]


def test_watchlist_round_trips_currency_and_id(repo):
    from stockapp.core.models import Ticker, WatchlistItem

    item_id = repo.add_watchlist_item(
        WatchlistItem(
            ticker=Ticker("MSFT"),
            added_at=date.today(),
            target_price=300.0,
            currency="EUR",
        )
    )
    items = repo.list_watchlist()
    assert len(items) == 1
    assert items[0].id == item_id
    assert items[0].currency == "EUR"

    repo.remove_watchlist_item(item_id)
    assert repo.list_watchlist() == []


def test_get_price_history_includes_same_day_timestamps(repo):
    """Regression test: querying with end=date.today() must include rows
    timestamped later today. SQLite compares the DateTime column against a
    bare date string, and "2026-08-11T23:00:00" sorts AFTER "2026-08-11" —
    so an unnormalized bound silently dropped today's data. See
    SqlRepository.get_price_history."""
    from datetime import datetime, time, timedelta

    from stockapp.core.models import PricePoint, Ticker

    ticker = Ticker("AAPL")
    late_today = datetime.combine(date.today(), time(23, 0))
    repo.save_price_points([PricePoint(ticker=ticker, timestamp=late_today, close=100.0)])

    rows = repo.get_price_history(ticker, date.today() - timedelta(days=5), date.today())
    assert len(rows) == 1
    assert rows[0].timestamp == late_today
