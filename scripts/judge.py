"""AI-judgment allocator: the evidence pack and the seal (added 2026-11-21, owner decision, before the freeze).

The formula allocator (allocator.py) is fixed code. This is the other half of the question "can an AI manage a mix of
strategies?": once a week a language model reads the same evidence, argues both sides and decides next week's weights.
The decision is SEALED before the week starts and can never be changed; allocator.py then scores it like every other
rival (weekly rebalancing, same costs). Nothing is traded.

  python3 judge.py brief REPO            -> the evidence pack (JSON): rules, eligible sleeves with their record up to
                                            the last closed day, market regime, what the formula and the simple rules
                                            hold, results so far, and the judge's own earlier seals with how they did
  python3 judge.py seal REPO FILE [--dry] -> validates FILE and appends it to data/allocator/judge.jsonl
        FILE = {"weights": {sleeve: share, ...}, "bull": "...", "bear": "...", "risk": "...", "decision": "...",
                "model": "..."}

Rules the seal enforces (a seal that breaks one is refused, nothing is written):
  - only eligible sleeves (the list in the brief: at least 10 active days in the last 120, duplicates excluded);
  - every share between 0.02 and 0.25, shares add up to 1.00 (fully invested, no cash);
  - the short-premium option sleeves (W1, W2, D2, D3) together at most 0.25 (allocator.GROUP_CAP, since 2026-11-21);
  - sealed while the stock market is closed, before 09:30 New York of the first trading day it applies to
    ("effective"), and only one seal per effective day;
  - bull, bear and decision texts are present (at least 40 characters each), so the reasoning is on record.
Evidence only reaches the last closed trading day, so the weights cannot see the week they are for.
"""
import json, os, sys, math, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, allocator

NY = ZoneInfo("America/New_York")
LO, HI = 0.02, allocator.CAP
FILE = os.path.join("data", "allocator", "judge.jsonl")


def effective_day(now):
    """First full or half trading session that opens after `now`."""
    d = now.date()
    if not (tcal.is_open(d) and now.hour * 60 + now.minute < 9 * 60 + 30): d += dt.timedelta(days=1)
    while not tcal.is_open(d): d += dt.timedelta(days=1)
    return d


def market_closed(now):
    d = now.date(); hm = now.hour * 60 + now.minute
    return not tcal.is_open(d) or hm < 9 * 60 + 25 or hm >= 16 * 60 + 5


def context(repo):
    S = allocator.sleeves(repo); spy = allocator.dclose(repo, "SPY", total_return=True); vix = allocator.dclose(repo, "VIX")
    cal = sorted(d for d in set(spy) | {d for s in S.values() for d in s} if tcal.is_open(d))
    hist = cal[-allocator.WIN:]; dup = allocator.duplicates(S, hist); el = {}
    for name, series in S.items():
        if name in dup: continue
        raw = [series.get(x, 0.0) for x in hist if x >= min(series, default="9999")]
        if sum(1 for x in raw if x) >= allocator.MIN_DAYS: el[name] = raw
    return S, spy, vix, cal, hist, dup, el


def brief(repo, now=None):
    now = now or dt.datetime.now(NY); S, spy, vix, cal, hist, dup, el = context(repo)
    start = tcal.START.isoformat(); regime = allocator.regime_of(spy, vix, cal)
    J = lambda f: [json.loads(l) for l in open(os.path.join(repo, "data", "allocator", f)) if l.strip()] if os.path.exists(os.path.join(repo, "data", "allocator", f)) else []
    W, PF = J("weights.jsonl"), J("portfolio.jsonl"); lastw = W[-1] if W else {}
    sm = lambda xs: round(sum(xs), 3)
    sleeves = []
    for k in sorted(el):
        s = S[k]; live = [s[d] for d in sorted(s) if d >= start]; prior = [s[d] for d in sorted(s) if d < start][-120:]
        x = el[k]; sd = math.sqrt(allocator.stats(x[-20:])[1]) if len(x) >= 2 else None
        sleeves.append({"sleeve": k, "live_days": len(live), "live_total_pct": sm(live), "last5_pct": sm(x[-5:]), "last20_pct": sm(x[-20:]),
                        "last60_pct": sm(x[-60:]), "daily_vol_20d_pct": round(sd, 3) if sd else None,
                        "backtest_days_before_test": len(prior), "backtest_mean_daily_pct": round(sum(prior) / len(prior), 4) if prior else None,
                        "backtest_is_flattered": k.startswith(allocator.SURV_SLEEVES),
                        "formula_weight": (lastw.get("weights") or {}).get(k, 0.0), "breaker": k in (lastw.get("breakers") or []),
                        "forced_in_formula": k in (lastw.get("forced") or [])})
    cum = {}
    for r in PF:
        for k in ("ai", "equal", "spy", "base_a", "sh_rp", "sh_mv", "sh_win", "sh_judge"):
            if r.get(k) is not None: cum[k] = cum.get(k, 0.0) + r[k]
    seals = []
    for l in (open(os.path.join(repo, FILE)) if os.path.exists(os.path.join(repo, FILE)) else []):
        if not l.strip(): continue
        r = json.loads(l); wk = dt.date.fromisoformat(r["effective"]).isocalendar()[:2]
        days = [p for p in PF if dt.date.fromisoformat(p["date"]).isocalendar()[:2] == wk and p.get("sh_judge") is not None]
        seals.append({"effective": r["effective"], "weights": r["weights"], "decision": r.get("decision"),
                      "week_result_pct": {k: sm([p.get(k) or 0.0 for p in days]) for k in ("sh_judge", "ai", "equal", "spy")} if days else None})
    eff = effective_day(now)
    return {"now_new_york": now.strftime("%Y-%m-%d %H:%M"), "evidence_through": cal[-1] if cal else None, "effective": eff.isoformat(),
            "market_closed_now": market_closed(now), "phase_of_effective_day": tcal.phase(eff),
            "rules": {"min_share": LO, "max_share": HI, "sum": 1.0, "short_premium_group_max": allocator.GROUP_CAP,
                      "short_premium_group": "W1, W2, D2, D3 together", "cash": "not allowed", "only_listed_sleeves": True,
                      "rebalancing": "weekly; changing a share costs 0% (intraday sleeves), 0.05% (daily library), 0.15% (crypto), 0.5% (options) of the amount moved"},
            "regime_last_day": regime.get(cal[-1]) if cal else None,
            "regime_last_10_days": [regime.get(d) for d in cal[-10:]],
            "spy_last5_pct": round((spy[cal[-1]] / spy[cal[-6]] - 1) * 100, 2) if len(cal) > 6 and cal[-1] in spy and cal[-6] in spy else None,
            "vix_last": vix.get(cal[-1]) if cal else None,
            "eligible_sleeves": sleeves, "excluded_duplicates": sorted(dup),
            "rivals_current_weights": lastw.get("shadows"), "formula_current_weights": lastw.get("weights"),
            "results_since_start_sum_of_daily_pct": {k: round(v, 3) for k, v in cum.items()}, "live_days": len(PF),
            "your_earlier_seals": seals[-8:],
            "cautions": ["live samples are tiny: a few days of results are mostly noise",
                         "backtest records are flattered, most of all where backtest_is_flattered is true",
                         "on past data every simple rule (risk parity, minimum variance, equal weight) beat the formula on Sharpe"]}


def seal(repo, path, dry=False, now=None):
    now = now or dt.datetime.now(NY); D = json.load(open(path)); err = []
    _, _, _, _, _, _, el = context(repo); w = {}
    try: w = {str(k): float(v) for k, v in (D.get("weights") or {}).items() if float(v) > 0}
    except Exception: err.append("weights must be a {sleeve: number} object")
    bad = sorted(k for k in w if k not in el)
    if bad: err.append("not eligible: " + ", ".join(bad))
    if any(v < LO - 1e-9 or v > HI + 1e-9 for v in w.values()): err.append("every share must be between %.2f and %.2f" % (LO, HI))
    if abs(sum(w.values()) - 1.0) > 0.001: err.append("shares add up to %.4f, not 1.00" % sum(w.values()))
    sp = sum(v for k, v in w.items() if k.startswith(allocator.SHORT_PREMIUM))
    if sp > allocator.GROUP_CAP + 1e-9: err.append("the short-premium option sleeves (W1, W2, D2, D3) hold %.2f together; the limit is %.2f" % (sp, allocator.GROUP_CAP))
    for k in ("bull", "bear", "decision"):
        if len(str(D.get(k) or "").strip()) < 40: err.append("'%s' text is missing or too short" % k)
    if not market_closed(now): err.append("the stock market is open: seal only while it is closed")
    eff = effective_day(now).isoformat(); f = os.path.join(repo, FILE)
    if os.path.exists(f) and any(json.loads(l).get("effective") == eff for l in open(f) if l.strip()): err.append("already sealed for " + eff)
    if err: return {"sealed": False, "errors": err, "effective": eff}
    row = {"effective": eff, "sealed_at": now.isoformat(timespec="seconds"), "evidence_through": brief(repo, now)["evidence_through"],
           "weights": {k: round(v, 4) for k, v in sorted(w.items())}, "bull": str(D["bull"])[:1500], "bear": str(D["bear"])[:1500],
           "risk": str(D.get("risk") or "")[:1000], "decision": str(D["decision"])[:1500], "model": str(D.get("model") or "")[:60]}
    if not dry:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "a") as fh: fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return {"sealed": not dry, "dry_run": dry, "effective": eff, "sleeves": len(w), "row": row}


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("brief", "seal"): print(__doc__); sys.exit(2)
    out = brief(a[1]) if a[0] == "brief" else seal(a[1], a[2], "--dry" in a)
    print(json.dumps(out, indent=1, default=str)); sys.exit(0 if a[0] == "brief" or out.get("sealed") or out.get("dry_run") else 1)
