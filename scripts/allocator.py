"""AI allocator: decides each day how much simulated capital every strategy sleeve gets, from evidence only.

  python3 allocator.py REPO [DAY]   -> data/allocator/weights.jsonl, portfolio.jsonl, report.json; prints the report
                                       plus today's weights and the rows for the "Allocation" sheet tab.

Sleeves = every library strategy (data/library/daily.json, marked to market) + every strategy in the ledger
(baseline A, variants, control list, adaptive ORB, options O/D1/D2/D3/W1-W4, crypto tracks pooled per track, agent
picks, ML meta). Ledger sleeves: daily return % = sum of that day's results (units risked) / 5, i.e. each trade
risks 1% of one of 5 slots.

Rule (fixed on 2026-11-19; revised once on 2026-11-19 for bias controls; code FROZEN from 2026-12-07, the start of
the verdict window: ops/freeze.json records the hash of allocator.py, library.py and corp.py on the first run on or
after that date, and every later report says whether the code still matches):
- Backtest evidence (days before 2026-11-16) is haircut by 50% (survivorship: today's S&P 100 universe; publication
  decay of well-known strategies) and, together, weighs at most as much as 20 live days.
  Revised 2026-11-20 (before the freeze; owner decision): the five stock-picking sleeves whose backtest runs on
  today's S&P 100 list (L6, L7, L8, L10, L15) are haircut by 75% instead (their past returns count at a quarter).
  Their history leaves out companies that later dropped out of the index, so it is rosier than the truth. The
  number was declared before any run and is not tuned.
- Weights for day t use only returns up to day t-1 (no look-ahead).
- Evidence window: the last 120 sleeve-days; a sleeve needs >= 10 non-zero days to be eligible.
- Regime of day t = SPY close vs its 50-day average (up/down) x VIX close <= 20 / > 20, both from day t-1.
- Mean estimate per sleeve: regime mean shrunk to the sleeve's overall mean (k = 20 days), overall mean shrunk to
  zero (k = 30 days). Variance = sample variance (floor 0.01).
- Thompson sampling: draw theta ~ Normal(mean, variance / n), seeded by (ISO week, sleeve) so reruns are identical.
  This keeps trying sleeves whose evidence is thin while backing those with consistent results.
  Revised 2026-11-20 (before the freeze; user decision): the random draw is renewed once a week instead of every day.
  A daily redraw flipped the weights every day (median holding run 1 day, 25% turnover a day) and rebalancing costs
  ate the whole result in the replay; exploration does not need a new draw each day. Means, variances, breakers
  and the no-trade band still update daily. Chosen on the mechanics, not on which variant scored best.
- Weights (revised 2026-11-19, before the freeze): multivariate quarter Kelly w = 0.25 x Sigma^-1 x theta over the
  sleeves with theta > 0, where Sigma is the Ledoit-Wolf shrunk covariance of the sleeves' last 60 daily returns
  (correlated sleeves share risk automatically; this replaces the old "halve the smaller of a pair with correlation
  > 0.7" rule). Long only (negative weights dropped and re-solved), capped at 25% per sleeve.
- ALWAYS FULLY INVESTED (revised 2026-11-20, before the freeze; user decision: "holding cash is not an option"):
  the weights always sum to 100%. The quarter-Kelly solution sets the PROPORTIONS between the backed sleeves; it is
  then scaled up to 100% with the 25% cap (excess over the cap is redistributed to the other backed sleeves). If the
  backed sleeves cannot absorb 100% (fewer than four of them), the rest goes, in this order and by inverse variance
  with the same cap, to: eligible sleeves whose draw was not positive, then sleeves stopped by the breaker, then
  sleeves with too little history. This replaces the 10% volatility target, which worked by holding cash. The
  forecast volatility is still reported. Consequence, stated plainly: the portfolio can no longer step aside; its
  only defences are choosing better sleeves and the hedged sleeves (short and market-neutral strategies L14-L16).
- Weekly rebalancing (added 2026-11-20 with the fully-invested rule): the portfolio trades to its target weights on
  the first trading day of each ISO week (the day the weekly Thompson draw changes). On other days it keeps its
  weights, except that a held sleeve stopped by its breaker (or merged as a duplicate) is sold the same day and its
  weight goes to the other held sleeves pro rata (then to that day's targets if the cap is in the way). Reason:
  being 100% invested multiplies every small daily weight change by about five compared with the old cash-heavy
  book; a replay showed 33% turnover a day and 5.9% lost to rebalancing costs. Chosen on the mechanics.
- Duplicates (added 2026-11-20): sleeves whose daily results over the evidence window agree within 0.05 on every
  day both traded, with at least 3 such days (for example the adaptive breakout while its settings equal the
  baseline) count once: the first one keeps the weight (baseline
  A first, then alphabetical), the others get none, and the equal-weight benchmark counts the group once.
- Rebalancing (added 2026-11-19): a sleeve whose target weight moves by less than 2 percentage points keeps its old
  weight (no-trade band); moving to or from zero always happens. Weight changes pay a cost per unit of turnover:
  0 for intraday sleeves (flat every night, so the next trades are simply sized differently), 0.05% for daily
  library sleeves, 0.15% for crypto, 0.5% for option sleeves.
- Implementable fills (added 2026-11-19, fills.py): intraday ledger trades are scored with the entry a real engine
  could have got (engine detection price, else the price 5 minutes after the signal bar); library sleeves come from
  daily.json, which uses the same rule. The ideal-fill version is reported beside it ("ideal_fills").
- Drawdown breaker: a sleeve whose last 10 days sum below -4% or whose drawdown from its 120-day peak exceeds 8%
  gets weight 0 until it recovers. Revised 2026-11-20 (before the freeze; user decision): the limits scale with the
  sleeve's own volatility so that volatile, stock-like sleeves are not benched permanently by normal swings:
  drawdown limit = max(8%, BRK_DD_K x its 20-day volatility), 10-day limit = max(4%, BRK_10_K x its 10-day
  volatility), volatility = sample sd of its daily returns over the 120-day window. The rule is never stricter than
  the original fixed limits (BREAKER_MODE = "fixed" restores them exactly).
- In the holdout the code and parameters stay frozen; weights keep updating day by day from new evidence, because
  the process itself is what is being tested.
Benchmarks: SPY buy-and-hold (close to close), equal weight of all live sleeves, baseline A sleeve alone, and
(added 2026-11-19 for SPY, 2026-11-20 for the other two; stricter) each benchmark scaled to the AI portfolio's
realised volatility over the same phase ("spy_vm", "equal_vm", "base_a_vm"), so that neither side can win on
drawdown just by carrying less risk.
Shadow allocators (added 2026-11-20, before the freeze): three simple rivals run beside the AI allocator under the
same rules (always 100% invested, 25% cap, weekly rebalancing, the same rebalancing costs, duplicates counted once,
only data up to the day before, sleeves with at least 10 active days): "sh_rp" risk parity (weights proportional to
1 / volatility), "sh_mv" minimum variance (Ledoit-Wolf covariance, long only), "sh_win" recent winners (the four
sleeves with the best mean over the last 20 days, 25% each). They never decide pass or fail, but a pass is called
ROBUST only if the AI's Sharpe is also above the best shadow's (and it beats SPY at double costs): otherwise its
complexity added nothing over a simple rule.
AI-JUDGMENT ALLOCATOR "sh_judge" (added 2026-11-21, owner decision, before the freeze): each weekend a language-model
task reads the same evidence (scripts/judge.py brief), argues the case for and against, and seals next week's weights
in data/allocator/judge.jsonl (same rules: fully invested, at most 25% per sleeve, or 50% for its own sleeves AP, AP2, AS since 2026-11-24, eligible sleeves only). A seal
counts only if it was made before 09:30 New York on the first trading day it applies to; a week without a valid seal
keeps the previous week's weights. It trades weekly with the same rebalancing costs as the other rivals. It is a
fourth rival in the "robust" test, and "judge_check" applies the same three-way rule to it as a candidate, so the
report shows formula, AI judgment and simple rules side by side.
Reported, never part of the verdict: "forced_fill" (the average share of the book held only to stay fully
invested, and what those holdings returned, against the backed holdings) and "exposure" (the beta of the AI's daily
returns to SPY over the phase, and the return left after removing beta x SPY).
Verdict (three-way since 2026-11-20, set before the window): PASS = beats every benchmark on Sharpe AND max drawdown
(raw and volatility-matched) with bootstrap P >= 0.9 (raw and volatility-matched); FAIL = for at least one benchmark
the chance that the AI's mean beats it is <= 0.10; otherwise INCONCLUSIVE (the pre-registered consequence of
inconclusive was a six-week extension until 2026-11-21; since then the test runs a fixed six months instead:
verdict window 2026-12-07..2027-05-14, interim reading on 2027-02-12, no further extension).
Benchmarks use total-return SPY (dividends added via corp.py), the same footing as the strategies.
Stress: the same rule run on the library at double costs (daily_2x.json) is reported beside the main result.
Netting (exploratory, never part of the verdict): what the AI portfolio would save if opposite trades in the same
stock from different daily library sleeves were netted before trading ("netted_exploratory").
Verdict metrics per phase (verdict = 2026-12-07..2027-05-14, the pre-registered primary window / train / holdout / v2 / all): total return, annualised Sharpe (sqrt 252), max drawdown, and
the chance that the AI portfolio's mean daily return beats each benchmark (stationary block bootstrap, block 5,
5,000 resamples, seed 20261119).
"""
import json, os, sys, math, random, hashlib, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ledger, tcal, corp, fills
NY = ZoneInfo("America/New_York")
WIN, MIN_DAYS, K_REG, K_ALL, CAP, KELLY, CORR, SEED = 120, 10, 20, 30, 0.25, 0.25, 0.7, 20261119
PRIOR_HAIR, PRIOR_EQ = 0.5, 20
PRIOR_HAIR_SURV, SURV_SLEEVES = 0.25, ("L6 ", "L7 ", "L8 ", "L10 ", "L15 ")
COV_WIN, BAND, REBALANCE = 60, 0.02, "weekly"
BREAKER_MODE, BRK_DD_K, BRK_10_K = "vol", 3.0, 2.5
# Every script that can change a number in the verdict (extended 2026-11-21 after the external review: the calendar,
# the AI-judgment seal rules, the ledger and the scripts that score the ledger sleeves were not covered before).
FROZEN_FILES = ["allocator.py", "library.py", "corp.py", "fills.py", 
                "tcal.py", "judge.py", "ledger.py", "weekly_opts.py", "deep_otm.py", "options_sim.py", "fees.py", "crypto_tracks.py", 
                "orb_daily.py", "orb_variants.py", "orb_adaptive.py", "agent_score.py", "smart_opt.py",
                # added 2026-11-24 (external review N2): the scripts that score Quantavius's own sleeves inside A1, the
                # G1 ranking, the witness that decides what counts, the statistics, the nightly runner, the contest
                # scorer, the evidence chain, the calibration score and the option fill helpers that approved option
                # strategies use. The player's own files (prompts, playbook, strategies/*.py) stay free.
                "picks.py", "aisleeve.py", "rank.py", "witness.py", "stats.py", "nightly.py", "seals.py", "chain.py",
                "calib.py", "optarch.py", "freeze.py"]
BASE = "A baseline (watchlist)"
# Sleeves removed from the book on 2026-11-23 by a rule that ignores results (owner decision, runbook item 32): a sleeve
# stays only if it is a benchmark, a control, the strategy menu the allocator manages (library L1-L17), or made or
# picked by the AI. Rule variants of baseline A and the fixed option structures are none of these. Their past trades
# stay in the ledger as history; they simply can no longer receive weight or count in the equal-weight benchmark.
DROPPED = ("A variant", "B variant", "C variant", "D variant", "E variant", "F variant", "G variant", "T variant",
           "O ATM calls", "D1 lottery calls", "D2 SPY put spreads", "D3 SPY call spreads", "W1", "W2", "W3", "W4",
           "L2 VWAP pullback", "L4 Gap fade")
# COST RULE (owner decision 2026-11-25, before the freeze; blind to results: it reads only the size of each trade's gross
# move, never its sign or profit): a sleeve or crypto strategy is dropped when its median absolute gross move per trade is
# below 2x its round-trip cost (listing reports/costrule/2026-11-25.json). Library sleeves L2 and L4 are in DROPPED above;
# the crypto strategies below are inside the pooled crypto sleeves, so their trades are left out of the pool. Their
# ledgers keep running and stay as history; only the book and the equal-weight benchmarks stop counting them.
COST_DROPPED_CRYPTO = ("15m fixed M1", "15m adaptive M1")
# Short-premium option sleeves (they sell option premium on SPY and fall together in a sell-off): together they may
# hold at most GROUP_CAP of the book, in the AI portfolio and in every rival allocator. Added 2026-11-21, before the
# freeze, after the external review; the stress test behind it is scripts/stress_short_premium.py. Duplicates: since
# 2026-11-21 two sleeves count as one only if they are equal to within rounding (DUP_TOL) on at least DUP_DAYS days on
# which both traded, so two different sleeves that each took one similar stop on a few days cannot be merged.
SHORT_PREMIUM, GROUP_CAP = ("W1", "W2", "D2 ", "D3 "), 0.25
DUP_DAYS, DUP_TOL = 5, 0.005


def jl(path): return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def dclose(repo, sym, total_return=False):
    rows = sorted((dt.datetime.fromtimestamp(b["t"], NY).date().isoformat(), b["o"], b["h"], b["l"], b["c"])
                  for b in jl(os.path.join(repo, "data", "bars", "1d", sym + ".jsonl")))
    if total_return: rows = corp.tr_adjust(repo, sym, rows)
    return {r[0]: r[4] for r in rows}


def sleeves(repo, lib_file="daily.json", realistic=True):
    S = {}
    f = os.path.join(repo, "data", "library", lib_file)
    if os.path.exists(f):
        for k, v in json.load(open(f)).items(): S[k] = dict(v)
    T = ledger.trades(repo)
    adj = fills.delay_r(repo, T) if realistic else {}
    for i, t in enumerate(T):
        if t["asset"] == "library": continue  # library sleeves come marked to market from daily.json
        if t["asset"] == "crypto" and t["strategy"] in COST_DROPPED_CRYPTO: continue  # cost rule, 2026-11-25
        name = t["strategy"]
        if t["asset"] == "crypto": name = "Crypto " + " ".join(name.split()[:2]) + " (pooled)"
        S.setdefault(name, {}); S[name][t["day"]] = S[name].get(t["day"], 0.0) + (t["result"] + adj.get(i, 0.0)) / 5 * 1.0
    # the AI's own picks (picks.py) and the AI's own approved strategies (aisleeve.py), both added 2026-11-23
    for f in (os.path.join(repo, "data", "picks", "daily.json"), os.path.join(repo, "data", "ai", "daily.json")):
        if os.path.exists(f):
            for k, v in json.load(open(f)).items(): S[k] = dict(v)
    return {k: v for k, v in S.items() if not k.startswith(DROPPED)}


def duplicates(S, days):
    """{sleeve: representative} for sleeves that are the same strategy in practice: on the days in `days` where both
    have a result they have at least DUP_DAYS such days and never differ by more than DUP_TOL (% of sleeve capital)."""
    order = sorted(S, key=lambda k: (k != BASE, k)); out = {}; reps = []
    for name in order:
        a = S[name]; hit = None
        for r in reps:
            b = S[r]; common = [x for x in days if a.get(x) and b.get(x)]
            if len(common) >= DUP_DAYS and all(abs(a[x] - b[x]) <= DUP_TOL for x in common): hit = r; break
        if hit: out[name] = hit
        else: reps.append(name)
    return out


# Sealed books (weekly judge seals, contests, daily challenger) are scored under the same per-sleeve caps the seal was
# checked against in judge.py: 50% for Quantavius's own sleeves, CAP for every other sleeve (owner decision 2026-11-24,
# item 55; pre-freeze code review 2026-11-25 found the scoring still capped every sleeve at CAP).
SEAL_OWN = ("AP Agent picks", "AP2 Agent picks", "AP3 Agent picks", "AP4 Agent picks", "AS AI strategies")
SEAL_OWN_CAP = 0.50


def seal_cap(name):
    return SEAL_OWN_CAP if name.startswith(SEAL_OWN) else CAP


def fill_to_one(tiers, cap=None):
    """tiers: list of {name: score > 0}. Returns weights summing to 1 (or less only if every sleeve is at the cap):
    each tier takes what is left, in proportion to its scores, with the per-sleeve cap (water-filling). cap: optional
    function name -> cap (seal_cap for sealed books); default CAP for every sleeve."""
    capf = cap or (lambda k: CAP)
    w = {}; left = 1.0
    for tier in tiers:
        tier = {k: v for k, v in tier.items() if v > 0 and k not in w}
        if left <= 1e-9 or not tier: continue
        free = dict(tier); got = {k: 0.0 for k in tier}; room = left
        for _ in range(len(tier) + 1):
            tot = sum(free.values())
            if tot <= 0 or room <= 1e-12: break
            over = {k for k, v in free.items() if got[k] + room * v / tot >= capf(k) - 1e-12}
            if not over:
                for k, v in free.items(): got[k] += room * v / tot
                room = 0.0; break
            for k in over: room -= capf(k) - got[k]; got[k] = capf(k); free.pop(k)
        for k, v in got.items():
            if v > 0: w[k] = v
        left = 1.0 - sum(w.values())
    return w


def group_cap(w):
    """Scales the short-premium option sleeves down to GROUP_CAP in total and hands the freed weight to the other
    sleeves in proportion to their weights, each still limited to CAP. Stays fully invested; if every other sleeve
    is at its cap the remainder stays where it was."""
    g = [k for k in w if k.startswith(SHORT_PREMIUM)]; tot = sum(w[k] for k in g)
    if tot <= GROUP_CAP + 1e-9: return w
    out = dict(w); f = GROUP_CAP / tot
    for k in g: out[k] = w[k] * f
    room = tot - GROUP_CAP; free = {k: v for k, v in w.items() if k not in g and v > 0}
    for _ in range(len(free) + 1):
        ft = sum(free.values())
        if ft <= 0 or room <= 1e-12: break
        over = [k for k, v in free.items() if out[k] + room * v / ft >= CAP - 1e-12]
        if not over:
            for k, v in free.items(): out[k] += room * v / ft
            room = 0.0; break
        for k in over: room -= CAP - out[k]; out[k] = CAP; free.pop(k)
    if room > 1e-9:
        for k in g: out[k] += room * w[k] / tot
    return out


def rebal_cost(name):
    """Cost (%) per unit of weight change. Intraday sleeves are flat overnight: new weights size the next trades."""
    if name.startswith(("L1 ", "L2 ", "L3 ", "L4 ", "L14 ", "A ", "Agent picks: stocks", "ML", "AP4 ")) or "variant" in name or "ORB" in name:
        return 0.0
    if name.startswith("Crypto") or "crypto" in name.lower(): return 0.15
    if name.startswith(("O ", "D1", "D2", "D3", "W1", "W2", "W3", "W4", "AP3 ")): return 0.5
    return 0.05


def ledoit_wolf(X):
    """Ledoit-Wolf (2004) shrinkage of the sample covariance toward a scaled identity. X: n x p."""
    n, p = X.shape
    X = X - X.mean(0); S = X.T @ X / n
    m = np.trace(S) / p; F = m * np.eye(p)
    d2 = ((S - F) ** 2).sum() / p
    if d2 <= 0: return F
    b2 = sum((((np.outer(x, x) - S) ** 2).sum()) for x in X) / n ** 2 / p
    k = min(b2, d2) / d2
    return k * F + (1 - k) * S


def regime_of(spy, vix, cal):
    out = {}; keys = sorted(spy)
    for i, d in enumerate(cal):
        prev = [k for k in keys if k < d][-50:]
        if len(prev) < 50: out[d] = "unknown"; continue
        m = sum(spy[k] for k in prev) / 50; last = prev[-1]
        vk = [k for k in sorted(vix) if k < d]
        v = vix[vk[-1]] if vk else 20
        out[d] = ("up" if spy[last] > m else "down") + ("-calm" if v <= 20 else "-stress")
    return out


def rstats(xs):
    """Mean and the UNFLOORED sample variance (review N12, 2026-11-24): used for reported Sharpe ratios, drawdown-free
    volatility matching and beta, where the 0.01 floor of stats() (a 0.1% daily volatility) would distort a
    diversified book. The floor stays in the weighting (stats, wstats), where it is a deliberate prior."""
    n = len(xs)
    if n < 2: return (xs[0] if xs else 0.0), 0.0
    m = sum(xs) / n
    return m, sum((x - m) ** 2 for x in xs) / (n - 1)


def stats(xs):
    n = len(xs)
    if n == 0: return 0.0, 0.01
    m = sum(xs) / n; v = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.01
    return m, max(v, 0.01)


def wstats(xs, ws):
    """Weighted mean, variance (floor 0.01) and effective sample size (sum of weights)."""
    W = sum(ws)
    if W <= 0: return 0.0, 0.01, 0.0
    m = sum(w * x for w, x in zip(ws, xs)) / W
    v = sum(w * (x - m) ** 2 for w, x in zip(ws, xs)) / W * (W / (W - 1) if W > 1 else 1)
    return m, max(v, 0.01), W


def evidence(series, days, name=""):
    """Returns and weights: live days weight 1; backtest days haircut and capped to PRIOR_EQ live days in total."""
    hair = PRIOR_HAIR_SURV if str(name).startswith(SURV_SLEEVES) else PRIOR_HAIR
    start = tcal.START.isoformat(); prior = [d for d in days if d < start]
    wp = min(1.0, PRIOR_EQ / len(prior)) if prior else 1.0
    xs = [series.get(d, 0.0) * (hair if d < start else 1.0) for d in days]
    ws = [wp if d < start else 1.0 for d in days]
    return xs, ws


def corr(a, b):
    n = len(a)
    if n < 20: return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb) if va and vb else 0.0


def weights_for(d, S, cal_idx, regime, cal):
    i = cal_idx[d]; hist_days = cal[max(0, i - WIN):i]; w = {}; info = {}
    reg = regime.get(d, "unknown"); dup = duplicates(S, hist_days); t2, t3, t4 = {}, {}, {}
    for name, series in S.items():
        if name in dup: info[name] = "duplicate of " + dup[name]; continue
        live = [x for x in hist_days if x >= min(series, default="9999")]
        raw = [series.get(x, 0.0) for x in live]
        nz = sum(1 for x in raw if x != 0)
        if nz < MIN_DAYS:
            if nz >= 1: t4[name] = 1.0 / stats(raw)[1]
            continue
        xs, ws = evidence(series, live, name)
        m_all, v, n = wstats(xs, ws)
        m0 = n * m_all / (n + K_ALL)
        rk = [k for k, x in enumerate(live) if regime.get(x) == reg]
        mr, _, nr = wstats([xs[k] for k in rk], [ws[k] for k in rk]) if rk else (m0, 0, 0.0)
        mu = (nr * mr + K_REG * m0) / (nr + K_REG)
        last10 = raw[-10:]; cum = peak = dd = 0.0
        for x in raw: cum += x; peak = max(peak, cum); dd = max(dd, peak - cum)
        lim_dd, lim_10 = 8.0, 4.0
        if BREAKER_MODE == "vol" and len(raw) > 1:
            mr = sum(raw) / len(raw); sd = math.sqrt(sum((x - mr) ** 2 for x in raw) / (len(raw) - 1))
            lim_dd, lim_10 = max(8.0, BRK_DD_K * sd * math.sqrt(20)), max(4.0, BRK_10_K * sd * math.sqrt(10))
        if sum(last10) < -lim_10 or dd > lim_dd: info[name] = "breaker"; t3[name] = 1.0 / v; continue
        wk = "%d-W%02d" % dt.date.fromisoformat(d).isocalendar()[:2]
        h = int(hashlib.sha1(f"{SEED}|{wk}|{name}".encode()).hexdigest()[:12], 16)
        theta = random.Random(h).gauss(mu, math.sqrt(v / max(n, 1.0)))
        if theta > 0: w[name] = theta
        else: t2[name] = 1.0 / v
        info[name] = round(mu, 4)
    names = sorted(w)
    if not names:
        full = group_cap(fill_to_one([t2, t3, t4]))
        info["_vol_forecast_pct"] = None; info["_fill"] = {"backed": 0, "filled": len(full)}
        return {k: round(x, 4) for k, x in full.items() if x > 0.0005}, info
    days60 = hist_days[-COV_WIN:]
    X = np.array([[S[k].get(x, 0.0) for k in names] for x in days60]) if len(days60) >= 2 else np.zeros((2, len(names)))
    Sig = ledoit_wolf(X)
    Sig[np.diag_indices_from(Sig)] = np.maximum(np.diag(Sig), 0.01)
    act = list(range(len(names))); wv = np.zeros(len(names))
    for _ in range(len(names) + 1):            # long only: drop negative weights and re-solve
        sub = np.ix_(act, act)
        sol = KELLY * np.linalg.solve(Sig[sub], np.array([w[names[i]] for i in act]))
        wv = np.zeros(len(names)); wv[act] = sol
        neg = [i for i, x in zip(act, sol) if x <= 0]
        if not neg: break
        act = [i for i in act if i not in neg]
        if not act: wv = np.zeros(len(names)); break
    backed = {names[i]: float(wv[i]) for i in range(len(names)) if wv[i] > 0}
    info["_backed"] = sorted(backed)
    full = group_cap(fill_to_one([backed, t2, t3, t4]))            # always fully invested: no cash
    wf = np.array([full.get(k, 0.0) for k in names])
    info["_vol_forecast_pct"] = round(float(np.sqrt(max(wf @ Sig @ wf, 0.0) * 252)), 3)   # backed sleeves only
    info["_fill"] = {"backed": len(backed), "backed_weight": round(sum(full.get(k, 0.0) for k in backed), 4),
                     "filled": len(full) - len([k for k in backed if k in full])}
    return {k: round(x, 4) for k, x in full.items() if x > 0.0005}, info


def shadow_targets(d, S, cal_idx, cal):
    """Target weights of the simple rival allocators for day d, from data before d only."""
    i = cal_idx[d]; hist = cal[max(0, i - WIN):i]; dup = duplicates(S, hist); el = {}
    for name, series in S.items():
        if name in dup: continue
        raw = [series.get(x, 0.0) for x in hist if x >= min(series, default="9999")]
        if sum(1 for x in raw if x) < MIN_DAYS: continue
        el[name] = raw
    if not el: return {"sh_rp": {}, "sh_mv": {}, "sh_win": {}}
    names = sorted(el); rp = {k: 1.0 / math.sqrt(max(stats(el[k])[1], 0.01)) for k in names}
    days = hist[-COV_WIN:]
    X = np.array([[S[k].get(x, 0.0) for k in names] for x in days]) if len(days) >= 2 else np.zeros((2, len(names)))
    Sig = ledoit_wolf(X); Sig[np.diag_indices_from(Sig)] = np.maximum(np.diag(Sig), 0.01)
    act = list(range(len(names))); mv = {}
    for _ in range(len(names) + 1):
        sol = np.linalg.solve(Sig[np.ix_(act, act)], np.ones(len(act)))
        neg = [a for a, x in zip(act, sol) if x <= 0]
        if not neg: mv = {names[a]: float(x) for a, x in zip(act, sol)}; break
        act = [a for a in act if a not in neg]
        if not act: break
    top = sorted(names, key=lambda k: -(sum(el[k][-20:]) / max(1, len(el[k][-20:]))))[:4]
    return {"sh_rp": group_cap(fill_to_one([rp])), "sh_mv": group_cap(fill_to_one([mv, rp])),
            "sh_win": group_cap(fill_to_one([{k: 1.0 for k in top}, rp]))}


SHADOWS = ("sh_rp", "sh_mv", "sh_win")
JUDGE = "sh_judge"


JUDGE_SEAL_ERRORS = []   # rows that raised while being checked (pre-freeze review 2026-11-25: reported, never silent)


def judge_seal_rows(repo):
    """Valid sealed rows of the AI-judgment allocator: {effective day: the full row}. A row counts only if sealed
    before 09:30 New York on its effective day and, from witness.ENFORCE_FROM, first seen by GitHub before then (the
    witness); the first valid row per effective day stands. A row that raises while being checked is skipped and
    recorded in JUDGE_SEAL_ERRORS (reported in judge_check.seal_rows_with_errors)."""
    import witness
    out = {}; f = os.path.join(repo, "data", "allocator", "judge.jsonl"); del JUDGE_SEAL_ERRORS[:]
    if not os.path.exists(f): return out
    WS = witness.sightings(repo)
    for n, line in enumerate(open(f), 1):
        if not line.strip(): continue
        try:
            r = json.loads(line); eff = r["effective"]
            sealed = dt.datetime.fromisoformat(r["sealed_at"]).astimezone(NY)
            limit = dt.datetime.fromisoformat(eff + "T09:30:00").replace(tzinfo=NY)
            w = {k: float(v) for k, v in r["weights"].items() if float(v) > 0}
            # GitHub must also have seen this exact row before 09:30 on its effective day (review N1, from witness.ENFORCE_FROM)
            seen = witness.on_time(WS, "seal", "judge.jsonl|%s|%s" % (eff, r.get("sealed_at")), witness.sha(r), eff)
            if sealed < limit and seen and w and eff not in out: out[eff] = dict(r, weights=w)
        except Exception as e:
            JUDGE_SEAL_ERRORS.append({"line": n, "error": "%s: %s" % (type(e).__name__, e)})
    return out


def judge_seals(repo):
    """Valid sealed weights of the AI-judgment allocator: {effective day: weights} (rule in judge_seal_rows)."""
    return {e: r["weights"] for e, r in judge_seal_rows(repo).items()}


def perf(xs):
    if not xs: return {"days": 0}
    cum = 1.0; peak = 1.0; mdd = 0.0
    for x in xs:
        cum *= 1 + x / 100; peak = max(peak, cum); mdd = max(mdd, 1 - cum / peak)
    m, v = rstats(xs)
    sd = math.sqrt(v) if len(xs) > 1 else 0
    return {"days": len(xs), "total_pct": round((cum - 1) * 100, 3), "sharpe": round(m / sd * math.sqrt(252), 2) if sd else None,
            "max_dd_pct": round(mdd * 100, 3), "mean_daily_pct": round(m, 4),
            "below_weighting_floor": len(xs) > 1 and v < 0.01}      # the 0.01 floor would have bound (review N12)


def p_beats(a, b, B=5000, restart=0.2):
    """Stationary block bootstrap: blocks of consecutive days with a mean length of 1/restart (5 days by default,
    i.e. one trading week). restart=0.1 (10-day blocks) is used only for the sensitivity reading."""
    diff = [x - y for x, y in zip(a, b)]; n = len(diff)
    if n < 10: return None
    rng = random.Random(SEED); hits = 0
    for _ in range(B):
        s = 0.0; k = 0; i = rng.randrange(n)
        while k < n:
            s += diff[i]; k += 1
            i = rng.randrange(n) if rng.random() < restart else (i + 1) % n
        hits += s > 0
    return round(hits / B, 3)


def freeze_check(repo, day):
    here = os.path.dirname(os.path.abspath(__file__))
    cur = {f: hashlib.sha256(open(os.path.join(here, f), "rb").read()).hexdigest() for f in FROZEN_FILES if os.path.exists(os.path.join(here, f))}
    fz = os.path.join(repo, "ops", "freeze.json")
    if day < tcal.ALLOC_FREEZE.isoformat(): return {"frozen": False, "freeze_date": tcal.ALLOC_FREEZE.isoformat()}
    if not os.path.exists(fz):
        os.makedirs(os.path.dirname(fz), exist_ok=True)
        json.dump({"recorded_on": day, "recorded_by": "nightly fallback (nobody ran scripts/freeze.py record)", "sha256": cur}, open(fz, "w"), indent=1)
    rec = json.load(open(fz))
    bad = [f for f in cur if rec["sha256"].get(f) != cur[f]]
    return {"frozen": True, "recorded_on": rec["recorded_on"], "code_matches_freeze": not bad, "changed_files": bad}


def power(n):
    """Annualised Sharpe gap the bootstrap can call at P >= 0.9 with n days (about 1.28 standard errors)."""
    return round(1.2816 * math.sqrt(252 / n), 2) if n else None


def simulate(repo, day, S, spy, vix, judge=True):
    cal = sorted(d for d in set(spy) | {d for s in S.values() for d in s} if d <= day and tcal.is_open(d))
    if not cal: return None
    cal_idx = {d: i for i, d in enumerate(cal)}; regime = regime_of(spy, vix, cal)
    start = tcal.START.isoformat(); rows = []; W = []; spy_keys = sorted(spy); wprev = {}; wk_prev = None
    backed_ref = set(); shw = {k: {} for k in SHADOWS}
    seals = judge_seals(repo) if judge else {}; jw = {}; j_missed = 0
    for d in cal:
        if d < start: continue
        tgt, info = weights_for(d, S, cal_idx, regime, cal)
        wk = dt.date.fromisoformat(d).isocalendar()[:2]; sh_ret = {}
        new_week = wk != wk_prev
        if new_week or not any(shw.values()):
            tg = shadow_targets(d, S, cal_idx, cal)
        for k in SHADOWS:
            old = shw[k]; cur = {a: round(b, 4) for a, b in tg[k].items() if b > 0.0005} if (new_week or not old) and tg[k] else old
            cst = sum(abs(cur.get(a, 0.0) - old.get(a, 0.0)) * rebal_cost(a) for a in set(cur) | set(old))
            sh_ret[k] = sum(b * S[a].get(d, 0.0) for a, b in cur.items()) - cst; shw[k] = cur
        jret = None; jnew = None
        if seals:
            # the seal for this week is the one whose effective day falls in this ISO week and is not after d
            cand = sorted(e for e in seals if e <= d and dt.date.fromisoformat(e).isocalendar()[:2] == wk)
            if cand and (new_week or d in seals): jnew = fill_to_one([{k: v for k, v in seals[cand[-1]].items() if k in S}], seal_cap)
            elif new_week and jw: j_missed += 1
            if jnew is not None:
                jnew = {a: round(b, 4) for a, b in jnew.items() if b > 0.0005}
                jc = sum(abs(jnew.get(a, 0.0) - jw.get(a, 0.0)) * rebal_cost(a) for a in set(jnew) | set(jw)); jw = jnew
            else: jc = 0.0
            if jw: jret = sum(b * S[a].get(d, 0.0) for a, b in jw.items()) - jc
        if new_week or not wprev: backed_ref = set(info.get("_backed") or [])
        if REBALANCE == "weekly" and wprev and wk == wk_prev:
            keep = {k: v for k, v in wprev.items() if info.get(k) != "breaker" and not str(info.get(k, "")).startswith("duplicate")}
            w = dict(wprev) if len(keep) == len(wprev) else fill_to_one([keep, tgt])
        else:
            w = {}
            for k in set(tgt) | set(wprev):
                a, b = tgt.get(k, 0.0), wprev.get(k, 0.0)
                w[k] = b if (a > 0 and b > 0 and abs(a - b) < BAND) else a
            w = fill_to_one([{k: v for k, v in w.items() if v > 0}]) if any(v > 0 for v in w.values()) else {}
        wk_prev = wk
        w = {k: round(v, 4) for k, v in w.items() if v > 0.0005}
        turn = {k: abs(w.get(k, 0.0) - wprev.get(k, 0.0)) for k in set(w) | set(wprev)}
        rcost = sum(v * rebal_cost(k) for k, v in turn.items()); wprev = w
        ai = sum(wt * S[k].get(d, 0.0) for k, wt in w.items()) - rcost
        fill_w = sum(wt for k, wt in w.items() if k not in backed_ref)
        fill_ret = sum(wt * S[k].get(d, 0.0) for k, wt in w.items() if k not in backed_ref)
        i0 = cal_idx[d]; dup = duplicates(S, cal[max(0, i0 - WIN):i0])
        live = [k for k, s in S.items() if s and min(s) <= d and k not in dup]
        eq = sum(S[k].get(d, 0.0) for k in live) / len(live) if live else 0.0
        lf = [k for k in live if not k.startswith(OWN_SLEEVES)]     # foundation only (2026-11-23): no sleeve the AI itself made
        eq_f = sum(S[k].get(d, 0.0) for k in lf) / len(lf) if lf else 0.0
        prev = [k for k in spy_keys if k < d]
        sp = (spy[d] / spy[prev[-1]] - 1) * 100 if d in spy and prev else 0.0
        base = S.get(BASE, {}).get(d, 0.0)
        rows.append({"date": d, "phase": tcal.phase(d), "regime": regime.get(d), "ai": round(ai, 5), "spy": round(sp, 5),
                     "equal": round(eq, 5), "equal_f": round(eq_f, 5), "base_a": round(base, 5), "n_live": len(live), "invested": round(sum(w.values()), 4),
                     "turnover": round(sum(turn.values()), 4), "rebal_cost": round(rcost, 5),
                     "fill_w": round(fill_w, 4), "fill_ret": round(fill_ret, 5),
                     **{k: round(v, 5) for k, v in sh_ret.items()},
                     **({JUDGE: round(jret, 5)} if jret is not None else {})})
        W.append({"date": d, "weights": w, "breakers": sorted(k for k, v in info.items() if v == "breaker"),
                  "duplicates": sorted(k for k, v in info.items() if isinstance(v, str) and v.startswith("duplicate")),
                  "vol_forecast_pct": info.get("_vol_forecast_pct"), "fill": info.get("_fill"),
                  "forced": sorted(k for k in w if k not in backed_ref), "shadows": {k: dict(v) for k, v in shw.items()},
                  **({"judge": dict(jw), "judge_weeks_without_seal": j_missed} if jw else {})})
    return rows, W


OWN_SLEEVES = ("AP ", "AP2 ", "AP3 ", "AP4 ", "AS ", "Agent picks")     # Quantavius's own sleeves: picks, sized picks, approved lab
# strategies and (since 2026-11-23, runbook item 43) its picks traded under the breakout rules or as calls; none of these
# may sit inside the foundation benchmark (equal_f)


def phase_report(rows):
    out = {}
    for ph in ("verdict", "all", "v2", "train", "holdout"):
        sel = [r for r in rows if ph == "all" or (ph == "v2" and r["date"] >= tcal.V2_START.isoformat())
               or (ph == "verdict" and r["date"] >= tcal.ALLOC_FREEZE.isoformat()) or r["phase"] == ph]
        if not sel: continue
        ai = [r["ai"] for r in sel]; sp = [r["spy"] for r in sel]
        sa = math.sqrt(rstats(ai)[1]) if len(ai) > 1 else 0; scales = {}
        for b in ("spy", "equal", "base_a"):
            xs = [r[b] for r in sel]; sb = math.sqrt(rstats(xs)[1]) if len(xs) > 1 and any(xs) else 0
            scales[b] = sa / sb if sb else 0.0
            for r in sel: r[b + "_vm"] = r[b] * scales[b]
        k_vm = scales["spy"]; BM = ("spy", "equal", "base_a", "spy_vm", "equal_vm", "base_a_vm")
        P = {k: perf([r[k] for r in sel]) for k in ("ai",) + BM}
        P["spy_vm_scale"] = round(k_vm, 3); P["vm_scales"] = {k: round(v, 3) for k, v in scales.items()}
        P["p_ai_beats"] = {k: p_beats(ai, [r[k] for r in sel]) for k in BM}
        P["avg_invested"] = round(sum(r.get("invested", 0) for r in sel) / len(sel), 4)
        P["shadows"] = {k: perf([r.get(k, 0.0) for r in sel]) for k in SHADOWS}
        for k in SHADOWS: P["p_ai_beats"][k] = p_beats(ai, [r.get(k, 0.0) for r in sel])
        js = [r for r in sel if r.get(JUDGE) is not None]
        if js:      # the AI-judgment allocator, on the days it has sealed weights for (all of the verdict window)
            P["shadows"][JUDGE] = dict(perf([r[JUDGE] for r in js]), covers_phase=len(js) == len(sel))
            P["p_ai_beats"][JUDGE] = p_beats([r["ai"] for r in js], [r[JUDGE] for r in js])
            P["ai_on_judge_days"] = perf([r["ai"] for r in js])
        fr = sum(r.get("fill_ret", 0) for r in sel); fw = sum(r.get("fill_w", 0) for r in sel) / len(sel)
        P["forced_fill"] = {"avg_weight": round(fw, 4), "return_pct_total": round(fr, 4),
                            "backed_return_pct_total": round(sum(r["ai"] + r.get("rebal_cost", 0) for r in sel) - fr, 4),
                            "days_with_fill": sum(1 for r in sel if r.get("fill_w", 0) > 0.0005)}
        ms, vs = rstats(sp) if len(sp) > 1 else (0.0, 0.0)
        beta = (sum((a - sum(ai) / len(ai)) * (b - ms) for a, b in zip(ai, sp)) / (len(sp) - 1) / vs) if len(sp) > 2 and vs > 0 else None
        P["exposure"] = {"beta_spy": round(beta, 3) if beta is not None else None,
                         "after_beta_pct_total": round(sum(a - beta * b for a, b in zip(ai, sp)), 4) if beta is not None else None}
        P["sharpe_gap_detectable"] = power(len(sel))
        P["turnover_per_day"] = round(sum(r.get("turnover", 0) for r in sel) / len(sel), 4)
        P["rebal_cost_pct_total"] = round(sum(r.get("rebal_cost", 0) for r in sel), 4)
        out[ph] = P
    return out


def verdict_check(P, stress=None):
    """Pre-registered three-way rule for one phase. PASS: beat every benchmark on Sharpe AND max drawdown with
    P >= 0.9, raw and volatility-matched. FAIL: for some benchmark P(AI mean > benchmark) <= 0.10. Else INCONCLUSIVE.
    Robust = a pass that also beats SPY at double costs AND beats the best rival allocator on Sharpe (risk parity,
    minimum variance, recent winners and, since 2026-11-21, the AI-judgment allocator)."""
    if not P or P["ai"].get("days", 0) < 10: return {"status": "not enough days"}
    ai = P["ai"]; res = {}; pa = P["p_ai_beats"]
    for b in ("spy", "equal", "base_a"):
        bm = P[b]; vm = P[b + "_vm"]; has_vm = bool(P.get("vm_scales", {}).get(b))
        sh = ai.get("sharpe") is not None and (bm.get("sharpe") is None or ai["sharpe"] > bm["sharpe"])
        dd = ai["max_dd_pct"] < bm["max_dd_pct"] and (not has_vm or ai["max_dd_pct"] < vm["max_dd_pct"])
        pb = (pa.get(b) or 0) >= 0.9 and (not has_vm or (pa.get(b + "_vm") or 0) >= 0.9)
        res[b] = {"sharpe": sh, "drawdown": dd, "p_ge_0.9": pb, "beats": sh and dd and pb,
                  "p": pa.get(b), "p_vm": pa.get(b + "_vm") if has_vm else None}
    ok = all(v["beats"] for v in res.values())
    lost = [b for b in res if pa.get(b) is not None and pa[b] <= 0.10]
    rob = None
    if stress: rob = (stress["ai"].get("sharpe") or -9) > (P["spy"].get("sharpe") or 0) and (stress["p_ai_beats"].get("spy") or 0) >= 0.9
    sh = {k: v.get("sharpe") for k, v in (P.get("shadows") or {}).items() if v.get("days") and v.get("sharpe") is not None}
    best = max(sh, key=sh.get) if sh else None
    beats_sh = best is None or (ai.get("sharpe") is not None and ai["sharpe"] > sh[best])
    return {"result": "pass" if ok else "fail" if lost else "inconclusive", "pass": ok, "clearly_behind": lost,
            "robust_2x": rob if ok else None, "best_shadow": best, "beats_best_shadow": beats_sh,
            "robust": bool(ok and rob and beats_sh) if ok else None, "by_benchmark": res}


def judge_check(rows, ph="verdict"):
    """The same three-way rule with the AI-judgment allocator as the candidate (benchmarks volatility-matched to it).
    Its rivals are the formula allocator and the three simple rules."""
    sel = [dict(r) for r in rows if r.get(JUDGE) is not None and (ph == "all" or (ph == "verdict" and r["date"] >= tcal.ALLOC_FREEZE.isoformat())
           or (ph == "second_half" and r["date"] >= tcal.HOLDOUT_START.isoformat()) or r["phase"] == ph)]
    if len(sel) < 10: return {"status": "not enough days", "days": len(sel)}
    j = [r[JUDGE] for r in sel]; sj = math.sqrt(rstats(j)[1]); scales = {}
    for b in ("spy", "equal", "equal_f", "base_a"):
        xs = [r[b] for r in sel]; sb = math.sqrt(rstats(xs)[1]) if any(xs) else 0
        scales[b] = sj / sb if sb else 0.0
        for r in sel: r[b + "_vm"] = r[b] * scales[b]
    BM = ("spy", "equal", "equal_f", "base_a", "spy_vm", "equal_vm", "equal_f_vm", "base_a_vm")
    P = {k: perf([r[k] for r in sel]) for k in BM}; P["ai"] = perf(j)
    P["vm_scales"] = scales; P["p_ai_beats"] = {k: p_beats(j, [r[k] for r in sel]) for k in BM}
    P["shadows"] = {k: perf([r.get(k, 0.0) for r in sel]) for k in SHADOWS}; P["shadows"]["formula"] = perf([r["ai"] for r in sel])
    out = verdict_check(P); out["judge"] = P["ai"]; out["p_judge_beats_formula"] = p_beats(j, [r["ai"] for r in sel])
    # A1 PRIMARY (2026-11-23, runbook item 35): ONE comparison with power - Quantavius's book against the equal-weight
    # foundation scaled to the book's own volatility. PASS: bootstrap P >= 0.9 and a higher Sharpe; FAIL: P <= 0.10.
    # The strict rule above (every benchmark, Sharpe AND drawdown) is kept as "A1 strict", a secondary reading.
    # since 2026-11-23 (before the window) the primary benchmark is the FOUNDATION equal weight: every live sleeve except
    # the AI's own (AP, AP2, AS). The earlier blend that includes them stays as a secondary reading ("primary_incl_own").
    def prim(key, label):
        pe = P["p_ai_beats"].get(key + "_vm"); sj_, se_ = P["ai"].get("sharpe"), P[key].get("sharpe")
        res = ("PASS" if pe is not None and pe >= 0.9 and sj_ is not None and se_ is not None and sj_ > se_
               else "FAIL" if pe is not None and pe <= 0.10 else "INCONCLUSIVE")
        return {"benchmark": label, "days": len(sel), "p_beats_vm": pe, "sharpe_book": sj_, "sharpe_benchmark": se_, "result": res}
    out["primary"] = dict(prim("equal_f", "equal weight of the foundation sleeves only (volatility-matched)"),
                          rule="A1 primary: book vs foundation equal weight (volatility-matched), P >= 0.9 and higher Sharpe = PASS; P <= 0.10 = FAIL")
    out["primary_incl_own"] = prim("equal", "equal weight of all live sleeves including the AI's own (volatility-matched)")
    # External review of 2026-11-23 (3.3, 3.5), secondary readings that decide nothing:
    # effective sample (the daily returns come from far fewer weekly decisions), the same probability with 10-day
    # blocks, and a market-neutral version (each side's SPY beta taken out) so a pass cannot be market drift alone.
    wk = lambda d: "%d-W%02d" % dt.date.fromisoformat(d).isocalendar()[:2]
    def beta(xs, ms):
        mx, mm = sum(xs) / len(xs), sum(ms) / len(ms); v = sum((m - mm) ** 2 for m in ms)
        return sum((x - mx) * (m - mm) for x, m in zip(xs, ms)) / v if v else 0.0
    spy_ = [r["spy"] for r in sel]; ef = [r["equal_f_vm"] for r in sel]; bj, be = beta(j, spy_), beta(ef, spy_)
    out["effective_sample"] = {"days": len(sel), "weekly_decisions": len({wk(r["date"]) for r in sel}),
                               "bootstrap_mean_block_days": 5,
                               "note": "the book changes once a week, so the evidence is closer to the number of weekly decisions than to the number of days"}
    out["sensitivity"] = {"p_beats_foundation_equal_vm_10day_blocks": p_beats(j, ef, restart=0.1),
                          "beta_to_spy_book": round(bj, 3), "beta_to_spy_benchmark": round(be, 3),
                          "p_beats_after_removing_spy_beta": p_beats([x - bj * m for x, m in zip(j, spy_)], [x - be * m for x, m in zip(ef, spy_)])}
    byr = {}
    for r in sel: byr.setdefault(str(r.get("regime")), []).append(r)
    out["by_regime"] = {k: {"days": len(v), "book_mean": round(sum(x[JUDGE] for x in v) / len(v), 4),
                            "foundation_equal_mean": round(sum(x["equal_f"] for x in v) / len(v), 4)} for k, v in byr.items()}
    out["seal_rows_with_errors"] = list(JUDGE_SEAL_ERRORS)   # rows skipped because checking them raised (never silent)
    out["note"] = "candidate = AI-judgment allocator; robust_2x is not computed for it (robust here = pass and ahead of every rival on Sharpe)"
    if out.get("pass"): out["robust"] = bool(out.get("beats_best_shadow"))
    return out


def netting(repo, rows, W):
    """Exploratory: cost saved per day if opposite trades in the same stock across daily library sleeves were
    netted before trading. Uses data/ledger/Library.jsonl (daily strategies only) and the day's sleeve weights."""
    wd = {x["date"]: x["weights"] for x in W}; ev = {}
    for t in ledger.load(repo, "Library"):
        if str(t.get("strategy", "")).startswith(("L1 ", "L2 ", "L3 ", "L4 ", "L14 ")): continue
        K = {"L5": 4, "L6": 10, "L7": 10, "L8": 8, "L9": 3, "L10": 5, "L11": 1, "L12": 1, "L13": 6, "L15": 16, "L16": 1}.get(str(t["strategy"]).split()[0], 5)
        legs = []
        if "/" in str(t["symbol"]):
            a, b = t["symbol"].split("/"); lg = str(t.get("side", "")).replace("long ", "")
            legs = [(lg, 0.5 / K), (b if lg == a else a, -0.5 / K)]
        else: legs = [(t["symbol"], (1 if t.get("side", "long") == "long" else -1) / K)]
        c = t.get("cost_side") or 0.05
        for sym, e in legs:
            ev.setdefault(t["entry_date"], []).append((t["strategy"], sym, e, c))
            if t.get("status") == "closed": ev.setdefault(t["exit_date"], []).append((t["strategy"], sym, -e, c))
    out = {}
    for r in rows:
        d = r["date"]; w = wd.get(d, {}); by = {}
        for strat, sym, e, c in ev.get(d, []):
            x = w.get(strat, 0.0) * e
            if x: g = by.setdefault(sym, [0.0, 0.0, c]); g[0] += abs(x); g[1] += x
        out[d] = sum((g[0] - abs(g[1])) * g[2] for g in by.values())
    return out


def run(repo, day=None):
    day = day or dt.datetime.now(NY).date().isoformat()
    S = sleeves(repo); spy = dclose(repo, "SPY", total_return=True); vix = dclose(repo, "VIX")
    sim = simulate(repo, day, S, spy, vix)
    if not sim: return {"error": "no data"}
    rows, W = sim
    os.makedirs(os.path.join(repo, "data", "allocator"), exist_ok=True)
    for fn, data in (("weights.jsonl", W), ("portfolio.jsonl", rows)):
        with open(os.path.join(repo, "data", "allocator", fn), "w") as f:
            for r in data: f.write(json.dumps(r, separators=(",", ":")) + "\n")
    rep = {"date": day, "sleeves": len(S), "freeze": freeze_check(repo, day), "phases": phase_report(rows)}
    if os.path.exists(os.path.join(repo, "data", "library", "daily_2x.json")):
        s2 = simulate(repo, day, sleeves(repo, "daily_2x.json"), spy, vix)
        if s2: rep["stress_2x"] = {ph: {"ai": v["ai"], "p_ai_beats": v["p_ai_beats"]} for ph, v in phase_report(s2[0]).items() if ph in ("verdict", "all", "v2")}
    rep["verdict_check"] = {ph: verdict_check(rep["phases"].get(ph), (rep.get("stress_2x") or {}).get(ph))
                            for ph in ("verdict", "holdout") if ph in rep["phases"]}
    if any(r.get(JUDGE) is not None for r in rows):
        # A1, Quantavius's own book, is THE VERDICT since 2026-11-23 (runbook item 34); "second_half" = from 2027-02-01
        rep["judge_check"] = {ph: judge_check(rows, ph) for ph in ("verdict", "second_half", "all")}
        rep["judge_latest"] = {"weights": W[-1].get("judge"), "weeks_without_seal": W[-1].get("judge_weeks_without_seal"), "seals": len(judge_seals(repo))}
    lib_ideal = "daily_ideal.json" if os.path.exists(os.path.join(repo, "data", "library", "daily_ideal.json")) else "daily.json"
    si = simulate(repo, day, sleeves(repo, lib_ideal, realistic=False), spy, vix)
    if si: rep["ideal_fills"] = {ph: {"ai": v["ai"], "base_a": v["base_a"]} for ph, v in phase_report(si[0]).items() if ph in ("verdict", "all", "v2")}
    try:
        sv = netting(repo, rows, W)
        rep["netted_exploratory"] = {"saving_pct_total": round(sum(sv.values()), 4),
                                     "ai_netted": perf([r["ai"] + sv.get(r["date"], 0.0) for r in rows])}
    except Exception as e: rep["netted_exploratory"] = {"error": str(e)[:120]}
    try:
        import checks; rep["stamp"] = checks.stamp(repo)
    except Exception as e: rep["stamp"] = {"error": str(e)[:120]}
    rep["latest_weights"] = W[-1] if W else {}
    json.dump(rep, open(os.path.join(repo, "data", "allocator", "report.json"), "w"), indent=1)
    cum = {"ai": 1.0, "spy": 1.0, "equal": 1.0, "base_a": 1.0}; sheet = []
    for r in rows:
        for k in cum: cum[k] *= 1 + r[k] / 100
        top = sorted(next(x for x in W if x["date"] == r["date"])["weights"].items(), key=lambda kv: -kv[1])[:4]
        sheet.append([r["date"], r["phase"], r["regime"], r["ai"], r["spy"], r["equal"], r["base_a"],
                      round((cum["ai"] - 1) * 100, 3), round((cum["spy"] - 1) * 100, 3), round((cum["equal"] - 1) * 100, 3),
                      round((cum["base_a"] - 1) * 100, 3), r["invested"], "; ".join("%s %.0f%%" % (k, v * 100) for k, v in top)])
    rep["sheet_rows"] = sheet
    return rep


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
