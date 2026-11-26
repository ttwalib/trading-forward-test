# Build list before 2026-11-29 (from the setup debate of 2026-11-24, runbook item 56)

For the build sessions. Do these with the day 3 list; schedule another session if there is no room.
1. DONE 2026-11-24 (item 58 session). Push the morning research and lab prompts from ops/prompts/morning.md and lab.md (update_trigger, full text):
   they now carry the item 56 freedoms (watchlist names allowed in picks; the lab chooses its track).
2. DONE 2026-11-25 as far as it helps (item 63): watchdog rebuilt with two runs (trig_01McTsF59Sw14Dm9ogHwr8Z1); NOT folded into
   the orchestrator because the 07:35 and 19:35 checks would be lost (runbook ORCHESTRATOR, WATCHDOG AND ORCHESTRATOR). Was: Merge the watchdog into the orchestrator: the orchestrator (21:05 ET) also re-runs a failed task and logs problems;
   then disable the watchdog with a one-line "retired" prompt. One nightly health task, not four runs.
3. DONE 2026-11-25 (item 63): KEPT as an AI task; reasons in runbook LIVE DECISIONS, WHY IT STAYS AN AI TASK. Was: Live decisions (13:05 ET): check what only it produces (midday implied-volatility snapshot, slippage quotes). If
   the engine's sealed bid/ask and a GitHub fetch can replace them, move it and retire the AI task; if not, keep it
   and say why in the runbook.
4. BUILT 2026-11-25 (item 63): scripts/daily.py coins, runbook AGENT MORNING COIN PICKS AND DROPS, pre-registration amendment row;
   live prompt text waits for the owner (ops/prompts/proposed/morning.md; the runbook already wins over the prompt). Was: Crypto picks: let Quantavius DROP a picked coin (today picked coins stay to the end): a "dropped" AgentPicks row
   ends the coin's track from the next hour; keep the 8-coin maximum as coins held at once.
5. SUPERSEDED 2026-11-24 by item 58 (bearish views go through puts and put spreads). Design note for the owner (do not build without his yes): SHORT PICKS. Today picks are long only; the ranking
   already states negative views. What it needs: sign handling in picks.py, a borrow fee, hard-to-borrow exclusion.
6. DONE 2026-11-25: reports/retired_tasks_2026-11-25.md. Was: Tell the owner which disabled tasks can be deleted (stocks, crypto tracks, ML nightly, deep OTM, picks review).
7. DONE 2026-11-25: weekday_runs reviewed; no task moved or retired by items 2-4, so no count changed (the old watchdog
   goes to 0 when trig_01HubnhXMKjQ5XXJKCNTHd2C disables it). Was: Review N8 (item 59): after each move or retirement, set that task's weekday_runs in ops/tasks.json (AI sessions it
   starts on an average weekday, 9.8 on 2026-11-24); ops/SPEC.md prints the total.
8. ONE AGENT (owner, Nov 24): compile the setup into one agent with many entry points (ops/agent/COMMON.md plus one module
   per job; every scheduled task becomes a thin prompt; schedules, separate sessions and pinned models unchanged), AFTER
   the window has opened and every queued change has run. Cloud task trig_016WmNKiuwvvea3P8WGQoJkF (from 2026-12-15
   10:23 New York) checks readiness first and re-schedules itself weekly until ready; it proves equivalence, switches the
   watchdog first, and never switches a sealing task over a weekend. After 2027-02-01 it defers to between test cycles.

## Build day 3 (2026-11-25 session, run at 2026-11-24 18:3x New York) and what is left

9. DONE: first GitHub stocks day of 2026-11-24 verified (Sentiment 27 rows from the ApeWisdom file fetched 08:51 NY,
   Trades 13 and AC control 22 rows in the nightly fetch, daily_stocks.json ok and written, stocks_scored.json by github,
   stocks-check parity identical). Note: GitHub ran the 07:40 cron at 08:51 and the 17:40 cron at 18:27, so the
   ApeWisdom file landed after the 08:05 morning research started.
10. BUILT, NOT SWITCHED: scripts/daily.py adaptive and picks-evening run in the nightly fetch; parity identical on
   2026-11-18 to 2026-11-24. A scheduled run may not change scheduled tasks, so these wait for the owner's approval in a
   live chat turn: (a) disable trig_01XqVW4yGp2cwSyEXUobMusn and give it ops/prompts/proposed/adaptive.md; (b) push
   ops/prompts/proposed/evening.md to trig_0158DyhLj3M3cKod2eXxFn1g AND set data/state/picks_evening.json
   "github_writes": true in the same session; (c) push ops/prompts/proposed/watchdog.md to trig_01McTsF59Sw14Dm9ogHwr8Z1;
   then copy the three files over ops/prompts/, delete ops/prompts/proposed/, set weekday_runs (adaptive 0) in
   ops/tasks.json, interventions rows, SPEC, runbook item 62 wording, setup guide.
11. DONE 2026-11-25 (build session; ATM calls BBY -36.6%, DKS -6.2%, DLTR -17.6%, average -20.1%; smart calls skipped: all three reported on 2026-11-24 before the open; the Twelve Data earnings calendar is not on the plan, IBKR earnings insights used): option replays (ATM call, smart call) of 2026-11-24 for BBY, DLTR, DKS: GitHub wrote that day's stock rows in
   the build test, so the old 20:20 prompt stops as "already scored". Add them with IBKR read-only option bars as the
   evening prompt describes (STEPS 4-6), or record them as missing.
12. PARTLY DONE 2026-11-25 (cost rule applied by the owner: L2, L4, crypto 15m fixed M1 and 15m adaptive M1 out of the book; (a) DONE: dashboard Scoreboard view, dashboard.py scoreboard(), artifact version 1795594884-8a7c). OPEN (item 32-34 follow-ups): (a, done) dashboard layout (scoreboard, AI layer, foundation; scripts/dashboard.py and
   ops/dashboard/index.template.html; republish slug 41628095-7dd8-4a9a-be2e-162e0f2d375f); (e) DONE 2026-11-26: the Nov 25 lab
   run was checked (track correct, gate REJECT, nothing frozen touched); the stale point-in-time cache was rebuilt to 2016-03 to 2026-11 on the owner's request and reproduces the run; see reports/lab_check/2026-11-25.md. DONE (b): lab_daily path
   and the neighbour check tested on a copy (plateau passes, lone peak and missing grid fail; note: lab_daily drops
   returns dated on non-trading days instead of rolling them like lab_crypto). DONE (c): cost rule listing in
   reports/costrule/2026-11-25.json (would drop L2 VWAP pullback, L4 Gap fade, 15m fixed and adaptive M1); it is NOT a
   written rule, so nothing was applied and the owner decides. (d) moved to ops/dec8_plan.md (the ML gate is still
   "always take", PBO 0.7).
13. PROPOSED 2026-11-26 (owner: "proceed"; nothing built yet, the owner decides before any step). A longer history for
   daily lab ideas, with a longer tuning window and the held-out data unchanged. Why: lab ideas on daily bars tune on
   2016-2021, and a strategy with a long look-back (for example the 250 days of dispersion_reversal) loses most of 2016 to
   warm-up, so its tuning starts in 2017. Extending the tuning window into 2022 onwards is NOT proposed, because that
   would remove the only held-out test (reports/lab_check/2026-11-25.md, "Rebuild of the point-in-time cache").
   Proposal: (a) Backfill the daily archive and the point-in-time files to 2006. The membership file
   (github.com/fja05680/sp500) already reaches back to the 1990s, but the prices do not: scripts/fetch_free.py pit()
   takes them from Alpaca, whose stock history most likely starts in 2016 (check this first), and fetch_free.py cuts
   data/hist/1d at 2016-01-01 (line 262). A source before 2016 is therefore needed for the S&P 100 + ETFs and, above all,
   for the members that later left the index. Without the departed names the backfill brings the survivorship bias
   back, and it would be better not to do it. CBOE already gives the index series (VIX) from earlier years. (b) If a
   source is found, add a one-off fetch mode (like "pit2016") on GitHub Actions; fetch_free.py is not frozen. Then
   rebuild data/pit/monthly_top100.json with pitu.lists(repo, rebuild=True) and check archive coverage with the gate's
   98% rule. (c) The new split would be: tune 2006-2021, keep 2022 onwards held out, unchanged, and run CPCV over the
   whole history. This changes the runbook (LEARNING + STRATEGY LAB, DAILY STRATEGIES and IMPROVE A BASELINE: "tuned on
   2016-2021"; review.py's default data start 2016-01-04), so it is a rule change for the owner. The freeze allows no
   rule changes from 2026-11-30, so it must be decided and written before then, or wait until after the test. (d) Ideas
   already rejected (dispersion_reversal, the shelf entries marked "do not test again") are not re-tested on the longer
   history; that would be the same idea tried again after seeing its result. Every new run on the new split counts as a
   new trial. (e) The 2008-2009 and 2011 crises would enter the tuning data; report the result with and without them so that
   one regime does not choose the settings. Open questions for the owner: which price source (free, with delisted names) is
   acceptable, and whether to do this before 2026-11-30 or after the test.
