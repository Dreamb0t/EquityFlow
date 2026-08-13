"""
Pure logic for ranking Guided Trading's stock recommendations. Kept separate
from the screener scraper so the scoring/ranking rule is unit testable
without hitting Yahoo's screener endpoint.
"""

from __future__ import annotations

# Weighted toward sustained (52-week) growth over a single day's noise —
# "high growth", not "today's biggest mover".
YEAR_WEIGHT = 0.8
DAY_WEIGHT = 0.2


def growth_score(day_change_pct: float, year_change_pct: float) -> float:
    return year_change_pct * YEAR_WEIGHT + day_change_pct * DAY_WEIGHT


def rank_candidates(candidates: list, limit: int) -> list:
    """candidates: anything with a `.growth_score` attribute. Returns the
    top `limit`, highest score first."""
    return sorted(candidates, key=lambda c: c.growth_score, reverse=True)[:limit]
