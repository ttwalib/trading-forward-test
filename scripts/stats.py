"""Bias-aware strategy statistics from the repo ledger (run nightly by the orchestrator).

  python3 stats.py REPO DAY > out.json        (also writes REPO/reports/stats/DAY.json)
  python3 stats.py series REPO STRATEGY > daily.csv   daily return series + SPY/BTC returns (for the residual-edge
                                                       analyzer vendored in vendor/tradermonty/residual_edge)

Per strategy and phase (all / v2 = from 2026-11-20, the first full day of the extended setup / verdict = from
2026-12-07, the pre-registered window / train / holdout), on closed trades, result = return per unit risked:
- n, mean, 90% bootstrap interval of the mean (10,000 resamples, seed 20261119), p_gt0 = bootstrap share of means > 0.
- q_bh: Benjamini-Hochberg adjusted one-sided p-value across all strategies with n >= 5 in that phase (controls the
  false discovery rate of "this strategy is profitable" claims; ~60 strategies are tested at once).
- psr: probabilistic Sharpe ratio (P(true per-trade Sharpe > 0), skew/kurtosis adjusted, Bailey & Lopez de Prado).
- dsr: deflated Sharpe ratio: PSR against the Sharpe the best of N trials would reach by luck (N = the larger of the
  strategies tested and the unique trials in data/trials.jsonl, which logs every ML config, lab idea and variant tried).
- alpha / alpha_t / beta: per-trade OLS of result on the benchmark return over the same holding window (SPY for stock
  and SPY-option strategies, BTC for crypto, Newey-West t with 1 lag). alpha is the edge left after market exposure.
- kelly_share: 1/4 Kelly (mean / variance) capped at 10%, only for strategies with n >= 20, q_bh <= 0.10 and dsr >= 0.9
  and no active breaker; otherwise 0. Shares are scaled so they sum to at most 100%.
- breaker: drawdown circuit breaker (idea from tradermonty drawdown-circuit-breaker): "on" if the last 10 trades lost
  more than 4 units in total, the losing streak is >= 6, or the drawdown from the cumulative peak exceeds 8 units.
- verdict: promising (whole 90% interval > 0, q_bh <= 0.10, dsr >= 0.9) / losing (whole interval < 0) / benched
  (n >= 20 and p_gt0 < 0.2) / unproven.
  Changed 2026-11-20: promising and losing need n >= MIN_N_VERDICT (20) closed trades, and q_bh / psr / dsr need
  n >= MIN_N_SHARPE (10). With a handful of near-identical stop-outs (-1.02 R each) the bootstrap interval collapses
  to a point and the Sharpe is a huge number, so labels on n < 20 were artefacts. Below 20 the verdict is
  "unproven (n<20)"; the numbers are still shown.
"""
import json, os, sys, math, random, datetime as dt
from statistics import NormalDist
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, tcal
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York"); N01 = NormalDist()
SEED, B = 20261119, 10000
MIN_N_VERDICT, MIN_N_SHARPE = 20, 10


def boot(xs, rng):
    n = len(xs); means = []
    for _ in range(B):
        means.append(sum(xs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.05 * B)], means[int(0.95 * B) - 1], sum(1 for m in means if m > 0) / B


def moments(xs):
    n = len(xs); m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    s = math.sqrt(v) if v > 0 else 0.0
    if s == 0: return m, 0.0, 0.0, 3.0
    sk = sum(((x - m) / s) ** 3 for x in xs) / n; ku = sum(((x - m) / s) ** 4 for x in xs) / n
    return m, s, sk, ku


def psr(xs, sr0=0.0):
    n = len(xs)
    if n < 3: return None
    m, s, sk, ku = moments(xs)
    if s == 0: return 1.0 if m > 0 else 0.0
    sr = m / s; den = 1 - sk * sr + (ku - 1) / 4 * sr * sr
    if den <= 0: den = 1e-6
    return N01.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(den))


def expected_max_sr(srs, n_trials=0):
    """Sharpe the best of N independent trials reaches by luck (False Strategy Theorem). N = the larger of the
    strategies with results and the trial ledger (every config, variant and lab idea ever evaluated, kept or not)."""
    N = max(len(srs), int(n_trials or 0))
    if len(srs) < 2 or N < 2: return 0.0
    k = len(srs); mu = sum(srs) / k; var = sum((x - mu) ** 2 for x in srs) / (k - 1)
    g = 0.5772156649
    return math.sqrt(var) * ((1 - g) * N01.inv_cdf(1 - 1 / N) + g * N01.inv_cdf(1 - 1 / (N * math.e)))


def bh(pvals):
    items = sorted((p, k) for k, p in pvals.items()); m = len(items); q = {}; prev = 1.0
    for i in range(m - 1, -1, -1):
        p, k = items[i]; prev = min(prev, p * m / (i + 1)); q[k] = prev
    return q


def ols_nw(y, x):
    n = len(y)
    if n < 8: return None
    mx, my = sum(x) / n, sum(y) / n; sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0: return None
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx; a0 = my - b * mx
    e = [c - a0 - b * a for a, c in zip(x, y)]
    # Newey-West variance of the intercept (lag 1) for the regression on a constant + x
    X = [(1.0, a) for a in x]
    def S(lag):
        s = [[0.0, 0.0], [0.0, 0.0]]
        for t in range(lag, n):
            u = e[t] * e[t - lag]
            for i in range(2):
                for j in range(2): s[i][j] += X[t][i] * X[t - lag][j] * u
        return s
    S0, S1 = S(0), S(1); w = 0.5
    Sm = [[S0[i][j] + w * (S1[i][j] + S1[j][i]) for j in range(2)] for i in range(2)]
    XX = [[n, sum(x)], [sum(x), sum(a * a for a in x)]]; det = XX[0][0] * XX[1][1] - XX[0][1] ** 2
    if det == 0: return None
    inv = [[XX[1][1] / det, -XX[0][1] / det], [-XX[1][0] / det, XX[0][0] / det]]
    M = [[sum(inv[i][k] * Sm[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    V = [[sum(M[i][k] * inv[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    se = math.sqrt(V[0][0]) if V[0][0] > 0 else None
    return a0, (a0 / se if se else None), b


class Bench:
    def __init__(self, repo):
        self.repo = repo; self.cache = {}

    def series(self, sym, tf):
        if (sym, tf) not in self.cache:
            f = os.path.join(self.repo, "data", "bars", tf, sym + ".jsonl"); d = {}
            if os.path.exists(f):
                for line in open(f):
                    if line.strip():
                        b = json.loads(line); d[int(b["t"])] = float(b["c"])
            self.cache[(sym, tf)] = (sorted(d), d)
        return self.cache[(sym, tf)]

    def at(self, sym, tf, ts):
        keys, d = self.series(sym, tf)
        if not keys: return None
        import bisect
        i = bisect.bisect_right(keys, ts) - 1
        return d[keys[i]] if i >= 0 and ts - keys[i] < (4 * 3600 if tf == "1h" else 3600) else None

    def ret(self, t):
        """Benchmark return over the trade's holding window, or None."""
        def ts(day, hm):
            if not hm: return None
            s = str(hm)
            try:
                d = dt.datetime.fromisoformat(s if len(s) > 5 else "%s %s" % (day, s)).replace(tzinfo=NY)
                return int(d.timestamp())
            except ValueError: return None
        a, b = ts(t["day"], t.get("entry")), ts(t["day"], t.get("exit"))
        if a is None or b is None or b <= a: return None
        sym, tf = ("BTC", "1h") if t["asset"] == "crypto" else ("SPY", "5m")
        pa, pb = self.at(sym, tf, a - (300 if tf == "5m" else 0)), self.at(sym, tf, b - (300 if tf == "5m" else 3600))
        return (pb / pa - 1) * 100 if pa and pb else None


def breaker(xs):
    if not xs: return "off"
    streak = 0
    for x in reversed(xs):
        if x <= 0: streak += 1
        else: break
    cum, peak, dd = 0.0, 0.0, 0.0
    for x in xs:
        cum += x; peak = max(peak, cum); dd = max(dd, peak - cum)
    on = sum(xs[-10:]) < -4 or streak >= 6 or dd > 8
    return "on" if on else "off"


def compute(repo, day):
    T = [t for t in ledger.trades(repo) if t["day"] <= day]
    bench = Bench(repo); rng = random.Random(SEED)
    out = {"date": day, "phases": {}}
    def inph(day, ph):
        if ph == "all": return True
        if ph == "v2": return day >= tcal.V2_START.isoformat()
        if ph == "verdict": return day >= tcal.ALLOC_FREEZE.isoformat()
        return tcal.phase(day) == ph
    try:
        import checks; NT = checks.n_trials(repo); out["trials"] = checks.trials(repo); out["stamp"] = checks.stamp(repo)
    except Exception: NT = 0
    for ph in ("all", "v2", "verdict", "train", "holdout"):
        groups = {}
        for t in T:
            if not inph(t["day"], ph): continue
            groups.setdefault((t["strategy"], t["unit"]), []).append(t)
        rows = {}
        for (s, unit), ts in groups.items():
            ts.sort(key=lambda t: (t["day"], str(t.get("entry") or "")))
            xs = [t["result"] for t in ts]; n = len(xs)
            r = {"strategy": s, "unit": unit, "n": n, "mean": round(sum(xs) / n, 4)}
            if n >= 2:
                lo, hi, p = boot(xs, rng); r.update(ci_lo=round(lo, 4), ci_hi=round(hi, 4), p_gt0=round(p, 4))
            m, sd, _, _ = moments(xs) if n > 1 else (xs[0], 0, 0, 3)
            r["sr"] = round(m / sd, 4) if sd else None
            r["psr"] = round(psr(xs), 4) if n >= MIN_N_SHARPE else None
            pairs = [(t["result"], bench.ret(t)) for t in ts]; pairs = [(a, b) for a, b in pairs if b is not None]
            reg = ols_nw([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) >= 8 else None
            if reg: r.update(alpha=round(reg[0], 4), alpha_t=round(reg[1], 2) if reg[1] is not None else None, beta=round(reg[2], 4))
            r["breaker"] = breaker(xs)
            r["var"] = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else None
            rows[s] = r
        elig = {s: 1 - r["p_gt0"] for s, r in rows.items() if r["n"] >= MIN_N_SHARPE and "p_gt0" in r}
        q = bh(elig) if elig else {}
        srs = [r["sr"] for r in rows.values() if r.get("sr") is not None and r["n"] >= MIN_N_SHARPE]
        sr0 = expected_max_sr(srs, NT)
        for s, r in rows.items():
            r["q_bh"] = round(q[s], 4) if s in q else None
            ts = sorted([t for t in T if t["strategy"] == s and inph(t["day"], ph)],
                        key=lambda t: (t["day"], str(t.get("entry") or "")))
            r["dsr"] = round(psr([t["result"] for t in ts], sr0), 4) if r["n"] >= MIN_N_SHARPE else None
            ok = (r["n"] >= 20 and r["q_bh"] is not None and r["q_bh"] <= 0.10 and (r["dsr"] or 0) >= 0.9
                  and r["breaker"] == "off" and r["mean"] > 0 and r.get("var"))
            r["kelly_raw"] = min(0.10, 0.25 * r["mean"] / r["var"]) if ok else 0.0
            big = r["n"] >= MIN_N_VERDICT
            if big and r.get("ci_lo") is not None and r["ci_lo"] > 0 and (r["q_bh"] or 1) <= 0.10 and (r["dsr"] or 0) >= 0.9: v = "promising"
            elif big and r.get("ci_hi") is not None and r["ci_hi"] < 0: v = "losing"
            elif big and r.get("p_gt0", 1) < 0.2: v = "benched"
            else: v = "unproven" if big else "unproven (n<20)"
            r["verdict"] = v
        tot = sum(r["kelly_raw"] for r in rows.values())
        for r in rows.values():
            r["kelly_share"] = round(r["kelly_raw"] / max(1.0, tot), 4); r.pop("kelly_raw"); r.pop("var", None)
        out["phases"][ph] = {"strategies_tested": len(rows), "luck_sharpe": round(sr0, 4),
                             "rows": sorted(rows.values(), key=lambda r: (-(r.get("p_gt0") or 0), r["strategy"]))}
    os.makedirs(os.path.join(repo, "reports", "stats"), exist_ok=True)
    json.dump(out, open(os.path.join(repo, "reports", "stats", day + ".json"), "w"), indent=1)
    sheet = []
    for ph, P in out["phases"].items():
        for r in P["rows"]:
            sheet.append([day, r["strategy"], r["unit"], ph, r["n"], r["mean"], r.get("ci_lo"), r.get("ci_hi"), r.get("p_gt0"),
                          r.get("q_bh"), r.get("psr"), r.get("dsr"), r.get("alpha"), r.get("alpha_t"), r.get("beta"),
                          r.get("kelly_share"), r["breaker"], r["verdict"]])
    out["sheet_rows"] = sheet
    return out


def series(repo, strategy):
    T = [t for t in ledger.trades(repo) if t["strategy"] == strategy]; days = {}
    for t in T: days[t["day"]] = days.get(t["day"], 0.0) + t["result"] / 100  # 1 unit risked = 1% of equity
    b = Bench(repo); lines = ["date,strategy_return,spy_return,btc_return"]
    def dret(sym):
        keys, d = b.series(sym, "1d"); out = {}
        for i in range(1, len(keys)):
            day = dt.datetime.fromtimestamp(keys[i], NY).date().isoformat(); out[day] = d[keys[i]] / d[keys[i - 1]] - 1
        return out
    spy, btc = dret("SPY"), dret("BTC")
    for day in sorted(set(spy) & set(btc)):
        if day < min(days, default="9999"): continue
        lines.append("%s,%.6f,%.6f,%.6f" % (day, days.get(day, 0.0), spy[day], btc[day]))
    return "\n".join(lines)


if __name__ == "__main__":
    if sys.argv[1] == "series": print(series(sys.argv[2], sys.argv[3]))
    else:
        o = compute(sys.argv[1], sys.argv[2]); print(json.dumps(o, indent=1))
