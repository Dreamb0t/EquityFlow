"""
Pure logic for the dashboard's timeframe picker (1 Day / 5 Days / 1 Month /
6 Months / 1 Year / custom N days). Kept separate from the Qt widget so the
day-count and intraday-vs-daily decisions are unit testable without a GUI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Timeframe:
    label: str
    days: int


# Ordered for display in the dashboard's dropdown.
PRESET_TIMEFRAMES: list[Timeframe] = [
    Timeframe("1 Day", 1),
    Timeframe("5 Days", 5),
    Timeframe("1 Month", 30),
    Timeframe("6 Months", 182),
    Timeframe("1 Year", 365),
]

CUSTOM_LABEL = "Custom..."


def is_intraday(days: int) -> bool:
    """1-day views plot intraday (minute-level) data with a time-only x-axis;
    anything longer plots daily bars with a date x-axis."""
    return days <= 1


def moving_average_window(num_points: int, target: int = 20) -> int:
    """Never ask for a longer window than the data actually has."""
    if num_points <= 0:
        return 1
    return max(1, min(target, num_points))
