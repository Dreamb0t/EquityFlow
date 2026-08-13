"""
Growth-stock screener via yfinance's predefined market screens. Kept separate
from PriceScraper since it queries a market-wide screen endpoint rather than
one ticker at a time — the Guided Trading tab's recommendation source.
"""

from __future__ import annotations

from stockapp.analysis.growth_screening import growth_score, rank_candidates
from stockapp.core.interfaces import StockScreener
from stockapp.core.models import GrowthCandidate, Ticker

# Growth-oriented predefined screens (see yfinance.PREDEFINED_SCREENER_QUERIES)
# — merged and re-ranked by our own growth_score rather than trusting any one
# query's internal ordering.
_GROWTH_QUERIES = [
    "growth_technology_stocks",
    "undervalued_growth_stocks",
    "small_cap_gainers",
    "aggressive_small_caps",
]


class YFinanceGrowthScreener(StockScreener):
    def find_growth_candidates(self, limit: int = 20) -> list[GrowthCandidate]:
        import yfinance as yf

        seen: dict[str, GrowthCandidate] = {}
        for query in _GROWTH_QUERIES:
            try:
                result = yf.screen(query, count=25)
                quotes = result.get("quotes", [])
            except Exception:
                continue

            for quote in quotes:
                symbol = quote.get("symbol")
                price = quote.get("regularMarketPrice")
                if not symbol or price is None or symbol in seen:
                    continue  # first (highest-priority) query's data wins

                day_change = quote.get("regularMarketChangePercent") or 0.0
                year_change = quote.get("fiftyTwoWeekChangePercent") or 0.0
                seen[symbol] = GrowthCandidate(
                    ticker=Ticker(symbol),
                    name=quote.get("shortName") or quote.get("longName") or symbol,
                    price=float(price),
                    currency=quote.get("currency") or "USD",
                    day_change_pct=day_change,
                    year_change_pct=year_change,
                    growth_score=growth_score(day_change, year_change),
                )

        return rank_candidates(list(seen.values()), limit)
