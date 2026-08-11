"""
Desktop entrypoint. Deliberately thin: creates the Qt app, wires the container's
services into the main window, starts the background scheduler. All real logic
lives in services/ — this file (and main_window.py) is the only part that gets
replaced if/when this becomes a web app.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from stockapp.data.database import init_db
from stockapp.scheduler.jobs import start_scheduler
from stockapp.services.container import get_container
from stockapp.ui.desktop.main_window import MainWindow


def main() -> None:
    init_db()
    container = get_container()
    scheduler = start_scheduler()  # noqa: F841 — keep reference alive

    app = QApplication(sys.argv)
    window = MainWindow(container)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
