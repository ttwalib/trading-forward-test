"""Break-even cost per sleeve (report only; added 2026-11-23, runbook item 31; idea from Vibe-Trading's cost-sensitivity
study, re-expressed here, no code copied).

  python3 costgrid.py REPO [> data/nightly/costgrid.json]      (nightly step "costgrid")

For every sleeve whose costs can be measured, this reports the average result at 0.5x, 1x, 2x and 3x today's cost
assumptions and the BREAK-EVEN MULTIPLE: how many times today's costs the sleeve could pay before its average result
turns negative (below 1 = it already loses at today's costs; "never" = it makes money before costs are charged at all
only if the gross average is positive).

How cost is measured (no new simulation, so nothing here can change a result):
  - library sleeves: the nightly runs at 1x (data/library/daily.json) and 2x (daily_2x.json) cost; the daily cost is
    the difference. Library positions do not depend on costs, so the result is linear in the cost multiple and the
    break-even is exact for these sleeves, not an interpolation. Reported separately for the backtest priors (before
    2026-11-16) and the live days.
  - ledger sleeves with a gross column: baseline A (r_gross vs r_net, in R), crypto tracks (gross_pct vs pct, converted
    to R with the trade's own r/pct ratio), D1 lottery calls, D2/D3 spreads and W1-W4 (gross vs net %).
  - sleeves without a gross column (O calls, variants, adaptive ORB, agent picks) are listed as "not measurable".
It also reports, where trade sizes are known, the median absolute GROSS move per trade divided by the median cost per
trade (the input of the owner's cost rule of 2026-11-22: a sleeve whose ratio is under 2 is dropped). That ratio uses
sizes only, never the sign of a result.
Small samples: live figures cover a few days. Testing only, not financial advice.
"""
import json, os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger

START = "2026-11-16"
MULTS = (0.5, 1.0, 2.0, 3.0)


def summary(net, cost, gross_abs=None, unit=""):
    n = len(net)
    if n == 0: return {"n": 0}
    m, c = st.fmean(net), st.fmean(cost)
    out = {"n": n, "unit": unit, "mean_net_1x": round(m, 5), "mean_cost_1x": round(c, 5),
           "mean_at": {str(k): round(m - (k - 1) * c, 5) for k in MULTS}}
    if c > 0:
        k = 1 + m / c
        out["breakeven_mult"] = round(k, 2) if k > 0 else 0.0
        out["reading"] = ("loses even at zero cost" if k <= 0 else "loses at today's costs" if k < 1
                          else "survives double costs" if k >= 2 else "profitable at today's costs, not at double")
    else:
        out["breakeven_mult"] = None; out["reading"] = "no measurable cost"
    if gross_abs:
        mc = st.median([x for x in cost if x > 0]) if any(x > 0 for x in cost) else 0
        out["move_to_cost"] = round(st.median(gross_abs) / mc, 2) if mc else None
    return out


def library(repo):
    p1, p2 = (os.path.join(repo, "data", "library", f) for f in ("daily.json", "daily_2x.json"))
    if not (os.path.exists(p1) and os.path.exists(p2)): return {}
    d1, d2 = json.load(open(p1)), json.load(open(p2)); out = {}
    for name, s1 in d1.items():
        s2 = d2.get(name, {}); res = {}
        for label, keep in (("priors", lambda d: d < START), ("live", lambda d: d >= START)):
            days = [d for d in sorted(s1) if keep(d) and d in s2 and (s1[d] != 0 or s2[d] != 0)]
            res[label] = summary([s1[d] for d in days], [max(s1[d] - s2[d], 0.0) for d in days], unit="% of sleeve per active day")
        out[name] = res
    return out


def ledger_sleeves(repo):
    N = ledger.num; out = {}
    def add(name, net, cost, gabs, unit):
        out.setdefault(name, {"net": [], "cost": [], "gabs": [], "unit": unit})
        if net is None or cost is None: return
        out[name]["net"].append(net); out[name]["cost"].append(max(cost, 0.0))
        if gabs is not None: out[name]["gabs"].append(abs(gabs))
    for r in ledger.load(repo, "Trades"):
        if r.get("outcome") and r["outcome"] != "open":
            g, n = N(r.get("r_gross")), N(r.get("r_net"))
            if g is not None and n is not None: add("A baseline (watchlist)", n, g - n, g, "R per trade")
    for r in ledger.load(repo, "CryptoTracks"):
        if r.get("status") != "closed" or ledger.void_data(r): continue
        g, p, R = N(r.get("gross_pct")), N(r.get("pct")), N(r.get("r"))
        if None in (g, p, R) or p == 0: continue
        k = R / p                                    # R per percentage point for this trade
        add("Crypto %s (pooled)" % " ".join(str(r.get("track")).split()[:2]), R, (g - p) * k, g * k, "R per trade")
    for tab, name, gk, nk in (("DeepD1", "D1 lottery calls", "gross_return_pct", "return_pct"),):
        for r in ledger.load(repo, tab):
            if r.get("status") == "closed":
                g, n = N(r.get(gk)), N(r.get(nk))
                if g is not None and n is not None: add(name, n, g - n, g, "% of premium per trade")
    for r in ledger.load(repo, "DeepSpreads"):
        if r.get("status") == "closed":
            g, n = N(r.get("gross_pct")), N(r.get("pct"))
            nm = "D2 SPY put spreads" if r.get("side") == "put" else "D3 SPY call spreads"
            if g is not None and n is not None: add(nm, n, g - n, g, "% of max risk per trade")
    for r in ledger.load(repo, "Weekly"):
        if r.get("status") == "closed":
            g, n = N(r.get("gross_pct")), N(r.get("pct"))
            if g is not None and n is not None: add(str(r.get("strategy")), n, g - n, g, "% of max risk per trade")
    return {k: summary(v["net"], v["cost"], v["gabs"], v["unit"]) for k, v in out.items()}


def main():
    repo = sys.argv[1]
    led = ledger_sleeves(repo)
    names = {t["strategy"] for t in ledger.trades(repo) if t["asset"] not in ("library", "ml")}
    covered = set(led) | {"Crypto 15m fixed (pooled)", "Crypto 15m adaptive (pooled)", "Crypto 1h fixed (pooled)", "Crypto 1h adaptive (pooled)"}
    raw_crypto = {n for n in names if n.split()[0] in ("15m", "1h")}
    out = {"note": "Report only; never part of the verdict. Break-even multiple = times today's costs a sleeve could pay "
                   "before its average result turns negative. Live samples are small.",
           "library": library(repo), "ledger": led,
           "not_measurable": sorted(n for n in names - covered - raw_crypto)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
