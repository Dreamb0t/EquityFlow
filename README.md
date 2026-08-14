# EquityFlow

EquityFlow is a desktop app for tracking stocks: a live dashboard, an editable
portfolio with profit/loss tracking, a watchlist, price/balance-sheet alerts,
and two tools for exploring new ideas — Guided Trading (growth-stock
recommendations) and Play Trading (a paper-trading sandbox to try them out
before risking real money).

> **Disclaimer:** EquityFlow is for informational and educational purposes
> only. It is not financial advice, and nothing in the app is a
> recommendation to buy or sell any security.

## Getting started

**Requirements:** Python 3.10+ and an internet connection (live prices are
fetched from Yahoo Finance).

```bash
pip install -r requirements.txt
python main.py
```

On first run, EquityFlow creates a local SQLite database at
`~/.stockapp/stockapp.db` — no setup required. Your portfolio, watchlist,
alerts, and play trades all live there.

### Optional configuration

Settings are read from environment variables (or a `.env` file in the project
root) prefixed with `STOCKAPP_`. Everything has a sensible default; the only
one most people will ever touch is email alerts:

| Variable | Purpose | Default |
|---|---|---|
| `STOCKAPP_DATABASE_URL` | Where the SQLite DB lives | `~/.stockapp/stockapp.db` |
| `STOCKAPP_DISPLAY_CURRENCY` | Currency shown on first run | `USD` |
| `STOCKAPP_PRICE_MOVE_ALERT_PCT` | % move that triggers a price alert | `5.0` |
| `STOCKAPP_ALERT_CHECK_INTERVAL_MINUTES` | How often the background checker runs | `30` |
| `STOCKAPP_SMTP_HOST`, `STOCKAPP_SMTP_PORT`, `STOCKAPP_SMTP_USERNAME`, `STOCKAPP_SMTP_PASSWORD` | SMTP server for email alerts | unset (email disabled) |
| `STOCKAPP_ALERT_EMAIL_TO`, `STOCKAPP_ALERT_EMAIL_FROM` | Email alert addresses | unset |

Email alerts are entirely optional — without SMTP configured, alerts still
work, they just show up in-app instead of by email.

## The display currency

The toolbar at the top has a currency picker (USD, EUR, DKK, GBP, SEK, NOK).
It converts every price shown across every tab — it doesn't change what
currency a stock actually trades in, or what currency you recorded a
purchase in; those are tracked separately per position so nothing is lost in
translation.

## Tour of the tabs

### Dashboard

Pick a ticker (from your portfolio or watchlist) and a timeframe — 1 Day, 5
Days, 1 Month, 6 Months, 1 Year, or a custom number of days — then click
**Fetch latest data**. The 1-day view plots 5-minute intraday bars across the
full trading session; longer timeframes plot daily bars. The chart fetches
automatically once when the app starts, so you're not staring at a blank
graph.

### Stocks

The only place new stocks get added. Start typing a symbol or company name
and pick a match from the suggestions — this matters for companies listed on
multiple exchanges (e.g. Novo Nordisk trades as `NVO` on the NYSE and
`NOVO-B.CO` on Copenhagen; picking the wrong one gets you the wrong trading
hours and currency). Enter shares, price, and currency, then choose where it
goes: **Portfolio**, **Play Trading**, or both at once.

### Portfolio

Your real holdings, grouped by stock — expand a row to see the individual
buy lots (so buying the same stock at different prices over time stays
readable). Click **Refresh values** to pull live prices and see profit/loss
per stock and overall (green for gains, red for losses), plus an allocation
pie chart. Select a specific lot to edit or remove it. Adding new positions
happens in the Stocks tab, not here.

### Watchlist

Stocks you're following but don't own — with an optional note and target
price, for keeping an eye on something without it affecting your portfolio
totals.

### Alerts

A log of triggered alerts: price moves past a threshold, or irregularities
detected in a company's balance sheet. A background job checks periodically
while the app is open; **Check now** runs the same check on demand. If SMTP
is configured, alerts also go out by email — otherwise they just show up
here.

### Guided Trading

Stocks screened for strong growth indicators (recent momentum, weighted
below sustained 52-week appreciation — "high growth," not "today's biggest
mover"). Pick a recommendation and add a chosen number of shares to Play
Trading or Portfolio, or bulk-add every current recommendation to Play
Trading at once (10 shares each, or your own share count).

### Play Trading

A paper-trading sandbox — positions added here (from Guided Trading or the
Stocks tab) are tracked against live prices exactly like Portfolio, but
without spending real money. Good for testing out a recommendation before
committing to it for real.

## Project structure

The codebase is layered so the desktop UI can eventually be swapped for (or
joined by) a web UI without touching the business logic:

```
stockapp/
  core/        domain models + interfaces (the abstractions everything else depends on)
  scrapers/    concrete data sources (yfinance-based price/FX/screener, balance sheets)
  data/        SQLite persistence (SQLAlchemy)
  services/    application logic — the only thing the UI is allowed to call
  analysis/    pure calculation functions (growth %, volatility, screener ranking, ...)
  alerts/      notification delivery (in-app, email)
  scheduler/   background job that refreshes prices and checks alerts periodically
  ui/desktop/  PyQt6 desktop app (tabs, widgets, main window)
```

See [docs/Architecture.md](docs/Architecture.md) for more detail on the
layering, and [docs/webscraper_notes.md](docs/webscraper_notes.md) for how
the data-fetching layer works.

## Tests

```bash
pytest
```

Tests cover the pure-logic modules (`analysis/`) and the SQLite repository —
no network access required.
