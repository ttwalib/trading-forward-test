# Pre-freeze code review, 2026-11-25

Quantavius the 1st, simulated forward test (no orders). The owner asked for this review on 2026-11-23. It was run by a scheduled build session.

**Bottom line.** Six real defects were found, and all six are fixed on main with tests. None of them changed an existing seal or crossed a threshold. Two of them would have mattered from the first seal that gives an own sleeve more than 25%, which could be as early as 2026-11-29. Testing only, not financial advice.

## How the review was run

- **Review pull request:** pull request #1, `prefreeze-review` into `prefreeze-review-base`. The base branch is main with the reviewed scripts removed, and the head tree is identical to main at 9812815f. The diff therefore shows every reviewed script in full. The pull request was closed without merging, and both branches are left for the record.
- **Skill:** code-review:code-review. There is no CLAUDE.md in the repository, so the compliance pass had nothing to check.
- **Two independent reviewers:**
  - A bug scan of every file.
  - A logic review of the 2026-11-24 changes (runbook items 57-61), which confirmed each finding with an offline snippet.
- **Validation:** I re-read each finding against the code myself before fixing it.
- **Scope:** the 28 scripts in `allocator.FROZEN_FILES`, plus `judge.py`, `review.py`, `breadth.py`, `extdata.py`, `ape.py` and `checks.py` (the leak test).
- **Checks after the fixes:**
  - `python3 scripts/nightly.py COPY 2026-11-24` gives stamp ok true, with optional_failed empty.
  - `python3 scripts/checks.py verdict-leaktest COPY` passed.
  - `python3 scripts/no_orders.py .` is green.
  - `python3 tests/test_prefreeze_2026_11_25.py` passes. It fails on the old code.
  - On the copy, the formula book changed by under 0.001 points a day, through L13 only. sh_judge is unchanged.

## Defects found and fixed

| # | Where | What was wrong | Fix | Effect on results so far |
|---|---|---|---|---|
| D1 | `allocator.simulate` (the judge book) and `seals.score` (contests, daily challenger) | Sealed weights were rebuilt with `fill_to_one`, which caps every sleeve at 25%. `judge.py` accepts up to 50% for AP, AP2, AP3 and AS (item 55). A seal of AP2 0.40 would have been scored as 0.25, with the rest spread over other sleeves. If those were already full, part of the book would have been left in cash. In short, the A1 verdict would have scored a book Quantavius did not seal. | `fill_to_one(tiers, cap=None)` now takes an optional per-sleeve cap. `allocator.seal_cap` gives 50% to own sleeves and 25% to the rest, matching `judge.cap_of`, and both scoring paths use it. The formula and the shadow allocators are unchanged. | None. The only seal (2026-11-23) has a largest share of 0.25. |
| D2 | `rank.py` G1 summary | "At least 60 sealed days" counted the missed days too, because they carry IC 0. With 30 rankings and 69 missed days, the summary read PASS instead of "too few days" (pre-registration section 3). | Only sealed days count towards the 60; missed days still count as IC 0 in the mean. The summary gains `sealed_days`, and the function is now `rank.summary` so it can be tested. | None (window not open). |
| D3 | `aisleeve.as_mixes` | The AS mix came from the first row in the file for that effective day, valid or not. The allocator scores the first valid row. So an invalid row (for example, one edited after it was witnessed) could set the AS mix retroactively. | The new `allocator.judge_seal_rows` returns the scored row, and both `judge_seals` and `as_mixes` read from it. | None (no as_mix sealed yet). |
| D4 | `picks.puts` (AP3) | The last holding day was clamped to the run day. Every option position still held overnight was therefore closed that night and charged its exit fee and spread (at least 4% of the premium). It reappeared the next night, so the latest AP3 value in `data/picks/daily.json`, which the allocator and the evidence pack read, was always too low, and `closed` listed trades that never closed. | A hold that runs past the run day stays open. | AP3 has no picks yet. |
| D5 | `picks.puts` (AP3) | The calendar holds full trading days only. An option expiring on a half day (the 2026-12-24 weeklies) was closed on 12-28 at its 12-23 mark, so the expiry-day move was lost. | After its last day, a position is priced on that day's own bars, and the exit day is recorded as the expiry. | None yet. It would first matter in Christmas week. |
| D6 | `library.py` L13 pairs | The signal was computed on a close, and the trade was entered and exited at that same close. This breaks the library's stated rule, "decide on a close, trade at the NEXT open", which every other daily strategy follows. | Entries and exits decided on a close now fill at the next open. | L13 back history moved from +4.54 to +4.56 summed daily %. Sharpe stays 0.81. Forward days are unchanged (no trade since 2026-11-16). |
| D7 (hardening) | `allocator.judge_seals`, `seals.valid` | A row that raised while being checked, including inside the witness code, was dropped with `except Exception: continue`. A bug there would have silently carried last week's book forward. | Skipped rows are now counted and reported: `judge_check.seal_rows_with_errors`, and `rows_with_errors` in the seals output. Validity is unchanged. | None. |

Each fix has an interventions row, a runbook CHANGE LOG item 68 and a pre-registration amendment row dated 2026-11-25.

## Hand check of one A1 judge_check computation (data:validate-data)

The live book has only 2 scored days, so `judge_check` answers "not enough days". To check the arithmetic, I ran it on the 367-day replay series in `reports/replay/2026-11-21-mc_series.json`. The formula book stood in as the candidate and equal weight stood in for equal_f, and I recomputed everything independently with `statistics` and numpy.

| Item | `judge_check` | By hand |
|---|---|---|
| Volatility scale of the benchmark | used | 1.0884 |
| Book Sharpe | 0.33 | 0.33 |
| Benchmark Sharpe | 1.08 | 1.08 (1.08 after scaling: scaling leaves Sharpe unchanged, as it should) |
| Bootstrap P (book mean > scaled benchmark) | 0.091 | 0.092 (independent stationary bootstrap, mean block 5 days, other generator) |
| Result | FAIL | FAIL (P <= 0.10) |

**Assessment:** ready to share. The rule in the code matches pre-registration sections 0, 0b and 3:
- the benchmark is equal_f with the own sleeves excluded;
- the benchmark is scaled to the book's volatility;
- PASS needs P >= 0.9 and a higher Sharpe, and FAIL is P <= 0.10;
- the seed is 20261119;
- the window starts 2026-12-07.

**Caveat:** this check used a stand-in series, not live seals.

## Checked and found correct (non-defects, with the reason)

- **Short-sleeve signs:**
  - L4 uses `sg = -1`.
  - L14 uses `-(exit/entry - 1)` with the stop above the entry.
  - L15 uses `sg` per leg and charges borrow on shorts.
  - L16 marks the short negatively and charges borrow and cost on both sides.
  - L13 legs are `sa` and `-sa`, with borrow on the short leg.
- **Puts and put debit verticals:** each is a long debit position, so `price / mark - 1` is the right sign. Put calibration hits when the stock does worse than the control list.
- **Costs are charged on both sides:**
  - AP charges `2 * COST_SIDE`.
  - AP2 charges on its entry day and its exit day.
  - AP3 charges $0.68 per contract per leg (two legs for a spread), plus the allowance on each leg's premium at entry and on the exit value.
  - The library charges `2 * cost` per closed trade, and the 2x run doubles both sides.
- **Weights sum to 1:**
  - `fill_to_one` and `group_cap` reach 1 unless every sleeve is at its cap.
  - AP2 weights are rescaled over open positions.
  - The AS mix is normalised over active named members, and falls back to equal weight.
  - `judge._fill` respects each sleeve's own cap.
- **Seeded randomness:**
  - The Thompson draw uses `random.Random(sha1 of the week)`.
  - `p_beats` uses `Random(SEED)`, and so do stats and review.
  - No unseeded generator sits on a scored path.
- **No look-ahead in the allocator or the pack:**
  - `weights_for` and `shadow_targets` use the days before d.
  - The regime reading uses SPY and VIX before d.
  - The pack runs to `evidence_through`.
  - The chain half-spread uses the previous night's snapshot.
  - Lane admission needs `scores.day < day`.
  - AS mixes need effective day <= d.
- **Witness:**
  - It uses the GitHub push time (`WITNESS_AT`), and ignores it if it is in the future or more than 6 h old, falling back to the runner clock (the conservative side).
  - New York time comes from zoneinfo, so DST is handled.
  - The 09:30 deadline is applied.
  - The 2026-11-30 cut-over and the one-time grandfathering work as described.
  - An altered sha gets a new, ungrandfathered sighting.
  - `judge_seals`, `seals.valid` and `rank.score` all require the exact sha to have been seen on time.
- **G1 coverage:** a full trading day without a valid ranking counts as IC 0. A day without bars is excluded, and so are half days.
- **rstats:** it is the unfloored variance, used for reported Sharpe, volatility matching and beta. The 0.01 floor stays in the weighting on purpose (item 59, N12).
- **Nightly critical path:**
  - The critical set is library x3, witness, picks, aisleeve, allocator, stats and chain.
  - The second block runs only after the critical steps.
  - Optional failures go to `optional_failed` and cannot set ok.
- **Leak test:** every plant is real (late seal, on-time control seal, late ranking, late, edited and deleted pick, ML parity leak), and each plant can tell a leak from a catch.
- **Lane admission:**
  - Admission days are the third Tuesday from 2027-02-16.
  - It uses the previous night's scores.
  - The bar is at least 40 days, P >= 0.90 against every yardstick and DSR >= 0.90.
  - An admitted entry counts from the next trading day.
  - Exits happen on retirement or at recent P <= 0.10.
- **fills.delay_r:** the sign is right for the long-only ledger trades it covers (L14 is a library sleeve and does not pass through it).
- **freeze.py, chain.py:** a newly frozen file is flagged, and chain verify and update are consistent.
- **extdata.py, ape.py, breadth.py, review.py:** these are report and gate scripts with no verdict number. Their exceptions are logged into `notes` (extdata) or the gate output, not swallowed.

## Risks left (not defects)

- **R1, the chain half-spread fallback.** `picks.chain_half_spread` falls back silently to the 4% floor when a chain snapshot is unreadable. That is the documented floor, so the result stays within the rule, but a broken snapshot would not show. It is left as is, because the nightly `spreadcheck` reads the same files and reports them.
- **R2, AP plus AP2.** The two together can hold up to 100% of the same stock picks. This was the owner's choice on 2026-11-24 (record and flag, item 60); it is not a defect.
- **R3, the ML parity part of the leak test.** It picks the latest day with live candidates, so after a quiet day it tests an older day. It still passes, but it is weaker on quiet weeks.
- **R4, L13 history.** L13 trades written before this fix keep their old entry times in past reports. The ledger is rebuilt nightly by `library.py`, so `data/ledger/Library.jsonl` shows the new rule from tonight.
- **R5, the scope of the review.** The other frozen sleeve scorers (`weekly_opts`, `deep_otm`, `options_sim`, `orb_*`, `agent_score`, `smart_opt`, `crypto_tracks`, `corp`, `fees`, `ledger`) were read in the bug scan only. Most of them now score dropped or retired sleeves.

## External data status (ops/diag/extdata.json, 2026-11-25)

- **EDGAR:** ok, 1,533 rows at 13:48 UTC. It is not failing.
- **Cboe:** the JSON endpoint gave an HTTPError, and the HTML fallback worked.
- **Crypto:** Binance blocks GitHub (HTTP 451), and OKX is used instead.
