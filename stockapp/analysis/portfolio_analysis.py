"""
Pure math for the portfolio allocation pie chart: turns per-position values
into percentages of the whole. No currency/network concerns here — callers
pass in values already converted to a single common currency.
"""

from __future__ import annotations


def compute_distribution(values: dict[str, float]) -> dict[str, float]:
    """values: label -> value (e.g. ticker -> market value, all in the same
    currency). Returns label -> percentage of total (0-100), dropping any
    non-positive entries. An empty/all-zero input returns {}."""
    total = sum(v for v in values.values() if v > 0)
    if total <= 0:
        return {}
    return {label: (value / total) * 100 for label, value in values.items() if value > 0}
