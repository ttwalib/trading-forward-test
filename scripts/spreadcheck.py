"""AP3 spread allowance check (report only; added 2026-11-25, item 65; the open point of review item 59).

  python3 spreadcheck.py REPO            -> JSON to stdout (the nightly writes data/nightly/spreadcheck.json)

picks.py prices an option pick from its own trades plus PUT_SLIP = 2% of the premium on each side, as an allowance for
the bid/ask spread of a market order. This script measures the real half-spread in the stored option chains
(data/optarch/snap/ each night, data/optarch/snap_mid/ at midday): for contracts like the ones AP3 may buy (absolute
delta 0.35 to 0.65, both bid and ask quoted, ask above bid), half-spread = (ask - bid) / 2 / mid, in percent. It reports
the median and the 75th and 90th percentiles by underlying and overall, and the share of contracts whose half-spread is
above the allowance. Caveat: the free plan's chain feed is "indicative" (a delayed, derived quote, not the full NBBO),
so spreads may read wider than a live market. Nothing here changes a score; a finding goes to the owner as a decision.
"""
import gzip, json, os, sys, glob, statistics as st

ALLOW = 2.0          # picks.PUT_SLIP, percent of the premium per side
DMIN, DMAX = 0.35, 0.65


def q(xs, p):
    xs = sorted(xs)
    if not xs: return None
    k = (len(xs) - 1) * p; f = int(k); c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 3)


def half_spreads(path):
    d = json.load(gzip.open(path)); out = []
    for occ, v in d.get("c", {}).items():
        bid, ask, _, _, delta = v[:5]
        if bid is None or ask is None or delta is None or bid <= 0 or ask <= bid: continue
        if not (DMIN <= abs(delta) <= DMAX): continue
        mid = (bid + ask) / 2
        out.append((ask - bid) / 2 / mid * 100)
    return d.get("und"), d.get("day"), out


def run(repo):
    res = {"allowance_pct_per_side": ALLOW, "delta_band": [DMIN, DMAX], "feed": "indicative (free plan)", "sets": {}}
    for sub in ("snap", "snap_mid"):
        files = sorted(glob.glob(os.path.join(repo, "data", "optarch", sub, "*", "*.json.gz")))
        if not files: continue
        days = sorted({os.path.basename(f)[:10] for f in files})[-10:]          # the last ten stored days
        by, allv = {}, []
        for f in files:
            if os.path.basename(f)[:10] not in days: continue
            und, _, hs = half_spreads(f)
            by.setdefault(und, []).extend(hs); allv.extend(hs)
        res["sets"][sub] = {
            "days": days, "contracts": len(allv),
            "median": q(allv, .5), "p75": q(allv, .75), "p90": q(allv, .9),
            "share_above_allowance": round(sum(1 for x in allv if x > ALLOW) / len(allv), 3) if allv else None,
            "by_underlying": {u: {"n": len(v), "median": q(v, .5), "p90": q(v, .9)} for u, v in sorted(by.items()) if v}}
    s = res["sets"].get("snap") or {}
    if s.get("median") is not None:
        res["reading"] = ("allowance looks conservative" if s["median"] <= ALLOW and (s.get("share_above_allowance") or 0) < .25
                          else "allowance looks too small for many contracts: owner decision (raise PUT_SLIP or price at bid/ask from the chains)")
    return res


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "."), indent=1))
