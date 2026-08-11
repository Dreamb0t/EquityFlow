"""
Exchange rates via yfinance's FX tickers (e.g. "USDDKK=X"). Free, no API key —
good enough for display conversion; not for anything transactional.
"""

from __future__ import annotations

from stockapp.core.interfaces import FxRateProvider


class YFinanceFxRateProvider(FxRateProvider):
    def get_rate(self, base: str, quote: str) -> float:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0

        import yfinance as yf

        symbol = f"{base}{quote}=X"
        info = yf.Ticker(symbol).fast_info
        rate = info.get("last_price") if hasattr(info, "get") else None
        if not rate:
            raise RuntimeError(f"Could not fetch FX rate for {symbol}")
        return float(rate)
