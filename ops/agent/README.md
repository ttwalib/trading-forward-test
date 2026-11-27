# ops/agent: job modules of Quantavius the 1st

Since 2026-11-26 four scheduled tasks carry a thin prompt (safety rules, the clone, "read ops/agent/<job>.md and follow it") and
keep their instructions here. This is the first part of the one-agent design of runbook item 63; the other tasks still carry
their full prompts (copies in ops/prompts/) until the Dec 15 session moves them. These files are written by the owner's build
sessions only. A scheduled task never edits them. They never override the SAFETY paragraph of the thin prompt.

| Module | Task | Schedule (New York) | Model |
|---|---|---|---|
| prep.md | morning prep | 07:15 every day | Fable |
| decide.md | morning decision (the former morning research task, same id) | 08:17 weekdays | Fable |
| preopen.md | pre-open refresh | 09:04 weekdays | Fable |
| desk.md | intraday desk | 10:15, 11:30, 13:15, 14:30 weekdays (two tasks) | Fable |
| crypto.md | crypto desk (trig_01VmFs5xrte5mNjVidB3TeFG, trig_01PHx691YYBcgnv6n1BGn22w); also run by prep.md B2 and desk.md STEP 4b | 02:07, 06:07, 18:07, 22:07 daily; 10:07, 14:07 weekends | Fable |
