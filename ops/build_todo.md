# Build list before 2026-11-29 (from the setup debate of 2026-11-24, runbook item 56)

For the build sessions. Do these with the day 3 list; schedule another session if there is no room.
1. DONE 2026-11-24 (item 58 session). Push the morning research and lab prompts from ops/prompts/morning.md and lab.md (update_trigger, full text):
   they now carry the item 56 freedoms (watchlist names allowed in picks; the lab chooses its track).
2. Merge the watchdog into the orchestrator: the orchestrator (21:05 ET) also re-runs a failed task and logs problems;
   then disable the watchdog with a one-line "retired" prompt. One nightly health task, not four runs.
3. Live decisions (13:05 ET): check what only it produces (midday implied-volatility snapshot, slippage quotes). If
   the engine's sealed bid/ask and a GitHub fetch can replace them, move it and retire the AI task; if not, keep it
   and say why in the runbook.
4. Crypto picks: let Quantavius DROP a picked coin (today picked coins stay to the end): a "dropped" AgentPicks row
   ends the coin's track from the next hour; keep the 8-coin maximum as coins held at once.
5. SUPERSEDED 2026-11-24 by item 58 (bearish views go through puts and put spreads). Design note for the owner (do not build without his yes): SHORT PICKS. Today picks are long only; the ranking
   already states negative views. What it needs: sign handling in picks.py, a borrow fee, hard-to-borrow exclusion.
6. Tell the owner which disabled tasks can be deleted (stocks, crypto tracks, ML nightly, deep OTM, picks review).
7. Review N8 (item 59): after each move or retirement, set that task's weekday_runs in ops/tasks.json (AI sessions it
   starts on an average weekday, 9.8 on 2026-11-24); ops/SPEC.md prints the total.
8. ONE AGENT (owner, Nov 24): compile the setup into one agent with many entry points (ops/agent/COMMON.md plus one module
   per job; every scheduled task becomes a thin prompt; schedules, separate sessions and pinned models unchanged), AFTER
   the window has opened and every queued change has run. Cloud task trig_016WmNKiuwvvea3P8WGQoJkF (from 2026-12-15
   10:23 New York) checks readiness first and re-schedules itself weekly until ready; it proves equivalence, switches the
   watchdog first, and never switches a sealing task over a weekend. After 2027-02-01 it defers to between test cycles.
