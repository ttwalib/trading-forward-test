# Runbook consolidation – equivalence check (2026-11-23, item 43g)

Old: ops/runbook.md before consolidation, 1,034 lines, now verbatim in ops/runbook_history.md (plus a 2-line header).
New: ops/runbook.md, 841 lines. A rewrite for clarity only: no rule, number, threshold, time, file path or command was
changed; where older passages conflicted, the later dated item won (list below). Every section heading that task
prompts cite is kept exactly; three headings had only their time in parentheses corrected:
"## LIVE DECISIONS (once a day at 13:05, on full trading days)" and "## ML NIGHTLY (GitHub, 03:07 UTC daily)";
"## WEEKLY REPORT" had no time and is unchanged. "THE ULTIMATE GOAL", "AUDIT TRIAGE", "MEDIAN OF THREE", "IDEA SHELF",
"LAB HYGIENE", "PICK PLAYBOOK" are all findable as text.

New global sections: THE ULTIMATE GOAL, SAFETY, SUCCESS, DATA FILES, GIT, LEDGER, DATES, INTERVENTIONS, plus two
reference sections that hold the system facts the old CHANGES items described: DATA FEED AND GITHUB JOBS, and NIGHTLY
MATHS, STRATEGY MENU, ALLOCATOR AND LANE. The CHANGE LOG table at the end points to ops/runbook_history.md.

## Items 13-43, one by one

| Item | Where the rule in force now lives / why it no longer applies |
|---|---|
| 13 ML at detection | DATA FEED AND GITHUB JOBS (ENGINE, "ML AT DETECTION"); LIVE DECISIONS 1b and 4 (ml.py predict reuses the row); ML NIGHTLY (never delete engine_ml). "Hourly run / 55 minutes earlier" is history (live runs are now once a day). |
| 14 Second crypto ML fit | DATA FEED AND GITHUB JOBS (SCHEDULE: 10:17 UTC, mode mlcrypto); ML NIGHTLY second paragraph. "Holdout freeze" dropped (item 34b). The 84-row status of 2026-11-20 is history. |
| 15 Survivorship haircut 25% | NIGHTLY MATHS ... ALLOCATOR (PRIOR_HAIR_SURV); INTERIM/FINAL STEP 4 point 13. Effect numbers are history. |
| 16 Engine revisions | DATA FEED AND GITHUB JOBS (ENGINE: "revision": true, fills.py, ml.py, engine-report). |
| 17 Dashboard signal chart | ORCHESTRATOR 4e (two-file publish, lightweight-charts-5.0.9.js, ops/dashboard/vendor/). Vendoring itself was one-off. |
| 18 Monte Carlo | NIGHTLY MATHS (REPORT-ONLY STEPS: montecarlo, seed, blocks, outputs, basis); WEEKLY REPORT (Monte Carlo table); INTERIM STEP 1/2. First result numbers are history. |
| 19 Six-month horizon | DATES (window, interim, final); PRE-REGISTERED VERDICT (HORIZON). Its holdout 2027-02-01..05-14 and ML freeze of 2027-01-29 no longer apply (item 34b): replaced by the second-half reading. |
| 20 AI-judgment allocator | AI-JUDGMENT ALLOCATOR (Sunday 13:23 ET); now the verdict A1 (item 34). |
| 21 Point-in-time experiment | NIGHTLY MATHS (POINT-IN-TIME EXPERIMENT pointer; priors unchanged, stand-in not used); WEEKLY REPORT one-off section (check); INTERIM STEP 4 point 12. Results are history. |
| 22 Audit checklist | CHANGE FREEZE AND AUDIT (audit works through ops/audit_checklist.md; date 2026-12-04). |
| 23 store.py merge fix | DATA FEED AND GITHUB JOBS (store.py merge rule); CHANGE FREEZE AND AUDIT (open items a and b for the audit). |
| 24 Option bars from the feed | DEEP OTM + WEEKLY (BARS); still used for marks and settlement of open legs. |
| 25 External-review response | CHANGE FREEZE AND AUDIT (17 frozen scripts, leaktest, no_orders); ORCHESTRATOR 1c (parity tolerances); NIGHTLY MATHS (replay_day); SAFETY (no_orders.py); PRE-REGISTERED VERDICT / INTERIM STEP 3b (ops/preregistration.md, H2/H3, sections 4, 6, 8). First replay-day results are history. |
| 26 Short-premium group cap | NIGHTLY MATHS ... ALLOCATOR (GROUP_CAP 25%); AI-JUDGMENT ALLOCATOR step 3 (judge.py refuses above it); stress file pointer. The sleeves are out of the book since item 32e. |
| 27 Allocator internals | NIGHTLY MATHS ... ALLOCATOR (0.005 on 5 days, 20 day-equivalents, 10 active days). L3 weight explanation is history. |
| 28 Challenger lane | NIGHTLY MATHS ... CHALLENGER LANE (registry, reviews, promote/retire thresholds, 3 a month). Seeds updated by items 34a, 35f/g (champion ai_judgment). |
| 29 Honest training history | NIGHTLY MATHS ... ML (pit_train.py, label, nightly refresh need). Descriptive results are history. |
| 30 Fresh restart | DATES (setup calendar, shakedown, slide to 2026-12-14); THE ULTIMATE GOAL (no reset, no deletion); CRYPTO TRACKS (30a, all paths); ML NIGHTLY (30b); ORCHESTRATOR step 0 (do not fire the two triggers, health files, re-run modes, crypto settings from data/state/crypto.json; also for the Watchdog); ADAPTIVE STOCKS (data/state/stocks.json, check); CHANGE FREEZE AND AUDIT (audit review 07:41, debate 09:51, 12:13 summary, reply before 2026-12-06). "Until the sheet-sync task exists ..." no longer applies (sheet-sync cancelled, item 43e). |
| 31 Report-only additions | NIGHTLY MATHS (costgrid, riskx, chain, CHAIN BROKEN); ORCHESTRATOR 5 and WEEKLY REPORT (one costgrid and one riskx line, "reports, not rules"); ORCHESTRATOR 4b (CHAIN BROKEN first). L18 dropped: NIGHTLY MATHS (SLEEVES). |
| 32 Refocus | a: NIGHTLY MATHS (RANKING AND CONFIDENCE: picks.py, score.json, five-day hold) and DATA FEED (daily bars for picked stocks); b: SLEEVES (AP, 0.10%); c: LEARNING + STRATEGY LAB (DAILY STRATEGIES); d: AGENT MORNING and LEARNING (PICK PLAYBOOK); e: SLEEVES (kept / DROPPED), STOCKS step 3-4 (skip S4, AC rows only, Reddit snapshot continues), DEEP OTM + WEEKLY (open nothing, reply text), AGENT EVENING (unchanged); f: headline order superseded by item 34d (A1, G1, G2), "follow preregistration section 3" kept in WEEKLY REPORT. |
| 33 More room for judgment | a: SLEEVES (AS) and LEARNING (lab_daily series); b: LEARNING (IMPROVE A BASELINE, odd ISO weeks); c: AGENT MORNING (SIZING, HOLDING AND CONFIDENCE) and SLEEVES (AP2; G1 on AP); d: AGENT MORNING (src tags; shortlist after 2026-12-08); e: WEEKLY REPORT LAYOUT, ORCHESTRATOR 4e (dashboard layout), INTERIM LAYOUT. |
| 34 Autonomy | THE ULTIMATE GOAL (freeze the referee, no holdout, verdict A1); PRE-REGISTERED VERDICT; AI-JUDGMENT ALLOCATOR (your_own_work, own sleeves eligible); DATES (frozen always false); SUCCESS (three headline tests caveat); every section that said "holdout" rewritten as the second-half reading. |
| 35 Stronger verdict | a: SUCCESS, PRE-REGISTERED VERDICT (A1 primary, A1 strict); b: AGENT MORNING (DAILY RANKING) and RANKING AND CONFIDENCE (rank.py, rank_score.json); c: AGENT MORNING (p=), AI-JUDGMENT step 3-4 (p_beat_equal), RANKING AND CONFIDENCE (calib.py); d: AI-JUDGMENT step 3-4 (lessons); e: AGENT MORNING (MORE DATA FOR PICKING); f: CHALLENGER LANE (judge_daily, now Mon/Thu per 43f); g: CHALLENGER LANE and AI-JUDGMENT (model contest times, files). Nightly steps rank, seals, calib and chain sources: NIGHTLY MATHS. |
| 36 Integrity review | INTERVENTIONS (log rule, WHO=quantavius, never edit rows; WITNESS 09:30, 08:05); PRE-REGISTERED VERDICT and SUCCESS (A1 primary benchmark equal_f); AI-JUDGMENT ALLOCATOR step 3 (LESSONS CAP 5 points, falsifiable lesson); LEARNING PICK PLAYBOOK (log with interventions.py). |
| 37 Jarvis review | a: AI-JUDGMENT (MEDIAN OF THREE); b: MEDIAN OF THREE (moves_over_5pts, pack_chars); c: PRE-REGISTERED VERDICT and SUCCESS (effective_sample, sensitivity); d: SUCCESS, WEEKLY REPORT, INTERIM (wording, strict beside it); e: forced fill unchanged (ALLOCATOR forced_fill, no parking sleeve: nothing to do); f: NIGHTLY CHAIN (critical vs optional steps) and ORCHESTRATOR 5 (optional_failed); g: AUDIT TRIAGE; h: PICK PLAYBOOK (q <= 0.10, 30 days); i: DATA FEED (GITHUB MINUTES pause order, now the fallback per item 39; never pause list; no lane job in tick/critical); j: DATA FEED (IBKR PATH deferred); k: already done by item 43f (daily challenger Mon/Thu). |
| 38 Shelf and pinned models | a: LEARNING (IDEA SHELF); b: INTERVENTIONS (MODELS PINNED, seal_models), WEEKLY REPORT (explain mixed models), AI-JUDGMENT ALLOCATOR (model pinned). |
| 39 GitHub minutes | DATA FEED AND GITHUB JOBS (GITHUB MINUTES: measured minutes, budget, fallback trigger about 8,000); ORCHESTRATOR 4f (minutes so far and projection every night). |
| 40 Budget and wide data | a: DATA FEED (UNIVERSE: intraday_wide_data, wide5m, 20 s skip, wide_skipped); b: NIGHTLY MATHS (library_wide, optional, lane after 2026-12-08); c: INTERVENTIONS (picks-witness workflow on push); d: NIGHTLY CHAIN (replay-days, five a night); e: DATA FEED (no hourly crypto runs, reason); f: DATA FEED (lane-build jobs on GitHub, under about 7,000 minutes); USD 30: GITHUB MINUTES. |
| 41 Point-in-time universe | NIGHTLY MATHS (POINT-IN-TIME UNIVERSE, library_wide pit counting); LEARNING DAILY STRATEGIES (pitu.member, "universe": "pit", survivorship_note, limits). First-run numbers are history. |
| 42 Cost view | NIGHTLY MATHS (RANKING AND CONFIDENCE: cost_view, break-even); WEEKLY REPORT PICKS (one line per sleeve, exact wording); INTERIM LAYOUT and STEP 4 point 11. |
| 43 Consolidation | a: SLEEVES (OWN_SLEEVES out of equal_f, options later as own per-pick choice); b: DATA FEED SCHEDULE and ORCHESTRATOR 4b(o); c: LIVE DECISIONS; d: WEEKLY REPORT (Fri 21:41, PICKS section), ORCHESTRATOR 0 (picks review disabled), LEARNING PICK PLAYBOOK input; e: LEDGER (sheet retired, new tabs, aliases, copied rows), every section's sheet writes turned into ledger writes; f: CHALLENGER LANE (Mon/Thu 08:41); g: this consolidation. |

Items 1-12 and the unnumbered 2026-11-20 bullets were also carried over (dq tolerances, stats n >= 20, breakers, weekly
Thompson draw, VOID (DATA), fully invested, L14-L17, ML champion rule, engine from 09:35, pinger, borrow file,
intraday_wide false, crypto bars, freeze guard and tag, health line and watchdog, engine-report, crypto costs); their
replay results are history only.

## Conflicts resolved (the later dated item wins)

1. Holdout (items 14, 19, 30b, PRE-REGISTERED VERDICT, ADAPTIVE STOCKS, CRYPTO TRACKS, AI-JUDGMENT "in the frozen
   holdout", WEEKLY "mark as holdout evidence", INTERIM phase "holdout") vs item 34b: no holdout; second-half reading
   from 2027-02-01 (judge_check.second_half), freeze nothing. ML freeze of 2027-01-29 dropped.
2. The verdict: H1 formula verdict_check (2026-11-19/20) vs item 34a / 35a / 36: A1 (the book) with A1 primary against
   equal_f; H1's rule kept as A1 strict and as the formula's foundation reading.
3. Report headline order: item 32f (G1, G2, H1) vs items 33e/34d (A1, G1, G2, AI layer, foundation).
4. Live decisions: hourly 10:05-15:05 (section heading, orchestrator step 5, tasks.json) vs item 43c: once at 13:05;
   step 0 "only the 11:05 and 13:05 runs" -> both sets in the one run; step 2 "within the last 65 minutes" -> the whole
   session so far; steps 1 and 3 and the atm_call rows dropped.
5. Weekly report: Fri 17:40 (tasks.json) vs item 43d: Fri 21:41; picks review task (Fri 23:40) disabled and merged.
6. Sheet: LEDGER "after the sheet write succeeds", orchestrator Stats overwrite and Regime L:T, "Library trades" and
   "Allocation" tab writes, Data check rows, Variants rows, item 30 "stock tasks still read and write the sheet cells"
   and "until the sheet-sync task exists" vs item 43e: sheet retired, ledger only, no sync task.
7. Ledger mirror check against the sheet (ORCHESTRATOR 4-pre, ML NIGHTLY step 1) vs item 43e: no longer needed (check);
   the "ledger complete and pushed before the maths" requirement is kept.
8. Nightly maths: requested by the orchestrator (item 2 / 4b i-ii) vs item 43b: scheduled at 21:00 New York, requested
   only when missing or failed.
9. Daily challenger: every trading morning (item 35f) vs item 43f: Mondays and Thursdays 08:41 (item 37k thereby done).
10. GitHub minutes: item 37i pause at 80% of 3,000 vs item 39/40: overage allowed under a USD 30 budget; the pause order
    is the fallback above 3,000 + budget (about 8,000).
11. Actions budget USD 10 (item 39) vs item 40: USD 30.
12. Feed schedule: 09:30-15:55 every 5 minutes (2026-11-19) vs CURRENT SCHEDULE (2026-11-20): pinger 09:00-15:55 and
    backup tick at :50.
13. Crypto tracks and ML nightly as AI tasks (sections CRYPTO TRACKS, ML NIGHTLY 19:47) vs item 30a/b: GitHub jobs.
14. Playbook threshold q <= 0.25 and 10 days vs 2026-11-23 tightening / item 37h: q <= 0.10 and 30 pick days.
15. Audit date 2026-12-01 and freeze from 2026-12-01 vs item 30: audit 2026-12-04, no-new-features freeze from
    2026-11-30.
16. Pinger token expiry: renewed 2026-11-23, expiry 2027-06-15 (both mentions agree).
17. Formula weights "set daily" (2026-11-19 verdict text) vs weekly rebalancing (2026-11-20): weekly.
18. Strategy lab Wednesday PART B (prompt) vs item 32c / 33b: daily strategies in even ISO weeks, improve a baseline in
    odd ISO weeks.
19. Pick-playbook input "latest picks review findings in Learning" vs item 43d (picks review merged into the weekly
    report): read the weekly report's picks section and any Learning ledger rows (check).
20. Deep OTM + weekly entry rules (D1/D2/D3/W1-W4 entry days, late-run rule, W4 expiry) vs item 32e: open nothing;
    only marks and settlement remain.

## Rules marked "(check)" (8)

1. LEDGER: DataCheck field mapping of the old "Data check" row format (list order vs dict).
2. STOCKS step 1: whether /tmp/bars_ctrl.json is built from the store with `hist.py export 5m`.
3. STOCKS step 2: the "Variants" summary row has no ledger tab.
4. ADAPTIVE STOCKS: settings read and written in data/state/stocks.json instead of the sheet cells.
5. ORCHESTRATOR 4: the ledger mirror check against the sheet treated as no longer needed.
6. LEARNING PICK PLAYBOOK: inputs now the weekly report's picks section and the Learning ledger.
7. WEEKLY REPORT: one-off sections (point-in-time experiment; crash drill and shadow replay) if not yet shown.
8. ML NIGHTLY: the one-time `decisions.py build-hist` before the first build (whether daily.py ml does it).

Nothing in force was dropped. Dropped as no longer applying: the frozen holdout and every "if frozen" branch; sheet
writes and the Stats-tab overwrite; retired option steps (S4, live atm_call quotes, D1/D2/D3/W entry rules); hourly live
decisions; the picks review task; the crypto-tracks and ML-nightly AI task steps; superseded dates (2026-12-01 audit,
USD 10 budget, 80% pause trigger); past replay and measurement results (kept in ops/runbook_history.md).
