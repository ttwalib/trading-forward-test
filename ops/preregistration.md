# Quantavius the 1st: pre-registration record

This file is the dated record of what the forward test will be judged on. Everything here was written before the
verdict window opens on 2026-12-07. The runbook (`ops/runbook.md`) holds the working detail; where the two differ on a
judging rule, this file and the runbook section PRE-REGISTERED VERDICT are meant to agree, and a difference is a defect
to be logged below. This file was first committed on 2026-11-21 (commit 2e4faf8). The tag
`prereg-2026-11-21` marks a data commit of the same day that holds it; GitHub stores the push time.

Nothing is traded. All results are simulated on real market prices. This is testing, not financial advice.

## 0. THE ULTIMATE GOAL (owner, 2026-11-23; supersedes every earlier or conflicting goal in this file and the runbook)

AUTONOMY. Quantavius uses its own judgment and machine learning on real market data to pick its own stocks, to
formulate and develop its own winning strategies, and to decide how its own book is run. The fixed rules, the
strategy library and the benchmarks are the FOUNDATION: a baseline it builds on and is measured against, not the
thing being tested. The test asks one question at three levels: does Quantavius's own judgment beat the foundation,
forward, after costs?

Principle: FREEZE THE REFEREE, NOT THE PLAYER. From the window's start the scoring code (allocator, judge rules,
ledger, calendar, fills, costs: section 5) cannot change. What Quantavius decides keeps evolving to the end:
its picks, its playbook, its strategies, its models, its weekly allocation. Every such decision is sealed before the
outcome it is scored on, so no holdout is needed for validity. There is therefore no frozen holdout any more; the
second half (from 2027-02-01) is reported separately as a robustness reading only.

## 0b. What counts as success, and the autonomy statement (2026-11-23, before the window)

SUCCESS is one sentence (worded 2026-11-23 after the external review: a PASS is reported as PROMISING, NOT PROOF, never as "beat the market"; at P 0.9 about one test in ten passes with no skill; the A1 STRICT result is always printed beside it): the test succeeds if A1 PRIMARY is PASS at the end of the window (Quantavius's own weekly book beats the
volatility-matched equal weight of the foundation sleeves, bootstrap P >= 0.9 and a higher Sharpe). Everything else is evidence
for how to read that result, never a second way to pass:
- A SKILL SIGNAL (reported as such, never as a pass) needs A1 not FAIL and at least one of G1 PRIMARY (daily ranking) or G1
  picks with P >= 0.95; two chances, so the bar is higher than 0.9.
- G2, the model contest, the daily challenger, the calibration scores, H1, H3 and every foundation reading are reported with
  their raw numbers and decide nothing.
- With about 109 days an INCONCLUSIVE A1 is the most likely honest result even if Quantavius has some skill; the report says
  so and points to G1, which has far more observations.
AUTONOMY STATEMENT: every change by the owner, a build session or Quantavius itself to a prompt, the pick playbook, a rule, a
script Quantavius's results depend on, a model or a schedule is a row in `ops/interventions.jsonl` (append only, in the hash
chain; `scripts/interventions.py`), and the nightly report `data/nightly/interventions.json` lists the watched commits too.
Reports quote the date of the last intervention as "autonomous since". Regimes are tagged per day (allocator `regime`) and the
reports show the result by regime so one trend cannot explain a pass. A model change for a sealing task is an intervention.

## 1. Amendment log

Changes made before the window are allowed if they are dated and visible. After 2026-12-07 only defects may be fixed
(section 6).

| Date | Amendment | Why |
|---|---|---|
| 2026-11-19 | Original question: does the AI-managed portfolio beat SPY, an equal-weight mix and baseline A over the verdict window, on Sharpe and drawdown, with bootstrap chance of at least 0.9? Volatility-matched SPY and implementable fills added the same day. | First registration. |
| 2026-11-20 | Three-way result (pass, fail, inconclusive). Always fully invested (owner decision). Volatility-matched versions of all three benchmarks. Weekly rebalancing. Duplicate sleeves count once. Three shadow allocators; a pass is "robust" only if the AI also beats SPY at double costs and the best shadow on Sharpe. Stock-picking backtests count at 25%. Strategies L14 to L17 added. | Replay showed no skill on past data; the owner did not want a cash-heavy book. |
| 2026-11-21 | Six-month horizon: window 2026-12-07 to 2027-05-14 (109 trading days). The 2027-02-12 reading is interim and decides nothing. No extension. | A 46-day window could only detect a very large lead. This also removes the earlier two-looks problem. |
| 2026-11-21 | AI-judgment allocator (`sh_judge`) added as a rival of the formula and included in the robust rule. | To test AI judgment itself, not only a formula. |
| 2026-11-21 | Freeze list extended from 4 to 17 scripts (section 5). | External review: the calendar, the seal rules, the ledger and the sleeve-scoring scripts could change the verdict but were not frozen. |
| 2026-11-21 | Separate hypotheses H2 and H3 registered (section 3). H1 is unchanged. | External review: the strategy lab and the agent picks had no rule of their own. |
| 2026-11-21 | Response rule if a simple rule wins (section 4, owner decision). | Decide in advance what a disappointing result leads to. |
| 2026-11-22 | Owner confirmed in writing: H1 stays on the frozen formula; the revised approach runs beside it as a labelled challenger and never counts towards H1. Owner also confirmed H1-H3 as registered. | Removes the last open choice in section 4. |
| 2026-11-22 | Challenger lane (runbook items 28-29): register, forward scoring, fixed quarterly reviews from 2027-05-18, promotion and retirement rules, monthly cap, honest point-in-time training history. Outside the frozen scripts; no weight in H1, H2 or H3. | Owner wants the test to keep running and building on new data. |
| 2026-11-22 | Fresh restart (runbook item 30): the setup is finished this week (scripted work moves to GitHub with the repo ledger as the only record; sleeves trimmed by a rule that ignores results), runs alone in a shakedown from 2026-11-30 to 2026-12-04, is audited on 2026-12-04 (moved from 2026-12-01), and the freeze and verdict window open on 2026-12-07 only if the shakedown met section 8 and no audit defect is open; otherwise both move to 2026-12-14. The end date stays 2027-05-14. The trial count is not reset, no data is deleted (everything before the window is warm-up history, as before), and no strategy, allocator, benchmark or verdict rule changes. | Owner decision: start the judged window on a finished, tested setup instead of changing it during the window. Written before any data in the window exists. |
| 2026-11-23 | Pinger token renewed by the owner (expiry 2027-06-15, after the test ends). No backup owner for the pinger: the owner accepts the risk. | Owner decisions; closes two items of the external review. A pinger outage cannot change verdict numbers (fills.py falls back to the bar 5 minutes after the signal); it only degrades the engine's timing evidence, and the health alert reports it. |
| 2026-11-23 | Audit review on 2026-12-04: the independent audit (05:10 ET, model Fable) is challenged by a second AI review (07:41 ET, model Opus, reports/audit/2026-12-04-review.md) and a debate round that settles each disputed point by re-running the test (09:51 ET, reports/audit/2026-12-04-debate.md: settled defect / settled risk / dismissed / disputed). The owner and a second person he chooses then read the plain summary and reply before 2026-12-06. A settled defect that blocks, or a failed shakedown, moves the window to 2026-12-14. | Owner decision: human review by the owner and one more person, plus an AI that debates the findings, so that no single AI session's blind spot decides the freeze. |
| 2026-11-23 | Repository review (HKUDS/Vibe-Trading, FinceptTerminal): three report-only nightly steps added (break-even cost per sleeve, risk breakdown, tamper-evident hash chain over the append-only evidence files; runbook item 31). One trial logged for a library sleeve L18 ETF IBS reversion, whose rule was written down before its backtest; the backtest loses after costs (2,128 trades, +0.015% gross and -0.086% net per trade), so it is held back pending the owner's decision. After 2026-12-07, in the lane only: AI model contest, factor library, strategy health tracking, leveraged-ETF and VIX strategies, qlib reference model. | Owner decision. Nothing here changes a strategy, the allocator, a benchmark or the verdict rule. |
| 2026-11-23 | L18 ETF IBS reversion DROPPED by the owner: not added to the library and not placed in the lane. Its one trial stays in the lifetime trial log. | Owner decision after the pre-declared backtest lost after costs; a losing sleeve could still receive weight through the always-invested fill. |
| 2026-11-23 | REFOCUS ON THE GOAL (runbook item 32). The owner's goal is an AI that picks its own stocks and develops its own winning strategies, so the two hypotheses that measure exactly that become the headline: G1 (the AI's picks, now measured directly as open-to-close returns against the random control list; the old breakout-rule comparison H3 stays as a secondary reading) and G2 (the strategy lab, formerly H2, widened to daily stock and ETF strategies). H1, the allocation verdict, is unchanged in every rule and is reported beside them as the portfolio-level test. New sleeve "AP Agent picks (open to close)". Sleeves trimmed by a purpose rule that ignores results: rule variants of baseline A (A-G, T) and the fixed option structures (O, D1, D2, D3, W1-W4) leave the book and stop opening positions; their history stays. A versioned pick playbook lets the picking learn, one change a week at most, scored forward only. No reset: the trial count stands, no data is deleted, the window still opens 2026-12-07 (or 12-14) and ends 2027-05-14. | Owner decision ("all six; recalibrate or restructure if needed"). Written before any data in the window exists. The equal-weight benchmark changes with the sleeve list; that is declared here. |
| 2026-11-23 | More room for the AI's own judgment (runbook item 33). (a) Sleeve "AS AI strategies (lab, approved)": every gate-approved lab strategy, equal weight, forward days only, eligible for weight in the book from its forward start. (b) Lab track "improve a baseline": one change to one library strategy, approved only if it passes the gate and beats the unmodified original on held-out data; for G2 its forward benchmark is the unmodified original over the same days. (c) Sleeve "AP2": the morning research's own weights (0.05-0.40) and holding periods (1-5 days), sealed before the open; descriptive comparison with AP; G1 stays on AP. (d) After 2026-12-08 the ML ranker may supply a shortlist; picks are tagged by source and G1 judges all picks together, with the split by source descriptive. (e) Reports and dashboard in three layers: scoreboard, AI layer, foundation. | Owner decision: the rules and benchmarks are a foundation for the AI to build on. Written before any data in the window exists. More sleeves change the equal-weight benchmark; declared here. |
| 2026-11-23 | AUTONOMY RESTRUCTURE (section 0, runbook item 34). The ultimate goal is autonomy; it supersedes every earlier goal. (1) The verdict is now A1, Quantavius's own weekly book (judge_check), with H1's rule unchanged; the formula (H1) becomes a foundation reading and a lane yardstick; the lane champion is the AI-judgment allocator. (2) No frozen holdout: learning, the playbook, the lab, model refits and adaptive retunes continue to 2027-05-14; the scoring code stays frozen from the window's start; 2027-02-01 onwards is a second-half robustness reading. (3) Quantavius's evidence pack now includes its own work (picks vs control, playbook version, approved strategies, risk shares), dated no later than its evidence cut, and its own sleeves (AP, AP2, AS) are eligible for its seals from their first live day. (4) Scoreboard A1, G1, G2 in that order; three headline tests, declared. | Owner decision. Written before any data in the window exists. No data deleted, trial count kept, window dates unchanged. |
| 2026-11-23 | Stronger verdict (runbook item 35): A1's primary rule becomes ONE comparison (book vs volatility-matched equal weight; P >= 0.9 and higher Sharpe), the old all-benchmarks rule stays as A1 strict; G1's primary becomes a daily ranking of 44 fixed stocks scored by rank correlation, the picks-vs-control test becomes G1 secondary; stated confidence on picks and seals scored for calibration (report); a lessons journal in every seal; more fundamental data for picking; lane challengers judge_daily (daily seals from 2026-12-07) and the model contest (Opus, Sonnet, from 2026-11-29). | Owner decision ("all seven"). A single primary comparison and a 44-stock daily ranking raise the power to detect real skill; the stricter readings are kept beside them. Written before any data in the window exists. |
| 2026-11-23 | Integrity and bias review (runbook item 36), all before any window data: (1) the A1 primary benchmark is the FOUNDATION equal weight, i.e. every live sleeve except Quantavius's own (AP, AP2, AS); the earlier blend that includes them stays beside it as `primary_incl_own`; (2) a server-side witness records when GitHub first saw each pick, and from 2026-11-30 a pick counts only if first seen before 09:30 New York, with its sizing and confidence read from the first-seen copy; (3) an append-only intervention log; (4) one stated definition of success (section 0b). H1's rules and the baseline and control rules are unchanged. | Own sleeves sat inside the benchmark; pick times were self-reported; human changes to the player were not recorded; several headline tests had no single success sentence. |
| 2026-11-23 | External review of the Nov 23 guide (runbook item 37), before any window data: the weekly book is the MEDIAN of three independent samples of the same evidence pack (sample dispersion recorded each week); seal rows list moves over 5 points (recorded, never clipped); judge_check adds the number of weekly decisions, a 10-day-block probability and a SPY-beta-removed probability as secondary readings; a PASS is worded "promising, not proof" with A1 strict beside it; NO SPY parking sleeve; audit triage covers every reviewer's blocking finding and a human can hold the window; playbook changes need q <= 0.10 and 30 pick days; nightly critical and optional steps separated. The A1 primary rule, the seed and the 5-day block length are unchanged. | One model sample a week is partly a random draw; about 23 weekly decisions carry the evidence; three AI reviewers share blind spots. |
| 2026-11-23 | Runbook item 38: (1) an idea shelf (ops/idea_shelf.md) the lab may draw from; shelf ideas pass the same trial log, split, CPCV and gate, and each entry is a logged intervention; (2) the model of every sealing task (weekly book and samplers, model contest, daily challenger) is pinned to 2027-05-14; a forced replacement is logged and reported as a break in that series. No scoring rule changes. | Outside ideas should be visible inputs, not hidden help; a model swap mid-window would blur both the verdict and the contest. |
| 2026-11-23 | Runbook item 40: 5-minute data for the whole universe is stored for research, ML and a report-only wide run of the intraday strategies; the foundation's intraday strategies, the engine, baseline A and the control list keep their 44-stock lists; picks are also witnessed on push; five replay days a night. No scoring rule changes. | Owner raised the GitHub budget; the foundation stays comparable with its history. |
| 2026-11-23 | Runbook item 41: point-in-time universe (scripts/pitu.py, the rule of scripts/pit.py) applied to the report-only wide intraday run and required by the lab gate for stock ideas. No scoring rule of A1, G1 or G2 changes. | Today's S&P 100 list flatters any history computed on it. |
| 2026-11-23 | Runbook item 43: the four "Agent picks: ..." sleeves (Quantavius's picks under fixed rules or as calls) leave the foundation benchmark equal_f because they are Quantavius's own work; nightly maths runs on a GitHub schedule; live decisions once a day; picks review merged into the weekly report; the sheet is retired (the repository ledger was already the record); the daily challenger runs on Mondays and Thursdays. The A1 rule itself, its seed and block length are unchanged. | Own work was still inside the benchmark; scoring must not depend on an AI task; fewer sessions, fewer failure points. |
| 2026-11-24 | Lane cap raised from 3 to 6 new entries a calendar month (scripts/registry.py MAX_NEW_PER_MONTH). Promotion rules, review dates and the lifetime trial count are unchanged; more entries raise the deflated-Sharpe bar for every promotion. | Owner expects four or more new ideas a month. Made before any lane entry had a scored forward day, so it cannot be steered by results. |
| 2026-11-24 | Lab gate: a tuned strategy must also pass a neighbour check (review.py neighbours: one-step neighbours' median score above 0 and at least half the chosen score, on the tuning data). Report-only cross-checks with outside libraries (scripts/xcheck.py) and a nightly cost reality check. No verdict rule, sleeve, benchmark or frozen script changed. | Owner "proceed" after the review of ML for Trading, FinceptTerminal and awesome-quant; guards G2 against lone-peak settings before any lab approval. |
| 2026-11-23 | Runbook OUTSIDE CONTEXT DATA: free context sources (FRED, Cboe put/call, FINRA short-sale share, crypto funding and stablecoins, SEC EDGAR 8-K and Form 4 counts) fetched on GitHub into data/ext and shown to every seal in the identical evidence pack (judge.py "market_context", nothing after evidence_through), and to the morning research and the lab as context. Report only: no scoring, benchmark, sleeve or verdict rule changed; the trial count is unaffected (no rule was chosen on these data). | Owner request, before the freeze |
| 2026-11-21 | Option bars come from the free data feed instead of passing through the AI. Entries, exits, strikes, fees and scripts unchanged. | Runs were failing silently; hand-pasted prices are a reliability risk. |
| 2026-11-21 | Weight cap for short-premium option sleeves and the stress test behind it (section 7). | External review: the crash drill excluded option sleeves. |

## 2. What the test is, in one paragraph

Each week Quantavius seals the weights of its own book across every eligible sleeve: the foundation's strategy
library and rules, and its own work (its stock picks, AP and AP2, and its approved strategies, AS). Each morning it
researches and seals its own stock picks, sizes and holding periods before the open. Twice a week its lab invents or
improves a strategy and submits it to a fixed promotion gate; machine learning trains nightly on the growing record.
All of it is scored forward over 109 trading days (2026-12-07 to 2027-05-14) against the foundation: SPY, an equal-
weight mix of all sleeves, baseline A, the random control list, the cycle-1 formula and three simple allocation rules.
The book is fully invested and partly hedged, so a comparison with SPY is a comparison of a hedged book with an
unhedged one; volatility-matched and market-adjusted figures are given next to the raw ones.

## 3. Hypotheses

Each hypothesis has its own data, its own rule and its own result. They are never pooled, and a pass on one never
rescues another.

THE SCOREBOARD (restructured 2026-11-23 for the ultimate goal, section 0). Three headline results, reported in this
order, each with its own rule, never pooled: A1 (Quantavius's own book: "the verdict"), G1 (its stock picks), G2 (its
strategies). Three were tested, so a single pass is reported with the plain note that the chance of at least one false
pass is about three times that of one. H1 (the cycle-1 formula) becomes a FOUNDATION reading: its rule is unchanged
and it is still computed and reported, but it no longer decides anything.

### A1 (headline, "the verdict"): Quantavius's own book
- Subject: the book Quantavius seals every week (`scripts/judge.py seal`, scored as `sh_judge` in
  data/allocator/portfolio.jsonl): its own judgment of the weights across every eligible sleeve, including its own
  picks and strategies, from one dated evidence pack.
- PRIMARY RULE (2026-11-23, more power): the book against the equal-weight foundation scaled to the book's own
  volatility, over the window's daily returns: PASS if the day-block bootstrap chance (allocator.p_beats, seed
  20261119) that the book's mean beats it is >= 0.9 AND the book's Sharpe is higher; FAIL if that chance is <= 0.10;
  otherwise INCONCLUSIVE (`judge_check.verdict.primary`). This is the verdict.
- STRICT READING (secondary, the rule A1 had until 2026-11-23): exactly H1's three-way rule with the book as the candidate (allocator report `judge_check`, phase "verdict"):
  Sharpe AND max drawdown against SPY, equal weight and baseline A, raw and volatility-matched, block-bootstrap chance
  >= 0.9 for a PASS, <= 0.10 against any of them for a FAIL, otherwise INCONCLUSIVE. ROBUST if it also beats, on
  Sharpe, the cycle-1 formula and each simple rule (risk parity, minimum variance, recent winners).
- A week without a seal carries the last seal forward; it is counted and reported.

### G1 PRIMARY (2026-11-23): Quantavius's daily ranking of 44 fixed stocks
- Each full trading day before 09:30 New York it scores the 22 watchlist and 22 control-list stocks from -2 to +2
  (`scripts/rank.py seal`). Daily information coefficient = Spearman rank correlation of the scores with that day's
  open-to-close returns. PASS if at least 60 sealed days in the window, mean IC above zero and the day-block bootstrap
  chance of a positive mean >= 0.9; FAIL at <= 0.10; otherwise INCONCLUSIVE (data/picks/rank_score.json).

### G1 secondary: the AI's own stock picks, measured directly
- Subject: every stock the morning research picked before 09:30 New York with status "picked" (ledger AgentPicks).
- Measure: each pick held from that day's official open to that day's close, equal weight; the day's result is the
  average over that day's picks (`scripts/picks.py`, data/picks/score.json). Costs are equal on both sides and so
  are left out of the comparison.
- Benchmark: the same measure on the 22 stocks of the fixed random control list on the same days.
- Data: pick days from the opening of the verdict window (2026-12-07, or 2026-12-14 if it moves) to 2027-05-14.
- Rule: PASS if there are at least 60 pick days and the day-block bootstrap chance (allocator.p_beats, seed 20261119)
  that the picks' mean beats the control list's is at least 0.9. FAIL if that chance is 0.10 or lower. Fewer than 60
  pick days: "too few to judge". Otherwise INCONCLUSIVE.
- Reported with it, descriptive only: the five-day hold (pick-day open to the close four trading days later) against
  the control list; results by catalyst type and by playbook version; H3 below.
- The pick playbook (ops/pick_playbook.md) may change at most once a week, each change a numbered version logged
  with its date and reason in data/picks/playbook_log.jsonl and counted as a trial. G1 judges all versions together:
  it asks whether the AI's picking, including its learning, beats random selection.

### G2 (headline): the AI's own strategies (H2 below, widened)
H2's rule applies unchanged to crypto strategies. Since 2026-11-23 the lab also invents strategies for stocks and ETFs
on daily bars. For those: the same gate must approve them; data = trades entered after the strategy's Created date,
from its stored code on stored bars, after 0.05% per side; benchmark = SPY held over the same days each trade was
open; PASS if there are at least 30 forward trades, the mean net result per trade is above zero and the day-block
bootstrap chance that the mean beats the benchmark's is at least 0.9; FAIL at 0.10 or lower. Crypto and daily
strategies are judged separately and both results are reported.

### H1 (foundation reading since 2026-11-23): the cycle-1 formula
Rule unchanged; computed and reported beside A1; decides nothing. Runbook section PRE-REGISTERED VERDICT; computed mechanically by `verdict_check` in the allocator report.
Window 2026-12-07 to 2027-05-14. Result: pass, fail or inconclusive; a pass is robust only if it also survives double
costs and beats the best rival allocator (risk parity, minimum variance, recent winners, AI judgment).

### H2: the strategy lab (does the AI invent strategies that work forward?)
- Subject: every strategy the lab invented and the promotion gate marked APPROVED ("Strategy lab" tab; code in
  `strategies/`). The lab invents only in the train phase (to 2027-01-29).
- Data: only trades entered after each strategy's Created date and on or before 2027-05-14, from its stored code run
  on stored bars, after the 0.2% per side cost. Nothing from the split-sample test that approved it counts.
- Benchmark: the six original fixed crypto strategies (track "1h fixed") on the same coins over the same dates.
- Rule: pooled forward trades of all approved strategies. PASS if there are at least 30 forward trades, the mean net
  result per trade is above zero, and the day-block bootstrap chance (10,000 resamples, seed 20261121) that the mean
  beats the benchmark's mean is at least 0.9. FAIL if that chance is 0.10 or lower. Fewer than 30 forward trades:
  "too few to judge". Otherwise INCONCLUSIVE.
- A lab with no approved strategy by 2027-01-29 is reported as "the lab approved nothing": that is a result.

### H3 (secondary reading of G1 since 2026-11-23): the agent picks under the breakout rule
- Subject: stocks picked before 09:30 ET with status "picked" ("Agent picks" tab), traded with the unchanged
  baseline-A rules ("Agent trades", rules "baseline A").
- Benchmark: the fixed random control list (variant "AC control") under the same rules on the same days. The watchlist
  under the same rules is shown beside it for context only.
- Data: trades from 2026-12-07 to 2027-05-14, result in R after costs.
- Rule: PASS if there are at least 60 agent trades and the day-block bootstrap chance (10,000 resamples, seed
  20261121) that the agent's mean R per trade beats the control list's is at least 0.9. FAIL if that chance is 0.10
  or lower. Fewer than 60 trades: "too few to judge". Otherwise INCONCLUSIVE.
- Reported with it, descriptive only: the share of picks that triggered, results by catalyst type, and the option
  replays (ATM call, smart call).

### Not hypotheses
- The machine-learning filter is judged by its standing champion rule (at least 60 taken out-of-sample trades and
  overfit probability below 0.5, compared with taking every trade). The reports state whether it ever beat
  "take every trade". So far it has not.
- Individual strategies, option structures and crypto tracks are exploratory: reported with Benjamini-Hochberg
  q-values and deflated Sharpe, never called proven.
- There is no primary shortlist of strategies. Choosing among the sleeves is the allocator's job and is exactly what H1
  tests; a hand-picked shortlist would add a second selection step made with hindsight.

## 4. If a simple rule wins (owner decision, 2026-11-21)

Owner's instruction: if a simple rule wins, the AI must review its strategies and adjust its approach to maximise
returns.

- Trigger: in the interim report (data to 2027-02-12) or the final report (2027-05-18), the best simple rule (equal
  weight, risk parity, minimum variance or recent winners) has a higher Sharpe than BOTH kinds of AI allocation (the
  formula and the AI-judgment allocator) over the verdict window so far.
- Review (written into that report): where the AI lost to the simple rule. At least: sleeve by sleeve contribution,
  costs and turnover, forced-fill cost, market exposure, how concentrated the book was, which sleeves the formula
  backed that then lost, and whether the AI-judgment allocator's written reasons held up.
- Adjusted approach ("version 2"): the AI writes a revised allocation approach whose stated aim is the highest return
  after costs, with Sharpe and worst drawdown always reported beside it. The revision is declared in writing, with its
  parameters, before it sees any forward data, and every variant tried on past data is logged as a trial.
- What does not change: H1. The frozen scripts stay frozen to 2027-05-14 and the verdict is still judged on the
  original formula. If the trigger fires at the interim report, version 2 runs beside the frozen book from the next
  Monday as a labelled challenger (its own script, outside the freeze list); its results are reported separately and
  never count towards H1.
- After the final report: the next test's primary entry is version 2 if it beat the best simple rule over its own
  forward period, otherwise the best simple rule itself becomes the baseline to beat. Either way the final report says
  plainly that the simple rule won this test.

## 5. Freeze list (from 2026-12-07): the REFEREE

`ops/freeze.json` records the hash of these scripts on the first nightly run on or after 2026-12-07; the nightly run
and the freeze-guard workflow compare them on every push:

`allocator.py` (weights, benchmarks, bootstrap, verdict), `library.py`, `corp.py`, `fills.py`, `tcal.py` (the
calendar and the window), `judge.py` (seal rules), `ledger.py` (trade table), and the scripts that score the ledger
sleeves: `weekly_opts.py`, `deep_otm.py`, `options_sim.py`, `fees.py`, `crypto_tracks.py`, `orb_daily.py`,
`orb_variants.py`, `orb_adaptive.py`, `agent_score.py`, `smart_opt.py`.

Not frozen, because they do not produce a verdict number: data fetching, checks, dashboard, statistics for the
exploratory tables, machine learning (it has its own freeze on 2027-01-29) and the strategy lab.

## 6. Defects found after 2026-12-07

- Only a defect may be fixed: code that does not do what this record and the runbook say. A better idea is not a defect.
- Each fix is logged in the runbook with: what was wrong, since when, which results it touched, and the old and new
  hash. The amendment table above gets a row.
- Results affected by the defect are reported both ways (as first computed and after the fix) in every later report.
- A fix that would change which side of a threshold H1 lands on is flagged in the final report's first paragraph.

## 7. Short-premium option sleeves

The sleeves that sell option premium (W1, W2, D2, D3) can lose several times their usual gain in one bad week, and a
calm test window flatters them. The stress test and the weight cap that follow from it are recorded in
`reports/replay/2026-11-21-short_premium_stress.json` and in the runbook (CHANGES, item 26).

- Stress test (SPY daily history 2016 to 2026, every position held to expiry, stops ignored, calm-market credits):
  each position risks 0.20% of its sleeve, so the worst single week cost a sleeve 0.4% to 0.7%, the worst four weeks
  1.1% to 1.5%, the 2020 crash 1.2% to 1.9% and the 2022 bear market 1.4% to 2.7%. The losses are bounded by the
  position size, not by luck: a spread cannot lose more than its max risk.
- Weight cap: W1, W2, D2 and D3 together hold at most 25% of the book (`GROUP_CAP` in `allocator.py`), in the AI
  portfolio, in every simple rival and in the AI-judgment seals. With the cap, the worst four weeks of the stress
  test would have cost the whole book about 0.4%.
- The interim and final reports give, next to H1, how much of the AI portfolio's return came from these four sleeves
  (weight times sleeve return, day by day), so the reader can see H1's result without them.

## 8. Shakedown thresholds (first applied to the shakedown week 2026-11-30 to 2026-12-04, then checked weekly from 2026-12-07; a breach is reported first in the weekly report)

| Measure | Threshold |
|---|---|
| 5-minute feed ticks on a full trading day | at least 70 of about 84; longest gap at most 20 minutes |
| Scheduled tasks that failed and were not re-run the same day | none |
| Live-versus-replay parity | no outcome flags; feature flags on at most 10% of candidates |
| GitHub Actions minutes, projected for the month | at most 70% of the allowance |
| Days with a missing ledger row for a strategy that should have traded | none unexplained |
| Weekly random-day replay against stored results | identical |
| GitHub scripted jobs (ops/diag/daily_*.json, data/nightly/ml_report.json, data/nightly/stamp.json) | every scheduled run ok, or re-run ok the same day |
