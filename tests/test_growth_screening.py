from dataclasses import dataclass

from stockapp.analysis.growth_screening import growth_score, rank_candidates


def test_growth_score_weights_year_change_above_day_change():
    steady_grower = growth_score(day_change_pct=0.0, year_change_pct=100.0)
    todays_spike = growth_score(day_change_pct=100.0, year_change_pct=0.0)
    assert steady_grower > todays_spike


def test_growth_score_matches_weighted_formula():
    assert growth_score(day_change_pct=10.0, year_change_pct=50.0) == 50.0 * 0.8 + 10.0 * 0.2


@dataclass
class _Candidate:
    growth_score: float


def test_rank_candidates_sorts_descending_and_limits():
    candidates = [_Candidate(growth_score=s) for s in [5.0, 50.0, 20.0, -10.0]]
    ranked = rank_candidates(candidates, limit=2)
    assert [c.growth_score for c in ranked] == [50.0, 20.0]


def test_rank_candidates_handles_empty():
    assert rank_candidates([], limit=5) == []
