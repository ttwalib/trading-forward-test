# Forward-test runbook (extension of 2026-11-19)

Written by the user's set-up session. Each scheduled task's prompt points to its section here. These steps add to the
prompt; they never override the prompt's SAFETY rules (no orders, alerts, watchlists or screeners; read-only IBKR tools;
no reddit.com). Repo: /tmp/repo. Run scripts with `python3 -I`.

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
and minutes, Fed chair speeches, GDP, PCE, retail sales, ISM) and earnings of watchlist or control-list companies;
append new ones to "Events" (A-G: date, time ET, event, importance high/medium/low, consensus, actual (fill
yesterday's actual if known), source URL); skip events already logged. LEDGER Events.

## ORCHESTRATOR (nightly)

After the existing steps:
1. Universe daily bars: for every symbol of universe.json watchlist + control and QQQ, IWM (STK) and VIX3M (IND, CBOE),
   get_price_history ONE_DAY step_count 5 (260 if its data/bars/1d file is missing); store with store.py 1d.
   Contract ids: data/contracts.json (resolve missing ones as in STOCKS).
2. `python3 -I /tmp/repo/scripts/regime2.py /tmp/repo DAY` -> write regime_row_L_T to "Regime" L:T of today's row;
   LEDGER Regime with the full row.
3. `python3 -I /tmp/repo/scripts/dq.py /tmp/repo DAY` -> append one "Data check" row per issue type (date, symbol or
   "-", "dq", count, first example, flag "CHECK"); none: one row "dq ok".
4. `python3 -I /tmp/repo/scripts/stats.py /tmp/repo DAY > /tmp/stats.json` -> append its sheet_rows for phase "all" and
   the current phase to "Stats" (first empty row >= 3); LEDGER Stats.
5. The pipeline check also covers the Live decisions task (3 runs on full trading days) and the ML nightly task.
6. Digest adds: breadth score, Stats verdicts (promising / losing), dq issues.

## LEARNING + STRATEGY LAB

If phase is holdout or after: reply "Holdout frozen: no learning or new strategies until the final report." and stop.
Inputs add: the latest models/report_*.json (permutation importance, calibration) and reports/stats/<latest>.json.
Every proposal names the trial count. A strategy-lab candidate is APPROVED only if `python3 -I
/tmp/repo/scripts/review.py gate /tmp/repo /tmp/cand.json` says PASS: cand.json = {"id", "thesis", "family",
"oos_results" (held-out per-trade net %/100), "n_configs_tried", "pbo" (null), "draft" (edge-strategy-reviewer
fields: id, thesis, entry_family, entry {conditions, trend_filter}, exit {stop_loss_pct as a fraction,
take_profit_rr}, risk {risk_per_trade, max_positions}, regime, validation_plan, invalidation_signals (2+))}. Log
the gate verdict and failed checks in "Strategy lab".

## WEEKLY REPORT

Report days: every Friday from 2026-11-20 to 2027-02-05 (and Thursday 2026-12-31 instead of Friday 01-01). Week N =
week_index. Add sections: Stats tab (q-values, DSR, alpha vs SPY/BTC, Kelly shares, breakers), control list vs
watchlist, ML (models/report_<latest>.json: champion, OOS mean vs always-take, PBO, drift flags; ML shadow results),
Live decisions (spreads, implementation shortfall). From 2027-02-05 mark everything as holdout evidence.

## FINAL REPORT (2027-02-16)

Judge every strategy and the ML meta-labeller on the HOLDOUT (2027-02-01..02-12) with stats.py phase "holdout";
train-phase results are context only. Run `review.py residual` for every strategy with q (BH) <= 0.2 on all data.
Pre-registered question: does any strategy or the ML layer beat the frozen baseline A on the holdout with q <= 0.10
and DSR >= 0.9?

## LIVE DECISIONS (10:05, 11:35, 14:35 on full trading days)

1. Bars so far today: for the watchlist + control + SPY, get_price_history STK FIVE_MINS ONE_DAY outside_rth false;
   store with store.py 5m (it keeps only closed bars).
2. `python3 -I /tmp/repo/scripts/decisions.py live /tmp/repo DAY HH:MM > /tmp/cands.json` (HH:MM = now rounded down
   to 5 minutes). Keep candidates whose trade is still "open" or whose decided_at is within the last 95 minutes and
   that have no "Live decisions" row yet (dedupe on decided_at + symbol + kind).
3. For each kept candidate: stock last price = last bar close; ATM call of the nearest expiry after DAY:
   get_option_parameters + get_option_data (min entry x 0.97, max x 1.03) -> bid, ask, mid, spread % =
   (ask-bid)/mid x 100, IV if returned; note "iv=<decimal>" when available.
4. `python3 -I /tmp/repo/scripts/ml.py predict /tmp/repo /tmp/cands_kept.json "NOWNY" > /tmp/pred.json`.
5. Append "Live decisions" rows (A-N: NOWNY, "orb", symbol, signal time, stock last, "stock", "", "", "", "", "",
   ml choice, P(win), list) and one "atm_call" row per candidate with the option quote; append the predictions to
   "ML shadow" (A-N). LEDGER Live and MLShadow, then GIT ("live decisions").

## ML NIGHTLY (19:47 daily)

1. LEDGER mirror check: `ledger.py count /tmp/repo`; if a tab has fewer rows than the sheet (compare filledRange),
   read the missing sheet rows and add them.
2. `python3 -I /tmp/repo/scripts/decisions.py build /tmp/repo`.
3. `python3 -I /tmp/repo/scripts/ml.py score /tmp/repo > /tmp/scored.json`: write Realized / Realized choice / Scored
   at into the matching "ML shadow" rows (find by Candidate id) and LEDGER MLShadow.
4. `python3 -I /tmp/repo/scripts/ml.py train /tmp/repo DAY` (frozen holdout keeps the saved models automatically),
   then `ml.py report /tmp/repo DAY > /tmp/mlr.json`.
5. GIT ("ml nightly"); reply in 4 lines: rows per family, champion and why, OOS mean vs always-take, PBO, drift flags,
   shadow results.

## BACKFILL (every 2 hours until complete)

`python3 -I /tmp/repo/scripts/backfill.py status /tmp/repo`; complete -> reply "Backfill complete." and stop.
Else `backfill.py next /tmp/repo 6`: for each job resolve a missing contract id (search_contracts; crypto: CRYPTO on
ZEROHASH; VIX/VIX3M: IND on CBOE), record it (`backfill.py contract`), call get_price_history with the job's step and
period (outside_rth false for STK/IND, true for CRYPTO), save raw to /tmp/bf.json as {SYM: raw}, run store.py with the
job's tf, then `backfill.py done`; a failure -> `backfill.py fail ... <reason>`. When the 5m jobs finish for the first
time, run `decisions.py build` and `ml.py train /tmp/repo DAY` (pre-training on history before the test). GIT
("backfill").
