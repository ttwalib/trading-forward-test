"""Quantavius's daily ranking of a fixed stock list (added 2026-11-23, runbook item 35b, pre-registration G1 primary).

  python3 rank.py seal REPO FILE     validates and seals today's ranking (before 09:30 New York, full trading days)
  python3 rank.py score REPO [DAY]   scores every sealed day -> data/picks/rank_score.json (nightly step "rank")

Why: with 3-8 picks a day, picking skill takes many months to show. The standard quant test of stock selection is a
RANKING: every morning Quantavius scores each of a FIXED list of 44 liquid stocks (the 22-stock watchlist and the
22-stock random control list, data/universe.json) from -2 (expect it to do worst today) to +2 (expect best), using
the same research as its picks. The day's information coefficient (IC) is the rank correlation (Spearman) between
the scores and the stocks' open-to-close returns. 44 scores a day give far more evidence than a handful of picks.
FILE = {"scores": {"AAPL": 1, ...}, "model": "...", "note": "..."}; at least 40 of the 44 symbols, integer scores,
at least 5 non-zero. One seal per day; data/picks/rank/DAY.json; chained by scripts/chain.py.
G1 primary rule (pre-registration): mean daily IC over the verdict window > 0 with day-block bootstrap chance >= 0.9
and at least 60 sealed days = PASS; chance <= 0.10 = FAIL; otherwise INCONCLUSIVE.
Nothing is traded. Testing only, not financial advice.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal
NY = tcal.NY


def names(repo):
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); return U["watchlist"] + U["control"]


def seal(repo, path, now=None):
    now = now or dt.datetime.now(NY); d = now.date(); D = json.load(open(path)); err = []
    if not (tcal.is_trading(d) and tcal.START <= d <= tcal.END): err.append("not a full trading day of the test")
    if now.hour * 60 + now.minute >= 9 * 60 + 30: err.append("too late: rankings must be sealed before 09:30 New York")
    L = names(repo); sc = D.get("scores") or {}
    try: sc = {str(k).upper(): int(v) for k, v in sc.items()}
    except Exception: err.append("scores must be integers")
    bad = [k for k, v in sc.items() if k not in L or v not in (-2, -1, 0, 1, 2)]
    if bad: err.append("not on the list or outside -2..2: " + ", ".join(sorted(bad)[:10]))
    if len([k for k in sc if k in L]) < 40: err.append("score at least 40 of the %d listed symbols" % len(L))
    if sum(1 for v in sc.values() if v) < 5: err.append("at least 5 non-zero scores")
    f = os.path.join(repo, "data", "picks", "rank", d.isoformat() + ".json")
    if os.path.exists(f): err.append("already sealed for " + d.isoformat())
    if err: return {"sealed": False, "errors": err}
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump({"date": d.isoformat(), "sealed_at": now.isoformat(timespec="seconds"), "scores": sc,
               "model": str(D.get("model") or "")[:60], "note": str(D.get("note") or "")[:500]}, open(f, "w"), separators=(",", ":"))
    with open(f) as fh: line = fh.read()
    with open(f, "w") as fh: fh.write(line + "\n")
    return {"sealed": True, "date": d.isoformat(), "n": len(sc)}


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else None


def score(repo, day=None):
    import picks, allocator, witness
    day = day or dt.datetime.now(NY).date().isoformat(); d0 = os.path.join(repo, "data", "picks", "rank"); rows = []
    WS = witness.sightings(repo); valid_days = set(); first = None
    for fn in sorted(os.listdir(d0)) if os.path.isdir(d0) else []:
        R = json.load(open(os.path.join(d0, fn))); d = R["date"]
        if d > day: continue
        first = d if first is None or d < first else first
        sealed = dt.datetime.fromisoformat(R["sealed_at"]).astimezone(NY)
        if sealed.date().isoformat() != d or sealed.hour * 60 + sealed.minute >= 570: continue
        # GitHub must have seen this exact ranking before 09:30 (review N1, from witness.ENFORCE_FROM)
        if not witness.on_time(WS, "rank", "rank|%s|%s" % (d, R.get("sealed_at")), witness.sha(R), d): continue
        valid_days.add(d)
        xs, ys = [], []
        for s, v in R["scores"].items():
            B = picks.bars(repo, s)
            if d in B and B[d][0]:
                r = (B[d][1] / B[d][0] - 1) * 100
                if abs(r) < 60: xs.append(v); ys.append(r)
        if len(xs) < 30: continue
        ic = spearman(xs, ys)
        top = [y for x, y in zip(xs, ys) if x > 0]; bot = [y for x, y in zip(xs, ys) if x < 0]
        rows.append({"date": d, "n": len(xs), "ic": round(ic, 4) if ic is not None else None,
                     "spread_pct": round(sum(top) / len(top) - sum(bot) / len(bot), 4) if top and bot else None,
                     "verdict_window": tcal.info(d)["verdict_window"]})
    # COVERAGE (review N6, 2026-11-24): from the first ranking day, every full trading day without a valid ranking
    # counts as IC 0 ("missed"), so skipping a hard day can never raise the score. A day whose bars are missing (data,
    # not Quantavius) is left out as before.
    if first:
        for d in tcal.trading_days(first, day):
            if d not in valid_days:
                rows.append({"date": d, "n": 0, "ic": 0.0, "spread_pct": None, "missed": True,
                             "verdict_window": tcal.info(d)["verdict_window"]})
        rows.sort(key=lambda r: r["date"])
    def summ(R):
        ic = [r["ic"] for r in R if r["ic"] is not None]
        if not ic: return {"days": 0}
        m = sum(ic) / len(ic); sd = (sum((x - m) ** 2 for x in ic) / (len(ic) - 1)) ** 0.5 if len(ic) > 1 else None
        p = allocator.p_beats(ic, [0.0] * len(ic)) if len(ic) >= 10 else None
        return {"days": len(ic), "missed_days": sum(1 for r in R if r.get("missed")),
                "coverage": round(1 - sum(1 for r in R if r.get("missed")) / len(R), 3) if R else None, "mean_ic": round(m, 4), "t": round(m / (sd / len(ic) ** 0.5), 2) if sd else None,
                "p_mean_ic_above_0": p, "days_positive": sum(1 for x in ic if x > 0),
                "g1_primary": ("too few days (%d of 60)" % len(ic) if len(ic) < 60 else "PASS" if p is not None and p >= 0.9
                               else "FAIL" if p is not None and p <= 0.10 else "INCONCLUSIVE")}
    out = {"note": "Spearman rank correlation between Quantavius's sealed morning scores (-2..+2) of 44 fixed stocks and "
                   "their open-to-close returns. Positive = it ranks better than chance.",
           "all": summ(rows), "verdict": summ([r for r in rows if r["verdict_window"]]), "rows": rows}
    json.dump(out, open(os.path.join(repo, "data", "picks", "rank_score.json"), "w"), indent=1)
    return {k: out[k] for k in ("all", "verdict")}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "seal": print(json.dumps(seal(a[1], a[2]), indent=1))
    elif a[0] == "score": print(json.dumps(score(a[1], a[2] if len(a) > 2 else None), indent=1))
