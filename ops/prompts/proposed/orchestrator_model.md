# Proposed change: orchestrator model Sonnet -> Opus (owner approval of 2026-11-23, "if theres room go ahead")

APPLIED on 2026-11-26 (UTC 07:15) on the owner's "apply": the orchestrator now runs on claude-opus-5-5.

A scheduled build session on 2026-11-26 (UTC 04:25) found room for this change, but update_trigger was refused for a scheduled session, so nothing is live yet.
The owner applies this by saying "apply" in his build chat (or by changing the model of the task himself where he manages scheduled tasks).

- Task id: trig_01PgUGPDdTViNz1u3Wkqy4GW (Quantavius the 1st – orchestrator, nightly 21:05 ET)
- Change: model claude-sonnet-5-5 -> claude-opus-5-5, in a call that changes the model only (no prompt, name or schedule change in the same call).
- Room check: reports/usage/2026-11-25.md, section "Orchestrator on Opus: room check".
- On apply: an interventions row (kind model), the pre-registration amendment row "process change before the freeze: orchestrator model Sonnet -> Opus, owner approval 2026-11-23; no rule, sleeve or verdict change", a runbook change-log line, ops/tasks.json (orchestrator model), ops/SPEC.md (python3 scripts/spec.py . ops/SPEC.md) and the project notes.
