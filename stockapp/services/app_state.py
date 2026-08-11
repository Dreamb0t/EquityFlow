"""
Small mutable, observable app-wide state — currently just the selected display
currency. Deliberately kept out of core/ since it's UI-facing session state,
not domain data: a future web version would keep one of these per user/session
instead of one per desktop process, but the shape (a value + change listeners)
stays useful.

Persisted to a JSON file next to the SQLite DB so the choice survives restarts
without needing a DB migration.
"""

from __future__ import annotations

import json
from typing import Callable

from stockapp.config.settings import APP_DIR, settings

STATE_FILE = APP_DIR / "app_state.json"


class AppState:
    def __init__(self):
        self.display_currency: str = self._load_display_currency() or settings.display_currency
        self._listeners: list[Callable[[], None]] = []

    def _load_display_currency(self) -> str | None:
        if not STATE_FILE.exists():
            return None
        try:
            data = json.loads(STATE_FILE.read_text())
            return data.get("display_currency")
        except (json.JSONDecodeError, OSError):
            return None

    def set_display_currency(self, currency: str) -> None:
        currency = currency.upper()
        if currency == self.display_currency:
            return
        self.display_currency = currency
        self._persist()
        for listener in list(self._listeners):
            listener()

    def _persist(self) -> None:
        try:
            STATE_FILE.write_text(json.dumps({"display_currency": self.display_currency}))
        except OSError:
            pass  # non-fatal — just means the choice won't survive a restart

    def on_change(self, callback: Callable[[], None]) -> None:
        """Register a callback fired (with no args) whenever display_currency
        changes. Tabs use this to re-render currency-dependent values."""
        self._listeners.append(callback)
