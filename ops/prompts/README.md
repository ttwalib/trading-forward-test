# Copies of the scheduled tasks' prompts

The scheduled tasks live in claude.ai (scheduled tasks of the owner's account); their prompts are copied here so an
auditor or reviewer can read exactly what each task is told. Rewritten 2026-11-23 (tools audit: the sheet retired,
TOOLS AND SKILLS, no WebFetch in tasks, ApeWisdom from GitHub, retired tasks dropped). Every later prompt change updates
the copy and adds a row to ops/interventions.jsonl.

| File | Task | Id |
|---|---|---|
| morning.md | Morning research + events (08:05 ET daily, Fable; coin-drop text proposed in proposed/morning.md, awaiting the owner's approval; the runbook already applies) | trig_01NH3ceZ9ypKfB94HSpRW65A |
| stocks.md | Stocks + control list (09:12, 16:12 ET, Sonnet) | trig_01Udt8Hay1dh3AyxtaP4ejDN |
| adaptive.md | Adaptive stocks (17:20 ET, Sonnet; retirement proposed in proposed/adaptive.md, awaiting the owner's approval) | trig_01XqVW4yGp2cwSyEXUobMusn |
| evening.md | Evening scoring of picks (20:20 ET, Sonnet; option-only prompt proposed in proposed/evening.md, awaiting the owner's approval) | trig_0158DyhLj3M3cKod2eXxFn1g |
| orchestrator.md | Orchestrator (21:05 ET, Sonnet) | trig_01PgUGPDdTViNz1u3Wkqy4GW |
| watchdog.md | Watchdog (07:35, 19:35 ET, Sonnet; rebuilt 2026-11-24) | trig_01McTsF59Sw14Dm9ogHwr8Z1 |
| lab.md | Learning + strategy lab (Mon, Wed, Fri, Sat 23:15 ET, Fable) | trig_012qn78KzSzn173hQGXeEnJq |
| weekly_report.md | Weekly report incl. picks (Fri 21:41 ET, Fable) | trig_01GEc25Hnp6tGicRbiankK62 |
| interim_report.md | Interim report (2027-02-16, Fable) | trig_01R5sHJU64phYuAxf7PQBNjz |
| final_report.md | Final report (2027-05-18, Fable) | trig_01LhTmXikGruYFghXwBp5a9D |
| audit.md | Independent audit (2026-12-04, Fable) | trig_01T8geep8ASxd12yhTx17EnU |
| audit_review.md | Audit review and challenge (2026-12-04, Opus) | trig_01Tp6mr79CGx8Dmmpq7S6Roo |
| audit_debate.md | Audit debate (2026-12-04, Opus) | trig_017j7xXYaLnjqvYr2wAispX9 |
| lane_review.md | Lane review (quarterly, Opus) | trig_016a7pogjLwtXMd93miFK33w |

Unchanged on 2026-11-23 (their prompts already matched the setup; they read only the evidence pack or the repo and
need no other tools): weekly seal trig_01BCM9DiYtxCt9tXRPupjpTU, samplers B trig_01Tnw4Txgzkbq2aoXg56HSVW and C
trig_01SwTbwvHuiLaTkzCYs5RpCq, model contest Opus trig_01XfudQxCJPMX1r798rNi8CS and Sonnet trig_016Ks7T65PzF4KNrUUtyYJk2,
daily challenger trig_01W21jTsy2zySucZ7iTHKHGf, live decisions trig_018iuZdjimqtB2HRNmKpJn1m (rewritten earlier the same
day).
Retired (disabled, one-line "retired" prompts): crypto tracks, ML nightly, picks review, history download and, from
2026-11-23, deep OTM + weekly options trig_012o6Jbkhg14NZ4Sq8N4spLW (nothing open).

SKILLS BY TASK (2026-11-23): sealing tasks (weekly seal, samplers, contest, daily challenger) use NO skills and only the
evidence pack, so every seal sees identical inputs; scripted tasks (stocks, adaptive, evening, live decisions,
orchestrator, watchdog) need none; morning research: earnings-reviewer earnings-preview checklist; lab:
backtest-expert, trade-performance-coach (Saturdays), data:statistical-analysis, data:explore-data, data:validate-data;
reports (weekly, interim, final): dataviz, docs, trade-performance-coach (weekly), data:validate-data,
data:statistical-analysis; audit, review, debate, lane review: data:statistical-analysis, data:validate-data
(audit also backtest-expert); build sessions: code-review:code-review.

| evening_review.md | Evening review + prep (20:47 ET weekdays) | trig_013i7PDxNJPCsBBZoKbfZGVw |

PROPOSED (2026-11-25, build day 3): ops/prompts/proposed/ holds prompts written by a scheduled build session that could not push them, because a scheduled run may not change scheduled tasks without the owner's approval. A session the owner approves pushes them with update_trigger, copies them over the live copies here and deletes the proposed file.
