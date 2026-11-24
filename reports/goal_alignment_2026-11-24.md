# Goal alignment review, 2026-11-24

The owner asked for a review of every standing rule against THE ULTIMATE GOAL (runbook top block, 2026-11-23): Quantavius
picks its own stocks, develops its own strategies and runs its own book; the rules, library and benchmarks are the
foundation it is measured against; "freeze the referee, not the player". Each rule was put in one of three groups:
REFEREE (how the result is measured: must stay fixed), FOUNDATION (what Quantavius is measured against: must stay
fixed), or PLAYER (how Quantavius decides: should be free to evolve, within honest-testing guards).

## Changed today

| Rule | Was | Now | Why |
|---|---|---|---|
| Challenger lane | "Zero weight in the verdict"; a winner could matter only after the test (first review 2027-05-18) | LANE ADMISSION (item 53): own-strategy entries that beat every yardstick join the AS sleeve on fixed monthly dates from 2027-02-16 | Quantavius's own models can earn weight in its own book during the test |
| Lane cap | 3 new entries a month | 6 (item 52) | The owner expects four or more ideas a month |
| Learning findings | "Findings are proposals" (to the owner) | Findings act through Quantavius's own levers: playbook, new strategies, ranking, seal lessons | Learning should change what Quantavius does, not wait for a person |
| Morning pick filters | One fixed list, including the catalyst-or-gap method | FIXED FILTERS (eligibility, long only, 3-8 picks, 09:30) and a STARTING METHOD the playbook may replace | The method is the player's; the eligibility rules keep fills honest |
| registry.py wording | "Cycle 1 judged exactly as registered; no weight" | Points to lane admission | Matches the new rule |
| Audit checklist | No admission check | Step 1.6 tests admission for look-ahead | New path into the book must be audited |

## Kept, with the reason

| Rule | Group | Reason it fits the goal |
|---|---|---|
| No orders, read-only tools, human approval for any real or paper order | Safety | Owner's standing rule; unrelated to autonomy of judgment |
| A1 = Quantavius's own weekly book is the verdict; formula, simple rules, SPY, equal weight are readings | Referee | Already the goal's scoreboard |
| The 17 frozen scripts, freeze guard, hash chain, interventions log | Referee | The referee is frozen; the player is not |
| Decisions sealed before outcomes (picks witness 09:30, ranking 09:30, seals while the market is closed) | Referee | Without it no result can be trusted |
| No holdout; ML, lab, playbook and retunes continue to 2027-05-14 | Player | Already aligned (item 34) |
| Trial count never reset; lab gate (CPCV, PBO, coverage, neighbour check); deflated Sharpe | Guard on the player | Stops Quantavius fooling itself; a lucky strategy is not a winning one |
| Baseline A, control list, library, adaptive and crypto tracks fixed | Foundation | They are the measuring stick; moving them would hide skill or its absence |
| Playbook change bar (q <= 0.10, 30 pick days, one change a week) | Guard on the player | Set on the external review (item 37). Consequence: the first evidence-based change is possible from about early January |
| Long only; liquidity filters; 3-8 picks a day | Fixed filters | Short picks would need borrow data the ledger does not have; liquidity keeps fills realistic; 3-8 keeps G1 measurable |
| Weekly seal reads only the evidence pack (no web) | Referee | Every weight can be checked later against exactly what Quantavius saw; the pack carries market context |
| Pinned models for sealing tasks | Referee | A model swap would be a break in the series |
| Research budgets, Mon/Thu daily challenger | Operations | Usage limits; no effect on what Quantavius may decide |
| G2 counts lab approvals only | Referee | Pre-registered; admitted lane entries are reported beside it |
| Simple-rule response (pre-registration section 4) | Player | Quantavius may itself follow a simple rule in its book; the version-2 challenger runs beside it |

## Decided by the owner the same day (item 55)

Both were decided on 2026-11-24: own sleeves may hold up to 50% each, and the weekly seal may set as_mix. The original questions follow.

## The questions as put

1. OWN-WORK CEILING. Every sleeve, Quantavius's own included, is capped at 25% of its weekly book (judge.py LO/HI,
   allocator.CAP). Its own work (AP, AP2, AS) can therefore hold at most 75%, and at least 25% must sit in foundation
   sleeves. Keeping it limits concentration risk; raising the cap for own sleeves gives Quantavius more room to back
   itself. Changing it after 2026-12-07 is not possible.
2. CHOICE INSIDE AS. The AS sleeve pools approved strategies (and now admitted lane entries) at equal weight, so
   Quantavius can weight AS as a whole but not the strategies inside it. An optional "as_mix" in the weekly seal,
   read by aisleeve.py (not frozen), would let it choose. It adds one field to the seal prompts.
