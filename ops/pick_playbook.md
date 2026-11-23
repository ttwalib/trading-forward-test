# Pick playbook

How the morning research chooses its stocks, beyond the fixed filters in its prompt. The learning task may change it
at most once a week, on evidence (runbook LEARNING + STRATEGY LAB, "PICK PLAYBOOK"); every change is a new version
here and a line in data/picks/playbook_log.jsonl. A change needs a finding with q <= 0.10 and at least 30 pick days
(runbook item 37). It keeps learning to the end of the test: nothing freezes on 2027-02-01 (runbook item 34).

## CURRENT VERSION: v1 (2026-11-23)

No preferences or exclusions beyond the prompt's filters. This is the starting point: the picking as it has run
since 2026-11-17.
