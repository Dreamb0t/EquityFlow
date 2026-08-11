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

        info = yf.Ticker(str(ticker)).fast_info
        return PricePoint(
            ticker=ticker,
            timestamp=datetime.now(),
            close=info["last_price"],
            open=info.get("open"),
            high=info.get("day_high"),
            low=info.get("day_low"),
            volume=info.get("last_volume"),
        )

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

        info = yf.Ticker(str(ticker)).fast_info
        currency = info.get("currency") if hasattr(info, "get") else None
        return (currency or "USD").upper()
