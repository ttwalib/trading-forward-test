# Quantavius the 1st – simulated trading forward test (ttwalib/trading-forward-test)

Simulated forward test, **16 November 2026 – 12 February 2027** (extended on 19 November 2026; crypto runs to 14 February, final report 16 February). **Nothing is traded.** Prices come read-only from Interactive Brokers. Results live in the test sheet; this repo is the long-term store and the source for statistics and machine learning.

## Pre-registration (fixed on 2026-11-19, before any holdout data exists)

- Phases (`scripts/tcal.py`): **train** 2026-11-16 .. 2027-01-29 (tuning, learning and ML training allowed); **holdout** 2027-02-01 .. 2027-02-12 (frozen: no retuning, no challenger promotion, no new strategies, ML models frozen as of 2027-01-29).
- Primary question (revised 2026-11-19, still before any holdout data): does the **AI-managed portfolio** (`allocator.py` over every strategy sleeve) beat total-return SPY buy-and-hold, an equal-weight mix of all sleeves and baseline A over the **verdict window 2026-12-07 .. 2027-02-12** (allocator and library code frozen from Dec 7; about 47 out-of-sample days), after per-symbol costs, on Sharpe and max drawdown, with block-bootstrap P >= 0.9, and still beat SPY at double costs? The Feb 1-12 holdout is a second check. Individual strategies are exploratory (BH q-values and deflated Sharpe reported).
- Controls: baseline A rules never change; baseline A also runs on a fixed random control list of 22 S&P 100 names (`data/universe.json`, seed 20261119) to separate rule edge from watchlist selection.
- Every strategy and every ML config ever tried counts as a trial (deflated Sharpe, PBO).
- Gaps in data are shown, never filled.

## Layout

- `data/bars/<tf>/<SYM>.jsonl`: bar history `{"t": epoch start UTC, "o","h","l","c","v"}`, merged by `scripts/store.py`.
- `data/ledger/<Tab>.jsonl`: machine-readable mirror of every sheet log (`scripts/ledger.py`), upserted by key.
- `data/decisions/{stock,crypto}.jsonl`: decision dataset with decision-time features and counterfactual labels (`scripts/decisions.py`).
- `data/universe.json`: liquid universe, watchlist and control list. `data/contracts.json`, `data/backfill_state.json`: backfill state.
- `models/`: saved ML models (`stock.pkl`, `crypto.pkl`) and nightly ML reports.
- `reports/stats/<day>.json`: nightly bias-aware statistics. `reports/walkforward/`: crypto walk-forward checks. `reports/residual/`: residual-edge reports.
- `snapshots/<date>.json`: nightly copy of settings, tournament and regime.
- `vendor/tradermonty/`: MIT-licensed code from tradermonty/claude-trading-skills (commit 427b1f7d): residual-edge analyzer, edge-strategy reviewer, drawdown circuit breaker and crypto regime references. See its LICENSE.
- `jobs.json`: registry of scheduled tasks and the daily pipeline.

## Scripts

| Script | Purpose |
|---|---|
| `tcal.py` | Test calendar: trading days, half days, weekly expiries, phases, frozen flag |
| `ledger.py` | Sheet mirror + unified closed-trade table |
| `stats.py` | Bootstrap CIs, BH q-values, PSR/DSR, alpha/beta vs SPY/BTC (Newey-West), 1/4-Kelly shares, drawdown breaker |
| `regime2.py` | In-house breadth (% above SMA20/50, 20-day highs-lows), QQQ/IWM trend, crypto breadth, BTC realized vol, crypto score, VIX term |
| `decisions.py` | Decision dataset (baseline-A breakouts on watchlist + control, crypto track trades) and live candidates |
| `ml.py` | Meta-labelling + instrument choice; purged/embargoed walk-forward, CSCV PBO, calibration, permutation importance, PSI drift, shadow scoring |
| `review.py` | Strategy-lab promotion gate (OOS, DSR, PBO, vendored edge reviewer) and residual-edge analysis |
| `library.py` | Strategy library: 13 widely used strategies (intraday momentum, VWAP pullback, gap and go, gap fade, RSI(2), Bollinger, Donchian trend, momentum, sector rotation, earnings drift, overnight, turn of month, pairs) run on stored bars, next-open fills, costs, sleeve returns |
| `corp.py` | Reference data: dividends/splits from IBKR (total-return prices), earnings dates with known-at times (IBKR earnings insights), macro calendar features (data/macro.json), midday snapshots (spreads, implied vol, IV percentile) |
| `checks.py` | Integrity: 5m bar-timing test, IBKR vs Twelve Data cross-check (exclusions for ML), live-vs-replay parity (look-ahead detector), `fresh` (is the free feed current?), trial ledger for the deflated Sharpe, reproducibility stamp |
| `fetch_free.py` | Free data feed run by GitHub Actions (`.github/workflows/data.yml`): Alpaca free plan (SIP stock/ETF bars, crypto bars, dividends, splits) and Cboe VIX/VIX3M, written straight into `data/` so no prices pass through the AI. Keys only in repo secrets. Request a run by editing `ops/fetch_request.json` |
| `allocator.py` | AI allocator: regime-aware Thompson sampling with quarter-Kelly weights, correlation and drawdown limits; AI portfolio vs SPY, equal weight and baseline A |
| `dq.py` | Data-quality and staleness checks |
| `backfill.py` | Resumable historical backfill planner |
| `greeks.py`, `weekly_opts.py`, `deep_otm.py`, `options_sim.py`, `smart_opt.py` | Options simulation and Greeks |
| `orb_daily.py`, `orb_variants.py`, `orb_adaptive.py`, `crypto_tracks.py`, `agent_score.py`, `walkforward.py`, `uncertainty.py`, `sentiment.py`, `fees.py`, `store.py`, `hist.py` | Strategy simulators and helpers |

This is testing, not financial advice. Nothing here places, previews or changes orders.
