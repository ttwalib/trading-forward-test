# Quantavius the 1st: pre-registration record

This file is the dated record of what the forward test will be judged on. Everything here was written before the
verdict window opens on 2026-12-07. The runbook (`ops/runbook.md`) holds the working detail; where the two differ on a
judging rule, this file and the runbook section PRE-REGISTERED VERDICT are meant to agree, and a difference is a defect
to be logged below. This file was first committed on 2026-11-21 (commit 2e4faf8). The tag
`prereg-2026-11-21` marks a data commit of the same day that holds it; GitHub stores the push time.

Nothing is traded. All results are simulated on real market prices. This is testing, not financial advice.

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
| 2026-11-21 | Option bars come from the free data feed instead of passing through the AI. Entries, exits, strikes, fees and scripts unchanged. | Runs were failing silently; hand-pasted prices are a reliability risk. |
| 2026-11-21 | Weight cap for short-premium option sleeves and the stress test behind it (section 7). | External review: the crash drill excluded option sleeves. |

## 2. What the test is, in one paragraph

A fully invested, partly hedged book of strategy sleeves (stock, option and crypto strategies), re-weighted once a week
by a fixed formula (`scripts/allocator.py`), judged over 109 trading days against simple alternatives. The book's
market exposure is far below SPY's (beta about 0.3 on past data), so the final report must say plainly that a
comparison with SPY is a comparison of a hedged book with an unhedged one, and must give the volatility-matched and
market-adjusted figures next to the raw ones.

## 3. Hypotheses

Each hypothesis has its own data, its own rule and its own result. They are never pooled, and a pass on H2 or H3 never
rescues H1. H1 is the primary hypothesis and the only one called "the verdict".

### H1 (primary): the AI's allocation
Unchanged. Runbook section PRE-REGISTERED VERDICT; computed mechanically by `verdict_check` in the allocator report.
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

### H3: the agent picks (does the AI's morning research pick better stocks?)
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

## 5. Freeze list (from 2026-12-07)

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

## 8. Shakedown thresholds (checked weekly from 2026-12-07; a breach is reported first in the weekly report)

| Measure | Threshold |
|---|---|
| 5-minute feed ticks on a full trading day | at least 70 of about 84; longest gap at most 20 minutes |
| Scheduled tasks that failed and were not re-run the same day | none |
| Live-versus-replay parity | no outcome flags; feature flags on at most 10% of candidates |
| GitHub Actions minutes, projected for the month | at most 70% of the allowance |
| Days with a missing ledger row for a strategy that should have traded | none unexplained |
| Weekly random-day replay against stored results | identical |
