# Copies of the scheduled tasks' prompts

The scheduled tasks live in claude.ai (scheduled tasks of the owner's account); their prompts are copied here so an
auditor or reviewer can read exactly what each task is told. Rewritten 2026-11-23 (tools audit: the sheet retired,
TOOLS AND SKILLS, no WebFetch in tasks, ApeWisdom from GitHub, retired tasks dropped). Every later prompt change updates
the copy and adds a row to ops/interventions.jsonl.

| File | Task | Id |
|---|---|---|
| ../agent/prep.md | Morning prep (07:15 ET daily, Fable; thin task prompt: safety rules, the clone, "read ops/agent/prep.md and follow it") | trig_01HTP8W5B7BiCcbcxbXurc8G |
| ../agent/decide.md | Morning decision: picks and ranking (08:17 ET weekdays, Fable; thin prompt; morning.md is the superseded full prompt, kept for the record) | trig_01NH3ceZ9ypKfB94HSpRW65A |
| ../agent/preopen.md | Pre-open refresh (09:04 ET weekdays, Fable; thin prompt) | trig_01DCL9hsysSu67gRsyZphGeU |
| ../agent/desk.md | Intraday desk (10:15 and 13:15 ET; 11:30 and 14:30 ET weekdays, Fable; thin prompt) | trig_01UAvRZUscnyqvgMP6dwzL8G, trig_01EEMRpMkt98YRYkaTxgG2gG |
| ../agent/crypto.md | Crypto desk (02:07, 06:07, 18:07, 22:07 ET daily; 10:07 and 14:07 ET weekends; Fable; thin prompts like the desk's) | trig_01VmFs5xrte5mNjVidB3TeFG, trig_01PHx691YYBcgnv6n1BGn22w |
| daily_challenger.md | Daily challenger seal (08:41 ET every weekday from 2026-12-07, Fable; every weekday since 2026-11-26, own-sleeve cap names AP4) | trig_01W21jTsy2zySucZ7iTHKHGf |
| evening_review.md | Evening review + prep (20:47 ET trading days, Fable since 2026-11-26) | trig_013i7PDxNJPCsBBZoKbfZGVw |
| live_decisions.md | Live decisions (13:05 ET once, Sonnet; since 2026-11-26 no position review and no AgentPicks rows: the intraday desk owns them) | trig_018iuZdjimqtB2HRNmKpJn1m |
| weekly_seal.md | Weekly seal, Quantavius's own book (Sun 13:23 ET, Fable) | trig_01BCM9DiYtxCt9tXRPupjpTU |
| samplerB.md, samplerC.md | Weekly book samplers B and C (Sun 13:02 and 13:11 ET, Fable) | trig_01Tnw4Txgzkbq2aoXg56HSVW, trig_01SwTbwvHuiLaTkzCYs5RpCq |
| contest_opus.md, contest_sonnet.md | Model contest seals (Sun 13:41 and 13:56 ET, Opus and Sonnet) | trig_01XfudQxCJPMX1r798rNi8CS, trig_016Ks7T65PzF4KNrUUtyYJk2 |
| stocks.md | Stocks + control list (09:12, 16:12 ET, Sonnet) | trig_01Udt8Hay1dh3AyxtaP4ejDN |
| adaptive.md | Adaptive stocks (17:20 ET, Sonnet; retirement proposed in proposed/adaptive.md, awaiting the owner's approval) | trig_01XqVW4yGp2cwSyEXUobMusn |
| evening.md | Evening scoring of picks (20:20 ET, Sonnet; option-only prompt proposed in proposed/evening.md, awaiting the owner's approval) | trig_0158DyhLj3M3cKod2eXxFn1g |
| orchestrator.md | Orchestrator (21:05 ET, Opus since 2026-11-26) | trig_01PgUGPDdTViNz1u3Wkqy4GW |
| watchdog.md | Watchdog (07:35, 19:35 ET, Sonnet; rebuilt 2026-11-24; task list of the 2026-11-26 restructure) | trig_01McTsF59Sw14Dm9ogHwr8Z1 |
| lab.md | Learning + strategy lab (Mon, Wed, Fri, Sat 23:15 ET, Fable) | trig_012qn78KzSzn173hQGXeEnJq |
| weekly_report.md | Weekly report incl. picks (Fri 21:41 ET, Fable) | trig_01GEc25Hnp6tGicRbiankK62 |
| interim_report.md | Interim report (2027-02-16, Fable) | trig_01R5sHJU64phYuAxf7PQBNjz |
| final_report.md | Final report (2027-05-18, Fable) | trig_01LhTmXikGruYFghXwBp5a9D |
| audit.md | Independent audit (2026-12-04, Fable) | trig_01T8geep8ASxd12yhTx17EnU |
| audit_review.md | Audit review and challenge (2026-12-04, Opus) | trig_01Tp6mr79CGx8Dmmpq7S6Roo |
| audit_debate.md | Audit debate (2026-12-04, Opus) | trig_017j7xXYaLnjqvYr2wAispX9 |
| lane_review.md | Lane review (quarterly, Opus) | trig_016a7pogjLwtXMd93miFK33w |

Since 2026-11-26 the six sealing prompts are copied here too (they name AP3 and AP4 among the own sleeves). 
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
