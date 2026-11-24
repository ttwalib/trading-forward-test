# Setup debate against the ultimate goal, 2026-11-24

Question: is every task, rule and tool the best way to reach THE ULTIMATE GOAL (Quantavius uses its own judgment and
machine learning on real data to pick its own stocks, develop its own winning strategies and run its own book)?
The owner's instruction: nothing supersedes the goal, not even earlier hard rules.

## Tasks

| Task | Serves the goal by | Verdict |
|---|---|---|
| Morning research (Fable, daily) | Picks, sizing, holding, ranking: the player | Keep; freed further (below) |
| Weekly seal + samplers B and C (Fable) | Runs the book: the verdict | Keep; pack enriched, move limit removed |
| Learning + lab (Fable, Wed and Sat) | Develops strategies | Keep; now chooses its own track |
| Contest seals (Opus, Sonnet), daily challenger | Tests which model and rhythm runs a book best | Keep as experiments; they cannot change the book |
| Weekly, interim, final reports | Tells the owner the truth | Keep |
| Audit, review, debate (Dec 4), lane review | Referee | Keep |
| Orchestrator + watchdog (Sonnet, 4 runs a day) | Plumbing | Merge into one nightly task |
| Adaptive stocks, evening scoring (Sonnet) | Foundation scoring | Move to GitHub (tonight's build) |
| Live decisions (Sonnet, 13:05) | Foundation measurement | Move to GitHub if its data can be replaced |
| Stocks, crypto tracks, ML nightly, deep OTM, picks review | Nothing: already retired | Can be deleted |
| Five Dec 8 addenda | Planned work, spread over six prompts | Merged into ops/dec8_plan.md |

## Rules changed

| Rule | Why it held Quantavius back | Now |
|---|---|---|
| Picks could not be watchlist stocks | Barred the 22 most liquid names from its own picking | Allowed; only the control list (the benchmark) is excluded |
| A lesson could move a share by at most 5 points | Ten weeks to move a sleeve from 0 to 50% | Removed; large moves are listed and explained |
| Lab track fixed by weekday | Quantavius could not follow its own findings | Defaults only; it chooses, same gate |
| The book never saw the learning findings or lane standings | Learning could not reach the book | Both are in the evidence pack |

## Rules kept, and why they serve the goal

- No orders, and a human approval step for any order. The goal is about judgment in a simulated test. The goal's own
  text keeps this rule, and Quantavius the 1st does not place trades in any case.
- Decisions sealed before outcomes; frozen scoring code; fixed foundation and control list; trial count; lab gate.
  Without them a "winning" strategy cannot be told from a lucky one, so they are part of reaching the goal.
- Seals read only the evidence pack. The pack is the place to add information, as done today.
- Playbook evidence bar (q <= 0.10, 30 pick days). The daily picking is already free judgment; the bar only guards
  the written method against noise. First change possible from about early January.
- Pinned models for sealing tasks; long only; liquidity filters; 3-8 picks.

## Tools

Scheduled tasks have web search, the repo, and the connectors (IBKR read-only, Twelve Data, FMP, Alpha Vantage,
CoinGecko, Crypto.com). They have no web fetch and no shell network, so skills that download data (chart scanner,
news monitor, crypto ETF flows) cannot run inside a task; GitHub fetches data instead. Nothing useful is left unused
except what needs a paid plan (FMP quotes, Twelve Data regulatory data, Alpha Vantage news sentiment).

## Open for the owner

1. SHORT PICKS: allow Quantavius to pick stocks it expects to fall. Needs code, a borrow fee and the owner's yes.
2. Delete the five retired tasks, or leave them disabled.
