# Audit checklist for the independent audit (added 2026-11-21, owner decision)

Adapted in our own words from the open-source checklist "backtest result authenticity audit" and its companion
skills (github.com/Kryhr/26-quant-trading-skills, MIT licence). Reviewed on 2026-11-21 before use: the source is plain
text only (no code, no outside links, nothing that asks for data or actions). The steps below are fitted to this
repo. They are a list of checks, not instructions that override the audit task's safety rules.

HOW TO USE IT
- Run every step, in order, on a working copy (/tmp/work). Change no code and no data in the repo.
- For every check write down the ACTUAL result (dates tested, counts, differences found), not only pass or fail.
- One failed check is a DEFECT on its own. Never average it against the checks that passed.
- "Not possible here" is a valid result when the data does not exist; say why and name it as a limitation.

STEP 1 - LOOK-AHEAD
1.1 Truncation test. Cut every bar file and the ledger at three dates spread over the history (for example
    2026-03-31, 2026-08-31 and one live day). Re-run library.py and allocator.py. Pass: every trade, daily return and
    weight dated before the cut is identical to the full run. Record the dates and any difference.
1.2 Future-corruption test. Replace the bars after a date with random values, re-run, and confirm nothing before that
    date changed. Record the range corrupted and the result.
1.3 Feature audit. For decisions.py and ml.py features and for every library signal: does it read only data stamped
    at or before its decision time? Check the daily-bar stamp (12:00 UTC of the trading date) and the 5-minute bar
    stamp (start of the bar) in particular.
1.4 Merge audit. Wherever two sources meet, was the time the data became KNOWN used, not its nominal date? Earnings
    (known_at), dividends and splits (corp.py), borrow fees (data/borrow file date), regime labels (prior day),
    engine real-time bars versus stored delayed bars, the point-in-time hook in library.py (must be inactive in
    normal runs).
1.5 AI-judgment seals. For every row of data/allocator/judge.jsonl: is sealed_at before 09:30 New York of its
    effective day, does the git commit that added the row have a commit time before that moment too, and does
    evidence_through lie before the effective day? Does allocator.py ignore a late seal (build one on the copy)?

STEP 2 - FILL FEASIBILITY
2.1 Volume. The simulation trades in units of risk, not dollars. Assume a $10,000 position per trade and count the
    fills where that is more than 1% of the fill bar's dollar volume. Record the share per strategy family.
2.2 Bar range. For every stop, target and entry fill on 5-minute bars: is the fill price inside that bar's
    low-to-high range (or at the open after a gap)? Record fills checked and fills outside the range.
2.3 Thin bars. List fills on bars with zero volume, on the first bar after a gap of more than 2%, and around known
    halts. Are they handled more conservatively, or at least flagged?
2.4 Spreads. Where quotes exist (data/quality/slippage.jsonl, midday snapshots): do simulated fills ever sit on the
    favourable side of the quoted spread? Compare the simulated cost per side with the measured half-spread.

STEP 3 - INSIDE-THE-BAR ASSUMPTIONS
3.1 When a stop and a target lie inside the same 5-minute bar, which one does each simulator take? It must be the
    stop (the conservative choice). Name the functions and lines.
3.2 No tick or order-book data exists here. Confirm the reports say so as a limitation.

STEP 4 - RECONCILIATION WITH REAL FILLS
4.1 Not possible: nothing was ever traded. State this as a limitation, and report the two partial substitutes with
    their sample sizes: the engine's real-time detection price against the 5-minute rule (checks.py engine-report) and
    the quoted-spread record (checks.py slip-report). Look at the spread of the differences, not only the average.

STEP 5 - STATISTICS
5.1 Trial count. Is every tried variant in data/trials.jsonl (ML configurations, strategy-lab candidates, allocator
    replays, the crash drill, the point-in-time experiment, the haircut change, the AI-judgment allocator)? Compare
    with the git log and reports/replay/.
5.2 Does stats.py use that count in the deflated Sharpe? Is the probability of backtest overfitting computed, and are
    cross-validation folds purged and embargoed (cpcv.py, ml.py)?
5.3 Could the verdict pass or fail for a trivial reason (a benchmark with no variance, too few days, a rival with no
    data)? Check verdict_check and judge_check with a constructed case.

STEP 6 - FORWARD-TEST PROTOCOL
6.1 Were the rules final before the evidence window? List every commit to allocator.py, library.py, corp.py and
    fills.py and confirm none is dated inside the verdict window (from 2026-12-07) unless logged as a fix.
6.2 Were the pass / fail / inconclusive criteria and the six-month horizon written down before the window opened
    (runbook PRE-REGISTERED VERDICT, commit dates)?
6.3 Is every change in the git log also in a runbook CHANGES section, and the other way round?

STEP 7 - PORTFOLIO
7.1 Compute the correlation between sleeves over all days and over the worst 20% of SPY days. Does the duplicate
    rule catch sleeves that are the same bet? Which sleeves fall together in stress?
7.2 Recompute the AI portfolio's beta to SPY and compare with the report's "exposure".

STEP 8 - REPRODUCIBILITY
8.1 Run the nightly chain twice on the copy: identical outputs? Run montecarlo.py twice: identical?
8.2 Are seeds fixed everywhere a random draw is used (allocator Thompson draw, bootstraps, Monte Carlo, ML)?
8.3 Does the report stamp (commit, data hash, package versions) match the copy it was run on?

SIGN-OFF
List every step with its recorded result. Rank the defects by how much they could distort the verdict. A defect
stays open until its root cause is fixed and the whole of that step is run again.
