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
        yf_ticker = yf.Ticker(symbol)

        rate = self._from_fast_info(yf_ticker)
        if rate is None:
            rate = self._from_history(yf_ticker)
        if rate is None:
            raise RuntimeError(f"Could not fetch FX rate for {symbol}")
        return rate

    @staticmethod
    def _from_fast_info(yf_ticker) -> float | None:
        try:
            info = yf_ticker.fast_info
            price = info.get("last_price") if hasattr(info, "get") else None
            return float(price) if price else None
        except Exception:
            return None

    @staticmethod
    def _from_history(yf_ticker) -> float | None:
        try:
            df = yf_ticker.history(period="5d", interval="1d")
            if df.empty:
                return None
            return float(df["Close"].iloc[-1])
        except Exception:
            return None
