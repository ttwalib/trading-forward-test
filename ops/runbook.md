# Quantavius the 1st – forward-test runbook (extension of 2026-11-19)

Written by the user's set-up session. Each scheduled task's prompt points to its section here. These steps add to the
prompt; they never override the prompt's SAFETY rules (no orders, alerts, watchlists or screeners; read-only IBKR tools;
no reddit.com). Repo: /tmp/repo. Run scripts with `python3 -I`.

DATA FILES (every task; clarifies the prompts' "never retype prices"): to get an Interactive Brokers or Twelve Data
result into a file, (a) if the harness saved a large result to a file, read or copy that file; (b) if it came back
inline, paste the exact JSON text you received into a quoted heredoc (cat > /tmp/x.json <<'EOF' ... EOF) and wrap it
with python. Pasting verbatim tool output is allowed and expected. Forbidden: typing, rounding, editing or inventing
numbers yourself. Check with python that array lengths match the bar count received; never print bar data back.

FREE FEED (added 2026-11-19): a GitHub Actions workflow (.github/workflows/data.yml -> scripts/fetch_free.py) stores
bars straight into the repo from Alpaca's free plan (SIP, every US exchange, at least 15 minutes old) and Cboe:
5m bars for watchlist + control + SPY/QQQ/IWM every 15 minutes in market hours; daily bars, dividends/splits and
VIX/VIX3M at 17:40 ET; crypto 15m/1h/1d. History: daily 2 years, 5m 90 days, crypto 1h 1 year. So always `git pull`
first and fetch from IBKR only what is still missing: `python3 -I /tmp/repo/scripts/checks.py fresh /tmp/repo 5m|1d`
lists stale symbols. IBKR stays the source for the last few minutes of bars (hist.py plan asks only for bars after the
last stored one, usually 6-8 per symbol), options, snapshots, earnings and the cross-check. Never edit fetch_free.py's
output by hand. Daily bars sit at 12:00 UTC of the trading date (fixed 2026-11-19; before that they sat at 00:00 UTC and
read as the previous New York day). IBKR quotes DOGE to the cent; the feed replaces those bars with full-precision ones.
Since 2026-11-19 (second change that day) the workflow runs every 5 minutes, 09:30-15:55 ET ("tick"): 5m bars, then
scripts/engine.py, a fixed-code signal engine (no AI) that seals every baseline-A breakout with its detection time and
the real-time IEX price at that moment in data/decisions/engine/DAY.jsonl. Daily bars and dividends/splits now cover
the whole S&P 100 snapshot (library universe). data/hist holds the long research archive (daily since 2016, 5m for 2
years); only the strategy lab and the ML read it. IMPLEMENTABLE FILLS (scripts/fills.py): every intraday result used
for the verdict fills at the engine's detection price, else at the price 5 minutes after the signal bar; the ideal
signal-close version is reported beside it. Never call the ideal version the result.

## DATES (every task)

`python3 -I /tmp/repo/scripts/tcal.py today` prints the facts for today (New York): stock_test_active,
crypto_test_active, settle_only_window, full_trading_day, half_day, close_time, phase ("train" / "holdout" /
"before" / "after"), frozen (true in the holdout 2027-02-01..02-12), weekly_expiry (YYYYMMDD), weekly_entry_day,
week_entry_days, is_friday_report_day, week_index. Use these instead of any date list written in a prompt.
Test: stocks and options 2026-11-16 .. 2027-02-12; crypto to 2027-02-14; option settlement to 2027-02-19; final
report 2027-02-16. Holidays: 11-26, 12-25, 01-01, 01-18, 02-15. Half days (no new stock or option entries, marks and
settlements only): 2026-11-27 and 2026-12-24 (close 13:00).

## LEDGER (every task that writes trade or log rows)

After the sheet write succeeds, write the SAME rows (lists in sheet column order, or dicts with the ledger field names)
to /tmp/L.json and run `python3 -I /tmp/repo/scripts/ledger.py add /tmp/repo <KEY> /tmp/L.json`. Keys and columns:
Trades (A-M), VariantTrades (A-F), Options (A-M), DeepD1 ("Deep OTM" D1 rows, A-O), DeepSpreads (D2/D3 rows, A-U),
Weekly ("Weekly options" A-R), CryptoTracks (closed trades, A-N), AdaptiveStocks (A-F), AgentTrades (A-L),
AgentPicks (A-I), Sentiment (A-J), Regime (A-K plus L-T: write a dict with the extended names from regime2.py),
Events (A-G), Live (A-N), MLShadow (A-N), Stats (A-R). Rows are upserted by key, so re-runs never duplicate. Updated
rows (status changes, marks) are passed again in full. Then commit and push with the prompt's GIT step (tasks that had
no git step now do one: `git -C /tmp/repo config user.name forward-test-bot`, `git -C /tmp/repo config user.email
forward-test-bot@users.noreply.github.com` first).

## STOCKS (16:12 scoring)

1. Control list: symbols = `data/universe.json` "control" (22 random S&P 100 names, fixed). Contract ids from
   `data/contracts.json`; a missing id: search_contracts (exact symbol, US primary STK listing), then
   `python3 -I /tmp/repo/scripts/backfill.py contract /tmp/repo SYM ID`. Fetch their 5-minute bars like the watchlist
   (get_price_history STK FIVE_MINS ONE_DAY outside_rth false), save /tmp/bars_ctrl.json, store them with store.py 5m.
2. `python3 -I /tmp/repo/scripts/orb_daily.py /tmp/bars_ctrl.json DAY 16:00 > /tmp/ctrl.json`. Append each trade to
   "Variant trades" with variant exactly "AC control" (DAY, "AC control", symbol, outcome, r_net, entry_time) and one
   "Variants" row (DAY, "AC control", trades, wins, total_r_net, targets, stops). The baseline rules are unchanged;
   this only measures whether watchlist selection adds anything.
3. LEDGER: Trades, Options, VariantTrades (incl. AC rows); morning run: Sentiment.

## DEEP OTM + WEEKLY

Use DATES: open new D1/D2/D3/W positions only when full_trading_day; W1-W3 only when weekly_entry_day is true
(expiry = weekly_expiry; on a holiday week the expiry is the last open session, e.g. Thu 2026-12-24 and 2026-12-31).
Late-run rule: an entry day of the current week in week_entry_days that has no W1-W3 rows and is earlier than today.
W4 expiry = weekly_expiry of the entry day if after DAY, else next week's. Mark and settle every day of
settle_only_window as well. LEDGER: DeepD1, DeepSpreads, Weekly, then GIT ("deep otm").

## ADAPTIVE STOCKS

If frozen: score only (orb_adaptive.py score); do NOT run optimize; keep "Adaptive"!B3/D3 unchanged and write the
change-log row with decision "frozen holdout: no retune". LEDGER: AdaptiveStocks.

## CRYPTO TRACKS

If frozen: in REVIEW skip optimize (keep A3/C3) and log decision "frozen holdout: no retune". After STEP 3, ML shadow:
LEDGER CryptoTracks first (closed trades and newly opened rows with status "open"), then
`python3 -I /tmp/repo/scripts/ml.py predict-crypto /tmp/repo "NOWNY" > /tmp/mlc.json`; append its rows to "ML shadow"
(A-N in field order; P(win) = pred_best; Predicted results = pred_json) and LEDGER MLShadow.

## AGENT EVENING

LEDGER AgentTrades.

## AGENT MORNING

LEDGER AgentPicks and AgentTrades. EVENTS (every day, at most 3 extra searches and 2 fetches, after the picks):
scheduled US macro events for today and the next 2 trading days (CPI, PPI, jobs report, jobless claims, FOMC decision
and minutes, Fed chair speeches, GDP, PCE, retail sales, ISM) and earnings of watchlist or control-list companies (event text exactly "earnings SYM", e.g. "earnings AAPL", so the
library's earnings-drift strategy can find it). Earnings dates themselves now come from IBKR (MONDAY step below); the
"earnings SYM" rows are a fallback. If a CPI / jobs report / FOMC date differs from data/macro.json, fix the file (with
the official source URL in the commit message) and GIT ("macro calendar");
append new ones to "Events" (A-G: date, time ET, event, importance high/medium/low, consensus, actual (fill
yesterday's actual if known), source URL); skip events already logged. LEDGER Events.
MONDAY (or the first open day of the week) EARNINGS REFRESH: search_earnings_insights for all watchlist + control
contract ids (data/contracts.json), start = today minus 7 days, end = today plus 45 days, size 50, paginate until a
short page; save the responses as a JSON list to /tmp/earn.json and run
`python3 -I /tmp/repo/scripts/corp.py ingest-earnings /tmp/repo /tmp/earn.json`. GIT ("earnings dates").

## ORCHESTRATOR (nightly)

After the existing steps:
1. Universe daily bars: run `checks.py fresh /tmp/repo 1d` first. fresh true -> skip this step (the free feed already
   stored today's bars and dividends/splits). Otherwise, only for the listed stale symbols (STK; VIX and VIX3M are IND on CBOE),
   get_price_history ONE_DAY step_count 5 (skip symbols whose data/bars/1d file is missing: the backfill fills them) with include_corporate_actions
   true (not for VIX/VIX3M); save the responses as {SYM: response} to /tmp/d1.json; store with store.py 1d, then
   `python3 -I /tmp/repo/scripts/corp.py ingest-bars /tmp/repo /tmp/d1.json` (dividends + splits).
   Contract ids: data/contracts.json (resolve missing ones as in STOCKS).
1b. CROSS-SOURCE CHECK: `python3 -I /tmp/repo/scripts/checks.py xcheck-plan /tmp/repo DAY` -> for each listed symbol
   Twelve Data get_time_series (interval 1day, outputsize 5); save as {SYM: response} to /tmp/td.json; then
   `checks.py xcheck /tmp/repo /tmp/td.json`. Flagged days are excluded from ML automatically; list them in the digest.
   A Twelve Data error -> note "xcheck skipped" and go on.
   RATE LIMIT (added 2026-11-20): Twelve Data allows 8 credits per minute and the night needs 11 calls (9 xcheck
   symbols + BTC/USD and ETH/USD 1h). Send them in two batches: the first 6 xcheck symbols together, then
   `sleep 65`, then the last 3 xcheck symbols plus BTC/USD and ETH/USD (5 calls). Never more than 6 in one minute.
   A call answered "run out of API credits" -> wait 65 s and send that one call once more. For the BTC/ETH 1h check
   (prompt STEP 3) use outputsize 5, not 3, so the hour of the last stored IBKR 1h bar is still in the reply.
1c. LIVE vs REPLAY (full trading days): `python3 -I /tmp/repo/scripts/checks.py parity /tmp/repo DAY` (after today's 5m
   bars are stored). ok false -> one "Data check" row (date, "-", "parity", issue count, first issue, "CHECK").
2. `python3 -I /tmp/repo/scripts/regime2.py /tmp/repo DAY` -> write regime_row_L_T to "Regime" L:T of today's row;
   LEDGER Regime with the full row.
3. `python3 -I /tmp/repo/scripts/dq.py /tmp/repo DAY` -> append one "Data check" row per issue type (date, symbol or
   "-", "dq", count, first example, flag "CHECK"); none: one row "dq ok".
4. `python3 -I /tmp/repo/scripts/stats.py /tmp/repo DAY > /tmp/stats.json` -> write its sheet_rows for phases "all", "v2",
   "verdict" (from 2026-12-07) and the current phase to "Stats" by OVERWRITING rows 3+ (changed 2026-11-20: the tab
   holds only the latest night; appending ~80 rows a night would fill its 1,000 rows in two weeks). Write the rows from
   row 3 down in updates of at most ~900 cells, then clear (null) every old row below the new last row up to the tab's
   previous filledRange end. The full history stays in the repo: data/ledger/Stats.jsonl and reports/stats/DAY.json.
   LEDGER Stats.
4-pre. LEDGER COMPLETE BEFORE STATS (added 2026-11-20): stats.py and allocator.py read the repo ledger, so before
   step 4b run the ML NIGHTLY step 1 mirror check (`ledger.py count /tmp/repo` vs the sheet's filledRange of "Trades",
   "Options", "Variant trades", "Crypto tracks", "Weekly options", "Agent trades", "Adaptive stocks"; add any missing
   sheet rows with ledger.py add). On 2026-11-19 the ledger lacked the 11-16..11-18 baseline rows at 21:05 (the ML
   task mirrored them at 22:05), so that night's Stats and Allocation rows were computed on 5 instead of 22 baseline
   trades and had to be rewritten.
4b. STRATEGY LIBRARY + AI ALLOCATOR (after stats): `python3 -I /tmp/repo/scripts/library.py /tmp/repo DAY > /tmp/lib.json`
   (rebuilds data/ledger/Library.jsonl and data/library/daily.json itself); append its new_closed_rows to "Library trades"
   (first empty row >= 3, A-L). Then the cost stress run `library.py /tmp/repo DAY --cost-mult 2 > /tmp/lib2.json`
   (writes data/library/daily_2x.json only) and the ideal-fill comparison `library.py /tmp/repo DAY --fill-lag 0`
   (writes data/library/daily_ideal.json only). Then `python3 -I /tmp/repo/scripts/allocator.py /tmp/repo DAY > /tmp/alloc.json`; write
   every sheet_rows row whose date is not yet in "Allocation" (first empty row >= 3, A-M) and LEDGER Allocation with
   the same rows. From 2026-12-07 the report's freeze.code_matches_freeze must be true; false -> "Data check" row
   "FREEZE BROKEN: <changed_files>" flagged CHECK and say so first in the digest (never edit ops/freeze.json).
   Digest also carries: verdict_check (pass so far, per benchmark incl. vol-matched SPY "spy_vm"), the AI result with
   implementable vs ideal fills (ideal_fills), turnover_per_day and rebal_cost_pct_total, the latest vol_forecast_pct,
   and netted_exploratory (never part of the verdict).
4e. DASHBOARD: after the allocator and stats, `python3 -I /tmp/repo/scripts/dashboard.py /tmp/repo` (writes
   data/dashboard.json, which the dashboard artifact reads; GitHub Actions also refreshes it every 5 minutes).
4d. ENGINE: count today's data/decisions/engine/DAY.jsonl rows and their median delay_min; ops/diag/engine.json
   errors -> one "Data check" row. No rows on a full trading day while live runs found breakouts -> flag CHECK.
   Median delay_min above 20 -> one "Data check" row (date, "-", "engine delay", median, rows, "CHECK"): detections
   that late are ignored by fills.py (5-minute fallback), so the engine is not doing its job. Cause seen 2026-11-19:
   GitHub ran the */5 schedule only about hourly; fix = the external pinger in ops/engine_pinger.md (owner set-up).
4c. SLIPPAGE: `python3 -I /tmp/repo/scripts/checks.py slip-report /tmp/repo` -> one digest line: rows, median spread %,
   median drift % per delay bucket, model cost %; model_cheaper_than_spread true -> flag CHECK in the digest.
5. The pipeline check also covers the Live decisions task (hourly at :05 from 10:05 to 15:05 on full trading days) and the ML nightly task.
6. Digest adds: breadth score, Stats verdicts (promising / losing), dq issues, the AI portfolio vs SPY / equal weight /
   baseline A (verdict window from 2026-12-07, v2 and all) with the 2x-cost stress line, the top 3 allocator weights,
   xcheck flags, parity result and the trial count.

## CHANGES 2026-11-20 (before the verdict window; listed for the final report)

- dq.py: daily stock jumps are tested on the split/dividend-adjusted series, earnings-day gaps are skipped, only the
  last 30 days are listed, and OHLC sanity allows 0.1%. checks.bar_timing: the close tolerance is 0.6% (official
  closing auction vs the last 5m trade). This took the nightly dq list from 48 to 8 issues. The archive itself was
  checked: after corp.tr_adjust no unrecorded splits remain. BKNG's 25:1 split (2026-04-06) is recorded and adjusted
  in library and allocator prices. The remaining large moves are real (Covid 2020, 2025-04-09, earnings gaps; RTX
  2020-04-03 is the Carrier/Otis spin-off and only touches the 2020 research archive).
- stats.py: promising / losing / benched need n >= 20; q_bh, psr and dsr need n >= 10. Below that the verdict is
  "unproven (n<20)".
- allocator.py: drawdown breaker limits scale with each sleeve's volatility: max(8%, 3 x 20-day vol) and
  max(4%, 2.5 x 10-day vol). They are never stricter than before. Replay on the library history 2025-06-02..2026-11-19
  (reports/replay/2026-11-20-breaker.json): breaker-days fell from 1,321 to 362; the AI went from -4.04% (Sharpe
  -1.25, max DD 5.4%) to -3.68% (Sharpe -1.04, max DD 4.9%), against equal weight +11.8% and SPY +23.5% over the same
  days. Logged as 2 trials.
- Orchestrator: Stats tab overwritten nightly; ledger mirror check before stats/allocator; Twelve Data in two
  batches; engine delay flag. The 2026-11-19 Stats and Allocation rows were recomputed on the complete ledger.
- allocator.py (second change 2026-11-20): the Thompson draw is renewed weekly (seed = ISO week + sleeve), not
  daily. Replay 2025-06-02..2026-11-19, run once (reports/replay/2026-11-20-weekly_redraw.json): turnover 25% -> 8.5%
  a day, rebalancing cost 4.29% -> 1.48%, AI -3.68% -> -1.20% (Sharpe -0.42, max DD 2.2%); still below cash and below
  equal weight. Five diagnostic variants were tried first and logged as trials; none of them was adopted.
- VOID (DATA) rule: a crypto-track trade whose stop distance is below 10% of its round-trip cost (0.04% X, 0.06% M)
  is void: ledger.trades(), stats.py, allocator.py and the ML crypto rows skip it; crypto_tracks.py refuses such a
  signal (data_ok). The rule uses entry and stop only. It voids exactly one trade, in both 1h tracks: DOGE M2
  2026-11-17 18:00, -80.21 R, opened on IBKR bars rounded to the cent (stop 0.0075% away); on the corrected bars it
  is about -0.46 R (2.3% stop, 12-bar time stop). The rows stay in data/ledger/CryptoTracks.jsonl and on the sheet;
  `ledger.py voids /tmp/repo` lists them. Reports name void trades next to the crypto results. The six 15m M1
  trades with stops of 0.4-0.5% (below their 0.6% cost) are real and stay in.
- ops/freeze.json does not exist yet: allocator.py records the hashes on its first run on or after 2026-12-07, so
  changes to frozen files before then (allocator.py today) need no owner action.

## LEARNING + STRATEGY LAB

If phase is holdout or after: reply "Holdout frozen: no learning or new strategies until the final report." and stop.
From 2026-12-07 never edit scripts/allocator.py, scripts/library.py, scripts/corp.py or scripts/fills.py
(verdict-window freeze; the hash check in allocator.py reports any change).
LONG HISTORY + CPCV (2026-11-19): research and test lab ideas on the archive in data/hist (daily bars since 2016 for
the S&P 100 + ETFs, 5-minute bars for 2 years for the 47 intraday symbols; read with decisions.hist_bars(repo, tf, SYM),
or decisions.bars with decisions.USE_HIST = True to join the archive to the stored bars). Use implementable fills for
intraday ideas (fill at the open of the bar after next, as fills.py). Save the daily returns of EVERY setting tried
as {"configs": {setting: {date: ret %}}} and run `python3 -I /tmp/repo/scripts/cpcv.py /tmp/cfg.json`; put its output
in cand.json as "cpcv". A candidate without a passing cpcv is not approved (the gate checks it). New ideas enter only as new strategies through the gate below.
Every parameter set or idea you evaluate, kept or dropped, is a trial: the gate logs its own; log any other sweep with
`python3 -I /tmp/repo/scripts/checks.py trial /tmp/repo learning "<short name>" <configs tried>`.
Inputs add: the latest models/report_*.json (permutation importance, calibration) and reports/stats/<latest>.json.
Every proposal names the trial count. A strategy-lab candidate is APPROVED only if `python3 -I
/tmp/repo/scripts/review.py gate /tmp/repo /tmp/cand.json` says PASS: cand.json = {"id", "thesis", "family",
"oos_results" (held-out per-trade net %/100), "n_configs_tried", "pbo" (cpcv pbo), "cpcv" (cpcv.py output), "draft" (edge-strategy-reviewer
fields: id, thesis, entry_family, entry {conditions, trend_filter}, exit {stop_loss_pct as a fraction,
take_profit_rr}, risk {risk_per_trade, max_positions}, regime, validation_plan, invalidation_signals (2+))}. Log
the gate verdict and failed checks in "Strategy lab".

## WEEKLY REPORT

Report days: every Friday from 2026-11-20 to 2027-02-05 (the 2027-01-01 report covers trades through 2026-12-31). Week N =
week_index. Add sections: Stats tab (q-values, DSR, alpha vs SPY/BTC, Kelly shares, breakers), control list vs
watchlist, ML (models/report_<latest>.json: champion, OOS mean vs always-take, PBO, drift flags; ML shadow results),
Engine (detections, median delay_min, misses), implementable vs ideal fills (ideal_fills: how much the delay costs),
allocator turnover and rebalancing cost, vol forecast vs realised, netted_exploratory, verdict_check so far,
Live decisions (spreads, implementation shortfall; checks.py slip-report for the week and to date: spread cost, drift
by delay bucket, and whether the simulated costs are cheaper than reality), the strategy library and the AI allocator (data/allocator/report.json:
AI portfolio vs SPY / equal weight / baseline A, current weights, breakers, the 2x-cost stress result, and the
"sharpe_gap_detectable" line so readers see how much evidence the window holds). Data integrity: dq summary, bar timing
convention, IBKR vs Twelve Data flags, live-vs-replay parity, freeze status, trial count, and the report's stamp
(commit, data hash, package versions). Show stats for all data, v2 (from 2026-11-20) and the verdict window (from 2026-12-07) side by side. From 2027-02-05 mark everything as holdout evidence.

## PRE-REGISTERED VERDICT (changed 2026-11-19, before any data in the window)

The test is about the AI's process, not a fixed strategy: does the AI-managed portfolio (scripts/allocator.py over all
strategy sleeves, code frozen from 2026-12-07, weights set daily from data up to the day before) beat (a) total-return
SPY buy-and-hold, (b) an equal-weight mix of all sleeves and (c) baseline A alone, over the VERDICT WINDOW
2026-12-07..2027-02-12 (about 47 trading days; allocator report phase "verdict"), after per-symbol costs, on Sharpe
AND max drawdown, with block-bootstrap P(AI mean > benchmark) >= 0.9? It must also stay ahead of SPY at double costs
(stress_2x) to be called robust. Added 2026-11-19, before the window (both stricter): against SPY the drawdown and
the bootstrap must ALSO beat SPY scaled to the AI portfolio's realised volatility ("spy_vm"), so a mostly-cash
portfolio cannot win on drawdown for free; and every intraday result uses implementable fills (fills.py), including
baseline A as the benchmark. The allocator report's verdict_check applies this rule mechanically. The Feb 1-12 holdout is a second, independent check (phase "holdout").
Why the window moved: 10 holdout days can only detect a Sharpe gap of about 6.4; 47 days about 3. Individual strategies are reported with BH q-values and deflated Sharpe but are
exploratory. Strategies keep collecting data; the allocator and the strategy lab may favour, drop or add them only in
the train phase through their fixed rules.

## FINAL REPORT (2027-02-16)

Answer the PRE-REGISTERED VERDICT first (data/allocator/report.json verdict_check and phase "verdict", then
"holdout", "v2", "all"; show the ideal-fill comparison and the netted variant as context only;
the stress_2x result; freeze.code_matches_freeze must be true or the verdict is void and you say so). Then judge every
strategy and the ML meta-labeller on the HOLDOUT (2027-02-01..02-12) with stats.py phase "holdout";
train-phase results are context only. Run `review.py residual` for every strategy with q (BH) <= 0.2 on all data.
Pre-registered question: does any strategy or the ML layer beat the frozen baseline A on the holdout with q <= 0.10
and DSR >= 0.9?

## LIVE DECISIONS (hourly at :05, 10:05 to 15:05, on full trading days)

0. MIDDAY SNAPSHOT (only the 11:05 and 13:05 runs): 11:05 -> for each watchlist + control stock get_price_snapshot
   market_data_names ["bid_ask", "implied_volatility_percentile"]; 13:05 -> stocks ["implied_vol_underlying",
   "historical_vol"] and each universe etf except VIX/VIX3M ["bid_ask"]. Ask for exactly these two fields per call
   (larger field sets time out). Save as {SYM: response} to /tmp/snap.json and run
   `python3 -I /tmp/repo/scripts/corp.py ingest-snap /tmp/repo /tmp/snap.json "NOWNY"`. These feed the per-symbol
   cost model and next day's IV features. Failures: skip that symbol.
1. Bars so far today (`git pull` first: the free feed has usually stored everything up to about 20-35 minutes ago):
   for the watchlist + control + SPY, only the bars not stored yet:
   `python3 -I /tmp/repo/scripts/hist.py plan /tmp/repo 5m NOW <symbols comma-separated> 78` gives each symbol's
   step_count; get_price_history STK FIVE_MINS step_count=<that> outside_rth false (one symbol per call); put the
   results into one {SYM: result} file (DATA FILES rule) and store with store.py 5m (it keeps only closed bars and
   merges overlaps). Hourly runs then move about 12 bars per symbol instead of the whole day.
1b. ENGINE: `git pull` again; data/decisions/engine/DAY.jsonl lists the signals the 5-minute engine sealed (detection
   time, delay_min, real-time fill_price). Report each new candidate's engine delay and fill in the row's list
   column ("engine 6.2 min @ 123.45"); a candidate the engine missed -> "engine: missed".
2. `python3 -I /tmp/repo/scripts/decisions.py live /tmp/repo DAY HH:MM > /tmp/cands.json` (HH:MM = now rounded down
   to 5 minutes). Keep candidates whose trade is still "open" or whose decided_at is within the last 65 minutes and
   that have no "Live decisions" row yet (dedupe on decided_at + symbol + kind).
3. For each kept candidate: stock last price = last bar close; ATM call of the nearest expiry after DAY:
   get_option_parameters + get_option_data (min entry x 0.97, max x 1.03) -> bid, ask, mid, spread % =
   (ask-bid)/mid x 100, IV if returned; note "iv=<decimal>" when available.
3b. SLIPPAGE (no orders): right after step 3, for each kept candidate's stock call get_price_snapshot with
   market_data_names ["bid_ask"] only (one symbol per call); save as {SYM: response} to /tmp/q.json (DATA FILES rule) and run
   `python3 -I /tmp/repo/scripts/checks.py slip-save /tmp/repo /tmp/cands_kept.json /tmp/q.json "NOWNY"`. It records what
   a real market order would have paid now vs the simulated fill (spread, drift, delay). A failed quote -> skip that symbol.
4. `python3 -I /tmp/repo/scripts/ml.py predict /tmp/repo /tmp/cands_kept.json "NOWNY" > /tmp/pred.json`, then
   `python3 -I /tmp/repo/scripts/checks.py live-save /tmp/repo /tmp/cands_kept.json "NOWNY"` (keeps the features as
   seen live for the nightly live-vs-replay check).
5. Append "Live decisions" rows (A-N: NOWNY, "orb", symbol, signal time, stock last, "stock", "", "", "", "", "",
   ml choice, P(win), list) and one "atm_call" row per candidate with the option quote; append the predictions to
   "ML shadow" (A-N). LEDGER Live and MLShadow, then GIT ("live decisions").

## ML NIGHTLY (19:47 daily)

1. LEDGER mirror check: `ledger.py count /tmp/repo`; if a tab has fewer rows than the sheet (compare filledRange),
   read the missing sheet rows and add them.
2. `python3 -I /tmp/repo/scripts/decisions.py build /tmp/repo`. If data/hist/5m exists and
   data/decisions/hist/stock.jsonl.gz does not, first run `decisions.py build-hist /tmp/repo` once (about 2 years of
   archive rows; ML training adds them automatically). Labels: y_stock is the implementable-fill result (fills.py);
   y_stock_ideal is kept for comparison only.
3. `python3 -I /tmp/repo/scripts/ml.py score /tmp/repo > /tmp/scored.json`: write Realized / Realized choice / Scored
   at into the matching "ML shadow" rows (find by Candidate id) and LEDGER MLShadow.
4. `python3 -I /tmp/repo/scripts/ml.py train /tmp/repo DAY` (frozen holdout keeps the saved models automatically),
   then `ml.py report /tmp/repo DAY > /tmp/mlr.json`.
5. GIT ("ml nightly"); reply in 4 lines: rows per family, champion and why, OOS mean vs always-take, PBO, drift flags,
   shadow results.

## BACKFILL (00:15, 02:15, 05:15, 06:15 ET until complete)

`python3 -I /tmp/repo/scripts/backfill.py status /tmp/repo`; complete -> reply "Backfill complete." and stop.
Price history now comes from the free feed, so most jobs are skipped automatically. A job with "contract_only": true
-> search_contracts, `backfill.py contract`, `backfill.py done /tmp/repo SYM TF`; fetch no prices for it.
Else `backfill.py next /tmp/repo 10`: for each job resolve a missing contract id (search_contracts; crypto: CRYPTO on
ZEROHASH; VIX/VIX3M: IND on CBOE), record it (`backfill.py contract`), call get_price_history with the job's step and
step_count (outside_rth false for STK/IND, true for CRYPTO; include_corporate_actions when the job says true), save raw
to /tmp/bf.json as {SYM: raw}, run store.py with the job's tf (and for 1d jobs `corp.py ingest-bars /tmp/repo
/tmp/bf.json`), then `backfill.py done`. The EARNINGS job: search_earnings_insights with its contract_ids, start =
one year ago (UTC midnight), size 50, offset += 50 until a short page; save the responses as a JSON list to
/tmp/earn.json, run `corp.py ingest-earnings /tmp/repo /tmp/earn.json`, then `backfill.py done /tmp/repo EARNINGS events`; a failure -> `backfill.py fail ... <reason>`. When the backfill completes for the
first time, run `decisions.py build` and `ml.py train /tmp/repo DAY`. GIT
("backfill").
