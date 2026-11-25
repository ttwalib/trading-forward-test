# Session note, 2026-11-25: pre-freeze code review (for claude/forward-test-setup.md)

Item to append to the project doc claude/forward-test-setup.md. This session could read the doc but did not rewrite it, because writing it back means retyping the whole 40 KB doc and could corrupt it. A later chat should copy this item in.

- Item 70 (pre-freeze code review, scheduled cloud run trig_011tCpYEs85GE3B1VygwbYLb, Nov 25; runbook item 68; commit 056067b9):
  - **How it ran.** Review pull request #1 (`prefreeze-review` against `prefreeze-review-base`, which is main without the reviewed scripts), skill code-review:code-review, closed without merging. Scope: the 28 frozen scripts plus judge, review, breadth, extdata, ape and checks.
  - **Six defects fixed on main, with tests in tests/test_prefreeze_2026_11_25.py:**
    - (D1) Sealed books (A1 weekly seal, contests, daily challenger) were scored with every sleeve capped at 25%, although judge.py accepts 50% for own sleeves. They now use allocator.seal_cap.
    - (D2) G1 PRIMARY counted missed days towards its 60 days. It now needs 60 sealed days (rank.summary sealed_days).
    - (D3) The AS mix could come from an invalid seal row. It now comes from the row the allocator scores (allocator.judge_seal_rows).
    - (D4) AP3 closed every still-open option position each night and charged its exit costs.
    - (D5) AP3 lost the expiry-day move for an expiry on a half day (2026-12-24).
    - (D6) L13 pairs traded at the same close as its signal. It now trades at the next open; its history moved by 0.02 points.
  - **Hardening.** Seal rows that raise while being checked are counted (judge_check.seal_rows_with_errors) instead of being dropped silently.
  - **Results so far.** No existing seal or result crossed a threshold. The only seal (Nov 23) has no share above 25%. The formula book moved by under 0.001 points a day, and sh_judge is unchanged.
  - **Checks run.** Nightly maths ok on a copy (stamp ok, optional_failed empty), verdict leak test passed, no-orders green.
  - **A1 hand check.** I recomputed judge_check by hand on the 367-day replay series. Sharpe 0.33 vs 1.08 matched, and the bootstrap P was 0.091 in the code against 0.092 by hand. The rule matches pre-registration sections 0, 0b and 3.
  - **Risks left.** The chain half-spread falls back silently to the 4% floor. AP plus AP2 can hold the same picks (owner's choice). The ML-parity part of the leak test is weaker on quiet days.
  - **EDGAR** is ok (1,533 rows).
  - **Report:** reports/audit/2026-11-25-code-review.md.
