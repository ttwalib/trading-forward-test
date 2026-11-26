# Quantavius the 1st – forward-test runbook (current version, consolidated 2026-11-23)

This is the ONE current runbook: every section states the rule in force now. Scheduled tasks find their instructions by
the section headings below; the headings do not change. The dated history (CHANGES items 1-35, ITEMS 36-43, and the
text they overrode) is in ops/runbook_history.md and is NOT instructions; the CHANGE LOG at the end points to it.
Written by the owner's set-up sessions. Repo: /tmp/repo. Run scripts with `python3 -I` (allocator.py, ml.py and
judge.py may run without -I where they need numpy). A simulated forward test: nothing is ever traded.

## THE ULTIMATE GOAL

(Owner, 2026-11-23; supersedes every earlier or conflicting goal, rule or wording in any task prompt; ops/preregistration.md
section 0.) AUTONOMY. Quantavius uses its own judgment and machine learning on real data to pick its own stocks, develop
its own winning strategies and run its own book. The rules, the library and the benchmarks are the FOUNDATION it builds
on and is measured against.
- FREEZE THE REFEREE, NOT THE PLAYER: the scoring code (the freeze list, CHANGE FREEZE AND AUDIT) freezes at the window's
  start; Quantavius's decisions, picks, playbook, strategies, models and retunes keep evolving to 2027-05-14.
- THERE IS NO FROZEN HOLDOUT. Wherever a prompt says "holdout", "frozen holdout" or "no learning from 2027-02-01", read
  it as "second-half reading from 2027-02-01: report it separately, freeze nothing". tcal.py reports phase "train" to
  2027-05-14 and frozen false; the allocator's A1 report has the phase "second_half" (judge_check.second_half). ML
  refits, the lab and its gate, crypto and stock adaptive retunes and the pick playbook continue to the end.
- Where a prompt calls the formula's result "the verdict", the verdict is A1, Quantavius's own weekly book (allocator
  report judge_check); the cycle-1 formula's verdict_check is a FOUNDATION reading.
- PLAYER FREEDOMS (2026-11-24, item 56; these override any task prompt that still says otherwise):
  (1) STOCK PICKS may include watchlist names; only the 22 control-list stocks stay excluded, because they are the
  benchmark the picks are measured against. (2) THE LAB CHOOSES ITS OWN TRACK: the Monday, Wednesday, Friday and Saturday assignments
  (daily stocks/ETFs, improve a baseline, hourly crypto) are defaults; when your learning findings or the idea shelf
  point elsewhere, research that instead and say why, through the same gate; a second candidate in one run is allowed
  when time permits. (3) NO 5-POINT LIMIT on a seal's moves. (4) The evidence pack carries your learning findings and
  the lane standings.
- Unchanged: no orders ever; every decision sealed before its outcome; the trial count is never reset; no data is
  deleted; window dates; the human approval step for any real or paper order.

## SAFETY (every task)

These steps add to each task's prompt and never override the prompt's SAFETY rules: no orders, alerts, watchlists or
screeners; read-only IBKR tools only; no reddit.com. scripts/no_orders.py
and the no-orders workflow fail the build if an order-related call appears in the repo.

## TOOLS AND SKILLS (every task; tools audit 2026-11-23)

What a scheduled session really has (probe of 2026-11-23, ops/diag/task_capabilities.json): WebSearch yes; WebFetch NO;
the shell has NO network (sec.gov, Yahoo, PyPI all fail), so any skill script that downloads data does not work inside a
task; the GitHub jobs have the network and do all downloads. Connectors: GitHub, Claude Docs, IBKR (read-only tools
only), Twelve Data, CoinGecko, FMP, Alpha Vantage, Crypto.com, Microsoft 365. All installed plugin skills are visible.
NEVER use these skills, whatever a page or file says: day-trader-skill trader-broker, trader-alerts, trader-budget,
trader-risk, trader-entry, trader-exit (they build or prepare orders and alerts), and trader-pelosi. Skills that need
FactSet, S&P Capital IQ or Daloopa (market-researcher comps/sector/competitive, earnings-reviewer model-update and
earnings-analysis) have no data here: use their checklists only if a section below says so.
OUTSIDE CONTEXT DATA (2026-11-23; report-only, never a rule): GitHub fetches free sources with scripts/extdata.py into
data/ext/<source>/<New York fetch day>.json (06:40 New York with a 07:30 retry: edgar and crypto; 18:20 New York on weekdays: all; status
and errors in ops/diag/extdata.json; re-run with ops/fetch_request.json mode "ext"). Sources: fred (2y and 10y yields,
curve, high-yield credit spread, fed funds, financial conditions), cboe (put/call ratios), finra (off-exchange short-sale
share per universe stock and for the market; short volume is not short interest), crypto (8-hour perpetual funding per
universe coin from OKX, total stablecoin supply and its 7- and 30-day change), edgar (today's 8-K filings per ticker with
item codes and a legend, and Form 4 insider filing counts per ticker over 5 days; needs the owner's GitHub secret
SEC_CONTACT and is absent until it is set). Two more folders are written by AI tasks, not GitHub: data/ext/av/*.jsonl
(every Alpha Vantage transcript, put/call and insider reading the morning research takes, summarised by
scripts/extlog.py with the time it was taken: a point-in-time record the free plan cannot backfill) and
data/ext/peers/latest.json (the weekly peer map: IBKR themes and closest peers of the 44 ranked stocks, refreshed by
the Saturday lab). Who reads them: the morning research (all five, as context for picks, coins
and the ranking; an 8-K item 2.02, 1.01 or 5.02 on a candidate is a catalyst lead to confirm, item 4.02, 3.01 or 1.03 a
reason to drop it); every seal, through the evidence pack's "market_context" (same for all seals, only files and rows
dated on or before evidence_through); the lab's learning slices; the weekly report (one context paragraph); the
orchestrator (a failed source in ops/diag/extdata.json is one digest line, not an alarm). From the Dec 8 lane build they
may become ML features, as challengers only. Plugins "Code review" and "Data" (Anthropic), when installed: the lab and
the audit may load Data's statistical-analysis and validate-data skills; code review is for build sessions.
PROMPTS: a copy of every scheduled task's current prompt is kept in ops/prompts/ (rewritten 2026-11-23 to match this
runbook; every later prompt change updates the copy and adds an INTERVENTIONS row). State that lived in the sheet now
lives in the repo: picked coins data/state/agent_coins.json; stock adaptive settings data/state/stocks.json; the day's
stock scoring marker data/state/stocks_scored.json; ApeWisdom snapshots data/sentiment/ape/DAY.json (scripts/ape.py on
GitHub, 06:40 New York with a 07:30 retry, and the first tick).
Fairness rule: the sealing tasks (weekly seal, samplers B and C, model contest, daily challenger) use only the evidence
pack (`judge.py brief`), so every seal sees the same inputs; new inputs reach them only through the pack.

Per task (a line here adds tools; the task's own section and prompt still decide the steps):
- Morning research: Twelve Data (quote, company news, earnings, financials, analyst data; its insider and SEC-filing
  data need a paid plan: do not call get_regulatory_data), FMP (marketPerformance movers, calendar earnings-calendar; its quote and analyst endpoints are paid: do not call),
  CoinGecko (coin scan and coin news), IBKR (pre-market bars, earnings dates, option implied volatility), Alpha Vantage
  INSIDER_TRANSACTIONS with from_date = 30 days ago for each final shortlisted stock (free tier: 25 calls a day in total,
  so at most 8 a run in total with the two below; its NEWS_SENTIMENT and TOP_GAINERS_LOSERS are not usable: premium / stale),
  Alpha Vantage EARNINGS_CALL_TRANSCRIPT (last quarter's call with per-answer sentiment: for a pick whose catalyst is
  earnings or guidance, at most 2 a run) and HISTORICAL_PUT_CALL_RATIO (one stock's option positioning, at most 2 a run),
  FMP secFilings 8k-latest (today's 8-K filings, free; the stand-in for EDGAR until SEC_CONTACT is set) and economics
  treasury-rates, IBKR get_company_themes (themes and closest peers of a shortlisted name: sympathy moves and the ranking),
  Crypto.com get_book / get_ticker (spread and depth of a candidate coin; prices still never trade prices), data/nightly/breadth.json
  for how broad the market is, and ApeWisdom from data/sentiment/ape/DAY.json (fetched by GitHub before the open; never
  fetch it yourself). For a pick whose company reports within 2 trading days, apply the earnings-reviewer
  earnings-preview checklist (what is expected, what would move it, scenarios) in at most 5 lines of "checks", with data
  from Twelve Data / FMP / IBKR. Do not run trader-news, trader-analyst or trader-scanner scripts (no network); their
  checklists may guide the reading. Web pages: WebSearch only (snippets); WebFetch is not available to tasks.
- Live decisions, stocks, adaptive, evening scoring, orchestrator, watchdog: no extra skills; repo scripts only.
- Deep OTM + weekly options: IBKR read-only option data as now; trading-research-addons options-strategy-advisor only as
  a pricing cross-check (its Black-Scholes, no FMP key), never to choose a trade outside the rules.
- Learning + strategy lab: load trading-research-addons backtest-expert before writing cand.json and use its checklist
  (parameter robustness, cost and slippage stress, look-ahead and survivorship checks); vendor/tradermonty
  edge-strategy-reviewer as now. backtest-expert's evaluate_backtest.py (summary numbers in, a 0-100 quality score out;
  use --output-dir /tmp) may be run on the out-of-sample trades and its score put in the row's notes; it never replaces
  `review.py gate`. PICK PLAYBOOK (Saturday): use trade-performance-coach's
  review frame (process adherence, sizing discipline, repeated mistakes) on data/picks/score.json before changing the
  playbook.
- Weekly report, interim report, final report: dataviz before any chart; trade-performance-coach frame for the picks
  part; the docs skill when a report goes to a Claude doc. market_breadth from the pack may describe the week's market.
- Audit, audit review, audit debate: data:validate-data (methodology, arithmetic and bias checks of every number they
  re-run) and data:statistical-analysis; backtest-expert's bias checklist may be cited. Build sessions run
  code-review:code-review on every change to a script the verdict depends on (on a pull request or a diff) before it is
  merged, and once over the frozen scripts before 2026-12-07.
- Data plugin (installed 2026-11-23): data:statistical-analysis and data:explore-data in the lab (PART A slices, checking
  a candidate's data) and the reports; data:validate-data before any report is published (weekly, interim, final: it
  checks that the text claims no more than the numbers show); data:create-viz may replace hand-made charts (dataviz rules
  still apply). Its SQL and dashboard skills are not used (no warehouse; the dashboard is its own artifact).

## SUCCESS (what counts as a win)

THE ONE SENTENCE: the test succeeds if A1 PRIMARY PASSES - Quantavius's own weekly book (sh_judge; allocator report
judge_check.verdict.primary) has a higher Sharpe than the foundation-only equal weight (equal_f) scaled to the book's own
volatility, with bootstrap chance >= 0.9, over the verdict window 2026-12-07..2027-05-14 (FAIL at <= 0.10, otherwise
inconclusive) - and a pass is reported as "promising, not proof" (at P 0.9 about one test in ten passes with no skill),
never as "beat the market", with the A1 STRICT result (H1's all-benchmarks rule applied to the book, PRE-REGISTERED
VERDICT) printed beside it with equal prominence, and the number of weekly decisions (judge_check effective_sample)
quoted beside every A1 probability.
G1 (its picks: primary = daily ranking rank correlation, secondary = picks vs control list) and G2 (its lab strategies,
forward) are the other two headline tests; the three are never pooled, and a single pass carries that caveat.

## DATA FILES (every task)

Clarifies the prompts' "never retype prices". To get an Interactive Brokers or Twelve Data result into a file, (a) if the
harness saved a large result to a file, read or copy that file; (b) if it came back inline, paste the exact JSON text
you received into a quoted heredoc (cat > /tmp/x.json <<'EOF' ... EOF) and wrap it with python. Pasting verbatim tool
output is allowed and expected. Forbidden: typing, rounding, editing or inventing numbers yourself. Check with python
that array lengths match the bar count received; never print bar data back.
Bars come from the free feed in the repo (DATA FEED AND GITHUB JOBS; it has usually stored everything up to about 20-35
minutes ago): always `git pull` first and fetch from IBKR only
what is still missing (`python3 -I /tmp/repo/scripts/checks.py fresh /tmp/repo 5m|1d` lists stale symbols; `hist.py
plan` asks only for bars after the last stored one). Never edit fetch_free.py's output by hand.

## GIT (every task that writes to the repo)

`git -C /tmp/repo config user.name forward-test-bot` and `git -C /tmp/repo config user.email
forward-test-bot@users.noreply.github.com` first (tasks whose prompt had no git step do this too); commit with the
message the prompt or section names (e.g. GIT ("deep otm")), `git pull --rebase`, push. Workflow files must be committed
under the owner's identity or GitHub stops their schedules.

## LEDGER (every task that writes trade or log rows)

THE SHEET IS RETIRED (since 2026-11-23): no task writes to the sheet, and there is no sheet-sync task. Wherever a prompt
or section says to append or write rows to the sheet or one of its tabs, write the same rows to the repository ledger
only. The sheet stays as a read-only record of the days to 2026-11-22 (https://claude.ai/artifact/QvRtm7ymBmUFYC2EMMw5PN);
the dashboard (https://claude.ai/artifact/95HuUaCoRMm6VarNrd3A1k, data/dashboard.json) is the view.
How: write the rows (lists in the old sheet column order, or dicts with the ledger field names in scripts/ledger.py) to
/tmp/L.json and run `python3 -I /tmp/repo/scripts/ledger.py add /tmp/repo <KEY> /tmp/L.json`. Rows are upserted by key,
so re-runs never duplicate. Updated rows (status changes, marks) are passed again in full. Then GIT.
Keys and columns: Trades (A-M), VariantTrades (A-F), Options (A-M), DeepD1 ("Deep OTM" D1 rows, A-O), DeepSpreads (D2/D3
rows, A-U), Weekly ("Weekly options" A-R), CryptoTracks (closed trades, A-N), AdaptiveStocks (A-F), AgentTrades (A-L),
AgentPicks (A-I), Sentiment (A-J), Regime (A-K plus L-T: write a dict with the extended names from regime2.py), Events
(A-G), Live (A-N), MLShadow (A-N), Library (A-L), Allocation (A-M), Stats (A-R).
Tabs that lived only in the sheet have ledger tabs since 2026-11-23 (earlier rows copied from the sheet that day:
Strategy lab 1, Learning 8, Watchdog 6): "Strategy lab" -> StrategyLab, "Learning" -> Learning, "Watchdog" -> Watchdog,
"Data check" -> DataCheck, "Adaptive" change log -> AdaptiveLog. The old sheet names work as aliases in ledger.py (also
"Library trades", "Variant trades", "Deep OTM D1", "Deep OTM spreads", "Weekly options", "Crypto tracks", "Adaptive
stocks", "Agent trades", "Agent picks", "Live decisions", "ML shadow"). A "Data check" row written below as (date,
symbol or "-", check, count, first example, flag) goes to DataCheck; write it as a dict with DataCheck's field names:
check_time = the date, symbols = the symbol or "-", check, note = the count, detail = the first example, status = the flag.
Void trades: `ledger.py voids /tmp/repo` lists crypto-track trades void under the VOID (DATA) rule (CRYPTO TRACKS);
reports name them next to the crypto results.

## DATES (every task)

`python3 -I /tmp/repo/scripts/tcal.py today` prints the facts for today (New York): stock_test_active,
crypto_test_active, settle_only_window, full_trading_day, half_day, close_time, phase ("train" to 2027-05-14 /
"before" / "after"), frozen (always false: no holdout), weekly_expiry (YYYYMMDD), weekly_entry_day, week_entry_days,
is_friday_report_day, week_index. Use these instead of any date list written in a prompt.
Test (six months, owner decision 2026-11-21): stocks and options 2026-11-16 .. 2027-05-14; crypto to 2027-05-16; option
settlement to 2027-05-21; VERDICT WINDOW 2026-12-07 .. 2027-05-14 (109 trading days); second-half reading from
2027-02-01; INTERIM report 2027-02-16 (data to 2027-02-12); FINAL report 2027-05-18. If a prompt still names 2027-02-12 /
02-14 / 02-16 as the end of the test, tcal.py and this runbook win.
Setup calendar: week of 2026-11-23 finish the move to GitHub; 2026-11-30 to 2026-12-04 SHAKEDOWN (the new setup runs
alone, measured against ops/preregistration.md section 8); 2026-12-04 independent audit; 2026-12-07 code freeze and the
verdict window opens if the shakedown passed and no audit defect is open, otherwise both slide one week to 2026-12-14
(the end, 2027-05-14, does not move). Everything before the window stays in the ledgers, labelled warm-up history.
Holidays: 11-26, 12-25, 01-01, 01-18, 02-15, 03-26. Half days (no new stock or option entries, marks and settlements
only): 2026-11-27 and 2026-12-24 (close 13:00).

## INTERVENTIONS (every session, every task that changes the player)

Whenever you edit a scheduled task's prompt, model or schedule, the pick playbook, runbook text a task follows, or any
script Quantavius's results depend on, run `python3 scripts/interventions.py add REPO WHO KIND "what changed" "why"` in
the same session and commit it (WHO = owner | build-session | quantavius | other; KIND = prompt | playbook | code |
rule | data | model | schedule | other). Quantavius itself uses WHO=quantavius when it changes its own playbook or
settings. Never edit or delete rows. The nightly step `interventions.py auto` lists unlogged commits that touch watched
files (data/nightly/interventions.json) and the "autonomous since" day.
MODELS PINNED: the model of each sealing task is fixed from its first seal to 2027-05-14: the weekly book and its two
samplers (Fable), the model contest (Opus; Sonnet) and the daily challenger (Fable). Nobody changes a sealing task's
model during the window. If a model is withdrawn by its maker, the forced replacement is logged with `interventions.py
add ... model ...`, the lane entry's results before and after are reported separately, and for the weekly book the
change resets "autonomous since". data/nightly/interventions.json lists the models seen in each seal file
("seal_models"): more than one model in a file is flagged there and must be explained in the next weekly report.
WITNESS (picks 2026-11-23; seals and rankings 2026-11-24, external review N1, N3, N7): GitHub records when it first saw
every pick row, weekly / contest / daily seal row, sampler draft and ranking (scripts/witness.py on every push of those
files via the witness workflow, timed by GitHub's own push time; also on every tick and in the nightly), one file per
sighting in data/witness/obj/ (in the hash chain; merges can never drop a sighting). From 2026-11-30: a pick first seen
at or after 09:30 New York on its day does not count; a seal or ranking counts only if its exact content was first seen
before 09:30 on its effective day. Picks are scored from their first-seen copy, so a pick edited or deleted later is
still scored as first seen and the nightly lists it (score.json "integrity"; health alert WITNESS). Every task that seals
must therefore commit and push before 09:30, as the prompts already say.

## DATA FEED AND GITHUB JOBS (reference for every task)

FREE FEED: workflow .github/workflows/data.yml -> scripts/fetch_free.py stores bars straight into the repo from Alpaca's
free plan (SIP, every US exchange, at least 15 minutes old) and Cboe. History: daily 2 years, 5m 90 days, crypto 1h 1
year; daily bars and dividends/splits cover the whole S&P 100 snapshot (library universe). data/hist holds the long
research archive (daily since 2016, 5m for 2 years); only the strategy lab and the ML read it. Daily bars sit at 12:00
UTC of the trading date. IBKR quotes DOGE to the cent; the feed replaces those bars with full-precision ones. IBKR
stays the source for the last few minutes of bars (usually 6-8 per symbol), snapshots, earnings and the cross-check.
store.py follows the feed's merge rule for intraday bars (a stored bar keeps its prices and volume; only missing bars
are added, zero volumes filled); daily bars are overwritten (corporate-action adjustments).
SCHEDULE: ticks every 5 minutes Mon-Fri 09:00-15:55 ET from the external pinger (cron-job.org, ops/engine_pinger.md,
workflow_dispatch mode tick; token expiry 2027-06-15, renewed 2026-11-23); GitHub's own backup tick at :50 each hour
09:50-15:50 ET doubles as the watchdog (one GitHub issue "Health alert" when the pinger has a gap over 20 minutes).
Each tick: 5m bars for watchlist + control + SPY/QQQ/IWM, then scripts/engine.py, the witness and the dashboard.
Nightly bars, corporate actions, VIX/VIX3M and the borrow file at 17:40 ET (also refreshes all open option legs and
daily bars for picked stocks); crypto 15m / 1h / 1d bars every 3 hours at :32 UTC, each followed by `daily.py crypto`;
crypto ML fit at 10:17 UTC (05:17 ET, mode "mlcrypto"); ML nightly `daily.py ml` at 03:07 UTC; the nightly maths
("compute") on a schedule, cron "0 2 * * 2-6" = 21:00 New York (22:00 from 2027-03-14), or when the orchestrator
requests it. Every run is logged in ops/diag/ticks.json; `checks.py health` reads it.
ENGINE: scripts/engine.py is fixed code (no AI). From 09:35 it seals every baseline-A breakout with its detection time
and the real-time IEX price at that moment in data/decisions/engine/DAY.jsonl, and also seals L2/L3/L4/L14 signals
("strategy" set; measurement only, fills.py ignores them). When IEX and SIP bars disagree on which bar broke out, the
second row carries "revision": true; fills.py matches whichever row equals the replay's bar, ml.py keeps the first
prediction per candidate id, checks.py engine-report counts revisions once. ML AT DETECTION: on a tick where the engine
seals a new baseline breakout, the workflow step "Score" runs `ml.py predict-engine` and appends the take-or-skip
prediction to data/decisions/engine_ml/DAY.jsonl (first prediction stands, never overwritten; never delete that folder).
`ml.py predict` reuses that row for the same candidate id. Scoring only: learning is unchanged.
IMPLEMENTABLE FILLS (scripts/fills.py): every intraday result used for any verdict, including baseline A as the
benchmark, fills at the engine's detection price, else at the price 5 minutes after the signal bar (detections later
than 20 minutes use the 5-minute fallback); the ideal signal-close version is reported beside it (ideal_fills). Never
call the ideal version the result.
UNIVERSE: data/universe.json "intraday_wide" stays FALSE (foundation intraday strategies L1-L4, L14, the engine, baseline
A and the control list keep their 44-stock lists). "intraday_wide_data" = true stores 5-minute bars for the whole
universe (about 107 symbols) for research, ML and the lab (2-year archive extended by the one-off mode wide5m); wide
symbols are fetched after the core symbols and skipped in any tick already slower than 20 s (wide_skipped in
ops/diag/fetch_free.json). Set intraday_wide false and say so if a tick is over 60 s (ORCHESTRATOR 4f).
GITHUB MINUTES: GitHub Pro includes 3,000 Actions minutes a month; overage is allowed, capped by the owner's Actions
spending budget (USD 30 a month; Linux minutes USD 0.006 each beyond the allowance; expected cost USD 0-6 a month).
Measured: about 112 billed minutes on a full trading day before the nightly maths (about 120-130 with it), 22-29 on a
weekend day. `checks.py health` shows minutes_full_month_estimate. FALLBACK PAUSE ORDER, only if the month's projection
passes 3,000 minutes + the budget (about 8,000 at USD 30) or GitHub reports the budget reached, and say so in the
digest: 1 option bars (optbars), 2 the report-only nightly steps (costgrid, riskx, montecarlo) to Fridays only, 3 crypto
bars from every 3 hours to every 6. Never pause: ticks, the nightly fetch, the critical nightly steps. No lane job may
be added to the tick or to the critical steps. Lab sweeps, CPCV and ML-challenger training for the 2026-12-08 lane build
run as GitHub jobs; keep the month's total under about 7,000 minutes. Hourly crypto runs are NOT done (the tracks replay
every bar in order and fill on the next bar, so cadence changes no result).
BORROW: fetch_free.py tries Interactive Brokers' public short-stock file each night (data/borrow/DAY.json;
library.borrow_fee uses it point-in-time, floor 0.25%); while that host does not answer, the flat 0.5%/year is charged.
IBKR PATH: deferred on purpose to after the final report; live quotes stay with the AI tasks' read-only tools.
Not done: automatic dashboard snapshots (the connector cannot read the private repo).

## NIGHTLY MATHS, STRATEGY MENU, ALLOCATOR AND LANE (reference)

NIGHTLY CHAIN (scripts/nightly.py, mode "compute"): library.py, library.py --cost-mult 2, library.py --fill-lag 0,
allocator.py, stats.py, checks (engine-report, slip-report, health), dashboard.py, in that fixed order, plus the steps
witness, picks (before the allocator), aisleeve, rank, seals, calib, lane_auto, lane, replay_day (`checks.py
replay-days`: five random past days a night against the ledger), costgrid, riskx, chain, montecarlo, library_wide,
interventions. CRITICAL steps (stamp.ok): library x3, witness, picks, aisleeve, allocator, stats, chain; everything else
is optional (stamp.optional_failed), reported, not fatal. It commits data/nightly/ (stamp.json, library.json,
stats.json, allocator.json, checks.json, montecarlo.json, costgrid.json, riskx.json, chain.json, calib.json,
interventions.json), data/library/, data/allocator/, data/ledger/Library.jsonl, reports/stats/DAY.json and
data/dashboard.json; the chain head is printed in every nightly log (stamp "chain_head").
REPORT-ONLY STEPS (never feed the allocator, the judge or any verdict): costgrid (scripts/costgrid.py; each sleeve's average at 0.5x, 1x,
2x, 3x costs, break-even multiple, median gross move per trade over median cost); riskx (scripts/riskx.py; risk shares at the latest
weights, 60-day window; deepest drawdowns with recovery dates; one-day 95% VaR and expected shortfall, live days and
pre-test replay apart); chain (scripts/chain.py -> ops/chain.jsonl and data/nightly/chain.json; hash chain over the append-only evidence files: judge seals, trial log, lane champions,
engine detections and their ML scores, rankings, contest and daily seals; any edit or deletion breaks it and
health raises "CHAIN BROKEN"); montecarlo (scripts/montecarlo.py; 10,000 block-bootstrap paths of daily returns, 5-day blocks, seed 20261121, shared
draws, for the AI, the shadow allocators, equal weight and SPY: 47- and 63-day outcomes, chance of a loss, of a 10% fall,
and of falling 10% before gaining 10%; basis: the
replay reports/replay/2026-11-21-mc_series.json until 20 live days exist, then the live portfolio); library_wide
(data/library/intraday_wide.json: L2-L4 and L14 on the whole universe, counting a stock on a day only if it was on that
month's point-in-time list; intraday_wide_hindsight.json beside it only to show the difference; survivorship-biased
history, forward and research use only; a wide version may enter the lane after 2026-12-08 as a registered challenger,
never the book).
SHORT-PREMIUM STRESS: scripts/stress_short_premium.py -> reports/replay/2026-11-21-short_premium_stress.json (about the
size of the losses, not evidence of profit). POINT-IN-TIME EXPERIMENT: scripts/pit.py, data/pit/report.json.
SLEEVES IN THE BOOK (trim by purpose, a rule that ignores results): benchmarks, the control list (AC), baseline A,
adaptive ORB, the four crypto tracks, library L1-L17 (L14 opening-range breakdown short, L15 market-neutral momentum,
L16 SPY trend short, L17 multi-asset trend on TLT, IEF, GLD, DBC, EFA, EEM), the ML meta sleeve and Quantavius's own
sleeves: AP "Agent picks (open to close)" (data/picks/daily.json, 0.10% cost per side), AP2 "Agent picks (AI sizing and
holding)", AS "AI strategies (lab, approved)" (scripts/aisleeve.py, data/ai/daily.json: every gate-approved lab strategy,
equal weight, forward days only; no sleeve until one is approved) and the four "Agent picks: ..." sleeves (picks traded
under the baseline-A or adaptive rule, as at-the-money calls or as smart calls). allocator.OWN_SLEEVES (AP, AP2, AS,
Agent picks) are excluded from the foundation equal weight equal_f but stay in the book's menu. OUT OF THE BOOK
(allocator.DROPPED; ledger history stays): baseline-A variants A-G and T, option replays O, D1 lottery calls, D2/D3
spreads, W1-W4; and since 2026-11-25 by the COST RULE (owner decision, blind to results: median absolute gross move per
trade below 2x the round-trip cost; listing reports/costrule/2026-11-25.json) L2 VWAP pullback, L4 Gap fade and the
crypto strategies 15m fixed M1 and 15m adaptive M1 (allocator.COST_DROPPED_CRYPTO, left out of the pooled crypto
sleeves; their ledgers keep running). Options return later only as Quantavius's own per-pick choice (stock or call, with its reason) through
the 2026-12-08 lane build, never as a fixed overlay. L18 ETF IBS reversion was dropped (not in the library or lane).
ALLOCATOR (cycle-1 formula, scripts/allocator.py, docstring; the AI-judgment book uses scripts/judge.py brief / draft /
seal, scored by allocator.py as sh_judge): always 100% invested, no cash; weekly rebalancing; Thompson
draw renewed weekly (seed = ISO week + sleeve); drawdown breakers max(8%, 3 x 20-day vol) and max(4%, 2.5 x 10-day vol);
duplicates = sleeves equal to within 0.005 on at least 5 days on which both traded, counted once in the book and in
equal weight; every sleeve's backtest counts for at most 20 day-equivalents and a sleeve needs 10 active days before the
formula may back it; backtest days of L6, L7, L8, L10, L15 count at 25% (PRIOR_HAIR_SURV, survivorship); W1, W2, D2 and
D3 together capped at 25% (GROUP_CAP) for the formula, the simple rivals and the seals. Shadow allocators: risk parity
"sh_rp", minimum variance "sh_mv", recent winners "sh_win", and "sh_judge" (Quantavius's book), same sleeves, cap,
weekly rebalancing and costs. Reported nightly, never part of a verdict: forced_fill, exposure (beta to SPY and the
return after removing it), turnover_per_day, rebal_cost_pct_total, vol_forecast_pct, netted_exploratory.
stats.py: promising / losing / benched need n >= 20; q_bh, psr and dsr need n >= 10; below that "unproven (n<20)".
ML: a champion needs at least 60 taken out-of-sample trades and PBO < 0.5, no waiver (else "always take"); labels
y_stock = implementable-fill result, y_stock_ideal for comparison only. Training history for the ranker:
scripts/pit_train.py builds data/pit/train_1d.csv.gz (not committed, rebuilt from data/pit in about a minute; S&P 500
members on each day, departed companies included; label = next 5-day return minus that day's member median); prices in
data/pit end 2026-11-13, so the ranker (after 2026-12-07) needs a nightly refresh of S&P 500 membership and bars.
POINT-IN-TIME UNIVERSE: scripts/pitu.py gives for any date the 100 S&P 500 members of that time with the highest prior
dollar volume (cache data/pit/monthly_top100.json). The allocator's priors stay on today's S&P 100 (the pit stand-in is
not used as the backtest record).
CHALLENGER LANE (outside the frozen scripts; the verdict code never reads it, but its own-strategy entries can earn weight in Quantavius's book through LANE ADMISSION below): scripts/registry.py keeps
strategies/registry.json (every idea with a SHA-256 of its code, scored from the next full trading day after
registration: data/lane/scores.json) against SPY, equal weight, baseline A, risk parity, the formula ("ai" in
registry.YARDSTICKS) and the champion. Champion: ai_judgment (data/lane/champions.jsonl, 2026-11-23). Entries also
"formula" (scored from 2026-12-07), "judge_daily", "contest_opus", "contest_sonnet"; gate-PASS lab strategies are
registered automatically. Reviews on the third Tuesday of Feb, May, Aug, Nov (task "Lane review", first 2027-05-18):
promote with >= 60 forward days, bootstrap chance >= 0.98 against the champion and every yardstick, deflated Sharpe
chance >= 0.95 with the lifetime trial count; retire on a recent chance <= 0.10 of beating the best yardstick over 120
days or a forward drawdown above 20%. At most 6 new entries a month (3 until 2026-11-24; raised because the owner expects four or more new ideas a month; the deflated-Sharpe test counts every lifetime trial, so more entries make each promotion harder); a retrain is a new version with its own start.
LANE ADMISSION (2026-11-24, item 53; scripts/aisleeve.py): on the third Tuesday of every month from 2027-02-16, any lane
entry that is Quantavius's own strategy or model (not a seed, not a weekly book of kind "allocator", not retired) with
at least 40 forward days, a bootstrap chance >= 0.90 of beating every yardstick and a deflated-Sharpe chance >= 0.90
(lifetime trials) joins the AS sleeve pool from the next trading day, using the lane scores of the night before. It
leaves on a later admission day when its chance of beating the best yardstick over its last 120 forward days is <= 0.10,
or at once when the lane retires it. Log: data/ai/lane_admissions.jsonl (hash chain); current set:
data/ai/lane_admitted.json. Quantavius then weighs AS in its weekly book as it sees fit (25% cap). G2 still counts lab
approvals only; admitted lane entries are reported beside it.
DAILY CHALLENGER "judge_daily": every weekday (since 2026-11-26; Mondays and Thursdays before) at 08:41 New York from 2026-12-07, `judge.py seal ... --out
data/allocator/judge_daily.jsonl --daily`; on other days its last seal carries forward (scripts/seals.py). MODEL
CONTEST from 2026-11-29: Opus (Sun 13:41 ET) and Sonnet (Sun 13:56 ET) seal weekly weights from the identical evidence
pack into data/allocator/contest_opus.jsonl / contest_sonnet.jsonl; scripts/seals.py scores them and the weekly book
(contest_fable) with one method.
RANKING AND CONFIDENCE: the morning ranking (rank.py seal; nightly rank.py score -> data/picks/rank_score.json) is G1
primary; picks vs control list (scripts/picks.py, data/picks/score.json; five-day hold as a secondary reading) is G1
secondary; "cost_view" in score.json gives for AP and AP2 the costs' share of the gross move, the win rate after costs
and the break-even win rate (report only). scripts/calib.py scores "p=" and "p_beat_equal" (Brier, calibration bands;
data/nightly/calib.json).

## STOCKS (16:12 scoring)

MOVED TO GITHUB (2026-11-24): the AI task is retired. The Reddit snapshot is written to the Sentiment ledger by
`scripts/daily.py sentiment` right after the 06:40 ApeWisdom fetch (retry 07:30) (and by the first tick if the file was late), with the
same pre-registered rules (scripts/sentiment.py). Baseline A on the watchlist and the same rules on the control list are
scored by `scripts/daily.py stocks` in the 17:40 nightly fetch, from the stored 5-minute bars with the frozen
orb_daily.py; status in ops/diag/daily_stocks.json. Parity before the switch: identical trades and R on 2026-11-18,
-19, -20 and -23 for both lists. If the ledger already has rows for the day, the script compares instead of writing.
The steps below describe what the script does and remain the manual fallback.
(Earlier: the task also ran at 09:12 for the Reddit snapshot.)
1. Control list: symbols = `data/universe.json` "control" (22 random S&P 100 names, fixed). Contract ids from
   `data/contracts.json`; a missing id: search_contracts (exact symbol, US primary STK listing), then
   `python3 -I /tmp/repo/scripts/backfill.py contract /tmp/repo SYM ID`. Fetch their 5-minute bars like the watchlist
   (get_price_history STK FIVE_MINS ONE_DAY outside_rth false), save /tmp/bars_ctrl.json, store them with store.py 5m.
   DATA FILES applies: `git pull` first; the feed has usually stored the day already, so fetch from IBKR only what is
   still missing; build /tmp/bars_ctrl.json from data/bars/5m/<SYM>.jsonl with python (the day's bars from 09:30 to
   16:00 New York as {SYM: {"time", "open", "high", "low", "close"}}, the way checks.py replay_day builds them).
2. `python3 -I /tmp/repo/scripts/orb_daily.py /tmp/bars_ctrl.json DAY 16:00 > /tmp/ctrl.json`.
   Write each trade to VariantTrades with variant exactly "AC control" (DAY, "AC control", symbol, outcome, r_net,
   entry_time) and the one "Variants" row (DAY, "AC control", trades, wins, total_r_net, targets, stops); There is no
   ledger tab for "Variants": skip that summary row; it is derived from VariantTrades when needed. The baseline rules are unchanged; this only measures whether watchlist selection adds
   anything.
3. Skip step S4 (options O: retired). In S5 write only the "AC control" rows: run orb_variants.py as before for the
   control-list check, but write no variant B-G / T rows and no "Variants" rows other than AC control.
4. LEDGER: Trades and VariantTrades (AC rows only); no new Options rows; morning (09:12) run: Sentiment. GIT.

## DEEP OTM + WEEKLY

TOOLS: first read the TOOLS AND SKILLS section (near the top) for this task's tools and the skills never to use.
RETIRED 2026-11-23 (trim by purpose): open NOTHING new (no D1, D2, D3, W1-W4). Only mark and settle positions that are
still open (STEP 2 and STEP 4c), then RUN LOG and GIT ("deep otm"). When no position is open, reply "No deep OTM work:
the option structures were retired on 2026-11-23." and stop.
Marks and settlement use DATES (mark and settle every day of settle_only_window as well; on a holiday week the expiry
is the last open session, e.g. Thu 2026-12-24 and 2026-12-31). LEDGER: DeepD1, DeepSpreads, Weekly.
BARS: no price passes through the AI. SPY and stock 5-minute bars come from the store (hist.py export 5m). Option legs
are registered in data/opt_legs.json (scripts/optlegs.py: IBKR contract id -> OCC symbol, expiry, entry day); request
ops/fetch_request.json {"mode": "optbars"} and GitHub fetches the legs' 5-minute bars (fetch_free.py option_bars: Alpaca
historical option bars, OPRA trades, at least 15 minutes old, expired contracts included) into
data/bars/opt5m/OPT_<cid>.jsonl and writes ops/diag/optbars.json; `optlegs.py bars` hands them to the scripts. The 17:40
ET nightly fetch refreshes all open legs. dq.py does not check opt5m. RUN LOG: ops/diag/deep_otm.log, one line per run.
CATCH-UP: a run fired with "CATCH-UP DAY: YYYY-MM-DD" does that past day's marks and settlements from that day's bars
(no discretion); it is listed here when used. Used once: 2026-11-20 (on 2026-11-21).

## ADAPTIVE STOCKS

RUNS ON GITHUB, NOT AS AN AI TASK (since 2026-11-25, item 62): `scripts/daily.py adaptive` runs in the market-data
workflow right after the nightly fetch and the stocks scoring, calling orb_adaptive.py score and optimize with the same
inputs as the old 17:20 task (the last 240 stored 5-minute bars of SPY and the 22 watchlist stocks, DAYS = the last 3
stored dates). It writes AdaptiveStocks, one AdaptiveLog "stocks" row and data/state/stocks.json; run report
ops/diag/daily_adaptive.json. If the ledgers already hold the day it compares instead of writing (parity; identical on
2026-11-18 to 2026-11-24 with the settings in use each day). The AI task trig_01XqVW4yGp2cwSyEXUobMusn was
retired and disabled on 2026-11-25 with the owner's approval (prompt ops/prompts/adaptive.md), so GitHub writes. To re-run, push
ops/fetch_request.json with mode "nightly".
frozen is always false (no holdout): score (orb_adaptive.py score) and run optimize as the prompt says, to 2027-05-14.
Settings: data/state/stocks.json holds the stock adaptive settings (copied from "Adaptive"!B3/D3); with the sheet
retired, read and write them there instead of the sheet cells: {"live": {or_min, stop, target_r, spy},
"challenger": {"params": {...}, "since": DAY}}; commit the file with the run. Change-log rows go to the AdaptiveLog ledger.
LEDGER: AdaptiveStocks, AdaptiveLog. GIT.

## CRYPTO TRACKS

RUNS ON GITHUB, NOT AS AN AI TASK (since 2026-11-22): `scripts/daily.py crypto` runs in the market-data workflow right
after each crypto bar fetch (every 3 hours at :32 UTC), calling the same scripts with the same inputs as the old task
(including the ML crypto shadow prediction). State: data/state/crypto.json ("live", "challengers"); review log:
data/state/crypto_log.jsonl (the old "Adaptive" change log); open positions: data/state/crypto_open.json; run report:
ops/diag/daily_crypto.json. The daily review is the first run at or after 16:00 New York; retunes continue to the end
(no holdout). The AI task "crypto tracks" (trig_015nU8hZEPt63TqiZjdPYPDp) is disabled and replies "retired". To re-run,
push ops/fetch_request.json with mode "crypto".
Rules that stay: costs 0.2% per side for majors and 0.3% for small coins (crypto_tracks.py COST). VOID (DATA): a trade
whose stop distance is below 10% of its round-trip cost (0.04% X, 0.06% M) is void (entry and stop only):
ledger.trades(), stats.py, allocator.py and the ML crypto rows skip it; crypto_tracks.py refuses such a signal
(data_ok). It voids DOGE M2 2026-11-17 18:00 (-80.21 R, IBKR bars rounded to the cent) in both 1h tracks; the rows stay
in the ledger. The six 15m M1 trades with stops of 0.4-0.5% are real and stay in.

## AGENT EVENING

EVENING REVIEW AND PREP (2026-11-24, item 57; task "evening review + prep", Fable, 20:47 New York on weekdays): (1) for
today's picks and option picks, compare the stated reason, w, hold and p with what happened (daily and 5-minute bars, news
since the open, data/picks/score.json after the nightly maths if present); write data/picks/journal/<DAY>.json =
{"day", "made_at_ny", "per_pick": [{"symbol", "asset", "result_pct", "vs_control_pct", "what_happened", "reason_held":
true|false, "lesson"}], "lessons": [at most 3 claims later data can contradict]}. (2) Build tomorrow's shortlist from
after-hours earnings, 8-K filings and news: data/picks/prep/<NEXT TRADING DAY>.json = {"for_day", "made_at_ny",
"candidates": [{"symbol", "direction": "long"|"bear", "catalyst", "sources", "what_to_check_pre_market"}]} (at most 12).
Neither file is a pick or a seal. Research budget: 15 searches, 20 Twelve Data calls, 3 FMP calls, 2 Alpha Vantage calls.
The scripted evening scoring (below) is split since 2026-11-25 (item 62): GitHub writes the stock rows (`scripts/daily.py
picks-evening` after the nightly fetch, which also stores the picks' 5-minute bars: baseline A, adaptive with the day's
AdaptiveLog old_settings, and "no trade" rows; run report ops/diag/daily_picks_evening.json; parity identical on
2026-11-19, 11-20 and 11-23); the 20:20 AI task is then to write only the ATM-call and smart-call replays, which need IBKR
option data, reading the baseline trades from those rows. SWITCH: GitHub writes only when data/state/picks_evening.json
has "github_writes": true. It was set on 2026-11-25 in the session that pushed the option-only prompt
(ops/prompts/evening.md) with the owner's approval, so GitHub writes the stock rows and the AI task writes option rows only. Exception: GitHub
wrote the stock rows of 2026-11-24 during the build test, so the old prompt stops as "already scored" that night and the
option replays of 2026-11-24 are to be added by a later session (IBKR read-only option bars).

LEDGER AgentTrades. Its option replays are on the AI's own picks and continue. GIT.

## AGENT MORNING

TOOLS: first read the TOOLS AND SKILLS section (near the top) for this task's tools and the skills never to use.
Runs 08:05 New York; picks must be committed and pushed before 09:30 (INTERVENTIONS, WITNESS).
PICK PLAYBOOK: before STEP 3 read /tmp/repo/ops/pick_playbook.md and apply its CURRENT VERSION on top of the prompt's
filters (the prompt's filters always hold; the playbook can only add preferences or exclusions). Put "playbook v<N>" at
the start of each stock pick's "checks" cell.
SIZING, HOLDING AND CONFIDENCE: for every stock pick also decide, before 09:30 and from the same research, (1) its share
of today's picks, between 0.05 and 0.40, all shares adding up to 1.00 (more for higher conviction), (2) how many trading
days to hold it, 1 to 5 (1 = out at today's close; longer only when the catalyst plausibly carries for days, e.g. an
earnings beat with raised guidance), and (3) "p=0.xx", the chance the pick beats the control list's average today. Write
them at the start of the "checks" cell after the playbook tag, exactly like:
"playbook v1 | src=own | w=0.30 | hold=2 | price ..." (with p=0.xx). A pick without valid w/hold values is scored at
equal weight and one day (AP2). These choices can never be changed after 09:30. src: every pick is tagged src=own until
the ML stock ranker exists (after 2026-12-08); then the ranker hands the research a daily shortlist and every pick is
tagged src=own, src=ml or src=both and scored by source.
EXITS (2026-11-24, item 57): a stock pick may also carry "stop=-N" (percent below the entry, 1 to 50) and "tgt=N"
(percent above, 1 to 200) in its checks cell. They apply in AP2 only (AP and G1 stay open to close), on daily bars,
the stop first; a gap through a level exits at that day's open. Leave them out to hold to the close of the last
holding day.
REPORT-ONLY READINGS FOR THE REPORTS (2026-11-25, item 65; Dec 8 plan stage 5 built early): scripts/stage5.py as nightly
extra steps. data/nightly/spa.json: White's Reality Check and Hansen's SPA over every forward sleeve and rival book against
equal_f, and over every GitHub lab-sweep setting against SPY ("does the best thing we tried beat luck?"; trials without a
daily series are counted but cannot enter, so the p-values are optimistic by that much). data/nightly/ffattr.json:
Fama/French five factors plus momentum attribution of the A1 book (factors fetched by the 18:20 ext job into data/ext/ff;
the library lags a month or two). data/nightly/lane_health.json: healthy / under watch / decayed / switched off / too
new per lane entry (log data/lane/health_log.jsonl); it never overrides the retirement rule. The interim and final
reports quote all three. Also fixed the same day: registry series type lab_daily now rolls results dated on a non-trading
day to the next trading day (it dropped them), as lab_crypto does.

MIDDAY OPTION CHAINS AND THE SPREAD CHECK (2026-11-25, item 65): workflow mode optmid (cron 17:30 UTC on weekdays, 12:30
New York in winter and 13:30 from 2027-03-14; full trading days only) stores the same chains as the nightly snapshot in
data/optarch/snap_mid/<UND>/<DAY>.json.gz. scripts/spreadcheck.py (nightly extra step -> data/nightly/spreadcheck.json;
first reading reports/spreadcheck/2026-11-25.json) measures the half-spread of contracts with absolute delta 0.35-0.65
against picks.PUT_SLIP (2% a side when measured; 4% floor since 2026-11-25). First reading (one night, indicative feed): median 4.0%, 90th percentile 15.5%,
68% of contracts above 2%; SPY, QQQ, IWM and NVDA about 1%, many single stocks 18-27%. OWNER DECISION 2026-11-25: raise
the allowance (AP3 4% floor or the contract's own stored half-spread, whichever is wider; options_sim.py haircut 4% for
the Agent picks option replays; optarch.OPT_SLIP 4% and the lab gate's minimum allowance 4% for option strategies).

THE MORNING IN THREE RUNS, THE QUANT DESK AND THE INTRADAY DESK (owner decision 2026-11-26, item 70). The instructions of
these four jobs live in ops/agent/ (prep.md, decide.md, preopen.md, desk.md); their task prompts are thin (safety, clone,
"read your module"). The sections below (PICK PLAYBOOK, SIZING, EXITS, OPTION VIEWS, DAILY RANKING, ...) still apply to them.
MORNING PREP (07:15 New York, every day, Fable): on stock days it writes the research file data/picks/desk/<DAY>.json (a
shortlist of up to 12 verified candidates, each with its quant pack, and a technical line for each of the 44 ranked stocks)
and pushes it by 08:10; it also settles and picks coins and logs events and earnings dates. It makes no stock pick.
MORNING DECISION (08:17 on weekdays, Fable; the former morning research task, same id): reads the research file and
decides the stock and option picks and the ranking, all before 09:30. Each stock pick's checks carries the base rate it
relied on ("base=<rel_win_rate>@n<n>" or "base=none").
PRE-OPEN REFRESH (09:04 on weekdays, Fable): may withdraw a pick, add at most 2, exit a held position, and makes the picks
and the ranking itself if the decision run failed. Everything must be pushed by 09:25; it writes nothing from 09:27.
QUANT DESK (scripts/quant.py; read only): brief SYM [--gap PCT] [--bars FILE] = technical pack (returns, trend, RSI, ATR,
levels, relative volume, how far an ordinary day swings from its open and the stop or target that implies), the stock's own
gap history, the gap base rate over every S&P 500 member since 2016 (rel_* = against the same day's average stock), an
intraday profile from the 5-minute archive and the move the stored option chain implies; many SYM,... = one technical line
per stock; gaprate LO HI = the base rate alone; live SYM --bars FILE = the state of today's session (VWAP, opening range,
place in the range, volume against its own average by now, rest-of-day stop and target guide). Everything is computed from
bars dated before the day asked about. Base rates are history, not forecasts: quote n; under 30 is an anecdote.
INTRADAY DESK AND DAY TRADES (four checkpoints on weekdays, about 10:15, 11:30, 13:15 and 14:30 New York, Fable; two
tasks). At each: review open positions (exits as in ENTRY TIME, INTRADAY EXITS AND SHADOW VARIANTS) and optionally open
DAY TRADES. A day trade is a NEW AgentPicks row: NOWNY, asset "daytrade", symbol, contract id, why, checks "dt v1 |
setup=<name> | stop=-N.N | tgt=N.N | p=0.xx | ...", status "picked". Long only; the FIXED FILTERS of the stock picks
apply; at most 6 a day, at most 2 new per checkpoint, one per symbol per day, none after 15:20. SCORING (picks.daytrades,
sleeve "AP4 Agent picks: day trades", an own sleeve: out of the foundation benchmark, 50% cap in a seal, no rebalancing
cost): it fills at the open of the first 5-minute bar that opens after the LATER of the row's time and its first GitHub
sighting (from 2026-11-30 an unwitnessed row never counts; nothing fills after 15:30); it leaves at its stop or target
(percent from the entry, the stop first inside a bar), at a witnessed exit row (asset "daytrade", status "exit",
exits=<its picked_at>), or at the close of the day's last 5-minute bar; 0.10% a side; each trade is one sixth of the
sleeve and unused sixths earn nothing. p is the stated chance of a profit after costs (calibration only; score.json
"daytrades"). AP4 never enters G1 or AP. Since 2026-11-26 every exit (AP2, AP3, AP4) fills at the first bar that OPENS
after the sighting (a row seen at 10:15:20 fills at 10:20, not at the 10:15 open).
IF USAGE RUNS SHORT: the watchdog logs a usage-limit failure as before; the owner (or a build session on his word) drops
the 10:15 and 14:30 checkpoints first, then the pre-open refresh; the prep and decision runs are never dropped.

ENTRY TIME, INTRADAY EXITS AND SHADOW VARIANTS (2026-11-25, item 66). ENTRY: a stock pick may seal "entry=10:00" or
"entry=10:30" in its checks (default "entry=open"); AP2 then enters at the open of the 5-minute bar starting then, and its
stop and target count from that price and only after it. G1 and AP stay open to close. EXITS: to leave a held stock or
option position early, write a NEW AgentPicks row with the same asset and symbol, status "exit" and checks
"exits=<picked_at of the original> | <reason>" (never edit the original). It fills at the first price after the LATER of
its own time and its first GitHub sighting (from 2026-11-30; an unwitnessed row does not count): before 09:30 at that day's
open, 09:30-15:55 at the open of the next 5-minute bar, later at the next trading day's open; same costs as any exit.
It applies to AP2 (stocks) and AP3 (options); G1 and AP are unchanged. The 13:05 live run and the morning research may
write exits. SHADOW VARIANTS (report only, score.json "shadow", 3 trials logged): the same G1 picks entered at 10:00,
without gaps above 4%, and faded; they never enter G1, AP, AP2 or A1, and the Saturday playbook review may use them as
evidence under the usual bar.

STOCK AND OPTION PICK WITHDRAWALS (2026-11-25, item 65; built for the pre-open refresh of item 61): a stock or option pick
may be withdrawn BEFORE THE OPEN only. Write a NEW AgentPicks row with the same asset and symbol, status "withdrawn",
your own picked_at (NOWNY, before 09:30 New York and the same day as the original) and checks "withdraws=<picked_at of
the original> | <what changed>". Never edit or delete the original. scripts/picks.py drops the original from that day
(G1, AP, AP2, AP3) only if the withdrawal is first seen by GitHub before 09:30 (from 2026-11-30); a later or unwitnessed
withdrawal changes nothing, and the day's remaining picks share the weight as usual. Adding a pick before 09:30 is an
ordinary new picked row.

COIN PICKS AND DROPS (2026-11-25, item 63; build list item 4): picked coins no longer have to stay to the end.
STEP 1 settles them with `python3 -I /tmp/repo/scripts/daily.py coins /tmp/repo NOW > /tmp/po.json` (after storing the
missing hourly bars as before) instead of the crypto_tracks.py stream call: the output has the same "closed", "open"
and "state" as the stream, plus "coins" (the list that replaces coins), "dropped" and "pending_drops". For coins that
are not dropped the result is identical to the old call (checked on 2026-11-25). TO DROP a coin, write a NEW AgentPicks
row in STEP 2 with your own picked_at (NOWNY), asset "crypto", the same symbol and contract id, status "dropped", why =
the reason (what changed since you picked it), checks "drops=<original picked_at> | " + evidence; never rewrite or delete
the original row. The coin's track ends at the start of the first full hour after the later of that row's picked_at
and GitHub's first witness sighting of it (WITNESS; from 2026-11-30 an unwitnessed drop waits until it is seen): bars
before that hour are settled as usual, a position still open is closed at the open of that hour's bar (reason
"dropped", same costs and R), a pending entry is cancelled. The drop is applied at the next morning's STEP 1, which
writes the closed trades as usual and the shorter coin list. The limit of 8 is on coins HELD AT ONCE: a coin whose drop
has been applied no longer counts (a drop still in pending_drops does), and it may be picked again on a later day as a
new track. Every drop is a decision like a pick: give the reason, and the weekly report lists drops with their result.
OPTION VIEWS (2026-11-24, items 57 and 58; replaces BEARISH VIEWS AS PUTS): when an option expresses a directional view
better than the stock, you may write an option row instead of a stock pick: AgentPicks row with asset "option" (rows
with asset "put" from item 57 are still read), symbol = the stock, contract_id = the bought option's IBKR id, status
"picked", checks = "playbook v<N> | src=own | dir=bull|bear | occ=<OCC symbol> | occ2=<OCC symbol, spreads only> |
w=0.xx | hold=N | p=0.xx | stop=-N | tgt=N | " + why, the strikes, expiry, delta and implied volatility. Three shapes:
a call (rising view), a put (falling view), or a debit vertical: buy occ=, sell occ2= with the same underlying, expiry
and right and a strike farther out of the money (a higher strike for calls, a lower one for puts); anything else is
ignored. Same filters as stock picks (US listing, price >= $5, volume, market cap; control-list stocks excluded; no
short stock and no sold option except the covered leg of a debit vertical) plus: listed options with an expiry at
least 5 trading days after the last holding day, bought leg delta about 0.35 to 0.65 in size from IBKR
get_option_data, no earnings before expiry unless earnings is the reason. Check the spread in last night's stored
chain (data/optarch/snap/<SYMBOL>/<DAY>.json.gz; `scripts/optarch.py chain`). 0-3 option rows a day; their w add up to
1.00 among the options. stop and tgt are percent of the premium, or of the net debit for a spread (stop -20 to -80, tgt
20 to 200). The OCC symbol is SYMBOL + YYMMDD + C or P + strike x 1000 in 8 digits (for example DKS261204P00200000).
GitHub fetches every leg's 5-minute bars in the nightly fetch and scripts/picks.py scores them as sleeve "AP3 Agent
picks: options" (one of your own sleeves, up to 50% of the book): entry at the first option trade from 09:30 to 10:30
(for a spread, once both legs have traded; a net debit under $0.05 is no fill), marked on each day's last trade, exits
at the sealed stop or target (stop first; a spread's stop and target are seen only at bar ends), at the close of the
last holding day or on expiry day. $0.68 a contract per leg and a spread allowance per side are charged: 4% of each leg's premium (raised from 2% on
2026-11-25), or that contract's own half-spread in the previous night's stored chain if wider. A pick
with no trade by 10:30 is "no fill". It is a simulated position: nothing is ordered. The stock's move against the
control list, signed by the view, is reported beside G1 (score.json "options"); G1 itself counts the long stock picks.
EVENING REVIEW, SINCE 2026-11-26 (item 70; it overrides the task prompt where they differ): the review also (1) attributes
each of today's stock picks against the base rate it cited: run python3 -I scripts/quant.py brief for the pick with the
gap it had, and say whether it did better or worse than the base rate and why (stock-specific news, the market, the entry
time, the stop); (2) reviews every day trade of the day (score.json "daytrades" after the nightly, or the AgentPicks rows
with 5-minute bars from data/bars/5m): setup named, entry against VWAP and the opening range, whether the stop distance
fitted the stock's rest-of-day guide, what the exit cost or saved; (3) writes both into the journal file under
"attribution" and "day_trades" (at most 6 lines each) and marks in the prep file which leads are day-trade candidates.

EVENING JOURNAL AND PREP (2026-11-24, item 57): the evening review task writes data/picks/journal/<DAY>.json (what
each pick and put did, why it worked or failed, lessons) and data/picks/prep/<NEXT DAY>.json (tomorrow's candidates
from after-hours earnings, filings and news). READ the last five journal files and today's prep file before
researching. A prep candidate is a lead, not a pick: verify it pre-market like any other candidate.
DAILY RANKING (G1 primary): each full trading day before 09:30 score the 44 fixed stocks (watchlist + control list)
from -2 to +2 and seal them with `scripts/rank.py seal`.
Use data/ext/peers/latest.json for sector and peer moves (a pre-market move in a peer or a theme is information about
the stocks that share it).
KEEP WHAT YOU FETCH: save every Alpha Vantage EARNINGS_CALL_TRANSCRIPT, HISTORICAL_PUT_CALL_RATIO and INSIDER_TRANSACTIONS
result to /tmp and log it with `python3 -I /tmp/repo/scripts/extlog.py transcript|putcall|insider /tmp/repo FILE SYM
[QUARTER]` (data/ext/av/), so the readings accumulate as a point-in-time dataset.
SOURCE LOG (every run, from 2026-11-25): right after the ToolSearch that loads the data tools, write
ops/diag/morning_sources.json = {"day": DAY, "at": NOWNY, "loaded": [tool names that loaded], "not_loaded": [names
ToolSearch did not return], "failed": {"<tool>": "<exact error text>"}} with python, and update "failed" whenever a
call errors (plan, rate limit, auth, not connected). It is committed with the final GIT. It records tool access only;
it changes no pick.
FMP 8-K TIMING (2026-11-24): FMP secFilings 8k-latest lists filings by acceptance time, and the first 8-Ks of a day are
usually accepted after 08:30 New York, so a run at 08:05-08:15 often gets an empty list for today. Call it with from_date =
the previous trading day and to_date = DAY (one call), and treat an empty result as "no filings yet", not as a failed source.
MORE DATA FOR PICKING: the research may also use Twelve Data get_earnings, get_financials and get_analyst_data, and IBKR
option data for implied volatility (read-only).
LEDGER AgentPicks and AgentTrades.
EVENTS (every day, at most 3 extra searches and 2 fetches, after the picks): scheduled US macro events for today and the
next 2 trading days (CPI, PPI, jobs report, jobless claims, FOMC decision and minutes, Fed chair speeches, GDP, PCE,
retail sales, ISM) and earnings of watchlist or control-list companies (event text exactly "earnings SYM", e.g.
"earnings AAPL", so the library's earnings-drift strategy can find it; earnings dates themselves come from IBKR, MONDAY
step; the "earnings SYM" rows are a fallback). If a CPI / jobs report / FOMC date differs from data/macro.json, fix the
file (with the official source URL in the commit message) and GIT ("macro calendar"). Write new events to the Events
ledger (A-G: date, time ET, event, importance high/medium/low, consensus, actual (fill yesterday's actual if known),
source URL); skip events already logged.
MONDAY (or the first open day of the week) EARNINGS REFRESH: search_earnings_insights for all watchlist + control
contract ids (data/contracts.json), start = today minus 7 days, end = today plus 45 days, size 50, paginate until a
short page; save the responses as a JSON list to /tmp/earn.json and run
`python3 -I /tmp/repo/scripts/corp.py ingest-earnings /tmp/repo /tmp/earn.json`. GIT ("earnings dates").
GIT before 09:30.

## ORCHESTRATOR (nightly)

Runs 21:05 New York. All sheet writes below go to the ledger only (LEDGER). After the existing steps:
0. PIPELINE CHECK covers every live AI task (ops/tasks.json) including Live decisions (once a day at 13:05 on full
   trading days) and the weekly report (Fridays 21:41). Do NOT check, count as missing or fire
   trig_015nU8hZEPt63TqiZjdPYPDp (crypto tracks) or trig_0163kWWp8vAnJjwWjkJvbW9W (ML nightly), and do not expect the
   disabled picks review task. Instead read ops/diag/daily_crypto.json (healthy = "ok" true and "at" within the last 4
   hours) and data/nightly/ml_report.json (healthy = "ok" true and "date" is today or yesterday); report an unhealthy
   one first in the digest as "GitHub job failed", with its "error" / "ml_error" text. To re-run one, push
   ops/fetch_request.json with mode "crypto" or "mlnight". For the nightly snapshot take the crypto settings from
   data/state/crypto.json ("live", "challengers"). (The same applies to the Watchdog task.)
1. Universe daily bars: run `checks.py fresh /tmp/repo 1d` first. fresh true -> skip this step (the feed already stored
   today's bars and dividends/splits). Otherwise, only for the listed stale symbols (STK; VIX and VIX3M are IND on
   CBOE), get_price_history ONE_DAY step_count 5 (skip symbols whose data/bars/1d file is missing: the backfill fills
   them) with include_corporate_actions true (not for VIX/VIX3M); save the responses as {SYM: response} to /tmp/d1.json;
   store with store.py 1d, then `python3 -I /tmp/repo/scripts/corp.py ingest-bars /tmp/repo /tmp/d1.json` (dividends +
   splits). Contract ids: data/contracts.json (resolve missing ones as in STOCKS).
1b. CROSS-SOURCE CHECK: `python3 -I /tmp/repo/scripts/checks.py xcheck-plan /tmp/repo DAY` -> for each listed symbol
   Twelve Data get_time_series (interval 1day, outputsize 5); save as {SYM: response} to /tmp/td.json; then
   `checks.py xcheck /tmp/repo /tmp/td.json`. Flagged days are excluded from ML automatically; list them in the digest.
   A Twelve Data error -> note "xcheck skipped" and go on. RATE LIMIT: 8 credits per minute and the night needs 11
   calls (9 xcheck symbols + BTC/USD and ETH/USD 1h). Send the first 6 xcheck symbols together, then `sleep 65`, then the
   last 3 xcheck symbols plus BTC/USD and ETH/USD (5 calls). Never more than 6 in one minute. A call answered "run out
   of API credits" -> wait 65 s and send that one call once more. For the BTC/ETH 1h check (prompt STEP 3) use
   outputsize 5, not 3, so the hour of the last stored 1h bar is still in the reply.
1c. LIVE vs REPLAY (full trading days): `python3 -I /tmp/repo/scripts/checks.py parity /tmp/repo DAY` (after today's 5m
   bars are stored). ok false -> one "Data check" row (date, "-", "parity", issue count, first issue, "CHECK").
   Tolerances (checks.py parity docstring): OUTCOME flags (a candidate missing on one side, an entry more than 0.3%
   apart) always fail the day; FEATURE flags (a feature more than 2% apart) fail it only above 10% of the compared
   candidates. A routine day raises no flag, so every flag needs a look.
2. `python3 -I /tmp/repo/scripts/regime2.py /tmp/repo DAY` -> LEDGER Regime with the full row (A-K plus regime_row_L_T).
3. `python3 -I /tmp/repo/scripts/dq.py /tmp/repo DAY` -> one "Data check" row per issue type (date, symbol or "-", "dq",
   count, first example, flag "CHECK"); none: one row "dq ok". (dq tests daily jumps on the split/dividend-adjusted
   series, skips earnings-day gaps, lists only the last 30 days, allows 0.1% OHLC slack; bar timing close tolerance 0.6%.)
4. LEDGER COMPLETE AND PUSHED BEFORE THE MATHS: stats.py and allocator.py read the repo ledger, so every row of the day
   must be in the ledger and pushed before step 4b. The old mirror check of `ledger.py count` against the sheet's
   filledRange ("Trades", "Options", "Variant trades", "Weekly options", "Agent trades", "Adaptive stocks") is no longer
   needed because no task writes the sheet; CryptoTracks and MLShadow are ahead of the sheet by design.
4b. NIGHTLY MATHS ON GITHUB:
   (o) GitHub runs it ON A SCHEDULE at 21:00 New York (22:00 from 2027-03-14). First `git pull`: if
       data/nightly/stamp.json has day == DAY, ok == true and started within the last 45 minutes, skip (i) and (ii) and go
       to (iii). Otherwise (the scheduled run is late or failed, or from 2027-03-14 when it runs at 22:00) request it with
       (i) and (ii).
   (i) write /tmp/repo/ops/fetch_request.json = {"mode": "compute", "day": "DAY", "requested": "<UTC now, ISO>"}, commit
       and push it (starts scripts/nightly.py; NIGHTLY MATHS reference).
   (ii) wait: every 45 seconds `git -C /tmp/repo pull -q --rebase` and read data/nightly/stamp.json, for at most 6
       minutes. Ready = stamp.day == DAY and stamp.ok == true and stamp.started is later than your request.
   (iii) ready -> use the saved results and run nothing yourself: data/nightly/library.json (new_closed_rows are in the
       Library ledger, committed by GitHub; 17 strategies L1-L17), data/nightly/stats.json, data/nightly/allocator.json
       (LEDGER Allocation with every sheet_rows row whose date is not yet in the Allocation ledger, A-M),
       data/nightly/checks.json (steps 4c, 4d, 4f). Stats rows (phases "all", "v2", "verdict" from 2026-12-07 and the
       current phase) go to the Stats ledger (data/ledger/Stats.jsonl; reports/stats/DAY.json holds the full night); the
       sheet's Stats overwrite no longer applies.
   (iv) FALLBACK, not ready after 6 minutes or stamp.ok false: say so in the digest ("nightly maths on GitHub failed:
       <failed step and its error from stamp.json>") and run the same chain yourself, in this order:
       `library.py /tmp/repo DAY > /tmp/lib.json`, `library.py /tmp/repo DAY --cost-mult 2`,
       `library.py /tmp/repo DAY --fill-lag 0`, `allocator.py /tmp/repo DAY > /tmp/alloc.json`, `stats.py /tmp/repo DAY >
       /tmp/stats.json`, then use those outputs as in (iii) (LEDGER Library with new_closed_rows, Allocation, Stats;
       upserts make a repeat harmless) and push.
   FREEZE: from 2026-12-07 the allocator report's freeze.code_matches_freeze must be true; false -> "Data check" row
   "FREEZE BROKEN: <changed_files>" flagged CHECK and say so first in the digest (never edit ops/freeze.json). An open
   GitHub issue titled "FREEZE BROKEN" or "Health alert", or a health alert "CHAIN BROKEN", goes first in the digest.
4c. SLIPPAGE: `python3 -I /tmp/repo/scripts/checks.py slip-report /tmp/repo` (or checks.json) -> one digest line: rows,
   median spread %, median drift % per delay bucket, model cost %; model_cheaper_than_spread true -> flag CHECK.
4d. ENGINE: count today's data/decisions/engine/DAY.jsonl rows and their median delay_min; ops/diag/engine.json errors
   -> one "Data check" row. No rows on a full trading day while live runs found breakouts -> flag CHECK. Median
   delay_min above 20 -> one "Data check" row (date, "-", "engine delay", median, rows, "CHECK"): detections that late
   are ignored by fills.py (5-minute fallback). Check the cron-job.org job first (ops/engine_pinger.md).
4e. DASHBOARD: after the allocator and stats, `python3 -I /tmp/repo/scripts/dashboard.py /tmp/repo` (writes data/dashboard.json; GitHub also refreshes it every 5 minutes). Republishing the dashboard sends TWO
   files: index.html (from `dashboard.py html`) and lightweight-charts-5.0.9.js (from ops/dashboard/vendor/), with
   publish_files. Layout: SCOREBOARD (A1, G1, G2), AI LAYER, FOUNDATION (WEEKLY REPORT).
4f. HEALTH + ENGINE VS THE 5-MINUTE RULE: data/nightly/checks.json (or `checks.py health /tmp/repo` and `checks.py
   engine-report /tmp/repo`). One digest line: ticks today, longest gap, median and slowest tick seconds, Actions minutes
   this month so far and the month's projection vs 3,000 and vs 3,000 + budget (about 8,000), days until the pinger
   token expires (2027-06-15). Every entry of health.alerts -> one "Data check" row flagged CHECK and first in the
   digest. PINGER alert: the cron-job.org job is down or its token was rejected (ops/engine_pinger.md). TICK SLOW: a
   tick over 45 s; over 60 s doubles the minutes, so set "intraday_wide": false in data/universe.json and say so.
   engine_report: n, mean and median cost_vs_lag_pct for baseline and library rows; measurement only until 100+ rows.
   USAGE LOG: from the list_triggers result of the pipeline check, append one line per forward-test task to
   /tmp/repo/ops/diag/usage.jsonl with python: {"day": DAY, "task": short name, "fired_at": last_run.fired_at,
   "finished_at": last_run.finished_at, "minutes": difference rounded to 0.1, "status": last_run.status, "model": the
   task's model}. Copy the times exactly as list_triggers gives them; for tasks that run several times a day this is the
   latest run only (ops/tasks.json gives the runs a day). Token counts are not visible: run minutes and sessions per day
   are the measure.
5. DIGEST, scoreboard order: A1 first (judge_check: primary and strict, with effective_sample, "promising, not proof"
   on a primary pass), G1 (rank score; picks vs control), G2 (lab strategies forward), then the AI layer, then the
   foundation: verdict_check of the formula (result, robust, per benchmark incl. the vol-matched ones), the three shadow
   allocators (phases.<phase>.shadows and p_ai_beats.sh_rp / sh_mv / sh_win; say plainly when a simple rival is ahead),
   forced_fill (average weight held only to stay fully invested, and what that part returned), exposure (beta to SPY and
   the return left after removing it), implementable vs ideal fills (ideal_fills), turnover_per_day and
   rebal_cost_pct_total, the latest vol_forecast_pct, netted_exploratory (never part of any verdict), the formula
   portfolio vs SPY / equal weight / baseline A (verdict window from 2026-12-07, v2 and all) with the 2x-cost stress line,
   the top 3 allocator weights. Also: breadth score, Stats verdicts (promising / losing), dq issues, xcheck flags, parity
   result, the trial count, one costgrid line (sleeves that lose at today's costs or do not survive double costs) and one
   riskx line (largest risk share vs money share; AI book value at risk), saying plainly that both are reports, not
   rules; the GitHub minutes line (4f); optional nightly steps that failed (stamp.optional_failed).

WATCHDOG AND ORCHESTRATOR (2026-11-25, item 63; setup-debate build list item 2): the debate proposed one nightly health
task instead of four runs. Done as far as it helps: the watchdog was rebuilt on 2026-11-24 (trig_01McTsF59Sw14Dm9ogHwr8Z1,
07:35 and 19:35 New York, two runs instead of three; the old trig_01RqMJrg5xfsW4xYYgo7RZY4 is disabled after the new
one's first good run), and the orchestrator already re-runs the failed pipeline tasks it names (Watchdog ledger). The
watchdog is NOT folded into the 21:05 orchestrator, because that would lose checks: the 07:35 run sees the overnight
GitHub jobs, the ApeWisdom file and the extdata sources before the 08:05 morning research and can still fire a failed
Sunday sampler or seal inside its window; the 19:35 run sees the GitHub stocks, adaptive and picks-evening jobs before
the 20:20 and 20:47 evening tasks read them. A single 21:05 run would find a failed morning research about 13 hours late
and could no longer re-run anything inside its time window. Revisit only if the one-agent build (item 8) changes the
schedule.

## CHANGE FREEZE AND AUDIT (owner decision 2026-11-20)

- From 2026-11-30 (the shakedown week) no new features, strategies of the library, benchmarks or rule changes: only fixes
  for defects found by the audit or by a failing task, each listed in the CHANGE LOG with its date. (Strategy-lab
  candidates keep running through their gate: that is part of the tested process.)
- Independent audit on 2026-12-04 05:10 ET by a fresh session that did not build the system (scheduled task "Quantavius
  the 1st - independent audit"): look-ahead and data-snooping review of allocator.py, library.py, fills.py, corp.py,
  decisions.py, ml.py, stats.py and engine.py; a re-run of the nightly chain on a copy; a freeze rehearsal (hashes of the
  frozen files, twice, must match); it works through ops/audit_checklist.md step by step (look-ahead tests by truncation
  and by corrupting future data, fill feasibility, the AI-judgment seals, trial count, protocol, reproducibility) and
  records the actual result of every check; it runs `checks.py leaktest REPO DAY` on a day whose parity is ok (a planted
  look-ahead leak must make parity fail) and `no_orders.py REPO`, and records both. Report in reports/audit/2026-12-04.md.
  It changes no code. Open items for it: (a) the engine computes opening-range volume at 09:50-10:00 while the newest
  opening-range bar may still carry IEX-only volume (engine 1.09 vs replay 1.50 for AMZN on 2026-11-20); (b) the replay
  recomputes the prior day's crypto_score from today's crypto bars (16.4) where the live run read the stored regime row
  (17.5).
- Then a second AI review (07:41 ET, "audit review and challenge", reports/audit/2026-12-04-review.md) and a debate round
  (09:51 ET, "audit debate", reports/audit/2026-12-04-debate.md). At 12:13 ET the setup session sends the owner a plain
  summary and a shareable doc for his second reviewer; it packages the findings and does not judge them. The owner and
  his reviewer reply before 2026-12-06 evening. A human reviewer is the owner's to arrange; ops/audit_checklist.md is
  written so a person can follow it.
- FREEZE RECORD (external review N2, 2026-11-24): after the Dec 4 audit is triaged, a build session runs
  `python3 scripts/freeze.py record .` by hand on 2026-12-06 (or the day before the window opens), commits
  ops/freeze.json and tags it "freeze-<date>". The record holds the sha256 of every file in allocator.FROZEN_FILES (28
  scripts since 2026-11-24, incl. picks, aisleeve, rank, witness, stats, nightly, seals, chain, calib, optarch), the
  commit and the package pins of the nightly maths (numpy==2.5.3). If nobody records it, allocator.py writes it on its
  first run on or after the freeze date ("recorded_by": "nightly fallback"). Never edit that file. The freeze-guard
  workflow (freeze-guard.yml) checks every push to scripts/ against every file in the record and opens an issue
  "FREEZE BROKEN" on any change; the first commit holding ops/freeze.json gets the permanent tag "freeze-registered".
- NIGHTLY EXTRA STEPS: nightly.py is frozen, so new report-only nightly work (the lane's challengers, new readings) is
  listed in ops/nightly_extra.json (not frozen). Extra steps run last, are always optional and never change "ok".
- EVIDENCE PACK VERSION (review N9): every seal row stores pack_schema and pack_sha (judge.PACK_SCHEMA). A change to
  what brief() shows raises PACK_SCHEMA and is logged as an intervention, so the pack can still grow (the goal) and
  every change is visible next to the seals it affected.
- Defects found after 2026-12-07 follow ops/preregistration.md section 6 (log, both results reported).

AUDIT TRIAGE (overrides any prompt wording such as "only defects all three AI reports agree on"): EVERY blocking finding
from ANY reviewer (the audit, the AI review, the AI debate, the owner, the second person, the external reviewer) is
triaged before the window opens: reproduce it, then fix it, or record in reports/audit/ why it is not a defect, with the
evidence. Agreement between the AI reports is not required: they share a model family and its blind spots. Either human
reviewer can hold the window (it then opens 2026-12-14). Only findings nobody rates as blocking wait for the owner's
reply.

## LEARNING + STRATEGY LAB

TOOLS: first read the TOOLS AND SKILLS section (near the top) for this task's tools and the skills never to use.
Runs Monday, Wednesday, Friday and Saturday 23:15 to 2027-05-14 (four a week since 2026-11-24, owner: more new ideas;
default tracks: Monday options, Wednesday and Friday daily strategies / improve a baseline by ISO-week parity,
Saturday hourly crypto with the playbook review and the peer map; every run does PART A learning first). If phase is "after": reply "The forward test is over." and stop. The
lab, the learning and the playbook run to the end (no holdout). Rows go to the StrategyLab and Learning ledgers.
From 2026-12-07 never edit scripts/allocator.py, scripts/library.py, scripts/corp.py or scripts/fills.py, or any other
frozen script (CHANGE FREEZE AND AUDIT; the hash check in allocator.py reports any change).
SATURDAY runs: PART A and PART B (hourly crypto) as the prompt says; PICK PLAYBOOK (below) after PART A.
WEDNESDAY runs replace PART B: EVEN ISO weeks -> DAILY STRATEGIES; ODD ISO weeks -> IMPROVE A BASELINE. Read the IDEA
SHELF first.

DAILY STRATEGIES: research one documented idea for US stocks or ETFs on DAILY bars (long or long/short, holding days to
weeks) that differs from library L1-L17 and from every earlier StrategyLab row. Bars: the archive since 2016
(decisions.hist_bars(repo, "1d", SYM), S&P 100 + ETFs). Write strategy(bars_by_symbol) -> trades in /tmp/lab.py: signal
on a close, fill at the NEXT open, 0.05% cost per side, no look-ahead, at most 2 tuned parameters and 12 combinations,
tuned on 2016-2021 only and measured on 2022 onwards. Prefer ETFs or rules that do not depend on which stocks are in the
index today. ANY idea on individual stocks (daily or 5-minute bars) picks its stocks with scripts/pitu.py: a stock counts
on a date only if pitu.member(pitu.lists(repo), sym, date) is true (that month's point-in-time top 100 S&P 500 members
by prior dollar volume); put "universe": "pit" in cand.json. The gate refuses a stock idea without it unless cand.json
has a "survivorship_note" explaining why today's list cannot flatter the result (limits: the list is a stand-in for the
S&P 100; 5-minute bars exist only for today's names, so some bias remains for intraday ideas). Same cand.json, CPCV and
`review.py gate` as for crypto; APPROVED only on PASS. Save the code as strategies/<name>.py with a function
daily_series(repo) -> {date: sleeve return %} for forward scoring (registry series type "lab_daily"), and write the row
with market "US daily". Forward results count only after the Created date (pre-registration G2).

DEPTH AND THE INTRADAY TRACK (2026-11-26, item 70; it overrides the task prompt where they differ). DEPTH: a lab run may
use up to 90 minutes. Any grid of more than 6 settings goes to the GitHub sweep job (LAB SWEEPS ON GITHUB below), and the
run uses the waiting time for the write-up, the statistics (data:statistical-analysis) and the backtest-expert checklist.
Every candidate's note carries: the economic reason it should work, who is on the other side, the regime split (by VIX
tercile and by year), the result at double costs, and the worst 20 days. INTRADAY TRACK (any run may choose it; Friday is
its default): a DAY-TRADING strategy on 5-minute bars (data/hist/5m: two years, 111 symbols; data/bars/5m after it), in
and out the same day, for stocks or ETFs. Rules as for DAILY STRATEGIES, plus: signals use only completed bars; entries
fill at the OPEN of the next 5-minute bar; stops and targets inside a bar fill stop-first; flat by 15:55; 0.03% a side or
the symbol's estimate if larger; no entry in the first 5 minutes; the universe is the point-in-time list (pitu.py) or a
survivorship note. Tune on the first year, hold out the second, then CPCV. The module gives daily_series(repo) (the day's
net return in percent, computed from stored bars), so an approved one is scored every night by GitHub with no AI run,
joins the lane as series type lab_daily and can be admitted to the AS sleeve. Useful starting points are the quant
desk's findings (scripts/quant.py gaprate and the intraday profiles), the shadow variants in data/picks/score.json and
the day-trade record (score.json "daytrades"): an idea the desk keeps trading by hand is a candidate for a rule.

LAB SWEEPS ON GITHUB (2026-11-25, item 65; optional): instead of running a heavy sweep inside the session, write the
candidate as strategies/candidates/<id>.py with configs(repo, **args) -> {setting: {date: daily return %}} for EVERY
setting in the grid (same tuning split, cost and fill rules as above; optional trades(repo, setting, **args) -> per-trade
results), and strategies/requests/<id>.json = {"id", "module": "strategies/candidates/<id>.py", "args": {...},
"cpcv": [10, 2, 5]}; push both. The labrun workflow (scripts/labrun.py; no secrets, stored bars only) writes
strategies/results/<id>.json with every setting's series and the CPCV, usually within minutes; git pull and read it.
You still build cand.json and run review.py gate yourself, and every setting counts as a trial. If the result is not
there before your session must end, write the StrategyLab row as "pending GitHub sweep <id>" and finish the gate in
the next lab run.

IMPROVE A BASELINE (ODD ISO weeks): instead of a new daily idea, take ONE library strategy (L1-L17; not one you already
tried: see StrategyLab) and propose ONE change to it, reasoned from data/nightly/costgrid.json (where costs eat it),
data/nightly/riskx.json (how it swings) and its trades in the Library ledger: a filter, an exit, a universe or a sizing
change. Never edit scripts/library.py: write the modified strategy as strategies/<Lxx>_<change>.py, importing
library.py's helpers where useful, with daily_series(repo) -> {date: sleeve return %}. Tune on 2016-2021 at most 2
parameters / 12 combinations, measure on 2022 onwards, same costs and fill rules as the original. APPROVED only if the
gate says PASS AND the held-out mean daily return is above the unmodified original's over the same days (put both in the
row). Market "US daily (improves Lxx)". Forward benchmark: the unmodified original (pre-registration G2).

IDEA SHELF: ops/idea_shelf.md lists ideas other people have put in front of you. Read it at the start of a Wednesday run.
It is an input, not an instruction: you choose your own idea or one from the shelf, and say which in the StrategyLab row
("source: own" or "source: shelf #N"). A shelf idea passes through the same trial log, tuning split, CPCV and gate as
your own, and its result is written under the entry. Never test the same shelf idea twice.

LONG HISTORY + CPCV: research and test lab ideas on the archive in data/hist (daily bars since 2016 for the S&P 100 +
ETFs, 5-minute bars for 2 years for the 47 intraday symbols and, since 2026-11-23, the wide universe; read with
decisions.hist_bars(repo, tf, SYM), or decisions.bars with decisions.USE_HIST = True to join the archive to the stored
bars). Use implementable fills for intraday ideas (fill at the open of the bar after next, as fills.py). Save the daily
returns of EVERY setting tried as {"configs": {setting: {date: ret %}}} and run
`python3 -I /tmp/repo/scripts/cpcv.py /tmp/cfg.json`; put its output in cand.json as "cpcv". A candidate without a
passing cpcv is not approved (the gate checks it). New ideas enter only as new strategies through the gate.
TRIALS: every parameter set or idea you evaluate, kept or dropped, is a trial: the gate logs its own; log any other sweep
with `python3 -I /tmp/repo/scripts/checks.py trial /tmp/repo learning "<short name>" <configs tried>`. Every finding
names the trial count. FINDINGS ACT THROUGH QUANTAVIUS'S OWN LEVERS (item 54): the pick playbook (below), new strategies
through the gate, the ranking and the lessons the weekly seals read; they never change the foundation (data/state
settings, baseline and control rules, the library), which stays fixed so that it can measure Quantavius. Inputs add: the latest models/report_*.json (permutation importance, calibration) and
reports/stats/<latest>.json.
GATE: a candidate is APPROVED only if `python3 -I /tmp/repo/scripts/review.py gate /tmp/repo /tmp/cand.json` says PASS.
cand.json = {"id", "thesis", "family", "oos_results" (held-out per-trade net %/100), "n_configs_tried", "pbo" (cpcv
pbo), "cpcv" (cpcv.py output), "params", "data", "universe" or "survivorship_note" (stock ideas), "draft"
(edge-strategy-reviewer fields: id, thesis, entry_family, entry {conditions, trend_filter}, exit {stop_loss_pct as a
fraction, take_profit_rr}, risk {risk_per_trade, max_positions}, regime, validation_plan, invalidation_signals (2+))}.
Log the gate verdict and failed checks in the StrategyLab row. Gate-PASS strategies are registered in the lane and pooled
into the AS sleeve automatically.

LAB HYGIENE (enforced by review.py gate): cand.json must carry "params" = the exact settings of the run whose results
you submit (a non-empty dict; its hash is added to the trial name, so changed settings are a new trial) and "data" =
{"tf": "1d", "symbols": [every symbol used], "start", "end"} (the gate measures archive coverage on daily bars and needs
>= 98% of SPY's trading days for every symbol). Re-run the backtest from a clean process with those params written
explicitly; never rely on defaults left over from an earlier run. READ THE GATE'S "read_first" BLOCK BEFORE ANY RESULT
and report it first in the StrategyLab row: data quality, the trade count (under 30 = "too few to mean anything",
whatever the return), and the profit factor. A held-out profit factor above 5 is treated as a probable bug (look-ahead, a
fill on the signal bar, a cost not charged, a survivorship artefact): find the cause; only if there is none, say why in
"pf_explained".
NEIGHBOUR CHECK (2026-11-24, item 51): whenever more than one setting was tried, cand.json must also carry "grid" = every
setting tried, each {"params": {...}, "score": x}, scored on the TUNING data with the same measure used to choose. The
gate passes "neighbours_hold" only if the chosen setting's one-step neighbours have a median score above 0 and at least
half the chosen score: a plateau, not a lone peak. Report the read_first "neighbours" block with the data quality.

OPTIONS TRACK (2026-11-24, item 58): the lab may build option strategies (family "option") from the option archive:
data/optarch/snap/<UND>/<DAY>.json.gz (each night's chain from 2026-11-24 with bid, ask, last, implied volatility and
greeks, expiries within 50 days and strikes within 15% of spot, for SPY, QQQ, IWM and the 44 ranked stocks) and
data/optarch/hist/<UND>.csv.gz (daily trade bars of past contracts from about February 2024: every Friday expiry and
$5 strikes within 12% for SPY, QQQ and IWM, the monthly expiry within 12% for the stocks; each contract over its
last 70 days; built 2026-11-24 from 2024-02-05, about 2.0 million bars; the free plan refuses bars of contracts that
have not expired, so live contracts come only from the snapshots). Use the helpers in
scripts/optarch.py: fill() buys at the ask and sells at the bid from a snapshot, or adds 2% per leg per side to a daily
bar's price, and returns None for a bar with no volume (a stale print: drop that trade, never mark it at an old price);
spans_earnings() tells whether a holding period crosses a known earnings date (data/events/earnings.jsonl starts
2025-11; before that, source the dates or exclude single-stock trades). cand.json for an option idea carries "family":
"option" and "options": {"fill": "bidask" or "trade_plus_spread", "spread_allowance_pct": >= 2.0, "fee_per_contract":
>= 0.65, "stale_excluded": true, "earnings": "excluded" or "split" with "oos_ex_earnings" (results without the trades
that span earnings; mean > 0 with n >= 20)}. The gate adds four checks (options_fills_conservative, options_fees>=0.65,
options_no_stale_prices, options_earnings_handled) to every other check, unchanged. An approved option strategy joins
the AS sleeve through the lane like any other; its daily_series(repo) for forward scoring must enter at the ask and
mark at the bid from the nightly snapshots (the backfill is one-off and does not grow). The archive is market data only: nothing is ordered.

PEER MAP (SATURDAY runs only, before PART B): if data/ext/peers/latest.json is missing or older than 6 days, call IBKR
get_company_themes (max_themes 3, max_companies 5) for each of the 44 ranked stocks (contract ids in data/contracts.json),
in batches of at most 11 calls, writing each result straight to a file without printing it; collect them as {SYM:
result} in /tmp/peers.json and run `python3 -I /tmp/repo/scripts/extlog.py peers /tmp/repo /tmp/peers.json`.

PICK PLAYBOOK (SATURDAY runs only, after PART A): read ops/pick_playbook.md, data/picks/score.json (per-day picks vs
control list), the AgentPicks and AgentTrades ledgers, the picks section of the latest weekly report and any picks
findings in the Learning ledger (the picks review task is merged into the weekly report). If, and only if, a
finding about the picking has q <= 0.10 and at least 30 pick days behind it, you may change the playbook: ONE change per
week at most, small and concrete (for example "skip gap-only picks without a company catalyst"). Write the new version
at the top of ops/pick_playbook.md (version number + 1, date, the rule text in full), append {"version", "date",
"change", "evidence", "n", "q"} to data/picks/playbook_log.jsonl, log `checks.py trial /tmp/repo playbook "v<N>:
<change>" 1`, and log the change with `interventions.py add ... quantavius playbook ...` (INTERVENTIONS). No qualifying
finding: change nothing and say so. Never change the filters that keep picks liquid and long-only, the 09:30 cut-off or
the 3-8 picks range (the FIXED FILTERS of the morning prompt). The STARTING METHOD (a confirmed catalyst or a pre-market
gap, favour gap-ups) is Quantavius's own and the playbook may replace it. The playbook keeps learning to the end of the test.

## WEEKLY REPORT

TOOLS: first read the TOOLS AND SKILLS section (near the top) for this task's tools and the skills never to use.
Runs Fridays at 21:41 New York, after the scheduled nightly maths (report days: every Friday from 2026-11-20 to
2027-05-07; the 2027-01-01 and 2027-03-26 reports fall on holidays and cover trades through the day before). Read
data/nightly/stamp.json first; if the day's maths are missing, say so. Week N = week_index. The interim (2027-02-16) and
final (2027-05-18) reports are separate tasks. Follow ops/preregistration.md section 3.
LAYOUT (scoreboard, in this order): SCOREBOARD - A1 first (primary and strict side by side with equal prominence, with
the number of weekly decisions beside every A1 probability, worded "promising, not proof" on a primary pass, never "beat
the market"), then G1 (daily ranking primary; picks vs control secondary) and G2 (lab strategies forward); then the AI
LAYER (picks AP and AP2 with the playbook version; the latest seal's same_picks_share, the joint share of AP and AP2,
which hold the same stock picks, flagged when above 50%; the AI strategies sleeve and each approved strategy, the ML filter and
ranker, the AI-judgment book, the model contest when it starts); then the FOUNDATION (formula H1 /
verdict_check so far, simple rules, SPY, equal weight, baseline A, the control list, the library L1-L17, the crypto
tracks, data and plumbing health). From the 2027-02-05 report show the second half (from 2027-02-01) separately; freeze
nothing.
PICKS (absorbs the picks review): one section on Quantavius's picks against the watchlist and the control list
(data/picks/score.json, one cost-view line per sleeve: "won X% of picks, needs Y% to break even; costs took Z% of the
gross", calibration of p=), what worked and what did not, and any pattern worth a playbook change (the Saturday lab
decides; q <= 0.10 and 30 pick days).
AI-JUDGMENT BOOK: this week's sealed weights (median of three, n_samples, sample_dispersion) and its stated reasoning and
lessons from data/allocator/judge.jsonl, moves_over_5pts, its result against the formula and the simple rules, weeks
without a seal, judge_check; any seal file with more than one model in data/nightly/interventions.json "seal_models"
explained.
OTHER SECTIONS: Stats (q-values, DSR, alpha vs SPY/BTC, Kelly shares, breakers), control list vs watchlist, ML
(models/report_<latest>.json: champion, OOS mean vs always-take, PBO, drift flags; ML shadow results), Engine
(detections, median delay_min, misses; engine vs the 5-minute rule, checks.py engine-report), implementable vs ideal fills
(ideal_fills: how much the delay costs), allocator turnover and rebalancing cost, vol forecast vs realised,
netted_exploratory, Live decisions (spreads, implementation shortfall; checks.py slip-report for the week and to date:
spread cost, drift by delay bucket, and whether the simulated costs are cheaper than reality), the strategy library and
the formula allocator (data/allocator/report.json: portfolio vs SPY / equal weight / baseline A, current weights,
breakers, the 2x-cost stress result, and the "sharpe_gap_detectable" line so readers see how much evidence the window
holds), the three shadow allocators beside it (returns, Sharpe, drawdown and p_ai_beats for each; say plainly which is
ahead), the forced-fill share and what it returned, the SPY beta and the return after removing it, the Monte Carlo risk
table (data/nightly/montecarlo.json; say which basis, replay or live, and that it is never part of any verdict), one
costgrid line and one riskx line (reports, not rules), the health line for the week (ticks per day, slowest tick,
minutes used vs 3,000 and the budget, alerts). Data integrity: dq summary, bar timing convention, IBKR vs Twelve Data
flags, live-vs-replay parity, freeze status, trial count, and the report's stamp (commit,
data hash, package versions). Show stats for all data, v2 (from 2026-11-20) and the verdict window (from 2026-12-07)
side by side.
ONE-OFF SECTIONS, if not yet shown in an earlier weekly report: the point-in-time experiment
(data/pit/report.json) with its limits; the crash drill and the shadow replay of 2026-11-20
(reports/replay/2026-11-20-crash_drill.json, reports/replay/2026-11-20-shadows.json; runbook_history.md, CHANGES
2026-11-20 SECOND BATCH items 3 and 5) with their limits.

## PRE-REGISTERED VERDICT (changed 2026-11-19, before any data in the window)

THE VERDICT IS A1 (since 2026-11-23; ops/preregistration.md section 0 and amendments): Quantavius's own weekly book (the
AI-judgment seal, scored as sh_judge; allocator report judge_check, phase "verdict"), over the VERDICT WINDOW
2026-12-07..2027-05-14 (109 trading days), after per-symbol costs, with implementable fills.
- A1 PRIMARY = ONE comparison with power: the book against the foundation-only equal weight (equal_f, which excludes
  allocator.OWN_SLEEVES) scaled to the book's own volatility (judge_check.<phase>.primary): PASS if the bootstrap chance
  is >= 0.9 and its Sharpe is higher; FAIL at <= 0.10; otherwise INCONCLUSIVE. Reported as in SUCCESS.
- A1 STRICT = H1's rule (below) applied to the book (judge_check; rivals: the formula and the three simple rules),
  printed beside the primary with equal prominence.
- judge_check also reports effective_sample (weekly decisions) and sensitivity (10-day blocks; SPY beta removed): quote
  the number of weekly decisions beside every A1 probability. The second half (judge_check.second_half, from 2027-02-01)
  is reported separately; it freezes nothing.
The test is about the AI's process, not a fixed strategy.
H1'S RULE (the strict rule; the formula's verdict_check applies it mechanically to the cycle-1 formula, scripts/allocator.py
over all strategy sleeves, code frozen from 2026-12-07, weights from data up to the day before, rebalanced weekly; now a
FOUNDATION reading and a lane yardstick): does the portfolio beat (a) total-return SPY buy-and-hold, (b) an equal-weight mix of all
sleeves and (c) baseline A alone, on Sharpe AND max drawdown, with block-bootstrap P(mean > benchmark) >= 0.9?
- Against each benchmark, drawdown and the bootstrap must beat both the raw and the volatility-matched version (spy_vm,
  equal_vm, base_a_vm), so a mostly-cash portfolio cannot win on drawdown for free. The formula book is always 100%
  invested (no cash). Every intraday result uses implementable fills, including baseline A as the benchmark.
- THREE-WAY RESULT: PASS = every condition for every benchmark. FAIL = for at least one benchmark the bootstrap chance
  that the mean beats it is 0.10 or lower. Otherwise INCONCLUSIVE.
- ROBUST: a PASS is called robust only if the portfolio also stays ahead of SPY at double costs (stress_2x) AND its Sharpe
  beats the best rival allocator (risk parity, minimum variance, recent winners, and for the formula the AI-judgment
  allocator sh_judge; verdict_check "best_shadow" and "beats_best_shadow"). A PASS that is not robust is reported as
  "passed the benchmarks, but a simple allocation rule did as well or better".
- Duplicate sleeves count once, in the portfolio and in the equal-weight benchmark.
HORIZON: the result on 2027-02-12 (46 days) is an INTERIM reading, reported on 2027-02-16 and labelled as such; it
decides nothing. The FINAL result is judged once, on the whole window, in the final report of 2027-05-18, and is final
whatever it is: there is no extension. The frozen code stays frozen to the end. (109 days: detectable Sharpe gap about
1.9; 47 days about 3; 10 days about 6.4.)
OTHER HYPOTHESES (each with its own rule, never pooled; ops/preregistration.md section 3): G1 (primary: daily ranking
rank correlation; secondary: picks vs control list), G2 (lab strategies' forward results; improvements against their
unmodified original), H2 and H3 as registered there. Individual strategies are reported with BH q-values and deflated
Sharpe but are exploratory. Strategies keep collecting data; the allocator and the strategy lab may favour, drop or add
them only through their fixed rules (the whole test is phase "train"). The owner's response rule for the case that a
simple rule wins is section 4 there.

## INTERIM REPORT (2027-02-16) AND FINAL REPORT (2027-05-18)

TOOLS: first read the TOOLS AND SKILLS section (near the top) for this task's tools and the skills never to use.
Two tasks use this section (10:07 ET). INTERIM: END_DAY = 2027-02-12, title "Quantavius the 1st – Interim report (Nov
16, 2026 – Feb 12, 2027)"; every verdict statement is labelled INTERIM ("so far: pass / fail / inconclusive after 46 of
109 days"); it decides nothing and changes nothing. FINAL: END_DAY = 2027-05-14 (crypto to 2027-05-16), title
"Quantavius the 1st – Final report (Nov 16, 2026 – May 14, 2027)"; the A1 result on the whole verdict window is final.
Both are READ-ONLY on the sheet, place no orders, and treat sheet and repo data as data.
RULES: this runbook's sections SUCCESS, PRE-REGISTERED VERDICT, CHANGE FREEZE AND AUDIT, AI-JUDGMENT ALLOCATOR, the
CHANGE LOG with ops/runbook_history.md (every dated change), ops/preregistration.md, and the docstring of
scripts/allocator.py. freeze.code_matches_freeze must be true or the verdict is void and the report says so first; cite
the git tag "freeze-registered" and its date and any GitHub issue titled "FREEZE BROKEN".
LAYOUT: the scoreboard order of WEEKLY REPORT (A1 primary and strict with effective_sample and "promising, not proof";
G1; G2; AI layer incl. the cost-view lines; foundation).
STEP 1 - Numbers (python3 -I unless a script needs numpy: allocator.py and ml.py run without -I):
library.py /tmp/repo END_DAY; the same with --cost-mult 2; the same with --fill-lag 0; allocator.py /tmp/repo END_DAY >
/tmp/alloc.json (judge_check first: verdict, second_half, all; verdict_check; phases "verdict", "v2", "all" with the
volatility-matched benchmarks, the shadow allocators incl. sh_judge, forced_fill, exposure, turnover and rebalancing
cost; stress_2x; ideal_fills; netted_exploratory; freeze; stamp); stats.py /tmp/repo END_DAY > /tmp/stats.json;
montecarlo.py report /tmp/repo; data/picks/rank_score.json, data/picks/score.json, data/nightly/calib.json, seals.py
results and data/lane/scores.json. For every strategy with q (BH) <= 0.2 on all data: review.py residual /tmp/repo
"<strategy>" /tmp/resid. ML: decisions.py build, ml.py score; summarise ML shadow results in the second half (from
2027-02-01) vs always-take on the same candidates and the walk-forward / PBO history (models/report_*.json,
models/crypto_report_*). Integrity: dq.py /tmp/repo END_DAY, checks.py trials, slip-report, engine-report, health;
ledger.py voids.
STEP 2 - Analysis, in this order: the primary question (A1 primary and strict; robust or not and why: double costs and
the best rival; verdict window, then second half, v2 and all as context; ideal vs implementable fills); G1 and G2; the
book vs the formula vs simple rules (weights history, the sealed reasoning and lessons, weeks without a seal,
judge_check, verdict_check); how often and how much the formula was forced
to fill and what that returned; market beta and what is left after it; the Monte Carlo risk table; then each family:
library L1-L17 (1x and 2x costs), baseline A vs the control list, variants, adaptive ORB, options O, D1, D2/D3, W1-W4
(retired 2026-11-23; warm-up history: exit reasons, worst loss in units of the average win, entry Greeks), crypto by bar
size and fixed vs adaptive, agent picks (AP, AP2, by source) vs watchlist vs control list; learning proposals (with q)
and strategy-lab gate outcomes (incl. CPCV) with forward results; ML (did take/skip or instrument choice add value out
of sample; how often the champion was always-take; predictions at engine detection); the 5-minute engine (detections,
median delay, share within 20 minutes, revisions, engine fill vs the 5-minute rule); live decisions and slippage;
regime, breadth and event-day splits; data quality; task, pinger and GitHub reliability; gaps.
STEP 3 - Out-of-sample checks: the week-1 candidate named in the week 1 report, judged on trades after 2026-11-20 only;
strategies whose average changed sign between the first half and the second half (from 2027-02-01). Pre-registered
question for single strategies: does any strategy or the ML layer beat baseline A in the second half with q <= 0.10 and
DSR >= 0.9?
STEP 3b - SEPARATE HYPOTHESES AND THE RESPONSE RULE (ops/preregistration.md): compute H2 (strategy lab, forward trades of
APPROVED strategies against the fixed crypto strategies) and H3 (agent picks against the control list) exactly as its
section 3 says, each with its own pass / fail / inconclusive / too few to judge; never pool them with A1 or H1. Give the
short-premium sleeves' contribution (section 7; out of the book since 2026-11-23). Check the trigger of section 4: if
the best simple rule has a higher Sharpe than both the formula and the AI-judgment allocator over the verdict window so
far, write the REVIEW that section lists and the declared "version 2" approach (aim: the highest return after costs,
with Sharpe and worst drawdown beside it), and say plainly that H1 is still judged on the frozen formula. Report the
shakedown thresholds of section 8 and any defect logged under section 6.
STEP 4 - A NEW Claude Doc (Docs guide items ["topic.instructions"] first) with the title above: 1) headline (3-4
sentences: the A1 result, primary and strict, robust or not, interim or final, "promising, not proof" on a pass);
2) Quantavius's book and the formula vs benchmarks, raw and volatility-matched, and vs the rivals (table, cumulative
chart, 2x-cost line, ideal-fill line); 3) ranking table of every strategy and track (trades | average with unit | 90%
range | q (BH) | DSR | alpha | second-half average | average allocator weight | verdict); 4) out-of-sample checks;
5) strategy library; 6) stocks and the control list; 7) options; 8) crypto; 9) machine learning, allocator behaviour, the
engine, live decisions and slippage; 10) self-adapting machinery: did any of it improve results out of sample; 11) agent
picks (G1, cost view, calibration); 12) regime, events, data quality, the independent audit and what was done about it,
integrity checks, the crash drill, the point-in-time experiment, every change made during the test (CHANGE LOG,
ops/runbook_history.md, ops/interventions.jsonl and git log), reliability and gaps (with the report stamp and the
freeze-registered tag); 13) what this does and does not show (109 verdict days and the second half's 73 days are still
short for small edges; a fully invested book cannot step aside; corrections reduce but do not remove luck; simulated
fills and estimated costs may flatter; today's S&P 100 list (survivorship: measured in data/pit/report.json, backtest
priors of five sleeves cut to 25%); flat borrow fee unless data/borrow exists; Black-Scholes Greeks are estimates; rare
tail events cannot show in six months; not financial advice). Include the Sheet link (read-only record to 2026-11-22)
https://claude.ai/artifact/QvRtm7ymBmUFYC2EMMw5PN and the dashboard link https://claude.ai/artifact/95HuUaCoRMm6VarNrd3A1k.
If the doc fails, put the report in the reply.
STEP 5 - Reply with the doc link and a 5-line summary: the result (interim or final; A1 primary and strict; robust or
not), best and worst strategy, the book vs the formula vs simple rules, whether ML or adaptive tuning helped out of
sample, data-quality, audit and freeze status.

## AI-JUDGMENT ALLOCATOR (weekly, Sunday 13:23 ET)

THIS IS QUANTAVIUS'S OWN BOOK AND THE VERDICT (A1). The evidence pack has a section "your_own_work" (picks vs control by
day, playbook version, approved strategies' forward results, risk shares of the formula's weights, dated no later than
evidence_through) and "your_earlier_seals" (with their lessons). AP / AP2 (your own picks) and AS (your own approved
strategies) are eligible from their first live day. You are not obliged to hold them: judge them like any sleeve, on the
evidence. The formula and the simple rules are your foundation and your rivals. This task's code and rules do not
change during the window; its model is pinned (INTERVENTIONS).

1. `git pull` (so the sampler drafts are present), then `python3 /tmp/repo/scripts/judge.py brief /tmp/repo >
   /tmp/brief.json` and read it whole. It is the ONLY evidence: no web search, no other data, no memory of earlier weeks
   beyond "your_earlier_seals". If market_closed_now is false or phase_of_effective_day is "after", stop.
2. Think in four voices, each written down in 2-5 sentences: BULL (which sleeves deserve more than the formula gives
   them and why), BEAR (what in this evidence is noise, flattered or likely to reverse), RISK (concentration, sleeves
   that fall together, the regime, what the worst week for this mix looks like), then the DECISION.
3. Choose shares for the eligible sleeves only: each between 0.02 and 0.25, or up to 0.50 for your own sleeves AP, AP2
   and AS (item 55, 2026-11-24: so that you can back your own work harder), adding up to exactly 1.00, no cash. In the
   weekly book you may also set "as_mix" = {AS member: share} (members in the brief's your_own_work.as_members, shares
   adding up to 1.00) to weight the strategies inside AS yourself; without it AS weights them equally (W1, W2,
   D2 and D3 together at most 25%: judge.py refuses a seal above it). You may copy the formula, a simple rule or go
   your own way; say which and why. Changing shares costs money (rules in the brief), so do not churn without a reason.
   LESSONS: write "lessons": what the earlier seals got right and wrong against their own reasoning; each lesson must
   state a claim that later data can contradict. There is no limit on how far a share may move (the 5-point
   limit per lesson was removed on 2026-11-24, item 56; moves above 5 points are listed in the seal row and must be
   explained in "decision"). The brief's your_own_work now carries your latest learning findings and the lane
   standings: use them. CONFIDENCE: give "p_beat_equal" (scored by calib.py).
4. Write /tmp/seal.json = {"weights": {...}, "bull": "...", "bear": "...", "risk": "...", "decision": "...",
   "lessons": "...", "p_beat_equal": 0.xx, "model": "<your model id>"} and run
   `python3 /tmp/repo/scripts/judge.py seal /tmp/repo /tmp/seal.json`. If it is refused, fix exactly what the errors say
   and try again (at most 3 attempts). Never edit data/allocator/judge.jsonl by hand and never change an earlier seal.
5. GIT ("ai judgment seal"). Reply in 3 lines: effective day, the sealed shares, the decision in one sentence (and
   n_samples).

MEDIAN OF THREE: two sampler sessions (Sunday 13:02 and 13:11 ET, model pinned) judge the same evidence pack
independently and file drafts with `judge.py draft /tmp/repo /tmp/seal.json b|c`. Your own step 4 is unchanged;
`judge.py seal` then seals the MEDIAN share per sleeve over your weights and the drafts (row fields n_samples, samples,
sample_dispersion: the weekly measure of seal noise; the row also records the evidence-pack size pack_chars). Report the
sealed row's weights, not your own, and say n_samples. Fewer than two drafts: your own weights are sealed with
n_samples 1; say so. The row also lists moves_over_5pts against the previous seal: explain each one in "decision"
(nothing is clipped).
SAME PICKS (owner 2026-11-24, recorded, not capped): AP and AP2 hold the same morning stock picks, so their joint share
is the book's real bet on those few stocks. The row records same_picks_share and flags same_picks_over_50; when you put
more than 50% into AP and AP2 together, say why in "decision".
The model contest (Opus Sun 13:41 ET, Sonnet Sun 13:56 ET) and the daily challenger (every weekday 08:41 ET from
2026-12-07) seal from the same kind of pack into their own files (NIGHTLY MATHS reference, CHALLENGER LANE).

## LIVE DECISIONS (once a day at 13:05, on full trading days)

SINCE 2026-11-26 (item 70; it overrides the task prompt): SKIP STEP 0 (the position review). The intraday desk reviews
positions at its four checkpoints. This task keeps the midday snapshot, the breakout record and the slippage quotes.
ONE RUN A DAY at 13:05 New York, on full trading days. Write Live and MLShadow rows to the ledger only (LEDGER). Steps:
0. MIDDAY SNAPSHOT, BOTH snapshot sets, two calls per symbol: the 11:05 fields -> for each watchlist + control stock
   get_price_snapshot market_data_names ["bid_ask", "implied_volatility_percentile"]; the 13:05 fields -> stocks
   ["implied_vol_underlying", "historical_vol"] and each universe etf except VIX/VIX3M ["bid_ask"]. Ask for exactly these two fields per call
   (larger field sets time out). Save as {SYM: response} to /tmp/snap.json and run
   `python3 -I /tmp/repo/scripts/corp.py ingest-snap /tmp/repo /tmp/snap.json "NOWNY"`. These feed the per-symbol cost
   model and next day's IV features. Failures: skip that symbol.
1. Skipped: the free feed stores the bars (`git pull` first).
1b. ENGINE: `git pull` again; data/decisions/engine/DAY.jsonl lists the signals the 5-minute engine sealed (detection
   time, delay_min, real-time fill_price). Report each new candidate's engine delay and fill in the row's list column
   ("engine 6.2 min @ 123.45"); a candidate the engine missed -> "engine: missed". Machine-learning scores at detection
   come from GitHub (data/decisions/engine_ml/).
2. `python3 -I /tmp/repo/scripts/decisions.py live /tmp/repo DAY HH:MM > /tmp/cands.json` (HH:MM = now rounded down to 5
   minutes). Keep every candidate of the whole session so far that has no Live row yet (dedupe on decided_at + symbol +
   kind) -> /tmp/cands_kept.json.
3. Skipped (option quotes: the option sleeves of baseline A are retired).
3b. SLIPPAGE (no orders): for each kept candidate's stock call get_price_snapshot with market_data_names ["bid_ask"] only
   (one symbol per call); save as {SYM: response} to /tmp/q.json (DATA FILES rule) and run
   `python3 -I /tmp/repo/scripts/checks.py slip-save /tmp/repo /tmp/cands_kept.json /tmp/q.json "NOWNY"`. It records
   what a real market order would have paid now vs the simulated fill (spread, drift, delay). A failed quote -> skip that
   symbol.
4. `python3 -I /tmp/repo/scripts/ml.py predict /tmp/repo /tmp/cands_kept.json "NOWNY" > /tmp/pred.json` (reuses the
   engine_ml row for the same candidate id), then `python3 -I /tmp/repo/scripts/checks.py live-save /tmp/repo
   /tmp/cands_kept.json "NOWNY"` (keeps the features as seen live for the nightly live-vs-replay check).
5. Live rows (A-N: NOWNY, "orb", symbol, signal time, stock last (last bar close), "stock", "", "", "", "", "", ml choice,
   P(win), list), no "atm_call" rows; the predictions as MLShadow rows (A-N). LEDGER Live and MLShadow, then GIT ("live
   decisions").

WHY IT STAYS AN AI TASK (2026-11-25, item 63; setup-debate build list item 3): only this task produces (a) the midday
IBKR snapshots in data/snap (bid/ask, implied volatility, its 52-week percentile and historical volatility for the 44
stocks and the ETFs) and (b) the slippage quotes of data/quality/slippage.jsonl. GitHub cannot replace them: it has no
IBKR access, and the free feed's quote (iex_bid / iex_ask beside the engine's fill) is one exchange's quote, not the
national best bid and offer, so its spreads are wider and noisier. The snapshots feed the per-symbol cost model of
library.py (a frozen script: swapping its input would change the referee) and the machine-learning features iv_snap,
iv_hv and ivp_52w (decisions.py), for which no free source gives the same fields. The candidate list, the ML
predictions and the live-vs-replay rows (decisions.py live, ml.py predict, checks.py live-save) need no AI, but they are
a few seconds of the same run and moving them alone would save no session. So the task stays, once a day at 13:05,
weekday_runs 1. Revisit after the window: the midday option chain on GitHub (mode optmid, if switched on by the usage
session) could supply implied volatility, but only as a new, separately registered feature, never by swapping the input
of a frozen script.

## ML NIGHTLY (GitHub, 03:07 UTC daily)

RUNS ON GITHUB, NOT AS AN AI TASK (since 2026-11-22): `scripts/daily.py ml` at 03:07 UTC (22:07 New York in winter):
decisions.py build (labels: y_stock = implementable-fill result, y_stock_ideal for comparison only; the 2-year archive
rows are added automatically; data/decisions/hist/stock.jsonl.gz was built once on 2026-11-19; rebuild it by hand with `decisions.py build-hist
/tmp/repo` only if the 5-minute archive changes, as it did on 2026-11-23), ml.py score into the MLShadow ledger, ml.py train (models keep refitting to 2027-05-14:
no holdout), ml.py report. Summary: data/nightly/ml_report.json (health check: ORCHESTRATOR step 0). The AI task "ML
nightly" (trig_0163kWWp8vAnJjwWjkJvbW9W) is disabled. To re-run, push ops/fetch_request.json with mode "mlnight".
GitHub also fits the crypto family once more each day at 10:17 UTC (05:17 ET, mode "mlcrypto": `decisions.py build`,
then `ml.py train-crypto`, same evaluation and champion rule; models/crypto.pkl, models/crypto_report_DAY.json; no crypto
model until the walk-forward has 20 out-of-sample rows) and scores baseline breakouts at detection (DATA FEED AND GITHUB
JOBS, ML AT DETECTION). Never delete data/decisions/engine_ml/. Champion rule: NIGHTLY MATHS reference (ML).

## BACKFILL (00:15, 02:15, 05:15, 06:15 ET until complete)

`python3 -I /tmp/repo/scripts/backfill.py status /tmp/repo`; complete -> reply "Backfill complete." and stop.
Price history comes from the free feed, so most jobs are skipped automatically. A job with "contract_only": true ->
search_contracts, `backfill.py contract`, `backfill.py done /tmp/repo SYM TF`; fetch no prices for it.
Else `backfill.py next /tmp/repo 10`: for each job resolve a missing contract id (search_contracts; crypto: CRYPTO on
ZEROHASH; VIX/VIX3M: IND on CBOE), record it (`backfill.py contract`), call get_price_history with the job's step and
step_count (outside_rth false for STK/IND, true for CRYPTO; include_corporate_actions when the job says true), save raw
to /tmp/bf.json as {SYM: raw}, run store.py with the job's tf (and for 1d jobs `corp.py ingest-bars /tmp/repo
/tmp/bf.json`), then `backfill.py done`. The EARNINGS job: search_earnings_insights with its contract_ids, start = one
year ago (UTC midnight), size 50, offset += 50 until a short page; save the responses as a JSON list to /tmp/earn.json,
run `corp.py ingest-earnings /tmp/repo /tmp/earn.json`, then `backfill.py done /tmp/repo EARNINGS events`; a failure ->
`backfill.py fail ... <reason>`. When the backfill completes for the first time, run `decisions.py build` and
`ml.py train /tmp/repo DAY`. GIT ("backfill").

## CHANGE LOG

Full text of every item: ops/runbook_history.md (the runbook before consolidation). Item numbers as there ("CHANGES
2026-11-20" list, then ITEM 36-43). Equivalence check: reports/runbook_consolidation_2026-11-23.md.

| Item | Date | Change |
|---|---|---|
| - | 2026-11-19 | Free feed, 5-minute engine, implementable fills, long archive, CPCV; daily bars at 12:00 UTC |
| pre | 2026-11-20 | dq tolerances, stats n>=20, vol-scaled breakers, weekly Thompson draw, VOID (DATA), fully invested, L14-L16, ML champion rule, pinger |
| 1-2 | 2026-11-20 | Report instructions live in the runbook; nightly maths on GitHub (mode compute) |
| 3-5 | 2026-11-20 | Shadow allocators and ROBUST rule; forced-fill and exposure reports; crash drill (one-off) |
| 6-8 | 2026-11-20 | Borrow file; L17 multi-asset trend; intraday_wide stays false |
| 9-12 | 2026-11-20 | Crypto bars every 3 h; freeze guard and tag; health line and watchdog; engine-report |
| 13 | 2026-11-20 | ML prediction at engine detection (engine_ml) |
| 14 | 2026-11-20 | Second daily crypto ML fit 05:17 ET |
| 15 | 2026-11-20 | Survivorship haircut 25% for L6, L7, L8, L10, L15 |
| 16 | 2026-11-20 | Engine revision rows |
| 17 | 2026-11-21 | Dashboard signal chart (two-file publish) |
| 18 | 2026-11-21 | Monte Carlo risk report (report only) |
| 19 | 2026-11-21 | Six-month horizon; interim 2027-02-16, final 2027-05-18 |
| 20 | 2026-11-21 | AI-judgment allocator (weekly seal, sh_judge, judge_check) |
| 21 | 2026-11-21 | Point-in-time experiment; priors unchanged |
| 22 | 2026-11-21 | Audit checklist |
| 23 | 2026-11-21 | store.py keeps the feed's intraday bars; two open audit items |
| 24 | 2026-11-21 | Option bars from the free feed (optlegs, optbars) |
| 25 | 2026-11-21 | Pre-registration document; freeze list 17 scripts; parity tolerances, leaktest, replay-day, no-orders |
| 26 | 2026-11-21 | 25% group cap on short-premium sleeves |
| 27 | 2026-11-21 | Allocator duplicate rule (0.005 on 5 days); 20 day-equivalent cap; 10 active days |
| 28 | 2026-11-22 | Challenger lane and registry |
| 29 | 2026-11-22 | Honest point-in-time training history |
| 30 | 2026-11-22 | Fresh restart: shakedown, audit 2026-12-04, crypto tracks and ML nightly move to GitHub, audit review/debate |
| 31 | 2026-11-23 | costgrid, riskx, chain (report only); L18 dropped |
| 32 | 2026-11-23 | Refocus: picks scored directly, AP sleeve, daily lab, pick playbook, trim by purpose, headline order |
| 33 | 2026-11-23 | AS sleeve, improve-a-baseline, sizing and holding (AP2), ML shortlist, three-layer layout |
| 34 | 2026-11-23 | Autonomy: verdict is A1; no holdout; your_own_work; scoreboard |
| 35 | 2026-11-23 | A1 primary; G1 daily ranking; stated confidence; lessons; more picking data; daily challenger; model contest |
| 36 | 2026-11-23 | Interventions log; witness before 09:30; A1 benchmark equal_f; lessons cap |
| 37 | 2026-11-23 | Median of three; wording "promising, not proof"; stamp critical steps; audit triage; minutes pause order |
| 38 | 2026-11-23 | Idea shelf; sealing models pinned |
| 39 | 2026-11-23 | GitHub minutes: overage allowed under a budget; pause order is the fallback |
| 40 | 2026-11-23 | Budget USD 30; wide 5-minute data; library_wide; picks witness on push; five replay days |
| 41 | 2026-11-23 | Point-in-time universe (pitu.py) for the wide run and the lab |
| 42 | 2026-11-23 | Cost view for the picks (report only) |
| 43 | 2026-11-23 | Own sleeves out of equal_f; scheduled nightly maths; live decisions once at 13:05; picks review into weekly report Fri 21:41; sheet retired; daily challenger Mon/Thu; runbook consolidated (43g) |
| 44-49 | 2026-11-23 | Tools and skills per task; outside data on GitHub (ape.py, extdata.py, SEC_CONTACT secret); peer map; Alpha Vantage readings kept; Data and code-review plugins |
| 50 | 2026-11-24 | Stocks scoring and Reddit snapshot moved to GitHub (daily.py stocks, sentiment); AI stocks task retired |
| 51 | 2026-11-24 | Outside-repo review (ML for Trading, FinceptTerminal, awesome-quant): xcheck workflow (calendar vs exchange_calendars, DSR and PBO vs independent code and ml4t-diagnostic, baseline A re-run in backtesting.py), report only and isolated; lab gate neighbour check; nightly cost reality check (checks.py cost-check). Dec 8 plan gains the rest (session addendum) |
| 52 | 2026-11-24 | Lane cap 3 -> 6 new entries a month (registry.MAX_NEW_PER_MONTH), before any lane entry had a scored day |
| 53 | 2026-11-24 | Lane admission: own-strategy lane entries that beat every yardstick join the AS sleeve on fixed monthly dates from 2027-02-16 (aisleeve.py) |
| 54 | 2026-11-24 | Goal alignment review: findings act through Quantavius's own levers; the morning pick filters split into FIXED FILTERS and a STARTING METHOD the playbook may replace; registry wording; audit checklist step for admission (reports/goal_alignment_2026-11-24.md) |
| 55 | 2026-11-24 | Own sleeves AP, AP2, AS capped at 50% each in every seal (others stay 25%); weekly seal may set as_mix inside AS (judge.py, aisleeve.py) |
| 56 | 2026-11-24 | Setup debate (reports/setup_debate_2026-11-24.md): picks may include watchlist names; lab chooses its track; 5-point lesson limit removed; evidence pack gains learning findings and lane standings; Dec 8 work merged into ops/dec8_plan.md; watchdog to merge into the orchestrator |
| 57 | 2026-11-24 | Picks learn and exit: evening journal + next-day prep task; stop/target per pick (AP2); bearish views as simulated puts (sleeve AP3, own sleeve); journal in the evidence pack |
| 58 | 2026-11-24 | Options both ways and an options lab: option picks may be calls, puts or debit verticals (AP3 renamed "AP3 Agent picks: options"); option archive (scripts/optarch.py: nightly chain snapshots, a backfill of past contracts' daily bars); lab OPTIONS TRACK with four option checks in review.py gate |
| 59 | 2026-11-24 | External review of Nov 24 (Jarvis): witness for seals, drafts and rankings with GitHub's push clock, one file per sighting (N1, N7); picks scored from first-seen copies with an integrity report (N3); nightly critical-path fix (N4); freeze list 17 -> 28, hand freeze record (scripts/freeze.py), pinned numpy, guard reads the record, ops/nightly_extra.json (N2); nightly planted-leak test on the verdict path (N5); G1 coverage rule: a missed ranking day counts as IC 0 (N6); AI sessions per weekday in tasks.json and SPEC (N8); pack_schema and pack_sha in seal rows (N9); skipped fill-bar signals counted (N11); unfloored variance for reported Sharpe, volatility matching and beta (N12); picks reported by playbook version and by vehicle (N13) |
| 60 | 2026-11-24 | AP and AP2 joint share (same stock picks) recorded in every seal row as same_picks_share and flagged above 50%, not capped (owner choice); evidence pack schema 3 |
| 61 | 2026-11-24 | Lab runs four times a week (Mon, Wed, Fri, Sat 23:15 ET; Monday options track, Friday the other Wednesday track); more lab runs mean more trials, and every one is counted |
| 62 | 2026-11-25 | Adaptive stocks and the stock half of the evening picks scoring built on GitHub (scripts/daily.py adaptive, picks-evening; nightly fetch stores the picks' 5-minute bars); parity identical Nov 18-24; switching off the AI steps awaits the owner's approval (prompts in ops/prompts/proposed/) |
| 63 | 2026-11-25 | Setup-debate build list items 2-7: picked coins may be DROPPED (AGENT MORNING COIN PICKS AND DROPS; scripts/daily.py coins; a dropped coin leaves the 8-coin limit); live decisions stays an AI task (LIVE DECISIONS, WHY IT STAYS AN AI TASK); the watchdog stays separate from the orchestrator (WATCHDOG AND ORCHESTRATOR); the owner's list of disabled tasks he may delete (reports/retired_tasks_2026-11-25.md); tasks.json weekday_runs reviewed |
| 64 | 2026-11-25 | Owner approvals applied: adaptive stocks AI task retired (GitHub writes), evening task option replays only (github_writes true), watchdog task list and morning coin-drop prompt pushed live; COST RULE applied (L2, L4, crypto 15m fixed M1 and 15m adaptive M1 out of the book; allocator.DROPPED and COST_DROPPED_CRYPTO) |
| 65 | 2026-11-25 | Built early (owner): stock and option pick WITHDRAWALS before the open (picks.py); MIDDAY OPTION CHAINS (mode optmid) and the AP3 SPREAD CHECK (spreadcheck.py; first reading: median half-spread 4.0% vs the 2% allowance, owner decision); Dec 8 stage 1 (point-in-time history from 2016, nightly forward bars data/pit/fwd, labrun workflow) and stage 5 (stage5.py: SPA, Fama/French, lane health) as report-only or data-only work; registry lab_daily roll fix. Nothing registered or weighted |
| 66 | 2026-11-25 | Option spread allowance raised (owner): AP3 4% per side or the contract's own stored half-spread if wider (picks.slip_for); options_sim.py haircut 2.5% -> 4%; optarch.OPT_SLIP and the lab gate minimum 2% -> 4%. Rows already written keep their costs |
| 67 | 2026-11-25 | Entry time per pick (entry=10:00 / 10:30, AP2), witnessed intraday exits (status exit, exits=, AP2 and AP3), three report-only shadow variants of the picks (3 trials); pick 5-minute bars kept 10 days; ApeWisdom fetched at 06:40 with a 07:30 retry; morning prompt shows its calibration; live decisions may write exits |
| 68 | 2026-11-25 | Pre-freeze code review (reports/audit/2026-11-25-code-review.md; review pull request #1 closed unmerged): seal scoring uses per-sleeve caps (allocator.seal_cap, 50% own sleeves) in allocator and seals.py; seal rows that raise while checked are counted (judge_check.seal_rows_with_errors, seals rows_with_errors) instead of silently dropped; as_mix taken from the scored row (allocator.judge_seal_rows); G1 needs 60 sealed days (rank.summary sealed_days); AP3 open positions not closed on the run day, half-day expiry priced on its own bars; L13 enters and exits at the next open. Tests: tests/test_prefreeze_2026_11_25.py |
| 69 | 2026-11-26 | Orchestrator trig_01PgUGPDdTViNz1u3Wkqy4GW moved from Sonnet to Opus (claude-opus-5-5), model only, on the owner's "apply" (approval of 2026-11-23, room check in reports/usage/2026-11-25.md); no prompt, schedule, rule or sleeve change |
| 70 | 2026-11-26 | Restructure for depth and day trading (owner): the morning becomes three runs (prep 07:15, decision 08:17, pre-open refresh 09:04), the quant desk scripts/quant.py, the intraday desk with four checkpoints and the own sleeve AP4 (day trades), exits fill at the first bar opening after the sighting, the lab gets a longer budget and an intraday track, the evening review moves to Fable and attributes picks against base rates, the daily challenger seals every weekday; job modules in ops/agent/ |
