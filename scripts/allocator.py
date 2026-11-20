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
- Volatility target: the portfolio's forecast volatility sqrt(w' Sigma w x 252) is scaled to 10% a year (scale at
  most 1.5x), then the 25% cap again; total capped at 100% (rest in cash, earning nothing).
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
(added 2026-11-19, stricter) SPY scaled to the AI portfolio's realised volatility over the same phase ("spy_vm"):
a mostly-cash portfolio cannot win on drawdown for free against it.
Benchmarks use total-return SPY (dividends added via corp.py), the same footing as the strategies.
Stress: the same rule run on the library at double costs (daily_2x.json) is reported beside the main result.
Netting (exploratory, never part of the verdict): what the AI portfolio would save if opposite trades in the same
stock from different daily library sleeves were netted before trading ("netted_exploratory").
Verdict metrics per phase (verdict = 2026-12-07..2027-02-12, the pre-registered primary window / train / holdout / v2 / all): total return, annualised Sharpe (sqrt 252), max drawdown, and
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
COV_WIN, VOL_TARGET, VOL_SCALE_MAX, BAND = 60, 10.0, 1.5, 0.02
BREAKER_MODE, BRK_DD_K, BRK_10_K = "vol", 3.0, 2.5
FROZEN_FILES = ["allocator.py", "library.py", "corp.py", "fills.py"]
BASE = "A baseline (watchlist)"


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
        name = t["strategy"]
        if t["asset"] == "crypto": name = "Crypto " + " ".join(name.split()[:2]) + " (pooled)"
        S.setdefault(name, {}); S[name][t["day"]] = S[name].get(t["day"], 0.0) + (t["result"] + adj.get(i, 0.0)) / 5 * 1.0
    return S


def rebal_cost(name):
    """Cost (%) per unit of weight change. Intraday sleeves are flat overnight: new weights size the next trades."""
    if name.startswith(("L1 ", "L2 ", "L3 ", "L4 ", "A ", "Agent picks: stocks", "ML")) or "variant" in name or "ORB" in name:
        return 0.0
    if name.startswith("Crypto") or "crypto" in name.lower(): return 0.15
    if name.startswith(("O ", "D1", "D2", "D3", "W1", "W2", "W3", "W4")): return 0.5
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


def evidence(series, days):
    """Returns and weights: live days weight 1; backtest days haircut and capped to PRIOR_EQ live days in total."""
    start = tcal.START.isoformat(); prior = [d for d in days if d < start]
    wp = min(1.0, PRIOR_EQ / len(prior)) if prior else 1.0
    xs = [series.get(d, 0.0) * (PRIOR_HAIR if d < start else 1.0) for d in days]
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
    reg = regime.get(d, "unknown")
    for name, series in S.items():
        live = [x for x in hist_days if x >= min(series, default="9999")]
        raw = [series.get(x, 0.0) for x in live]
        nz = sum(1 for x in raw if x != 0)
        if nz < MIN_DAYS: continue
        xs, ws = evidence(series, live)
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
        if sum(last10) < -lim_10 or dd > lim_dd: info[name] = "breaker"; continue
        wk = "%d-W%02d" % dt.date.fromisoformat(d).isocalendar()[:2]
        h = int(hashlib.sha1(f"{SEED}|{wk}|{name}".encode()).hexdigest()[:12], 16)
        theta = random.Random(h).gauss(mu, math.sqrt(v / max(n, 1.0)))
        if theta > 0: w[name] = theta
        info[name] = round(mu, 4)
    names = sorted(w)
    if not names: return {}, info
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
    wv = np.minimum(wv, CAP)
    vol = float(np.sqrt(max(wv @ Sig @ wv, 0.0) * 252))
    if vol > 0: wv = np.minimum(wv * min(VOL_SCALE_MAX, VOL_TARGET / vol), CAP)
    tot = wv.sum()
    if tot > 1: wv = wv / tot
    info["_vol_forecast_pct"] = round(float(np.sqrt(max(wv @ Sig @ wv, 0.0) * 252)), 3)
    return {names[i]: round(float(wv[i]), 4) for i in range(len(names)) if wv[i] > 0.0005}, info


def perf(xs):
    if not xs: return {"days": 0}
    cum = 1.0; peak = 1.0; mdd = 0.0
    for x in xs:
        cum *= 1 + x / 100; peak = max(peak, cum); mdd = max(mdd, 1 - cum / peak)
    m, v = stats(xs)
    sd = math.sqrt(v) if len(xs) > 1 else 0
    return {"days": len(xs), "total_pct": round((cum - 1) * 100, 3), "sharpe": round(m / sd * math.sqrt(252), 2) if sd else None,
            "max_dd_pct": round(mdd * 100, 3), "mean_daily_pct": round(m, 4)}


def p_beats(a, b, B=5000):
    diff = [x - y for x, y in zip(a, b)]; n = len(diff)
    if n < 10: return None
    rng = random.Random(SEED); hits = 0
    for _ in range(B):
        s = 0.0; k = 0; i = rng.randrange(n)
        while k < n:
            s += diff[i]; k += 1
            i = rng.randrange(n) if rng.random() < 0.2 else (i + 1) % n
        hits += s > 0
    return round(hits / B, 3)


def freeze_check(repo, day):
    here = os.path.dirname(os.path.abspath(__file__))
    cur = {f: hashlib.sha256(open(os.path.join(here, f), "rb").read()).hexdigest() for f in FROZEN_FILES if os.path.exists(os.path.join(here, f))}
    fz = os.path.join(repo, "ops", "freeze.json")
    if day < tcal.ALLOC_FREEZE.isoformat(): return {"frozen": False, "freeze_date": tcal.ALLOC_FREEZE.isoformat()}
    if not os.path.exists(fz):
        os.makedirs(os.path.dirname(fz), exist_ok=True)
        json.dump({"recorded_on": day, "sha256": cur}, open(fz, "w"), indent=1)
    rec = json.load(open(fz))
    bad = [f for f in cur if rec["sha256"].get(f) != cur[f]]
    return {"frozen": True, "recorded_on": rec["recorded_on"], "code_matches_freeze": not bad, "changed_files": bad}


def power(n):
    """Annualised Sharpe gap the bootstrap can call at P >= 0.9 with n days (about 1.28 standard errors)."""
    return round(1.2816 * math.sqrt(252 / n), 2) if n else None


def simulate(repo, day, S, spy, vix):
    cal = sorted(d for d in set(spy) | {d for s in S.values() for d in s} if d <= day and tcal.is_open(d))
    if not cal: return None
    cal_idx = {d: i for i, d in enumerate(cal)}; regime = regime_of(spy, vix, cal)
    start = tcal.START.isoformat(); rows = []; W = []; spy_keys = sorted(spy); wprev = {}
    for d in cal:
        if d < start: continue
        tgt, info = weights_for(d, S, cal_idx, regime, cal)
        w = {}
        for k in set(tgt) | set(wprev):
            a, b = tgt.get(k, 0.0), wprev.get(k, 0.0)
            w[k] = b if (a > 0 and b > 0 and abs(a - b) < BAND) else a
        tot = sum(w.values())
        if tot > 1: w = {k: v / tot for k, v in w.items()}
        w = {k: round(v, 4) for k, v in w.items() if v > 0.0005}
        turn = {k: abs(w.get(k, 0.0) - wprev.get(k, 0.0)) for k in set(w) | set(wprev)}
        rcost = sum(v * rebal_cost(k) for k, v in turn.items()); wprev = w
        ai = sum(wt * S[k].get(d, 0.0) for k, wt in w.items()) - rcost
        live = [k for k, s in S.items() if s and min(s) <= d]
        eq = sum(S[k].get(d, 0.0) for k in live) / len(live) if live else 0.0
        prev = [k for k in spy_keys if k < d]
        sp = (spy[d] / spy[prev[-1]] - 1) * 100 if d in spy and prev else 0.0
        base = S.get(BASE, {}).get(d, 0.0)
        rows.append({"date": d, "phase": tcal.phase(d), "regime": regime.get(d), "ai": round(ai, 5), "spy": round(sp, 5),
                     "equal": round(eq, 5), "base_a": round(base, 5), "n_live": len(live), "invested": round(sum(w.values()), 4),
                     "turnover": round(sum(turn.values()), 4), "rebal_cost": round(rcost, 5)})
        W.append({"date": d, "weights": w, "breakers": sorted(k for k, v in info.items() if v == "breaker"),
                  "vol_forecast_pct": info.get("_vol_forecast_pct")})
    return rows, W


def phase_report(rows):
    out = {}
    for ph in ("verdict", "all", "v2", "train", "holdout"):
        sel = [r for r in rows if ph == "all" or (ph == "v2" and r["date"] >= tcal.V2_START.isoformat())
               or (ph == "verdict" and r["date"] >= tcal.ALLOC_FREEZE.isoformat()) or r["phase"] == ph]
        if not sel: continue
        ai = [r["ai"] for r in sel]; sp = [r["spy"] for r in sel]
        sa, ss = math.sqrt(stats(ai)[1]) if len(ai) > 1 else 0, math.sqrt(stats(sp)[1]) if len(sp) > 1 else 0
        k_vm = sa / ss if ss else 0.0
        for r in sel: r["spy_vm"] = r["spy"] * k_vm
        P = {k: perf([r[k] for r in sel]) for k in ("ai", "spy", "equal", "base_a", "spy_vm")}
        P["spy_vm_scale"] = round(k_vm, 3)
        P["p_ai_beats"] = {k: p_beats(ai, [r[k] for r in sel]) for k in ("spy", "equal", "base_a", "spy_vm")}
        P["sharpe_gap_detectable"] = power(len(sel))
        P["turnover_per_day"] = round(sum(r.get("turnover", 0) for r in sel) / len(sel), 4)
        P["rebal_cost_pct_total"] = round(sum(r.get("rebal_cost", 0) for r in sel), 4)
        out[ph] = P
    return out


def verdict_check(P, stress=None):
    """Pre-registered pass rule for one phase: beat every benchmark on Sharpe AND max drawdown with P >= 0.9;
    for drawdown, SPY also means volatility-matched SPY. Robust = also beats SPY at double costs."""
    if not P or P["ai"].get("days", 0) < 10: return {"status": "not enough days"}
    ai = P["ai"]; res = {}
    for b in ("spy", "equal", "base_a"):
        bm = P[b]; sh = ai.get("sharpe") is not None and (bm.get("sharpe") is None or ai["sharpe"] > bm["sharpe"])
        dd = ai["max_dd_pct"] < bm["max_dd_pct"] and (b != "spy" or ai["max_dd_pct"] < P["spy_vm"]["max_dd_pct"])
        pb = (P["p_ai_beats"].get(b) or 0) >= 0.9 and (b != "spy" or (P["p_ai_beats"].get("spy_vm") or 0) >= 0.9)
        res[b] = {"sharpe": sh, "drawdown": dd, "p_ge_0.9": pb, "beats": sh and dd and pb}
    ok = all(v["beats"] for v in res.values())
    rob = None
    if stress: rob = (stress["ai"].get("sharpe") or -9) > (P["spy"].get("sharpe") or 0) and (stress["p_ai_beats"].get("spy") or 0) >= 0.9
    return {"pass": ok, "robust_2x": rob if ok else None, "by_benchmark": res}


def netting(repo, rows, W):
    """Exploratory: cost saved per day if opposite trades in the same stock across daily library sleeves were
    netted before trading. Uses data/ledger/Library.jsonl (daily strategies only) and the day's sleeve weights."""
    wd = {x["date"]: x["weights"] for x in W}; ev = {}
    for t in ledger.load(repo, "Library"):
        if str(t.get("strategy", "")).startswith(("L1 ", "L2 ", "L3 ", "L4 ")): continue
        K = {"L5": 4, "L6": 10, "L7": 10, "L8": 8, "L9": 3, "L10": 5, "L11": 1, "L12": 1, "L13": 6}.get(str(t["strategy"]).split()[0], 5)
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
