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
CURRENT SCHEDULE OF THE FEED (since 2026-11-20; supersedes the times above): ticks every 5 minutes Mon-Fri
09:00-15:55 ET come from the external pinger (cron-job.org, ops/engine_pinger.md) calling workflow_dispatch; GitHub's own
backup tick runs at :50 each hour 09:50-15:50 ET and doubles as the watchdog (GitHub issue "Health alert"). The engine
seals signals from 09:35. Nightly bars, corporate actions, VIX and the borrow file at 17:40 ET; crypto bars every 3 hours
at :32 (15 minutes before each crypto-tracks run); second daily crypto ML fit at 05:17 ET; nightly maths ("compute") when
the orchestrator requests it. Every run is logged in ops/diag/ticks.json; `checks.py health` reads it. GitHub Pro gives
3,000 Actions minutes a month; projected use is shown by the health line. Workflow files must be committed under the
owner's identity or GitHub stops their schedules.

## DATES (every task)

`python3 -I /tmp/repo/scripts/tcal.py today` prints the facts for today (New York): stock_test_active,
crypto_test_active, settle_only_window, full_trading_day, half_day, close_time, phase ("train" / "holdout" /
"before" / "after"), frozen (true in the holdout 2027-02-01..05-14), weekly_expiry (YYYYMMDD), weekly_entry_day,
week_entry_days, is_friday_report_day, week_index. Use these instead of any date list written in a prompt.
Test (SIX MONTHS since the owner's decision of 2026-11-21): stocks and options 2026-11-16 .. 2027-05-14; crypto to
2027-05-16; option settlement to 2027-05-21; INTERIM report 2027-02-16 (data to 2027-02-12); FINAL report 2027-05-18.
If a prompt still names 2027-02-12 / 02-14 / 02-16 as the end of the test, tcal.py and this runbook win.
Holidays: 11-26, 12-25, 01-01, 01-18, 02-15, 03-26. Half days (no new stock or option entries, marks and
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
BARS (since 2026-11-21): SPY and stock 5-minute bars come from the store (hist.py export 5m). Option legs are fetched
from IBKR one day at a time (ONE_DAY) and kept in data/bars/opt5m/OPT_<cid>.jsonl (store.py opt5m); hist.py export
opt5m gives every stored day of a leg for multi-day positions. Before this, each run fetched a whole week of bars for
every leg, which was too large to bring into files, and the runs of 2026-11-18 and 2026-11-20 wrote nothing (the W1-W3
positions of 2026-11-16 and 2026-11-18 stayed "pending"). RUN LOG: ops/diag/deep_otm.log, one line per run.
CATCH-UP: a run fired with "CATCH-UP DAY: YYYY-MM-DD" does that past day's work from that day's bars (no discretion:
the strikes and fills follow the same fixed rules); it is listed here when used. Used once: 2026-11-20 (on 2026-11-21).

## ADAPTIVE STOCKS

If frozen: score only (orb_adaptive.py score); do NOT run optimize; keep "Adaptive"!B3/D3 unchanged and write the
change-log row with decision "frozen holdout: no retune". LEDGER: AdaptiveStocks.

## CRYPTO TRACKS

DATA (changed 2026-11-20): GitHub stores crypto 15m / 1h / 1d bars from the free feed every 3 hours, 15 minutes before
each run. First `git -C /tmp/repo pull -q --rebase`, then run the hist.py plan as before: if it asks for 0 new bars,
skip every IBKR price call; if bars are still missing (the scheduled run was late), fetch only those from IBKR.

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
4b. STRATEGY LIBRARY + AI ALLOCATOR + STATS ON GITHUB (changed 2026-11-20: the maths runs on GitHub, not in this task).
   After step 4-pre (the ledger must be complete and PUSHED first):
   (i) write /tmp/repo/ops/fetch_request.json = {"mode": "compute", "day": "DAY", "requested": "<UTC now, ISO>"},
       commit and push it. That starts scripts/nightly.py on GitHub: library.py, library.py --cost-mult 2,
       library.py --fill-lag 0, allocator.py, stats.py, checks (engine-report, slip-report, health), dashboard.py, in
       that fixed order, and commits data/nightly/, data/library/, data/allocator/, data/ledger/Library.jsonl,
       reports/stats/DAY.json and data/dashboard.json.
   (ii) wait: every 45 seconds `git -C /tmp/repo pull -q --rebase` and read data/nightly/stamp.json, for at most
       6 minutes. Ready = stamp.day == DAY and stamp.ok == true and stamp.started is later than your request.
   (iii) ready -> use the saved results and run nothing yourself: data/nightly/library.json (append its
       new_closed_rows to "Library trades", first empty row >= 3, A-L; 17 strategies since 2026-11-20: L1-L17),
       data/nightly/stats.json (step 4's sheet_rows; if step 4 already ran locally, keep one of the two, not both),
       data/nightly/allocator.json (write every sheet_rows row whose date is not yet in "Allocation", first empty
       row >= 3, A-M; LEDGER Allocation with the same rows), data/nightly/checks.json (steps 4c, 4d, 4f).
   (iv) FALLBACK, not ready after 6 minutes or stamp.ok false: say so in the digest ("nightly maths on GitHub failed:
       <failed step and its error from stamp.json>") and run the same chain yourself, in this order:
       `library.py /tmp/repo DAY > /tmp/lib.json`, `library.py /tmp/repo DAY --cost-mult 2`,
       `library.py /tmp/repo DAY --fill-lag 0`, `allocator.py /tmp/repo DAY > /tmp/alloc.json`, then use those outputs
       as in (iii) and push.
   From 2026-12-07 the allocator report's freeze.code_matches_freeze must be true; false -> "Data check" row
   "FREEZE BROKEN: <changed_files>" flagged CHECK and say so first in the digest (never edit ops/freeze.json). The
   freeze-guard workflow opens a GitHub issue for the same thing; an open issue titled "FREEZE BROKEN" or
   "Health alert" goes first in the digest.
   Digest also carries: verdict_check (result, robust, per benchmark incl. the vol-matched ones), the three shadow
   allocators (phases.<phase>.shadows and p_ai_beats.sh_rp / sh_mv / sh_win; say plainly when a simple rival is ahead
   of the AI), forced_fill (average weight held only to stay fully invested, and what that part returned), exposure
   (beta to SPY and the return left after removing it), the AI result with implementable vs ideal fills
   (ideal_fills), turnover_per_day and rebal_cost_pct_total, the latest vol_forecast_pct, and netted_exploratory
   (never part of the verdict).
4e. DASHBOARD: after the allocator and stats, `python3 -I /tmp/repo/scripts/dashboard.py /tmp/repo` (writes
   data/dashboard.json, which the dashboard artifact reads; GitHub Actions also refreshes it every 5 minutes).
4d. ENGINE: count today's data/decisions/engine/DAY.jsonl rows and their median delay_min; ops/diag/engine.json
   errors -> one "Data check" row. No rows on a full trading day while live runs found breakouts -> flag CHECK.
   Median delay_min above 20 -> one "Data check" row (date, "-", "engine delay", median, rows, "CHECK"): detections
   that late are ignored by fills.py (5-minute fallback), so the engine is not doing its job. Cause seen 2026-11-19:
   GitHub ran the */5 schedule only about hourly; fix = the external pinger in ops/engine_pinger.md (owner set-up).
4f. HEALTH + ENGINE VS THE 5-MINUTE RULE (added 2026-11-20): data/nightly/checks.json (or `python3 -I
   /tmp/repo/scripts/checks.py health /tmp/repo` and `... engine-report /tmp/repo`). One digest line: ticks today, longest
   gap, median and slowest tick seconds, Actions minutes this month and projected vs 3,000, days until the pinger
   token expires (2027-03-31). Every entry of health.alerts -> one "Data check" row flagged CHECK and first in the
   digest. PINGER alert: the cron-job.org job is down or its token was rejected (ops/engine_pinger.md). TICK SLOW:
   a tick over 45 s; over 60 s doubles the minutes, so set "intraday_wide": false in data/universe.json and say so.
   engine_report: n, mean and median cost_vs_lag_pct for baseline and library rows. Measurement only until 100+ rows.
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

- (this session, 2026-11-20, owner decisions) allocator.py: ALWAYS FULLY INVESTED (the 10% volatility target, which
  worked by holding cash, is gone); weekly rebalancing; duplicate sleeves merged; equal weight and baseline A also
  volatility-matched; three-way verdict with a pre-registered six-week extension when inconclusive. library.py: three
  hedged sleeves so a fully invested book can defend itself: L14 opening-range breakdown (short), L15 market-neutral
  momentum, L16 SPY trend short; the intraday strategies moved into intraday_books() (no rule change; old sleeves'
  results are identical). ml.py: a champion needs at least 60 taken out-of-sample trades and PBO < 0.5, no waiver
  (the forest@0.55 champion took 24 trades with PBO 0.71 and is replaced by always-take). engine.py: starts at 09:35
  and also seals L2/L3/L4/L14 signals ("strategy" set; measurement only, fills.py ignores them).
  Replay of the new allocator on the library history 2025-06-02..2026-11-19, run once per variant and logged as
  trials (reports/replay/2026-11-20-fully_invested.json): daily rebalancing +4.26% (Sharpe 0.38, max DD 8.0%),
  turnover 33% a day, 5.9% lost to rebalancing; weekly rebalancing +4.11% (Sharpe 0.38, max DD 7.8%), turnover 18%,
  3.2% lost. Both are above the cash-heavy rule (-1.20%) and below equal weight (+10.0%, Sharpe 0.88) and SPY
  (+23.5%, Sharpe 1.17). Weekly rebalancing was adopted for the lower turnover, not for the return. The allocator
  has NOT shown skill on past data; the verdict window will show whether it has any.
- Crypto track costs were checked: 0.2% per side for majors and 0.3% for small coins (crypto_tracks.py COST).

- (2026-11-20, 14:25 Nairobi) External pinger live: cron-job.org calls workflow_dispatch (mode tick) every 5 minutes,
  Mon-Fri 09:00-15:55 ET; test call returned 204 and started a run. GitHub's own */5 schedule removed (it ran about
  hourly); one backup tick a hour at :50 and the 17:40 nightly stay. If engine delay_min is over 20 again, check the
  cron-job.org job first (token expiry 2027-03-31).

- (2026-11-20, later) SECOND BATCH, all before the freeze, owner request "implement the twelve suggestions":
  1. Report instructions live here: the weekly and final report prompts only point to this runbook.
  2. Nightly maths on GitHub (scripts/nightly.py, workflow mode "compute"; ORCHESTRATOR 4b). Tested twice on
     2026-11-20: 44 s, one billed minute.
  3. SHADOW ALLOCATORS (allocator.py): risk parity "sh_rp", minimum variance "sh_mv", recent winners "sh_win", same
     sleeves, cap, weekly rebalancing and costs as the AI. A pass is called ROBUST only if the AI also beats the best
     shadow on Sharpe (verdict_check.beats_best_shadow) and stays ahead of SPY at double costs.
     Replay on library history 2025-06-02..2026-11-19 (reports/replay/2026-11-20-shadows.json, 3 trials logged):
     AI +4.1% (Sharpe 0.38), risk parity +8.1% (1.00), minimum variance +3.9% (0.78), winners +7.5% (0.42), equal
     weight +10.0% (0.88), SPY +23.5% (1.17). EVERY simple rival beat the AI on Sharpe on past data.
  4. FORCED-FILL REPORT: on that history 19% of the book on average was held only to stay fully invested and it
     returned +2.0 of the +7.7 points before rebalancing costs. EXPOSURE: beta to SPY 0.31; after removing it the AI
     returned -2.5%. Both are reported nightly and never enter the verdict.
  5. CRASH DRILL, run once, no tuning afterwards (reports/replay/2026-11-20-crash_drill.json, 1 trial): daily
     sleeves only, today's S&P 100 (survivorship bias flatters it). 2020-02-19..04-30: AI -2.1% (max DD 7.5%),
     equal weight -5.7%, risk parity -2.8%, minimum variance -1.6%, SPY -13.2% (max DD 33.8%). 2022-01-03..10-14:
     AI -9.4% (max DD 10.8%), equal weight -8.6%, risk parity -7.1%, minimum variance -5.5%, winners -15.3%, SPY
     -23.8%. 2017-2022 whole: AI +21.3% (Sharpe 0.42), equal weight +39.9% (0.76), risk parity +24.0% (0.67), SPY
     +89.1% (0.64). Reading: the fully invested rule did not blow up in either crash, and it showed no edge over
     the simple rivals.
  6. BORROW COSTS: the IBKR connector has no borrow-fee or shortable field. fetch_free.py now tries Interactive
     Brokers' public short-stock file each night (data/borrow/DAY.json; library.borrow_fee uses it point-in-time,
     floor 0.25%); on 2026-11-20 that host did not answer from GitHub, so the flat 0.5%/year is still what is charged.
  7. L17 MULTI-ASSET TREND added (TLT, IEF, GLD, DBC, EFA, EEM; library.py docstring; 1 trial). Its two-year history
     (Sharpe about 1.1 on 504 days, 18 closed trades) entered the allocator's priors, so the four test days so far
     were recomputed with it: AI 11-16..11-19 was -2.03%, is now -1.61%. This is before the verdict window.
  8. WIDER INTRADAY UNIVERSE: switch "intraday_wide" in data/universe.json (5-minute feed, L2-L4, L14 and the engine's
     library signals on the whole S&P 100; baseline A and the control list never change). 90 days of 5-minute bars
     for the extra symbols were backfilled on 2026-11-20. It is turned on only if a tick stays under about 45 s; the
     decision and the measured seconds are recorded here.
     DECISION 2026-11-20 10:20 ET: intraday_wide stays FALSE. Market-hours ticks 09:35-10:20: feed part median 2.6 s,
     max 4.3 s, but whole GitHub runs took 31-45 s (checkout 5-8 s, feed + engine + dashboard 10-15 s, ML scoring
     9-11 s on ticks with a new breakout, commit 3-4 s). A universe 2.5 times wider would push busy ticks near or over
     60 s, which doubles the billed minutes (about 3,500 a month against 3,000). Revisit only with more minutes or a
     faster tick.
  9. CRYPTO DATA ROUND THE CLOCK: workflow cron every 3 hours (:32 UTC) stores crypto 15m / 1h / 1d bars from the free
     feed, so the crypto tasks only pull the repo (CRYPTO TRACKS).
  10. FREEZE GUARD: workflow freeze-guard.yml fails and opens an issue if a frozen script or ops/freeze.json changes
     after the freeze. PROOF OF PRE-REGISTRATION: the first commit holding ops/freeze.json gets the permanent tag
     "freeze-registered" (GitHub records the push time).
  11. HEALTH LINE (checks.py health; ops/diag/ticks.json; ORCHESTRATOR 4f) and a WATCHDOG on the hourly backup tick
     that opens one GitHub issue "Health alert" when the pinger has a gap over 20 minutes.
  12. ENGINE VS THE 5-MINUTE RULE (checks.py engine-report): measurement only.
  13. ML AT DETECTION (owner request 2026-11-20): on a tick where the engine seals a new baseline breakout, the
     workflow step "Score" runs `ml.py predict-engine` and appends the take-or-skip prediction to
     data/decisions/engine_ml/DAY.jsonl (first prediction stands, never overwritten). `ml.py predict` in the hourly
     LIVE DECISIONS run reuses that row for the same candidate id, so the "ML shadow" row carries the time the model
     could first have acted (predicted_at up to 55 minutes earlier than before). Learning is unchanged: this is
     scoring only, with features from the engine's real-time IEX bars. No effect on results while the champion is
     "always take". If the step fails (package or model-file mismatch on GitHub) the hourly run predicts as before.
  14. SECOND DAILY CRYPTO ML FIT (owner request 2026-11-20): workflow cron 10:17 UTC (05:17 ET), mode "mlcrypto":
     `decisions.py build`, then `ml.py train-crypto` (crypto family only; same evaluation, champion rule and holdout
     freeze; models/crypto.pkl, models/crypto_report_DAY.json). The nightly ML task stays the first fit. On
     2026-11-20 the crypto family had 84 labelled rows and no out-of-sample rows, so there is no crypto model yet;
     the extra fit changes nothing until the walk-forward has 20 out-of-sample rows.
  15. HARSHER HAIRCUT FOR SURVIVORSHIP (owner decision 2026-11-20, "Proceed"): in allocator.py the backtest days of
     L6, L7, L8, L10 and L15 count at 25% instead of 50% (PRIOR_HAIR_SURV). Their past record uses today's S&P 100
     list, which leaves out companies that later dropped out. The number was declared before any run and is not
     tuned. Effect on 2026-11-19 weights: L6 from 16.1% to 6.6%, L3 from 8.9% to 18.4%; L10 stays at the 25% cap.
     The four test days so far were recomputed: AI 11-16..11-19 was -1.61%, is now -1.18%. No replay on past data
     was run: in a replay every day counts as live, so the haircut does not act there. One trial logged.
  16. ENGINE REVISIONS (2026-11-20, fix): when the real-time IEX bars and the delayed SIP bars disagree on which bar
     broke out, the engine seals the same symbol twice (AMT 09:50 and 09:55, COIN 10:05 and 10:00 on 2026-11-20). The
     second row now carries "revision": true; fills.py still matches whichever row equals the replay's bar (unchanged),
     ml.py keeps the first prediction per candidate id, and checks.py engine-report counts revisions once.
  17. DASHBOARD SIGNAL CHART (2026-11-21, display only): the Live tab draws the engine's latest day on 5-minute candles
     with TradingView Lightweight Charts 5.0.9 (Apache 2.0), vendored in ops/dashboard/vendor/ by the one-off
     workflow mode "vendor" (no CDN). dashboard.py signal_charts() writes data/dashboard.json "charts". Republishing the
     dashboard now sends TWO files: index.html (from `dashboard.py html`) and lightweight-charts-5.0.9.js (copied from
     ops/dashboard/vendor/), with publish_files.
  18. MONTE CARLO RISK REPORT (2026-11-21, report only, never part of the verdict): scripts/montecarlo.py block-
     bootstraps daily returns (10,000 paths, 5-day blocks, seed 20261121, shared draws) for the AI, the shadow
     allocators, equal weight and SPY: 47- and 63-day outcomes, chance of a loss, chance of a 10% fall, and the chance
     of falling 10% before gaining 10%. Basis: the allocator replayed on past library data
     (reports/replay/2026-11-21-mc_series.json, built once) until 20 live days exist, then the live portfolio.
     nightly.py step "montecarlo" saves data/nightly/montecarlo.json. First result (replay, flattering): the AI's
     chance of a 10% fall before a 10% gain is 9%, against 1% for equal weight, 4% for SPY and under 1% for risk
     parity; its typical 47-day result is +0.5% against +1.6% for equal weight. The weekly and final reports describe
     it as context.
  19. SIX-MONTH HORIZON (owner decision 2026-11-21): tcal.py END 2027-05-14, holdout 2027-02-01..05-14, interim
     reading 2027-02-12, final report 2027-05-18; the six-week extension rule is gone (PRE-REGISTERED VERDICT).
  20. AI-JUDGMENT ALLOCATOR (owner decision 2026-11-21: "yes, robust"): scripts/judge.py (brief, seal), allocator.py
     "sh_judge", "judge_check", weekly task on Sundays 13:23 ET; first seal for the week of 2026-11-23. Why: the
     verdict so far judged only a fixed formula; this adds a decision made by a language model each week, sealed
     before the week starts, under the same constraints. One trial logged.
  21. POINT-IN-TIME EXPERIMENT (free build, owner decision 2026-11-21; scripts/pit.py, fetch_free.py mode "pit",
     data/pit/, library.py ELIGIBLE hook that is None in every normal run: output proven byte-identical; 3 trials).
     Source: community S&P 500 membership file (last change 2026-08-18) + Alpaca adjusted prices for all 561 members
     of 2024-2026, the 58 that left included. RESULT A (the measurement): the same four strategies on the S&P 500
     with today's list applied to the past versus the members at the time, 504 days before the test: L6 -1.0% vs
     -12.1%, L7 +42.1% vs +12.6%, L8 +195.7% vs +128.5%, L15 +55.2% vs +31.1%. Hindsight accounted for roughly 35% to
     70% of the hindsight-list return. RESULT B (the planned stand-in for the S&P 100, the 100 most-traded members each
     month): it came out BETTER than today's S&P 100 list (L8 +104.7% vs +49.0%), because ranking by trading volume
     picks the most active, fastest-moving names: it is a different kind of universe, not the S&P 100 without
     hindsight. DECISION: the stand-in is NOT used as the backtest record (it would raise the priors on a universe
     the live test does not trade). The allocator's priors are unchanged, and the 25% haircut for L6, L7, L8, L10,
     L15 stays; result A supports it. A true S&P 100 history (paid, about $30) would be needed to replace the priors.
  22. AUDIT CHECKLIST (owner decision 2026-11-21): ops/audit_checklist.md, adapted from an open-source checklist
     (github.com/Kryhr/26-quant-trading-skills, MIT) after a review of its files (text only, no code, no outside
     links). The independent audit of 2026-12-01 runs it step by step and records the actual result of every check.
  23. FIX (check-in of 2026-11-21, from the live-vs-replay parity check of 2026-11-20): the 10:05 live run's features
     differed from the nightly replay on 16 of 23 candidates (opening-range volume about half, entry a few cents
     off). Cause: in the task's own copy, store.py let IBKR bars overwrite the free feed's stored 5-minute bars, so
     the live features came from IBKR bars while the replay and the ML training use the feed's bars. store.py now
     follows the feed's merge rule for intraday bars (a stored bar keeps its prices and volume; only missing bars
     are added, zero volumes filled); daily bars are still overwritten (corporate-action adjustments). No effect on
     any decision so far: the stock ML champion is "always take", so no prediction used these features. Still open
     for the audit: (a) the 5-minute engine computes the opening-range volume at 09:50-10:00 while the newest
     opening-range bar may still carry IEX-only volume (engine 1.09 vs replay 1.50 for AMZN on 2026-11-20); (b) the
     replay recomputes the prior day's crypto_score from today's crypto bars (16.4) where the live run read the
     stored regime row (17.5).
  Not done: automatic dashboard snapshots (the connector still cannot read the private repo; support ticket open).

## CHANGE FREEZE AND AUDIT (owner decision 2026-11-20)

- From 2026-12-01 no new features, strategies of the library, benchmarks or rule changes: only fixes for defects
  found by the audit or by a failing task, each listed here with its date. (Strategy-lab candidates keep running
  through their gate: that is part of the tested process.)
- Independent audit on 2026-12-01 by a fresh session that did not build the system (scheduled task "Quantavius the
  1st - independent audit"): look-ahead and data-snooping review of allocator.py, library.py, fills.py, corp.py,
  decisions.py, ml.py, stats.py and engine.py; a re-run of the nightly chain on a copy; a freeze rehearsal (hashes of
  the frozen files, twice, must match); report in reports/audit/2026-12-01.md. It changes no code.
  Since 2026-11-21 it also works through ops/audit_checklist.md (look-ahead tests by truncation and by corrupting
  future data, fill feasibility, the AI-judgment seals, trial count, protocol, reproducibility).
- 2026-12-07: allocator.py records the hashes in ops/freeze.json on its first run. Never edit that file.

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

Report days: every Friday from 2026-11-20 to 2027-05-07 (the 2027-01-01 and 2027-03-26 reports fall on holidays and
cover trades through the day before). The interim report (2027-02-16) and the final report (2027-05-18) are separate
tasks. From 2027-02-05 mark everything as holdout evidence. Added 2026-11-21: the AI-judgment allocator (this week's
sealed weights and its stated reasoning from data/allocator/judge.jsonl, its result against the formula and the simple
rules, weeks without a seal, judge_check), and once, in the next report, the point-in-time experiment
(data/pit/report.json) with its limits. Week N =
week_index. Add sections: Stats tab (q-values, DSR, alpha vs SPY/BTC, Kelly shares, breakers), control list vs
watchlist, ML (models/report_<latest>.json: champion, OOS mean vs always-take, PBO, drift flags; ML shadow results),
Engine (detections, median delay_min, misses), implementable vs ideal fills (ideal_fills: how much the delay costs),
allocator turnover and rebalancing cost, vol forecast vs realised, netted_exploratory, verdict_check so far,
Live decisions (spreads, implementation shortfall; checks.py slip-report for the week and to date: spread cost, drift
by delay bucket, and whether the simulated costs are cheaper than reality), the strategy library and the AI allocator (data/allocator/report.json:
AI portfolio vs SPY / equal weight / baseline A, current weights, breakers, the 2x-cost stress result, and the
"sharpe_gap_detectable" line so readers see how much evidence the window holds). Added 2026-11-21: the Monte Carlo risk table (data/nightly/montecarlo.json; say which basis, replay or live, and that it is never part of the verdict). Added 2026-11-20: the three shadow allocators beside the AI (returns, Sharpe, drawdown and p_ai_beats for each; say plainly which is ahead), the forced-fill share and what it returned, the SPY beta and the
return after removing it, the health line for the week (ticks per day, slowest tick, minutes used vs 3,000, alerts), engine vs the 5-minute rule (checks.py engine-report), and once, in the first report, the crash drill and the
shadow replay from "CHANGES 2026-11-20 SECOND BATCH" with their limits. Data integrity: dq summary, bar timing
convention, IBKR vs Twelve Data flags, live-vs-replay parity, freeze status, trial count, and the report's stamp
(commit, data hash, package versions). Show stats for all data, v2 (from 2026-11-20) and the verdict window (from 2026-12-07) side by side. From 2027-02-05 mark everything as holdout evidence.

## PRE-REGISTERED VERDICT (changed 2026-11-19, before any data in the window)

The test is about the AI's process, not a fixed strategy: does the AI-managed portfolio (scripts/allocator.py over all
strategy sleeves, code frozen from 2026-12-07, weights set daily from data up to the day before) beat (a) total-return
SPY buy-and-hold, (b) an equal-weight mix of all sleeves and (c) baseline A alone, over the VERDICT WINDOW
2026-12-07..2027-05-14 (109 trading days since 2026-11-21, see SIX-MONTH HORIZON below; allocator report phase "verdict"), after per-symbol costs, on Sharpe
AND max drawdown, with block-bootstrap P(AI mean > benchmark) >= 0.9? It must also stay ahead of SPY at double costs
(stress_2x) to be called robust. Added 2026-11-19, before the window (both stricter): against SPY the drawdown and
the bootstrap must ALSO beat SPY scaled to the AI portfolio's realised volatility ("spy_vm"), so a mostly-cash
portfolio cannot win on drawdown for free; and every intraday result uses implementable fills (fills.py), including
baseline A as the benchmark. The allocator report's verdict_check applies this rule mechanically. The holdout (2027-02-01..05-14) is a second, independent check (phase "holdout").
Added 2026-11-20, before the window (owner decisions):
- NO CASH: the AI portfolio is always 100% invested (allocator.py "ALWAYS FULLY INVESTED"). Sitting out is not an
  option, so it can no longer beat a losing benchmark by holding cash.
- All three benchmarks are also compared volatility-matched (spy_vm, equal_vm, base_a_vm): drawdown and the bootstrap
  must beat both the raw and the volatility-matched version of each.
- THREE-WAY RESULT (verdict_check "result"): PASS = every condition above for every benchmark. FAIL = for at least
  one benchmark the bootstrap chance that the AI's mean beats it is 0.10 or lower. Otherwise INCONCLUSIVE.
- SIX-MONTH HORIZON (owner decision 2026-11-21, before any data in the window; it replaces the six-week extension
  rule of 2026-11-20): the VERDICT WINDOW is 2026-12-07..2027-05-14 (109 trading days; detectable Sharpe gap about
  1.9 instead of about 3). The result on 2027-02-12 (the old end, 46 days) is an INTERIM reading, reported on
  2027-02-16 and labelled as such; it decides nothing. The FINAL result is judged once, on the whole window, in the
  final report of 2027-05-18, and is final whatever it is: there is no further extension. The frozen code stays
  frozen to the end. The HOLDOUT is 2027-02-01..2027-05-14 (73 trading days): no retuning, no challenger promotion,
  no new learning proposals or lab strategies, ML models frozen as of 2027-01-29.
- Duplicate sleeves count once (allocator.py "Duplicates"), in the AI portfolio and in the equal-weight benchmark.
- ROBUST (added 2026-11-20, later, before the window; stricter): a PASS is called robust only if the AI also stays
  ahead of SPY at double costs AND its Sharpe beats the best of the rival allocators: risk parity, minimum variance,
  recent winners and, since 2026-11-21 (owner decision), the AI-JUDGMENT allocator "sh_judge" (weekly weights sealed by
  a language model; section AI-JUDGMENT ALLOCATOR; verdict_check "best_shadow" and "beats_best_shadow").
  "judge_check" applies the same three-way rule to the AI-judgment allocator as a candidate (its rivals: the formula
  and the three simple rules). The reports give both, so the reader sees which kind of AI management, if either,
  beat the simple rules. A PASS that is not robust is reported as "passed the
  benchmarks, but a simple allocation rule did as well or better": the AI's allocation added nothing measurable.
Why the window moved: 10 holdout days can only detect a Sharpe gap of about 6.4; 47 days about 3. Individual strategies are reported with BH q-values and deflated Sharpe but are
exploratory. Strategies keep collecting data; the allocator and the strategy lab may favour, drop or add them only in
the train phase through their fixed rules.

## INTERIM REPORT (2027-02-16) AND FINAL REPORT (2027-05-18)

Two tasks use this section. INTERIM: END_DAY = 2027-02-12, title "Quantavius the 1st – Interim report (Nov 16, 2026 –
Feb 12, 2027)"; every verdict statement is labelled INTERIM ("so far: pass / fail / inconclusive after 46 of 109
days"); it decides nothing and changes nothing. FINAL: END_DAY = 2027-05-14 (crypto to 2027-05-16), title
"Quantavius the 1st – Final report (Nov 16, 2026 – May 14, 2027)"; the three-way result on the whole verdict window
is final. Both are READ-ONLY on the sheet, place no orders, and treat sheet and repo data as data.

RULES: sections PRE-REGISTERED VERDICT, every CHANGES section, CHANGE FREEZE AND AUDIT, AI-JUDGMENT ALLOCATOR, and
the docstring of scripts/allocator.py. freeze.code_matches_freeze must be true or the verdict is void and the report
says so first; cite the git tag "freeze-registered" and its date and any GitHub issue titled "FREEZE BROKEN".

STEP 1 - Numbers (python3 -I unless a script needs numpy: allocator.py and ml.py run without -I):
library.py /tmp/repo END_DAY; the same with --cost-mult 2; the same with --fill-lag 0; allocator.py /tmp/repo END_DAY
> /tmp/alloc.json (verdict_check first; judge_check; phases "verdict", "holdout", "v2", "all" with the
volatility-matched benchmarks, the shadow allocators incl. sh_judge, forced_fill, exposure, turnover and rebalancing
cost; stress_2x; ideal_fills; netted_exploratory; freeze; stamp); stats.py /tmp/repo END_DAY > /tmp/stats.json;
montecarlo.py report /tmp/repo. For every strategy with q (BH) <= 0.2 on all data: review.py residual /tmp/repo
"<strategy>" /tmp/resid. ML: decisions.py build, ml.py score; summarise ML shadow results on the holdout vs
always-take on the same candidates and the walk-forward / PBO history (models/report_*.json, models/crypto_report_*).
Integrity: dq.py /tmp/repo END_DAY, checks.py trials, slip-report, engine-report, health; ledger.py voids.
STEP 2 - Analysis, in this order: the primary question (three-way result; robust or not and why: double costs and the
best rival; verdict window, then holdout, v2 and all as context; ideal vs implementable fills); formula vs AI
judgment vs simple rules (weights history, the judge's sealed reasoning, weeks without a seal, judge_check); how
often and how much the formula was forced to fill and what that returned; market beta and what is left after it; the
Monte Carlo risk table; then each family: library L1-L17 (1x and 2x costs), baseline A vs the control list, variants,
adaptive ORB, options O, D1, D2/D3, W1-W4 (exit reasons, worst loss in units of the average win, entry Greeks),
crypto by bar size and fixed vs adaptive, agent picks vs watchlist vs control list; learning proposals (with q) and
strategy-lab gate outcomes (incl. CPCV) with forward results; ML (did take/skip or instrument choice add value out of
sample; how often the champion was always-take; predictions at engine detection); the 5-minute engine (detections,
median delay, share within 20 minutes, revisions, engine fill vs the 5-minute rule); live decisions and slippage;
regime, breadth and event-day splits; data quality; task, pinger and GitHub reliability; gaps.
STEP 3 - Out-of-sample checks: the week-1 candidate named in the week 1 report, judged on trades after 2026-11-20
only; strategies whose average changed sign between train and holdout. Pre-registered question for single
strategies: does any strategy or the ML layer beat the frozen baseline A on the holdout with q <= 0.10 and DSR >= 0.9?
STEP 4 - A NEW Claude Doc (Docs guide items ["topic.instructions"] first) with the title above: 1) headline (3-4
sentences: the result, robust or not, interim or final); 2) AI portfolio vs benchmarks, raw and volatility-matched,
and vs the rivals incl. the AI-judgment allocator (table, cumulative chart, 2x-cost line, ideal-fill line);
3) ranking table of every strategy and track (trades | average with unit | 90% range | q (BH) | DSR | alpha |
holdout average | average allocator weight | verdict); 4) out-of-sample checks; 5) strategy library; 6) stocks and
the control list; 7) options; 8) crypto; 9) machine learning, allocator behaviour, the engine, live decisions and
slippage; 10) self-adapting machinery: did any of it improve results out of sample; 11) agent picks; 12) regime,
events, data quality, the independent audit and what was done about it, integrity checks, the crash drill, the
point-in-time experiment, every change made during the test (CHANGES sections and git log), reliability and gaps
(with the report stamp and the freeze-registered tag); 13) what this does and does not show (109 verdict days and 73
holdout days are still short for small edges; a fully invested book cannot step aside; corrections reduce but do not
remove luck; simulated fills and estimated costs may flatter; today's S&P 100 list (survivorship: measured in
data/pit/report.json, backtest priors of five sleeves cut to 25%); flat borrow fee unless data/borrow exists;
Black-Scholes Greeks are estimates; rare tail events cannot show in six months; not financial advice). Include
the Sheet link https://claude.ai/artifact/QvRtm7ymBmUFYC2EMMw5PN and the dashboard link
https://claude.ai/artifact/95HuUaCoRMm6VarNrd3A1k. If the doc fails, put the report in the reply.
STEP 5 - Reply with the doc link and a 5-line summary: the result (interim or final; robust or not), best and worst
strategy, formula vs AI judgment vs simple rules, whether ML or adaptive tuning helped out of sample, data-quality,
audit and freeze status.

## AI-JUDGMENT ALLOCATOR (weekly, Sunday 13:23 ET)

1. `python3 /tmp/repo/scripts/judge.py brief /tmp/repo > /tmp/brief.json` and read it whole. It is the ONLY evidence:
   no web search, no other data, no memory of earlier weeks beyond "your_earlier_seals". If market_closed_now is
   false or phase_of_effective_day is "after", stop.
2. Think in four voices, each written down in 2-5 sentences: BULL (which sleeves deserve more than the formula gives
   them and why), BEAR (what in this evidence is noise, flattered or likely to reverse), RISK (concentration, sleeves
   that fall together, the regime, what the worst week for this mix looks like), then the DECISION.
3. Choose shares for the eligible sleeves only: each between 0.02 and 0.25, adding up to exactly 1.00, no cash. You
   may copy the formula, a simple rule or go your own way; say which and why. Changing shares costs money (rules in
   the brief), so do not churn without a reason.
4. Write /tmp/seal.json = {"weights": {...}, "bull": "...", "bear": "...", "risk": "...", "decision": "...",
   "model": "<your model id>"} and run `python3 /tmp/repo/scripts/judge.py seal /tmp/repo /tmp/seal.json`. If it is
   refused, fix exactly what the errors say and try again (at most 3 attempts). Never edit data/allocator/judge.jsonl
   by hand and never change an earlier seal.
5. GIT ("ai judgment seal"). Reply in 3 lines: effective day, the shares, the decision in one sentence.
In the frozen holdout this task keeps running: it is a tested decision-maker like the formula, and its code and
rules do not change.

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

Since 2026-11-20 GitHub also fits the crypto family once more each day at 05:17 ET (CHANGES 2026-11-20 item 14) and
scores baseline breakouts at detection (item 13). `git pull` first; never delete data/decisions/engine_ml/. In step 5
add one line: engine predictions today (rows in data/decisions/engine_ml/DAY.jsonl) and the latest
models/crypto_report_*.json status.

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
