# Lane build plan from 2026-12-08 (one plan; replaces the main prompt's stage list and five addenda)

Written by the owner's set-up sessions (merged 2026-11-24, runbook item 56). Order = value for THE ULTIMATE GOAL:
Quantavius picking its own stocks, developing its own strategies and running its own book.

## Rules for every stage
- Outside the 17 frozen scripts. The scoring code and the A1 verdict stay untouched.
- A challenger earns weight only through the lane: promotion against ai_judgment (Quantavius's own book), or LANE
  ADMISSION into the AS sleeve (runbook item 53; monthly from 2027-02-16).
- Register each entry with scripts/registry.py BEFORE any forward day. Cap: 6 new entries a month; December starts
  empty. Register as soon as an entry passes its gates (CPCV, PBO, deflated Sharpe, neighbour check).
- Log every variant with checks.py trial. Join every outside value point-in-time by its fetch time.
- Training and search run on GitHub Actions. Keep the month under about 7,000 minutes (checks.py health).
- Outside packages: read them first, pin the exact version, and run them in an isolated job like
  .github/workflows/xcheck.yml (read-only token, no secrets) unless already in use.
- One stage per session; schedule the next session yourself (send_later). After each stage: runbook item,
  pre-registration amendment row, interventions row, SPEC, ops/tasks.json, project notes, and a short report to the
  owner in caveman style: built, what past data showed (say plainly when it shows nothing), what is next.
- First, once: confirm ops/freeze.json exists, the freeze guard passes, the Dec 4 audit reports are triaged, the
  nightly "lane" step is ok, no CHAIN BROKEN alert, and read reports/xcheck/2026-11-24.md. Fix audit defects first.
- Never place, preview, modify or cancel any order. No reinforcement learning (no orders; too little independent
  history): record the reason in the runbook.

## Stage 1 - Data for the ranker (DONE 2026-11-25, built early: pit history 2016-07 to 2026-11, 1.31M rows, 716 symbols, 18% of rows from companies that later left; look-ahead check 0 differences; IC table: no single feature above |t| 1.92 (dvol21); nightly forward bars in data/pit/fwd; labrun workflow tested. Rebuild data/pit/train_1d.csv.gz with pit_train.py build (about 6 minutes, gitignored, 83 MB))
1. Extend the point-in-time history (data/pit, scripts/pit_train.py) from 2024 back to 2016 with the free S&P 500
   change lists and Alpaca prices, departed companies included. Redo the look-ahead check and the univariate IC table.
2. Add a nightly GitHub refresh of S&P 500 membership and daily bars so the ranker can run forward.
3. Add a workflow mode "labrun": lab sweeps and CPCV on GitHub from strategies/requests/<id>.json to
   strategies/results/<id>.json; update the runbook LAB section (the lab still runs review.py gate itself).

## Stage 2 - ML stock ranker (the model behind Quantavius's picks)
1. Gradient boosting on the history, predicting next-week relative return; purged walk-forward (5-day label, embargo);
   weekly long-only top-N of current S&P 500 members with realistic costs. Method: chapters 7, 8 and 12 of Jansen's
   ML for Trading (MIT code; ideas, own implementation). Report IC with alphalens-reloaded (isolated job) beside the
   G1 daily ranking. Baseline to beat: Microsoft qlib Alpha158 with rolling-retrain gradient boosting.
2. Candidate features, each a logged trial kept only if it helps out of sample: option implied volatility and skew,
   earnings dates, the engine's sealed signals, measured slippage, crypto-to-stock links; FINRA short-sale share; Cboe
   and per-stock put/call (data/ext/av/putcall.jsonl); 8-K items and Form 4 insider trades for the 44 stocks via
   edgartools (data/ext/edgar); transcript tone (data/ext/av/transcript.jsonl) plus a FinBERT score; peer moves
   (data/ext/peers); FRED values as first published (ALFRED vintages) and crypto context as regime features; the
   Alpha Zoo factor families (Vibe-Trading, MIT: keep LICENSE and provenance). The av and peers histories start on
   2026-11-24: mark them "waiting for history", not failed.
3. If the ranker shows a real signal: write a daily shortlist before 08:00 ET (data/ml/shortlist/DAY.json), add the
   AGENT MORNING paragraph (picks tagged src=own, src=ml or src=both), and report G1 by source. If it shows nothing,
   say so and do not switch the shortlist on.
4. Every retrain is a registry version (hash, forward start); the lane retires decayed versions.

## Stage 3 - Allocation rivals for the book
1. Learned allocator (weekly sleeve weights from market conditions) as a challenger.
2. Baselines it must beat: hierarchical risk parity and a Carver-style handcrafted equal-risk book (own code);
   register at most one of them.

## Stage 4 - New strategy sources
1. Automatic strategy search with a hard monthly budget; only gate survivors are registered; every candidate counts.
2. Lane strategies: leveraged-ETF end-of-day rebalancing flows (add TQQQ/SQQQ/UPRO/SPXU/SOXL/SOXS data first) and a
   VIX range breakout through SPY or a tradable VIX fund (declare which before any backtest).
3. The report-only wide intraday run as one challenger, if it earns a slot.
4. Deep learning: one small network over the ranker's features, only if the boosting ranker showed a real
   out-of-sample signal; otherwise record "not tried: no signal to improve on".

## Stage 5 - Reports and health (report only) (items 1-3 DONE 2026-11-25: scripts/stage5.py spa, ff, health as nightly extra steps; item 4 stays for the Nov 29 seal check and later)
1. White's Reality Check or Hansen SPA over the lifetime trial log, for the interim and final reports.
2. Fama/French five-factor plus momentum attribution of A1 (pandas-datareader, isolated).
3. Strategy health states per lane entry (healthy / under watch / decayed / switched off); never overrides the
   pre-registered retirement rule.
4. Check the Opus and Sonnet contest seals are sealing and scoring (about 23 weekly seals can only show a large gap).

ADDED 2026-11-25 (build day 3, item 32-34 follow-up d): register the ML take/skip gate on baseline A as a lane challenger
(registry.register, series type "sleeve" on its "ML meta: ..." sleeve) as soon as the nightly ML has a champion other
than "always take"; it counts against the lane cap of 6 new entries a month.
