"""The AI's own stock picks, measured directly (added 2026-11-23, runbook item 32, pre-registration G1).

  python3 picks.py REPO [DAY]     (nightly step "picks", before the allocator)

Until now a pick only counted if the opening-range breakout rule happened to trigger on it, so the test measured the
breakout rule more than the picking. This script measures the picking itself, from official daily bars:

 1. DAY HOLD: each stock the morning research picked before 09:30 New York (ledger AgentPicks, asset "stock", status
    "picked") is held from that day's open to that day's close. The same is computed for the 22 stocks of the fixed
    random control list. pick day result = average over the picks; control = average over the control list.
 2. FIVE-DAY HOLD (secondary): the pick day's open to the close four trading days later, picks vs control list over
    the same days (overlapping; raw prices, so a dividend inside the five days is not added back).
 3. THE SLEEVE "AP Agent picks (open to close)": the day-hold average minus COST_SIDE (0.10%) on each side, as a daily
    series in data/picks/daily.json. The allocator reads it like any other sleeve (days without picks are 0), so the
    AI's own picking can earn weight in the judged book.
 4. THE SCORE data/picks/score.json: per-day rows and, for all days and for the verdict window, the mean difference
    picks minus control and the block-bootstrap chance that it is above zero (pre-registration G1: pass at >= 0.9
    with at least 60 pick days, fail at <= 0.10, otherwise inconclusive).
 5. THE SLEEVE "AP2 Agent picks (AI sizing and holding)" (2026-11-23, item 33c): the same picks, but with the weight
    and the holding period the morning research sealed before the open in the pick's "checks" cell ("w=0.30" share
    of that day's picks, 0.05 to 0.40; "hold=3" trading days, 1 to 5; missing or invalid values mean equal weight
    and one day, i.e. the plain sleeve). A position runs from the pick day's open to the close of its last holding
    day, marked on every close. Day return = weighted average over the open positions (weights rescaled to add up to
    1 over whatever is open that day), minus 0.10% of a position's share on its entry day and on its exit day.
    Comparing AP2 with AP shows whether the AI's sizing and timing add anything to its picking; G1 stays on AP.
Rules fixed in advance: equal weight per pick; a pick without a daily bar that day is listed under "missing" and left
out; a day's move beyond +/-60% is treated as a bad bar and left out; picks written at or after 09:30 never count.
Fills at the official open are an assumption (a market-on-open order); the cost above is the allowance for it.
Nothing is traded. Testing only, not financial advice.
"""
import json, os, re, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, ledger, witness
NY = tcal.NY
COST_SIDE = 0.10
SLEEVE = "AP Agent picks (open to close)"
SLEEVE2 = "AP2 Agent picks (AI sizing and holding)"


def bars(repo, sym):
    p = os.path.join(repo, "data", "bars", "1d", sym.replace("/", "_") + ".jsonl"); out = {}
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                b = json.loads(l); out[dt.datetime.fromtimestamp(b["t"], NY).date().isoformat()] = (b["o"], b["c"])
    return out


def moves(B, d, cal_idx, cal):
    """(open-to-close %, open-to-close-of-day+4 %) for one symbol; None where a bar is missing or broken."""
    if d not in B or not B[d][0]: return None, None
    o, c = B[d]; r1 = (c / o - 1) * 100
    if abs(r1) > 60: return None, None
    i = cal_idx[d]; r5 = None
    if i + 4 < len(cal) and cal[i + 4] in B:
        r5 = (B[cal[i + 4]][1] / o - 1) * 100
        if abs(r5) > 60: r5 = None
    return r1, r5


def build(repo, day=None):
    day = day or dt.datetime.now(NY).date().isoformat()
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    cal = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]
    cal_idx = {d: i for i, d in enumerate(cal)}
    picks = {}; sized = {}; probs = {}; W = witness.load(repo)
    for r in ledger.load(repo, "AgentPicks"):
        t = str(r.get("picked_at") or "")
        w = W.get(witness.row_id(r))
        # from 2026-11-30 a pick counts only if GitHub first saw it before 09:30 New York (scripts/witness.py); sizing and
        # confidence are read from the first-seen copy, so editing the row later changes nothing
        if (r.get("asset") == "stock" and r.get("status") == "picked" and t[:10] in cal_idx and t[11:16] < "09:30"
                and witness.counts(w, t[:10])):
            picks.setdefault(t[:10], [])
            if r["symbol"] not in picks[t[:10]]: picks[t[:10]].append(r["symbol"])
            ck = str((w or {}).get("checks") if w and not w.get("grandfathered") else r.get("checks") or ""); mw = re.search(r"\bw=([0-9.]+)", ck); mh = re.search(r"\bhold=([1-5])\b", ck)
            try: w = float(mw.group(1)) if mw else None
            except ValueError: w = None
            sized.setdefault(t[:10], {})[r["symbol"]] = (w if w is not None and 0.05 <= w <= 0.40 else None, int(mh.group(1)) if mh else 1)
            mp = re.search(r"\bp=(0?\.[0-9]+|1(?:\.0+)?)\b", ck)              # stated chance to beat the control list today
            if mp: probs.setdefault(t[:10], {})[r["symbol"]] = float(mp.group(1))
    cache = {}
    def B(s):
        if s not in cache: cache[s] = bars(repo, s)
        return cache[s]
    rows, series, started, calib = [], {}, False, []
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    for d in cal:
        if d in picks: started = True
        if not started: continue
        ps = picks.get(d, [])
        pm = [(s,) + moves(B(s), d, cal_idx, cal) for s in ps]
        cm = [moves(B(s), d, cal_idx, cal) for s in U["control"]]
        p1 = [x[1] for x in pm if x[1] is not None]; c1 = [x[0] for x in cm if x[0] is not None]
        p5 = [x[2] for x in pm if x[2] is not None]; c5 = [x[1] for x in cm if x[1] is not None]
        final = d < day or (d == day and any(d in B(s) for s in U["control"]))
        if not final: continue
        series[d] = round(mean(p1) - 2 * COST_SIDE, 5) if p1 else 0.0
        if ps:
            cmean = mean(c1) if c1 else None
            for sym, r1, _ in pm:
                if r1 is not None and cmean is not None and sym in probs.get(d, {}):
                    calib.append({"date": d, "kind": "pick", "id": sym, "p": probs[d][sym], "hit": r1 > cmean})
            rows.append({"date": d, "phase": tcal.phase(d), "verdict_window": tcal.info(d)["verdict_window"], "picks": ps,
                         "missing": [x[0] for x in pm if x[1] is None], "n": len(p1),
                         "picks_day": round(mean(p1), 4) if p1 else None, "control_day": round(mean(c1), 4) if c1 else None,
                         "picks_5d": round(mean(p5), 4) if p5 else None, "control_5d": round(mean(c5), 4) if p5 and c5 else None})
    # AP2: the AI's own weights and holding periods
    pos, series2 = [], {}
    for d in cal:
        if d not in series: continue
        ws = sized.get(d, {})
        if ws:
            if any(w is None for w, _ in ws.values()): ws = {k: (1.0, h) for k, (_, h) in ws.items()}     # any missing weight: equal
            tw = sum(w for w, _ in ws.values()); ws = {k: (w / tw, h) for k, (w, h) in ws.items()}       # each day's picks share 1
            for sym, (w, h) in ws.items():
                Bs = B(sym); i = cal_idx[d]
                if d in Bs and Bs[d][0] and abs(Bs[d][1] / Bs[d][0] - 1) < 0.6:
                    pos.append({"s": sym, "w": w, "mark": Bs[d][0], "last": cal[min(i + h - 1, len(cal) - 1)], "new": True, "end_i": i + h - 1})
        tot = sum(p["w"] for p in pos); r = 0.0
        for p in pos:
            Bs = B(p["s"])
            if d in Bs:
                r += p["w"] * ((Bs[d][1] / p["mark"] - 1) * 100 - (COST_SIDE if p["new"] else 0) - (COST_SIDE if cal_idx[d] >= p["end_i"] else 0)); p["mark"] = Bs[d][1]
            p["new"] = False
        series2[d] = round(r / tot, 5) if tot else 0.0
        pos = [p for p in pos if cal_idx[d] < p["end_i"]]
    def summary(R):
        a = [(r["picks_day"], r["control_day"]) for r in R if r["picks_day"] is not None and r["control_day"] is not None]
        f = [(r["picks_5d"], r["control_5d"]) for r in R if r["picks_5d"] is not None and r["control_5d"] is not None]
        out = {"pick_days": len(a), "picks": sum(r["n"] for r in R)}
        if a:
            out.update(mean_picks_day=round(mean([x for x, _ in a]), 4), mean_control_day=round(mean([y for _, y in a]), 4),
                       mean_diff_day=round(mean([x - y for x, y in a]), 4), days_ahead=sum(1 for x, y in a if x > y))
            if len(a) >= 10:
                import allocator
                out["p_picks_beat_control"] = allocator.p_beats([x for x, _ in a], [y for _, y in a])
            else: out["p_picks_beat_control"] = None
            n = out["pick_days"]; p = out["p_picks_beat_control"]
            out["g1"] = ("too few pick days (%d of 60)" % n if n < 60 else "PASS" if p is not None and p >= 0.9
                         else "FAIL" if p is not None and p <= 0.10 else "inconclusive")
        if f: out.update(pick_days_5d=len(f), mean_diff_5d=round(mean([x - y for x, y in f]), 4))
        return out
    os.makedirs(os.path.join(repo, "data", "picks"), exist_ok=True)
    json.dump({SLEEVE: series, SLEEVE2: series2} if any(v is not None and (w is not None or h != 1) for x in sized.values() for w, h in x.values() for v in [1]) else {SLEEVE: series}, open(os.path.join(repo, "data", "picks", "daily.json"), "w"), separators=(",", ":"))
    score = {"note": "Picks minus the fixed random control list, same days, before costs (costs are equal on both sides). "
                     "Days before 2026-12-07 are warm-up.", "cost_side_pct": COST_SIDE,
             "all": summary(rows), "verdict": summary([r for r in rows if r["verdict_window"]]), "rows": rows}
    json.dump(score, open(os.path.join(repo, "data", "picks", "score.json"), "w"), indent=1)
    json.dump(calib, open(os.path.join(repo, "data", "picks", "calib_picks.json"), "w"))
    return {"sleeve_days": len(series), "all": score["all"], "verdict": score["verdict"],
            "missing": {r["date"]: r["missing"] for r in rows if r["missing"]}}


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None), indent=1))
