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
| Growth chart + timeline dashboard (Must) | `services/dashboard_service.py`, `ui/desktop/widgets/chart_widget.py`, `ui/desktop/tabs/dashboard_tab.py` |
| Price + balance-sheet alerts (Must) | `alerts/alert_engine.py`, `alerts/notifiers.py`, `scheduler/jobs.py` |
| Watchlist + owned positions, editable (Must) | `services/watchlist_service.py`, `services/portfolio_service.py`, `ui/desktop/tabs/portfolio_tab.py` |
| Multi-currency, incl. DKK (Must) | `scrapers/fx_scraper.py`, `services/currency_service.py`, `services/app_state.py` |
| Portfolio allocation pie chart (Must) | `analysis/portfolio_analysis.py`, `ui/desktop/widgets/pie_chart_widget.py` |
| Basic analysis (Should) | `analysis/growth_analysis.py` |
| Share profiles / overview (Should) | not yet built — natural fit for the web version (`ui/web/` + multi-user `Repository`) |
| News scraping (Could) | `scrapers/news_scraper.py` (interface only, stubbed) |
| Trading capabilities (Could) | not started — would need a broker API integration behind a new interface |

## Multi-currency design

Two different "currency" concerns, handled differently:

- **User-entered prices** (a position's avg cost, a watchlist target price) are
  stored with an explicit `currency` field, chosen by the user at entry time
  (defaults to the app's current display currency). This is deliberate —
  what a broker actually charged can differ from a ticker's home-exchange
  currency (e.g. FX-hedged purchases), so it's not inferred.
- **Live/historical market prices** (from `PriceScraper`) are in the ticker's
  native trading currency, looked up via `PriceScraper.get_currency()` /
  `ScraperService.get_ticker_currency()` (cached per ticker for the process
  lifetime — a listing's currency doesn't change).

Both get converted to the user's selected **display currency** on render,
via `CurrencyService.convert()`, which wraps `FxRateProvider` (implemented by
`YFinanceFxRateProvider`) with a 15-minute cache. The selected display
currency itself lives in `services/app_state.py` (`AppState`), persisted to
`~/.stockapp/app_state.json`, with an observer list (`on_change`) tabs
subscribe to so switching currency in the toolbar re-renders every
currency-dependent value across tabs. `SUPPORTED_CURRENCIES` in
`currency_service.py` currently covers USD, EUR, DKK, GBP, SEK, NOK.

Note the portfolio pie chart does *not* need to re-fetch on a currency
change: converting every position through the same target currency scales
every slice by the same factor, so allocation percentages are invariant to
which display currency is selected (see
`tests/test_portfolio_analysis.py::test_currency_target_invariance`).

## Dashboard timeframes

`analysis/timeframes.py` defines the preset options (1 Day / 5 Days / 1
Month / 6 Months / 1 Year) plus a custom day count. 1-day selections fetch
live intraday (~5-minute) bars via `ScraperService.fetch_intraday()` and are
plotted with a time-only x-axis; anything longer reads/writes daily bars
through the repository cache and is plotted with a date x-axis
(`ui/desktop/widgets/chart_widget.py` picks the formatter based on
`DashboardSeries.intraday`). Intraday data is intentionally not cached in
the DB — the `price_points` table only holds daily bars, and mixing
granularities there would corrupt the daily-based analytics (moving
averages, day-over-day alerts).

## Editable portfolio + ids

`Position` and `WatchlistItem` now carry an `id` (populated by the
repository), and `Repository`/`PortfolioService`/`WatchlistService` operate
on ids rather than symbol+exchange — this is what makes editing safe (a
position's symbol/exchange can change without losing its identity) and fixes
a latent bug where removing "by ticker" could've matched more than one row.
`PortfolioTab`'s edit flow: select a row -> "Edit selected" loads it into the
existing add-form, which becomes "Save changes" until submitted or cancelled.

## Known gaps to fill in next

1. **Balance sheet source**: `YFinanceBalanceSheetScraper` works out of the box;
   `HtmlBalanceSheetScraper` is a skeleton for scraping a specific site directly —
   `_parse()` needs a chosen target site's table layout. `docs/notes.md`
   flags virk.dk as a candidate.
2. **Email alerts are opt-in**: the app runs fine with no `.env` at all — alerts
   just show up in the Alerts tab / in-app queue. `container.py` only wires in
   `EmailNotifier` if `STOCKAPP_SMTP_HOST` and `STOCKAPP_ALERT_EMAIL_TO` are
   set, so no credentials are required to run or test the app. Copy
   `.env.example` to `.env` and fill in `STOCKAPP_SMTP_*` when you want email
   too.
3. **Watchlist editing**: only Portfolio supports the select-and-edit flow so
   far; Watchlist is still add/remove-only (id-based, so extending it later
   is a small change).
4. **No P/L column** on the portfolio table yet — market value is computed
   for the pie chart but not shown per-row.

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
