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
- Thompson sampling: draw theta ~ Normal(mean, variance / n), seeded by (date, sleeve) so reruns are identical.
  This keeps trying sleeves whose evidence is thin while backing those with consistent results.
- Raw weight = quarter Kelly = 0.25 x max(theta, 0) / variance, capped at 25% per sleeve; then any pair of sleeves
  with 60-day correlation > 0.7 has the smaller weight halved; total capped at 100% (rest in cash).
- Drawdown breaker: a sleeve whose last 10 days sum below -4% or whose drawdown from its 120-day peak exceeds 8%
  gets weight 0 until it recovers.
- In the holdout the code and parameters stay frozen; weights keep updating day by day from new evidence, because
  the process itself is what is being tested.
Benchmarks: SPY buy-and-hold (close to close), equal weight of all live sleeves, baseline A sleeve alone.
Benchmarks use total-return SPY (dividends added via corp.py), the same footing as the strategies.
Stress: the same rule run on the library at double costs (daily_2x.json) is reported beside the main result.
Verdict metrics per phase (verdict = 2026-12-07..2027-02-12, the pre-registered primary window / train / holdout / v2 / all): total return, annualised Sharpe (sqrt 252), max drawdown, and
the chance that the AI portfolio's mean daily return beats each benchmark (stationary block bootstrap, block 5,
5,000 resamples, seed 20261119).
"""
import json, os, sys, math, random, hashlib, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, tcal, corp
NY = ZoneInfo("America/New_York")
WIN, MIN_DAYS, K_REG, K_ALL, CAP, KELLY, CORR, SEED = 120, 10, 20, 30, 0.25, 0.25, 0.7, 20261119
PRIOR_HAIR, PRIOR_EQ = 0.5, 20
FROZEN_FILES = ["allocator.py", "library.py", "corp.py"]
BASE = "A baseline (watchlist)"


def jl(path): return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def dclose(repo, sym, total_return=False):
    rows = sorted((dt.datetime.fromtimestamp(b["t"], NY).date().isoformat(), b["o"], b["h"], b["l"], b["c"])
                  for b in jl(os.path.join(repo, "data", "bars", "1d", sym + ".jsonl")))
    if total_return: rows = corp.tr_adjust(repo, sym, rows)
    return {r[0]: r[4] for r in rows}


def sleeves(repo, lib_file="daily.json"):
    S = {}
    f = os.path.join(repo, "data", "library", lib_file)
    if os.path.exists(f):
        for k, v in json.load(open(f)).items(): S[k] = dict(v)
    for t in ledger.trades(repo):
        if t["asset"] == "library": continue  # library sleeves come marked to market from daily.json
        name = t["strategy"]
        if t["asset"] == "crypto": name = "Crypto " + " ".join(name.split()[:2]) + " (pooled)"
        S.setdefault(name, {}); S[name][t["day"]] = S[name].get(t["day"], 0.0) + t["result"] / 5 * 1.0
    return S


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
        if sum(last10) < -4 or dd > 8: info[name] = "breaker"; continue
        h = int(hashlib.sha1(f"{SEED}|{d}|{name}".encode()).hexdigest()[:12], 16)
        theta = random.Random(h).gauss(mu, math.sqrt(v / max(n, 1.0)))
        if theta > 0: w[name] = min(CAP, KELLY * theta / v)
        info[name] = round(mu, 4)
    names = sorted(w, key=lambda k: -w[k])
    for a_i, a in enumerate(names):
        for b in names[a_i + 1:]:
            ra = [S[a].get(x, 0.0) for x in hist_days[-60:]]; rb = [S[b].get(x, 0.0) for x in hist_days[-60:]]
            if corr(ra, rb) > CORR: w[b] *= 0.5
    tot = sum(w.values())
    if tot > 1: w = {k: v / tot for k, v in w.items()}
    return {k: round(v, 4) for k, v in w.items() if v > 0.0005}, info


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
    start = tcal.START.isoformat(); rows = []; W = []; spy_keys = sorted(spy)
    for d in cal:
        if d < start: continue
        w, info = weights_for(d, S, cal_idx, regime, cal)
        ai = sum(wt * S[k].get(d, 0.0) for k, wt in w.items())
        live = [k for k, s in S.items() if s and min(s) <= d]
        eq = sum(S[k].get(d, 0.0) for k in live) / len(live) if live else 0.0
        prev = [k for k in spy_keys if k < d]
        sp = (spy[d] / spy[prev[-1]] - 1) * 100 if d in spy and prev else 0.0
        base = S.get(BASE, {}).get(d, 0.0)
        rows.append({"date": d, "phase": tcal.phase(d), "regime": regime.get(d), "ai": round(ai, 5), "spy": round(sp, 5),
                     "equal": round(eq, 5), "base_a": round(base, 5), "n_live": len(live), "invested": round(sum(w.values()), 4)})
        W.append({"date": d, "weights": w, "breakers": sorted(k for k, v in info.items() if v == "breaker")})
    return rows, W


def phase_report(rows):
    out = {}
    for ph in ("verdict", "all", "v2", "train", "holdout"):
        sel = [r for r in rows if ph == "all" or (ph == "v2" and r["date"] >= tcal.V2_START.isoformat())
               or (ph == "verdict" and r["date"] >= tcal.ALLOC_FREEZE.isoformat()) or r["phase"] == ph]
        if not sel: continue
        P = {k: perf([r[k] for r in sel]) for k in ("ai", "spy", "equal", "base_a")}
        P["p_ai_beats"] = {k: p_beats([r["ai"] for r in sel], [r[k] for r in sel]) for k in ("spy", "equal", "base_a")}
        P["sharpe_gap_detectable"] = power(len(sel))
        out[ph] = P
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
