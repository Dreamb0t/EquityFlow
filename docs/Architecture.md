        # Stock App — Architecture

A personal, local desktop app for tracking owned stocks and a watchlist: scraped
balance sheets, a growth/timeline dashboard, and price + balance-sheet-irregularity
alerts (in-app and email). Built as a layered architecture so it can become a web
app later without rewriting the business logic.

## Layers

```
ui/desktop/          Qt windows and widgets. Calls services/ only.
        |
services/            Application logic: orchestrates core + data + scrapers + alerts.
        |             This is the layer a future web backend (FastAPI routes) would
        |             call instead of ui/desktop/ — everything below is reused as-is.
        |
core/                 interfaces.py (ports: Repository, PriceScraper,
        |             BalanceSheetScraper, NewsScraper, Notifier) and
        |             models.py (framework-free dataclasses: Ticker, Position,
        |             WatchlistItem, BalanceSheetSnapshot, PricePoint, Alert)
        |
data/                 SQLAlchemy + SQLite implementation of Repository.
scrapers/             yfinance-based Price/BalanceSheet scrapers + an HTML scraper
                      skeleton for a specific source once one is chosen.
analysis/             Pure functions: growth metrics, moving averages, volatility,
                      rule-based balance-sheet irregularity detection.
alerts/               alert_engine.py (pure logic) + notifiers.py (InAppNotifier,
                      EmailNotifier).
scheduler/            APScheduler background job that periodically refreshes data
                      and re-runs alert checks.
config/               Single Settings object (pydantic-settings), reads .env.
```

Dependency direction is strictly inward: `ui -> services -> core interfaces`.
`data/`, `scrapers/`, `alerts/notifiers.py` implement those interfaces but are
never imported by `services/` directly — they're wired together once, in
`services/container.py`. That's the seam a web version plugs into: same
`Container`, new `ui/web/` package with FastAPI routes calling the same
services.

## Feature -> module map

| Requirement (from project brief) | Where it lives |
|---|---|
| Web scrape balance sheets (Must) | `scrapers/balance_sheet_scraper.py` |
| Growth chart + timeline dashboard (Must) | `services/dashboard_service.py`, `ui/desktop/widgets/chart_widget.py` |
| Price + balance-sheet alerts (Must) | `alerts/alert_engine.py`, `alerts/notifiers.py`, `scheduler/jobs.py` |
| Watchlist + owned positions (Must) | `services/watchlist_service.py`, `services/portfolio_service.py` |
| Basic analysis (Should) | `analysis/growth_analysis.py` |
| Share profiles / overview (Should) | not yet built — natural fit for the web version (`ui/web/` + multi-user `Repository`) |
| News scraping (Could) | `scrapers/news_scraper.py` (interface only, stubbed) |
| Trading capabilities (Could) | not started — would need a broker API integration behind a new interface |

## Known gaps to fill in next

1. **Balance sheet source**: `YFinanceBalanceSheetScraper` works out of the box;
   `HtmlBalanceSheetScraper` is a skeleton for scraping a specific site directly —
   `_parse()` needs a chosen target site's table layout.
2. **Email alerts**: SMTP settings are unset by default — copy `.env.example` to
   `.env` and fill in `STOCKAPP_SMTP_*`.
3. **UI content**: `main_window.py` has four placeholder tabs (Dashboard,
   Portfolio, Watchlist, Alerts) — wire real tables/forms to the services.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in SMTP credentials for email alerts
python main.py
```

## Tests

```bash
pytest
```

`tests/test_analysis.py` covers the pure-logic layers (analysis + alert engine) —
no DB or network needed.
