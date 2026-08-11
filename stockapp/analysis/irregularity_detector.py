"""
Rule-based checks over consecutive balance sheet snapshots. Starting point is
simple threshold rules; swap in something statistical later without touching
callers (alerts/alert_engine.py just consumes the list of findings).
"""

from __future__ import annotations

from dataclasses import dataclass

from stockapp.core.models import BalanceSheetSnapshot


@dataclass
class Irregularity:
    description: str
    severity: str  # "warning" | "critical"


def detect(history: list[BalanceSheetSnapshot]) -> list[Irregularity]:
    """history must be sorted oldest -> newest."""
    if len(history) < 2:
        return []

    findings: list[Irregularity] = []
    prev, latest = history[-2], history[-1]

    findings.extend(_check_debt_spike(prev, latest))
    findings.extend(_check_equity_drop(prev, latest))
    findings.extend(_check_liabilities_outpacing_assets(prev, latest))
    return findings


def _pct_change(old: float | None, new: float | None) -> float | None:
    if old in (None, 0) or new is None:
        return None
    return (new - old) / old * 100


def _check_debt_spike(
    prev: BalanceSheetSnapshot, latest: BalanceSheetSnapshot, threshold_pct: float = 25
) -> list[Irregularity]:
    change = _pct_change(prev.total_debt, latest.total_debt)
    if change is not None and change >= threshold_pct:
        return [
            Irregularity(
                f"Total debt jumped {change:.1f}% quarter-over-quarter", "warning"
            )
        ]
    return []


def _check_equity_drop(
    prev: BalanceSheetSnapshot, latest: BalanceSheetSnapshot, threshold_pct: float = -15
) -> list[Irregularity]:
    change = _pct_change(prev.total_equity, latest.total_equity)
    if change is not None and change <= threshold_pct:
        return [
            Irregularity(
                f"Stockholders' equity dropped {change:.1f}% quarter-over-quarter",
                "critical",
            )
        ]
    return []


def _check_liabilities_outpacing_assets(
    prev: BalanceSheetSnapshot, latest: BalanceSheetSnapshot
) -> list[Irregularity]:
    if not (prev.total_assets and prev.total_liabilities and latest.total_assets):
        return []
    prev_ratio = prev.total_liabilities / prev.total_assets
    if not latest.total_liabilities:
        return []
    latest_ratio = latest.total_liabilities / latest.total_assets
    if latest_ratio > prev_ratio * 1.2 and latest_ratio > 0.7:
        return [
            Irregularity(
                f"Liabilities-to-assets ratio rose to {latest_ratio:.2f}", "warning"
            )
        ]
    return []
