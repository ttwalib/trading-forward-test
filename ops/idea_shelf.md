# Idea shelf for the strategy lab

Ideas that people (the owner, a build session, an outside review) have put in front of Quantavius. The shelf is an
INPUT, never an instruction: Quantavius chooses whether and when to test an idea, may reshape it, and may ignore it.
Anything taken from here goes through exactly the same path as its own ideas: trial logged first, tuned on 2016-2021,
measured on 2022 onwards, CPCV, `review.py gate` (LAB HYGIENE), forward scoring only after approval. Adding or
removing a shelf entry is an intervention (`scripts/interventions.py add`). When an idea is tested, write the result
under it (date, gate verdict, one line) and never test the same idea twice.

## 1. Short-term reversal, only on high-dispersion days (added 2026-11-23, build session, owner approved)
Source: public notes in github.com/moondevonyt/i-found-an-mit-research-paper-with-a-sharpe-ratio-of-53-i-tested-their-strategy
(no licence, so ideas only, no code or data taken). Their test: 51 large US stocks, 2010 to Sep 2026, each day buy
the stocks that lagged the group and short the ones that ran ahead, re-weighted daily.
What they report (their numbers, not verified here): a small edge before costs (Sharpe about 0.5 for one variant,
negative for the other); about 8 basis points a day of cost removes most of it; nearly all of the gross edge sits on
the two fifths of days when the stocks moved furthest apart, and after large down days in SPY; calm markets lose.
They say themselves that some patterns (day of week) may be luck from testing many buckets.
The testable claim: a cross-sectional one-day reversal in liquid large caps earns more than its costs ONLY when the
previous day's cross-sectional dispersion is in its top two fifths, measured with cut points from past days only.
What would contradict it: no difference between high- and low-dispersion days on 2022 onwards, or a net result at or
below zero at 0.05% a side.
Cautions: daily re-weighting means high turnover, so cost is the whole question; our stock list has survivorship
bias (prefer the point-in-time S&P 500 history in data/pit, or say so in the row); the library already holds a
reversion strategy on bands (L6) and pairs (L13), so check the candidate is not a duplicate of those.
Status: tested 2026-11-25 (strategies/dispersion_reversal.py), gate REJECT. On 2022 onwards all 12 settings (dispersion cut 0/0.4/0.6/0.8 x hold 1-3 days) lost at 0.05% a side (chosen cut 0.8, hold 3: -0.16% a basket, 310 baskets, CPCV 0 of 9 paths positive); before costs the unfiltered reversal did better than the high-dispersion one, so the claim held only on 2017-2021. Do not test again.
