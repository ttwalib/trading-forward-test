"""Risk breakdown of the AI book and its rivals (report only; added 2026-11-23, runbook item 31; ideas from Vibe-Trading's
"Risk X-Ray", re-expressed here, no code copied).

  python3 riskx.py REPO [> data/nightly/riskx.json]      (nightly step "riskx")

1. RISK CONTRIBUTION of each sleeve in the AI formula's latest weights: w_i x Cov(r_i, r_book) / sd(r_book), over the
   last 60 trading days of the sleeves' daily series (the allocator's own covariance window; library sleeves include
   their backtest days, as the allocator sees them). Shares add up to 100%: a sleeve with 25% of the money can carry
   much more or much less than 25% of the swings.
2. DEEPEST DRAWDOWNS (peak, trough, recovery, length in trading days; still-open ones marked) of every book, on two
   bases kept apart: the live days since 2026-11-16 (data/allocator/portfolio.jsonl) and the pre-test replay
   (reports/replay/2026-11-21-mc_series.json, 2025-06-02 to 2026-11-19, the Monte Carlo basis).
3. ONE-DAY VALUE AT RISK and EXPECTED SHORTFALL at 95% (historical: the 5th-percentile day and the average of the days
   beyond it), per book and basis. With fewer than 20 days the figures are marked "too few days".
Nothing here feeds the allocator, the judge or the verdict. Testing only, not financial advice.
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

BOOKS = ("ai", "equal", "spy", "base_a", "sh_rp", "sh_mv", "sh_win", "sh_judge")
REPLAY = os.path.join("reports", "replay", "2026-11-21-mc_series.json")


def jl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def drawdowns(days, rets, top=5):
    """rets in % per day -> deepest drawdown periods on the compounded curve."""
    eq, peak, peak_d, out, cur = 1.0, 1.0, None, [], None
    for d, r in zip(days, rets):
        eq *= 1 + r / 100
        if eq >= peak * (1 - 1e-12):
            if cur: cur["recovered"] = d; cur["length"] = cur["_n"]; out.append(cur); cur = None
            peak, peak_d = eq, d
        else:
            dd = 1 - eq / peak
            if not cur: cur = {"peak": peak_d or days[0], "trough": d, "depth_pct": 0.0, "_n": 0}
            cur["_n"] += 1
            if dd * 100 > cur["depth_pct"]: cur["depth_pct"] = round(dd * 100, 3); cur["trough"] = d
    if cur: cur["recovered"] = None; cur["length"] = cur["_n"]; cur["open"] = True; out.append(cur)
    for x in out: x.pop("_n", None)
    return sorted(out, key=lambda x: -x["depth_pct"])[:top]


def var_es(rets):
    if len(rets) < 20: return {"n": len(rets), "note": "too few days"}
    x = np.sort(np.array(rets)); k = max(1, int(math.floor(0.05 * len(x))))
    return {"n": len(x), "var95_pct": round(float(-np.percentile(x, 5)), 3), "es95_pct": round(float(-x[:k].mean()), 3)}


def basis(rows):
    out = {}
    days = [r["date"] for r in rows]
    for b in BOOKS:
        pts = [(r["date"], r[b]) for r in rows if r.get(b) is not None]
        if not pts: continue
        d, x = zip(*pts)
        out[b] = {"days": len(x), "total_pct": round((np.prod([1 + v / 100 for v in x]) - 1) * 100, 3),
                  "drawdowns": drawdowns(list(d), list(x)), "tail": var_es(list(x))}
    return {"from": days[0] if days else None, "to": days[-1] if days else None, "books": out}


def contributions(repo):
    import allocator as A
    W = jl(os.path.join(repo, "data", "allocator", "weights.jsonl"))
    if not W: return {"note": "no weights yet"}
    last = W[-1]; w = last["weights"]; S = A.sleeves(repo)
    days = sorted({d for k in w for d in S.get(k, {}) if d < last["date"]})[-A.COV_WIN:]
    names = [k for k in w if k in S]
    if len(days) < 10 or not names: return {"date": last["date"], "note": "too few days"}
    X = np.array([[S[k].get(d, 0.0) for k in names] for d in days])
    wv = np.array([w[k] for k in names]); port = X @ wv
    sd = float(port.std(ddof=1))
    if sd <= 0: return {"date": last["date"], "note": "no variation"}
    cov = np.array([np.cov(X[:, i], port, ddof=1)[0, 1] for i in range(len(names))])
    rc = wv * cov / sd
    share = rc / rc.sum() if rc.sum() else rc
    rows = sorted(({"sleeve": n, "weight": round(float(wv[i]), 4), "risk_share": round(float(share[i]), 4),
                    "risk_vs_money": round(float(share[i] / wv[i]), 2) if wv[i] else None} for i, n in enumerate(names)),
                  key=lambda r: -r["risk_share"])
    return {"date": last["date"], "window_days": len(days), "book_daily_sd_pct": round(sd, 4), "sleeves": rows,
            "note": "risk_vs_money above 1 = the sleeve carries more of the book's swings than its share of the money"}


def main():
    repo = sys.argv[1]
    live = jl(os.path.join(repo, "data", "allocator", "portfolio.jsonl"))
    rp = os.path.join(repo, REPLAY); replay = json.load(open(rp))["rows"] if os.path.exists(rp) else []
    out = {"note": "Report only; never part of the verdict. Live and replay bases are kept apart.",
           "contributions": contributions(repo), "live": basis(live), "replay": basis(replay)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
