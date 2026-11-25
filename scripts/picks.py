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
SLEEVE3 = "AP3 Agent picks: options (AI sizing and holding)"
PUT_FEE = 0.68          # dollars per contract per side per leg (IBKR fixed $0.65 + about $0.03 regulatory fees)
PUT_SLIP = 2.0          # percent of each leg's premium per side: allowance for the bid/ask spread on a market order
PUT_FILL_BY = "10:30"   # the first option trade at or after 09:30 and before this time is the entry; else no fill
OPT_MIN_DEBIT = 0.05    # a spread whose net debit at entry is below this (dollars per share) is a no fill
OCC_RE = r"[A-Z]{1,6}\d{6}[CP]\d{8}"


def _occ_parts(o):
    return o[:-15], o[-15:-9], o[-9], int(o[-8:]) / 1000.0


def withdrawn(PR, W, cal_idx):
    """Picks withdrawn before the open (item 61, built 2026-11-25). A withdrawal is a NEW AgentPicks row with status
    "withdrawn", the same asset and symbol, and checks "withdraws=<picked_at of the original>"; it counts only if it is
    dated the same New York day as the original, before 09:30, and (from 2026-11-30) first seen by GitHub before 09:30
    like any pick. The original row is never edited. Returns the row ids (witness.row_id) of the withdrawn originals;
    their day's remaining picks share the weight as usual."""
    out = set()
    for r in PR:
        t = str(r.get("picked_at") or "")
        if r.get("status") != "withdrawn" or t[:10] not in cal_idx or t[11:16] >= "09:30": continue
        if not witness.counts(W.get(witness.row_id(r)), t[:10]): continue
        m = re.search(r"\bwithdraws=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)", str(r.get("checks") or ""))
        if not m or m.group(1)[:10] != t[:10] or m.group(1) > t: continue
        out.add("%s|%s|%s" % (m.group(1), r.get("asset"), r.get("symbol")))
    return out


def put_rows(repo, cal_idx, W):
    """Witnessed option picks (asset "option", or "put" from item 57; status "picked", sealed before 09:30 New York;
    item 58, 2026-11-24). The checks cell carries occ=<OCC symbol> (the contract bought: a call for a rising view, a put
    for a falling one), optional occ2=<OCC symbol> (the contract sold against it, making a debit vertical: same
    underlying, expiry and right, strike farther out of the money), w=, hold= (1-5 trading days), p= (chance the stock
    beats the control list today for a call, does worse for a put) and optional stop=/tgt= in percent of the premium
    (the net debit for a spread)."""
    out = {}
    PR = witness.pick_rows(repo)[0]; WD = withdrawn(PR, W, cal_idx)
    for r in PR:     # first-seen copies (review N3): later edits or deletions change nothing
        t = str(r.get("picked_at") or ""); w = W.get(witness.row_id(r))
        if witness.row_id(r) in WD: continue    # withdrawn before the open (item 61)
        if not (r.get("asset") in ("put", "option") and r.get("status") == "picked" and t[:10] in cal_idx and t[11:16] < "09:30" and witness.counts(w, t[:10])):
            continue
        ck = str(r.get("checks") or "")
        mo = re.search(r"\bocc=(" + OCC_RE + r")\b", ck)
        if not mo: continue
        o1 = mo.group(1); m2 = re.search(r"\bocc2=(" + OCC_RE + r")\b", ck); o2 = m2.group(1) if m2 else None
        u1, e1, r1, k1 = _occ_parts(o1)
        if r.get("asset") == "put" and r1 != "P": continue
        if o2:
            u2, e2, r2, k2 = _occ_parts(o2)
            if (u2, e2, r2) != (u1, e1, r1) or (r1 == "C" and k2 <= k1) or (r1 == "P" and k2 >= k1): continue   # debit verticals only
        mw = re.search(r"\bw=([0-9.]+)", ck); mh = re.search(r"\bhold=([1-5])\b", ck); mp = re.search(r"\bp=(0?\.[0-9]+)\b", ck)
        try: wt = float(mw.group(1)) if mw else None
        except ValueError: wt = None
        st, tg = _exits(ck)
        out.setdefault(t[:10], []).append({"und": r["symbol"], "occ": o1, "occ2": o2, "right": r1, "w": wt if wt and 0.05 <= wt <= 1.0 else None,
                                           "hold": int(mh.group(1)) if mh else 1, "p": float(mp.group(1)) if mp else None,
                                           "stop": st, "tgt": tg, "cid": str(r.get("contract_id") or "")})
    return out


def occ_key(occ):
    return "OPT_OCC_" + occ


def opt_bars(repo, occ):
    """Stored 5-minute option bars by day: {day: [(hhmm, o, h, l, c)]}."""
    f = os.path.join(repo, "data", "bars", "opt5m", occ_key(occ) + ".jsonl"); out = {}
    if os.path.exists(f):
        for l in open(f):
            if l.strip():
                b = json.loads(l); x = dt.datetime.fromtimestamp(b["t"], NY)
                if "09:30" <= x.strftime("%H:%M") < "16:00": out.setdefault(x.date().isoformat(), []).append((x.strftime("%H:%M"), b["o"], b["h"], b["l"], b["c"]))
    for v in out.values(): v.sort()
    return out


def spread_bars(a, b):
    """Net (long minus short) 5-minute bars of a debit vertical, on the bars where either leg traded, each leg carried
    forward from its last trade that day. Only open and close are known for a spread, so high = max(open, close) and
    low = min(open, close): a stop or target inside a bar is seen only at the bar's ends."""
    out = {}
    for d in set(a) | set(b):
        A = {r[0]: r for r in a.get(d, [])}; B_ = {r[0]: r for r in b.get(d, [])}; la = lb = None; rows = []
        for t in sorted(set(A) | set(B_)):
            if t in A: la = A[t]
            if t in B_: lb = B_[t]
            if la is None or lb is None: continue
            o = (A[t][1] if t in A else la[4]) - (B_[t][1] if t in B_ else lb[4]); c = la[4] - lb[4]
            rows.append((t, o, max(o, c), min(o, c), c))
        if rows: out[d] = rows
    return out


def puts(repo, cal, cal_idx, day, W):
    """AP3: each option pick (a single call or put, or a debit vertical) bought at the open (first trade 09:30-10:30;
    both legs for a spread) and marked on each day's last trade, exits at its sealed stop/target on the premium (stop
    first inside a bar) or at the close of its last holding day or expiry day, whichever comes first. Day return =
    weighted average over open positions (weights rescaled over what is open), minus the per-leg fee and the per-leg
    spread allowance on entry and exit, both as a percent of the premium paid. A pick that never trades in the fill
    window (or a spread whose net debit is under OPT_MIN_DEBIT) is "no fill"."""
    P = put_rows(repo, cal_idx, W); pos, series, closed, nofill = [], {}, [], []
    for d in cal:
        for x in P.get(d, []):
            l1 = opt_bars(repo, x["occ"]); legs = 1; gross = None
            if x["occ2"]:
                l2 = opt_bars(repo, x["occ2"]); ob = spread_bars(l1, l2); legs = 2
                f1 = [r for r in l1.get(d, []) if r[0] < PUT_FILL_BY]; f2 = [r for r in l2.get(d, []) if r[0] < PUT_FILL_BY]
                if f1 and f2:
                    st0 = max(f1[0][0], f2[0][0]); e = [r for r in ob.get(d, []) if r[0] >= st0]
                    b = [(st0, e[0][1], e[0][1], e[0][1], e[0][1])] if e else []
                    gross = (f1[0][1] + f2[0][1]) if b else None
                else: b = []
                if b and b[0][1] < OPT_MIN_DEBIT: b = []
            else:
                ob = l1; b = [r for r in ob.get(d, []) if r[0] < PUT_FILL_BY]
            exp = "20" + x["occ"][-15:-9]; exp = "%s-%s-%s" % (exp[:4], exp[4:6], exp[6:8])
            if not b: nofill.append({"date": d, "occ": x["occ"], "occ2": x["occ2"]}); continue
            e = b[0][1]; i = cal_idx[d]; last = cal[min(i + x["hold"] - 1, len(cal) - 1)]
            if exp < last: last = exp
            g = gross if gross else e   # premium the spread allowance is charged on (both legs for a spread)
            fee = (PUT_FEE * legs / (100 * e) * 100 if e else 0) + PUT_SLIP * g / e
            pos.append(dict(x, d0=d, entry=e, mark=e, last=last, ob=ob, new=True, fee=fee, start=b[0][0], legs=legs, g_ratio=g / e,
                            stop_px=e * (1 + x["stop"] / 100) if x["stop"] else None, tgt_px=e * (1 + x["tgt"] / 100) if x["tgt"] else None))
        if not pos:
            if any(d >= k for k in P): series[d] = 0.0
            continue
        ws = [p["w"] or 1.0 for p in pos]; tot = sum(ws); r = 0.0; done = []
        for p, wt in zip(pos, ws):
            bars_d = [b for b in p["ob"].get(d, []) if not (p["new"] and b[0] < p["start"])]
            px = None; out_now = d >= p["last"]
            for hhmm, o, h, l, c in bars_d:
                if p["stop_px"] is not None and l <= p["stop_px"]: px = min(o, p["stop_px"]) if hhmm != p["start"] or not p["new"] else p["stop_px"]; out_now = True; break
                if p["tgt_px"] is not None and h >= p["tgt_px"]: px = max(o, p["tgt_px"]) if hhmm != p["start"] or not p["new"] else p["tgt_px"]; out_now = True; break
            if px is None: px = bars_d[-1][4] if bars_d else p["mark"]
            px = max(px, 0.0)
            m0 = p["mark"]
            if m0 > 0:   # day return on the position's value at the start of the day; costs in the same units
                exit_cost = (PUT_FEE * p["legs"] / (100 * m0) * 100 + PUT_SLIP * p["g_ratio"] * px / m0) if out_now and px > 0 else 0
                r += wt * ((px / m0 - 1) * 100 - (p["fee"] if p["new"] else 0) - exit_cost)
            p["mark"] = px; p["new"] = False
            if out_now: done.append(p); closed.append({"date": p["d0"], "und": p["und"], "occ": p["occ"], "occ2": p["occ2"], "entry": p["entry"], "exit": px, "exit_day": d,
                                                        "gross_pct": round((px / p["entry"] - 1) * 100, 2)})
        series[d] = round(r / tot, 5)
        pos = [p for p in pos if p not in done]
    return series, closed, nofill, P



def bars(repo, sym):
    p = os.path.join(repo, "data", "bars", "1d", sym.replace("/", "_") + ".jsonl"); out = {}
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                b = json.loads(l); out[dt.datetime.fromtimestamp(b["t"], NY).date().isoformat()] = (b["o"], b["c"], b.get("h", max(b["o"], b["c"])), b.get("l", min(b["o"], b["c"])))
    return out


def _exits(ck):
    """Optional exits sealed in the checks cell (2026-11-24, item 57): stop=-4 (percent below entry) and tgt=8 (percent
    above entry). Valid ranges: stop -1 to -50, tgt 1 to 200; anything else is ignored."""
    def f(k, lo, hi):
        m = re.search(r"\b%s=([+-]?[0-9.]+)%%?" % k, ck)
        try: v = float(m.group(1)) if m else None
        except ValueError: v = None
        return v if v is not None and lo <= v <= hi else None
    s = f("stop", -50, -1); t = f("tgt", 1, 200)
    return (s, t)


def moves(B, d, cal_idx, cal):
    """(open-to-close %, open-to-close-of-day+4 %) for one symbol; None where a bar is missing or broken."""
    if d not in B or not B[d][0]: return None, None
    o, c = B[d][0], B[d][1]; r1 = (c / o - 1) * 100
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
    picks = {}; sized = {}; probs = {}; exits = {}; PR, W = witness.pick_rows(repo)
    vers = {}       # (pick day, symbol) -> playbook version, for the by-version report (review N13)
    WD = withdrawn(PR, W, cal_idx)
    for r in PR:    # first-seen copies (review N3): a witnessed pick edited or deleted later is still scored as first seen
        t = str(r.get("picked_at") or "")
        if witness.row_id(r) in WD: continue    # withdrawn before the open (item 61)
        w = W.get(witness.row_id(r))
        # from 2026-11-30 a pick counts only if GitHub first saw it before 09:30 New York (scripts/witness.py); sizing and
        # confidence are read from the first-seen copy, so editing the row later changes nothing
        if (r.get("asset") == "stock" and r.get("status") == "picked" and t[:10] in cal_idx and t[11:16] < "09:30"
                and witness.counts(w, t[:10])):
            picks.setdefault(t[:10], [])
            if r["symbol"] not in picks[t[:10]]: picks[t[:10]].append(r["symbol"])
            ck = str(r.get("checks") or ""); mw = re.search(r"\bw=([0-9.]+)", ck); mh = re.search(r"\bhold=([1-5])\b", ck)
            try: w = float(mw.group(1)) if mw else None
            except ValueError: w = None
            sized.setdefault(t[:10], {})[r["symbol"]] = (w if w is not None and 0.05 <= w <= 0.40 else None, int(mh.group(1)) if mh else 1)
            exits.setdefault(t[:10], {})[r["symbol"]] = _exits(ck)
            mv = re.search(r"\bplaybook v(\d+)", ck); vers[(t[:10], r["symbol"])] = int(mv.group(1)) if mv else None
            mp = re.search(r"\bp=(0?\.[0-9]+|1(?:\.0+)?)\b", ck)              # stated chance to beat the control list today
            if mp: probs.setdefault(t[:10], {})[r["symbol"]] = float(mp.group(1))
    cache = {}
    def B(s):
        if s not in cache: cache[s] = bars(repo, s)
        return cache[s]
    rows, series, started, calib, by_pick = [], {}, False, [], []
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
                if r1 is not None and cmean is not None:
                    by_pick.append({"date": d, "symbol": sym, "version": vers.get((d, sym)), "edge": r1 - cmean})
                if r1 is not None and cmean is not None and sym in probs.get(d, {}):
                    calib.append({"date": d, "kind": "pick", "id": sym, "p": probs[d][sym], "hit": r1 > cmean})
            rows.append({"date": d, "phase": tcal.phase(d), "verdict_window": tcal.info(d)["verdict_window"], "picks": ps,
                         "missing": [x[0] for x in pm if x[1] is None], "n": len(p1),
                         "picks_day": round(mean(p1), 4) if p1 else None, "control_day": round(mean(c1), 4) if c1 else None,
                         "picks_5d": round(mean(p5), 4) if p5 else None, "control_5d": round(mean(c5), 4) if p5 and c5 else None})
    # AP2: the AI's own weights and holding periods
    pos, series2, closed2 = [], {}, []
    for d in cal:
        if d not in series: continue
        ws = sized.get(d, {})
        if ws:
            if any(w is None for w, _ in ws.values()): ws = {k: (1.0, h) for k, (_, h) in ws.items()}     # any missing weight: equal
            tw = sum(w for w, _ in ws.values()); ws = {k: (w / tw, h) for k, (w, h) in ws.items()}       # each day's picks share 1
            for sym, (w, h) in ws.items():
                Bs = B(sym); i = cal_idx[d]
                if d in Bs and Bs[d][0] and abs(Bs[d][1] / Bs[d][0] - 1) < 0.6:
                    st, tg = exits.get(d, {}).get(sym, (None, None)); e0 = Bs[d][0]
                    pos.append({"s": sym, "w": w, "mark": e0, "entry": e0, "d0": d, "last": cal[min(i + h - 1, len(cal) - 1)], "new": True, "end_i": i + h - 1,
                                "stop": e0 * (1 + st / 100) if st else None, "tgt": e0 * (1 + tg / 100) if tg else None})
        tot = sum(p["w"] for p in pos); r = 0.0
        for p in pos:
            Bs = B(p["s"])
            if d in Bs:
                o, c, hi, lo = Bs[d]; px = c
                # sealed exits on daily bars, the stop first (conservative); a gap through a level exits at the open
                if p["stop"] is not None and (lo <= p["stop"]): px = min(o, p["stop"]) if not p["new"] else p["stop"]; p["end_i"] = cal_idx[d]
                elif p["tgt"] is not None and hi >= p["tgt"]: px = max(o, p["tgt"]) if not p["new"] else p["tgt"]; p["end_i"] = cal_idx[d]
                p["exit_px"] = px
                r += p["w"] * ((px / p["mark"] - 1) * 100 - (COST_SIDE if p["new"] else 0) - (COST_SIDE if cal_idx[d] >= p["end_i"] else 0)); p["mark"] = px
            p["new"] = False
        series2[d] = round(r / tot, 5) if tot else 0.0
        for p in pos:
            if cal_idx[d] >= p["end_i"] and d in B(p["s"]):
                closed2.append({"date": p["d0"], "gross": (p.get("exit_px", B(p["s"])[d][1]) / p["entry"] - 1) * 100})
        pos = [p for p in pos if cal_idx[d] < p["end_i"]]
    series3, closed3, nofill3, P3 = puts(repo, cal, cal_idx, day, W)
    bear = []
    for d, xs in sorted(P3.items()):
        cm = [moves(B(s), d, cal_idx, cal)[0] for s in U["control"]]; c1 = [x for x in cm if x is not None]
        for x in xs:
            m = moves(B(x["und"]), d, cal_idx, cal)[0]
            if m is not None and c1:
                bear.append({"date": d, "und": x["und"], "right": x.get("right", "P"), "spread": bool(x.get("occ2")), "stock_day": round(m, 4), "control_day": round(mean(c1), 4)})
                hit = m < mean(c1) if x.get("right", "P") == "P" else m > mean(c1)
                if x["p"] is not None: calib.append({"date": d, "kind": "put" if x.get("right", "P") == "P" else "call", "id": x["und"], "p": x["p"], "hit": hit})
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
    # COST VIEW (2026-11-23, report only; idea from a reviewed paper-trading kit): per position, how much of the gross
    # move the costs take and the win rate the picks would need to break even after costs, next to the win rate they got.
    def cost_view(trades, rt):
        t = [x for x in trades if x["gross"] is not None]
        if not t: return {"trades": 0}
        net = [x["gross"] - rt for x in t]; wins = [x for x in net if x > 0]; losses = [-x for x in net if x <= 0]
        g = sum(x["gross"] for x in t); aw = mean(wins) if wins else None; al = mean(losses) if losses else None
        return {"trades": len(t), "round_trip_cost_pct": rt, "gross_sum_pct": round(g, 3), "cost_sum_pct": round(rt * len(t), 3),
                "cost_share_of_gross": round(rt * len(t) / abs(g), 3) if g else None,
                "win_rate": round(len(wins) / len(t), 3), "avg_net_win_pct": round(aw, 3) if aw is not None else None,
                "avg_net_loss_pct": round(al, 3) if al is not None else None,
                "breakeven_win_rate": round(al / (aw + al), 3) if aw and al else None}
    ap_trades = []
    for d in cal:
        for sym in picks.get(d, []):
            mv = moves(B(sym), d, cal_idx, cal)[0]
            if mv is not None: ap_trades.append({"date": d, "gross": mv})
    cview = {"note": "report only; per position, unweighted; win rate after costs vs the break-even win rate",
             "AP": {"all": cost_view(ap_trades, 2 * COST_SIDE), "verdict": cost_view([x for x in ap_trades if x["date"] >= tcal.ALLOC_FREEZE.isoformat()], 2 * COST_SIDE)},
             "AP2": {"all": cost_view(closed2, 2 * COST_SIDE), "verdict": cost_view([x for x in closed2 if x["date"] >= tcal.ALLOC_FREEZE.isoformat()], 2 * COST_SIDE)}}
    os.makedirs(os.path.join(repo, "data", "picks"), exist_ok=True)
    out_sleeves = {SLEEVE: series, SLEEVE2: series2} if any(v is not None and (w is not None or h != 1) for x in sized.values() for w, h in x.values() for v in [1]) else {SLEEVE: series}
    if series3: out_sleeves[SLEEVE3] = series3
    json.dump(out_sleeves, open(os.path.join(repo, "data", "picks", "daily.json"), "w"), separators=(",", ":"))
    score = {"note": "Picks minus the fixed random control list, same days, before costs (costs are equal on both sides). "
                     "Days before 2026-12-07 are warm-up.", "cost_side_pct": COST_SIDE,
             "all": summary(rows), "verdict": summary([r for r in rows if r["verdict_window"]]), "cost_view": cview, "rows": rows,
             "options": {"note": "option picks (calls, puts and debit verticals; items 57-58): the stock's open-to-close move against "
                                 "the control list's, signed by the view (+ for a call, - for a put), so positive = the view was right. "
                                 "Report only; G1 counts the long stock picks; AP3 carries the option P&L.",
                         "n": len(bear), "mean_view_edge": round(mean([(b["stock_day"] - b["control_day"]) * (1 if b["right"] == "C" else -1) for b in bear]), 4) if bear else None,
                         "rows": bear, "closed": closed3, "no_fill": nofill3}}
    # By playbook version and by vehicle (review N13): the playbook keeps changing to the end, so results are also
    # reported per version; stock picks and option picks are reported apart. Report only.
    bv = {}
    for x in by_pick: bv.setdefault("v%s" % x["version"], []).append(x["edge"])
    score["by_version"] = {k: {"picks": len(v), "mean_edge_vs_control": round(mean(v), 4)} for k, v in sorted(bv.items())}
    score["by_vehicle"] = {"stock": {"picks": len(by_pick), "mean_edge_vs_control": round(mean([x["edge"] for x in by_pick]), 4) if by_pick else None},
                           "option": {"picks": len(bear), "mean_view_edge": score["options"]["mean_view_edge"]}}
    # Integrity (review N3): witnessed picks later edited or deleted in the ledger; they are scored as first seen.
    try:
        ig = witness.integrity(repo); score["integrity"] = {"altered": [x["id"] for x in ig["altered"] if x["kind"] == "pick"],
                                                              "missing_from_ledger": [x["id"] for x in ig["missing"] if x["kind"] == "pick"]}
    except Exception as e: score["integrity"] = {"error": str(e)[:200]}
    json.dump(score, open(os.path.join(repo, "data", "picks", "score.json"), "w"), indent=1)
    json.dump(calib, open(os.path.join(repo, "data", "picks", "calib_picks.json"), "w"))
    return {"sleeve_days": len(series), "all": score["all"], "verdict": score["verdict"],
            "missing": {r["date"]: r["missing"] for r in rows if r["missing"]}}


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None), indent=1))
