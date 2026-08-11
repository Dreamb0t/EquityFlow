"""
Price data via yfinance (wraps Yahoo Finance — free, no key required, and gives
both live quotes and history in one call). Swappable: anything implementing
PriceScraper works, e.g. a broker API later.
"""

from __future__ import annotations

from datetime import date, datetime

from stockapp.core.interfaces import PriceScraper
from stockapp.core.models import PricePoint, Ticker


class YFinancePriceScraper(PriceScraper):
    def get_latest_price(self, ticker: Ticker) -> PricePoint:
        import yfinance as yf

        yf_ticker = yf.Ticker(str(ticker))

        # fast_info is, despite the name, the flakier of the two — it's known
        # to intermittently miss keys or raise for some tickers. Try it first
        # (it's a single lightweight call), but always have a working
        # fallback via history(), which is what the dashboard's chart data
        # uses and is far more reliable.
        fields = self._fast_info_fields(yf_ticker)
        if fields is None:
            fields = self._history_fallback_fields(yf_ticker)
        if fields is None:
            raise RuntimeError(f"Could not fetch a live price for {ticker}")

        close, open_, high, low, volume = fields
        return PricePoint(
            ticker=ticker,
            timestamp=datetime.now(),
            close=close,
            open=open_,
            high=high,
            low=low,
            volume=volume,
        )

    @staticmethod
    def _fast_info_fields(yf_ticker):
        try:
            info = yf_ticker.fast_info
            price = info.get("last_price") if hasattr(info, "get") else None
            if not price:
                return None
            return (
                float(price),
                info.get("open"),
                info.get("day_high"),
                info.get("day_low"),
                info.get("last_volume"),
            )
        except Exception:
            return None

    @staticmethod
    def _history_fallback_fields(yf_ticker):
        try:
            df = yf_ticker.history(period="5d", interval="1d")
            if df.empty:
                return None
            last = df.iloc[-1]
            return (
                float(last["Close"]),
                float(last["Open"]) if "Open" in last else None,
                float(last["High"]) if "High" in last else None,
                float(last["Low"]) if "Low" in last else None,
                int(last["Volume"]) if "Volume" in last else None,
            )
        except Exception:
            return None

    def get_price_history(
        self, ticker: Ticker, start: date, end: date, interval: str = "1d"
    ) -> list[PricePoint]:
        import yfinance as yf

        df = yf.Ticker(str(ticker)).history(start=start, end=end, interval=interval)
        return [
            PricePoint(
                ticker=ticker,
                timestamp=idx.to_pydatetime(),
                close=row["Close"],
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]

    def get_currency(self, ticker: Ticker) -> str:
        import yfinance as yf

        yf_ticker = yf.Ticker(str(ticker))

        try:
            info = yf_ticker.fast_info
            currency = info.get("currency") if hasattr(info, "get") else None
            if currency:
                return currency.upper()
        except Exception:
            pass

        # fast_info dropped it — fall back to the slower but more complete
        # .info dict before giving up and assuming USD.
        try:
            currency = yf_ticker.info.get("currency")
            if currency:
                return currency.upper()
        except Exception:
            pass

        return "USD"
