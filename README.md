# Trading forward test (simulated)

Simulated forward test, 16 November – 13 December 2026. **Nothing is traded.** Prices come read-only from Interactive Brokers. Results live in the test sheet; this repo is the long-term store.

- `data/bars/<tf>/<SYM>.jsonl`: bar history, one bar per line `{"t": epoch start UTC, "o","h","l","c","v"}`. The nightly orchestrator merges new bars in with `scripts/store.py`.
- `reports/walkforward/<date>.json`: nightly walk-forward checks of the adaptive crypto tuning, made with `scripts/walkforward.py`.
- `snapshots/<date>.json`: nightly copy of the live/challenger settings, the tournament table and the regime row.
- `scripts/`: the simulation scripts that the scheduled tasks run.
- `scripts/greeks.py`: entry Greeks (Black-Scholes IV, delta, gamma, theta, vega) for multi-leg positions; used by weekly_opts.py and for D2/D3.
- `scripts/weekly_opts.py`: weekly-option strategies W1-W4 (SPY put credit spread, iron condor, trend debit spread, breakout call debit spread), entered Mondays and Wednesdays at 10:00 ET and expiring that Friday. Run by the deep OTM task.
- `jobs.json`: registry of the scheduled tasks and the order of the daily pipeline.

This is testing, not financial advice.
