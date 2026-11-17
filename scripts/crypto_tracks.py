"""Crypto tracks: X1-X3 (BTC, ETH, SOL) and M1-M3 (DOGE, SHIB, AVAX, LINK) on any bar size, with tunable parameters.

  stream:   python3 crypto_tracks.py stream STATE.json BARS.json NOW STEP PARAMS.json > out.json
  optimize: python3 crypto_tracks.py optimize BARS.json NOW STEP LIVE_PARAMS.json CHALLENGERS.json > opt.json

BARS.json: {"BTC": raw, ...} raw IBKR get_price_history arrays {"time","open","high","low","close","volume"} for one
bar size; STEP = its seconds (900 for FIFTEEN_MINS, 3600 for ONE_HOUR). PARAMS.json: {"X1": {...overrides}, ...}; {}
means the fixed rules; an optional "_coins": {"X": [...], "M": [...]} replaces the coin lists (a coin may be in both;
BTC bars are still needed as the M2 reference). With empty params the rules are exactly those of the 1-minute test (crypto_stream.py), only on
another bar size: "48 bars" means 48 bars of that size.
stream: each bar is processed once (bars at or before state.last_t[coin] are indicator warm-up only), positions carry
over in the state. Signal on a bar's close, fill at the next bar's open; stop checked first inside each bar.
optimize (end-of-day review, champion/challenger): see optimize() below. Live settings change only after a challenger
wins on fresh bars entered after it was proposed. Grid: entry knob x stop_atr x target_r x cost filter (min_edge).
Costs per side: 0.2% majors, 0.3% meme/small caps. R is measured against the first stop.
"""
import json, sys, itertools, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
MAJ, MEME = ("BTC", "ETH", "SOL"), ("DOGE", "SHIB", "AVAX", "LINK")
COST = {"X": 0.002, "M": 0.003}
DEFAULTS = {
    "X1": {"fast": 20, "slow": 50, "trend": 100, "stop_atr": 2, "target_r": None, "time_stop": None},
    "X2": {"bb_k": 2, "rsi_max": 30, "stop_atr": 2, "target_r": None, "time_stop": 48},
    "X3": {"entry_n": 20, "exit_n": 10, "stop_atr": 2, "target_r": None, "time_stop": None},
    "M1": {"vol_mult": 3, "stop_atr": 2, "trail_atr": 3, "target_atr": None, "target_r": None, "time_stop": 24},
    "M2": {"btc_move": 0.015, "stop_atr": 2, "trail_atr": None, "target_atr": 3, "target_r": None, "time_stop": 12},
    "M3": {"mom": 0.05, "stop_atr": 2, "trail_atr": 3, "target_atr": None, "target_r": None, "time_stop": 72}}
GRID = {  # entry knob values; every strategy also tries stop_atr in (1.5, 2, 3) and target_r in (None, 1, 2)
    "X1": [{"fast": 20, "slow": 50}, {"fast": 10, "slow": 30}, {"fast": 50, "slow": 100}],
    "X2": [{"rsi_max": 25}, {"rsi_max": 30}, {"rsi_max": 35}],
    "X3": [{"entry_n": 20}, {"entry_n": 40}, {"entry_n": 60}],
    "M1": [{"vol_mult": 3}, {"vol_mult": 4}, {"vol_mult": 6}],
    "M2": [{"btc_move": 0.01}, {"btc_move": 0.015}, {"btc_move": 0.02}],
    "M3": [{"mom": 0.03}, {"mom": 0.05}, {"mom": 0.08}]}
WARMUP, MIN_TRADES, MIN_GAIN = 120, 15, 3.0
MIN_OOS, MAX_OOS, MAX_AGE_DAYS = 10, 30, 5  # challenger: promote after >= MIN_OOS fresh trades; drop after MAX_OOS or MAX_AGE_DAYS


def P(params, s):
    p = dict(DEFAULTS[s]); p["min_edge"] = None; p.update((params or {}).get(s, {})); return p


def edge_ok(q, s, a, px):
    """Cost filter: skip a signal when ATR/price is below min_edge x the round-trip cost (None = off)."""
    return not q.get("min_edge") or a / px >= q["min_edge"] * 2 * COST[s[0]]


def et(t): return dt.datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d %H:%M")


def norm(raw, now, step):
    out = {}
    n = len(raw.get("close", [])); vol = raw.get("volume") or [0] * n
    for i in range(n):
        if raw["close"][i] is None: continue
        t = dt.datetime.strptime(raw["time"][i].replace("Z", "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
        t = int(t.timestamp()) // step * step
        if t + step > now: continue
        out[t] = {"t": t, "o": float(raw["open"][i]), "h": float(raw["high"][i]), "l": float(raw["low"][i]),
                  "c": float(raw["close"][i]), "v": float(vol[i] or 0)}
    return [out[k] for k in sorted(out)]


def ema(xs, n):
    k, out, e = 2 / (n + 1), [], None
    for i, x in enumerate(xs):
        e = x if e is None else x * k + e * (1 - k)
        out.append(e if i >= n - 1 else None)
    return out


def atr14(b, n=14):
    out, a = [], None
    for i, x in enumerate(b):
        tr = x["h"] - x["l"] if i == 0 else max(x["h"] - x["l"], abs(x["h"] - b[i-1]["c"]), abs(x["l"] - b[i-1]["c"]))
        if i < n: a = (a or 0) + tr / n; out.append(a if i == n - 1 else None)
        else: a = (a * (n - 1) + tr) / n; out.append(a)
    return out


def rsi14(cl, n=14):
    out, ag, al = [None], 0.0, 0.0
    for i in range(1, len(cl)):
        d = cl[i] - cl[i-1]; g, l = max(d, 0), max(-d, 0)
        if i <= n:
            ag += g / n; al += l / n
            out.append(None if i < n else (100 if al == 0 else 100 - 100 / (1 + ag / al)))
        else:
            ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n
            out.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    return out


def boll(cl, n=20, k=2):
    mid, lo = [], []
    for i in range(len(cl)):
        if i < n - 1: mid.append(None); lo.append(None); continue
        w = cl[i-n+1:i+1]; m = sum(w) / n; sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
        mid.append(m); lo.append(m - k * sd)
    return mid, lo


def rec(sym, p, px, t_exit, why, status):
    c = COST[p["s"][0]]; risk = p["entry"] - p["stop0"]
    net = px * (1 - c) - p["entry"] * (1 + c)
    return {"strategy": p["s"], "symbol": sym, "status": status, "entry_time": et(p["et"]), "entry": float("%.6g" % p["entry"]),
            "stop": float("%.6g" % p["stop0"]), "exit_time": et(t_exit), "exit_or_mark": float("%.6g" % px), "reason": why,
            "r": round(net / risk, 2), "pct": round(100 * net / p["entry"], 3), "gross_pct": round(100 * (px / p["entry"] - 1), 3)}


def run_x(sym, B, st, last_t, start, closed, params, step, only=None):
    cl = [b["c"] for b in B]; atr = atr14(B); r14 = rsi14(cl); cache = {}
    def E(n):
        if n not in cache: cache[n] = ema(cl, n)
        return cache[n]
    for s in ("X1", "X2", "X3"):
        if only and s not in only: continue
        q = P(params, s); k = sym + "|" + s; p = st.get(k)
        ef = es = etr = None
        if s == "X1": ef, es, etr = E(q["fast"]), E(q["slow"]), (E(q["trend"]) if q.get("trend") else None)
        mid, lo = boll(cl, 20, q["bb_k"]) if s == "X2" else (None, None)
        for i, b in enumerate(B):
            if b["t"] <= last_t: continue
            if p and p["st"] == "pending":
                p.update(st="open", entry=b["o"], stop0=b["o"] - p["k"] * p["a"], et=b["t"])
                p["tg"] = p["entry"] + p["tr"] * (p["entry"] - p["stop0"]) if p.get("tr") else None
            if p and p["st"] == "open" and p.get("xn"):
                closed.append(rec(sym, p, b["o"], b["t"], p["why"], "closed")); p = None
            elif p and p["st"] == "open":
                ex = None
                if b["o"] <= p["stop0"]: ex = (b["o"], "stop (gap)")
                elif b["l"] <= p["stop0"]: ex = (p["stop0"], "stop")
                elif p.get("tg") and b["o"] >= p["tg"]: ex = (b["o"], "target (gap)")
                elif p.get("tg") and b["h"] >= p["tg"]: ex = (p["tg"], "target")
                if ex:
                    closed.append(rec(sym, p, ex[0], b["t"], ex[1], "closed")); p = None
                    continue
            if p: p["n"] = p.get("n", 0) + 1
            if atr[i] is None or i == 0: continue
            if p:
                why = None
                if s == "X1" and ef[i] is not None and ef[i-1] is not None and es[i] is not None and es[i-1] is not None \
                        and ef[i] < es[i] and ef[i-1] >= es[i-1]: why = "EMA cross down"
                if s == "X2" and mid[i] is not None and b["c"] >= mid[i]: why = "middle band"
                if s == "X3" and i >= q["exit_n"] and b["c"] < min(x["l"] for x in B[i-q["exit_n"]:i]): why = "%d-bar low" % q["exit_n"]
                if not why and q.get("time_stop") and p["n"] >= q["time_stop"]: why = "%d-bar time stop" % q["time_stop"]
                if why: p["xn"], p["why"] = True, why
                continue
            if b["t"] + step <= start: continue
            sig = False
            if s == "X1" and ef[i-1] is not None and es[i] is not None and es[i-1] is not None and (etr is None or etr[i] is not None):
                sig = ef[i] > es[i] and ef[i-1] <= es[i-1] and (etr is None or b["c"] > etr[i])
            if s == "X2" and lo[i] is not None and r14[i] is not None: sig = b["c"] < lo[i] and r14[i] < q["rsi_max"]
            if s == "X3" and i >= q["entry_n"]: sig = b["c"] > max(x["h"] for x in B[i-q["entry_n"]:i])
            if sig and edge_ok(q, s, atr[i], b["c"]): p = {"s": s, "st": "pending", "a": atr[i], "n": 0, "k": q["stop_atr"], "tr": q.get("target_r")}
        st[k] = p


def run_m(sym, B, btc, st, last_t, start, closed, params, step, only=None):
    atr = atr14(B)
    for s in ("M1", "M2", "M3"):
        if only and s not in only: continue
        q = P(params, s); trail, tstop = q["trail_atr"], q["time_stop"]; k = sym + "|" + s; p = st.get(k)
        for i, b in enumerate(B):
            if b["t"] <= last_t: continue
            if p and p["st"] == "pending":
                e = b["o"]; a = p["a"]; s0 = e - q["stop_atr"] * a
                tg = e + q["target_r"] * (e - s0) if q.get("target_r") else (e + q["target_atr"] * a if q.get("target_atr") else None)
                p.update(st="open", entry=e, stop0=s0, stop=s0, hh=e, tg=tg, et=b["t"], n=0)
            if p and p["st"] == "open":
                ex = None
                if p.get("xn"): ex = (b["o"], p["why"])
                elif b["o"] <= p["stop"]: ex = (b["o"], "stop (gap)")
                elif b["l"] <= p["stop"]: ex = (p["stop"], "trail stop" if p["stop"] > p["stop0"] else "stop")
                elif p["tg"] and b["o"] >= p["tg"]: ex = (b["o"], "target (gap)")
                elif p["tg"] and b["h"] >= p["tg"]: ex = (p["tg"], "target")
                if ex:
                    closed.append(rec(sym, p, ex[0], b["t"], ex[1], "closed")); p = None; continue
                p["hh"] = max(p["hh"], b["h"]); p["n"] += 1
                if trail: p["stop"] = max(p["stop"], p["hh"] - trail * p["a"])
                if tstop and p["n"] >= tstop: p["xn"], p["why"] = True, "%d-bar time stop" % tstop
                continue
            if p or atr[i] is None or b["t"] + step <= start: continue
            sig = False
            if s == "M1" and i >= 24:
                avg = sum(x["v"] for x in B[i-24:i]) / 24; rng = b["h"] - b["l"]
                sig = (avg > 0 and b["v"] >= q["vol_mult"] * avg and b["c"] > b["o"] and rng > 0 and (b["c"] - b["l"]) / rng >= 2 / 3
                       and b["c"] > max(x["h"] for x in B[i-12:i]))
            if s == "M2" and i >= 4 and btc:
                t, t4 = b["t"], B[i-4]["t"]
                if t in btc and t4 in btc and t - t4 == 4 * step:
                    br = btc[t] / btc[t4] - 1; cr = b["c"] / B[i-4]["c"] - 1; sig = br >= q["btc_move"] and cr < 0.5 * br
            if s == "M3" and i >= 72:
                sig = b["c"] > max(x["h"] for x in B[i-72:i]) and b["c"] / B[i-24]["c"] - 1 >= q["mom"]
            if sig and edge_ok(q, s, atr[i], b["c"]): p = {"s": s, "st": "pending", "a": atr[i]}
        st[k] = p


def stream(state, data, now, step, params):
    st = state.get("pos", {}); last = state.get("last_t", {})
    start = state.get("start") or (now // step * step - step)
    closed, coverage = [], {}
    bars = {c: norm(data[c], now, step) for c in data}
    btc = {b["t"]: b["c"] for b in bars.get("BTC", [])}
    co = (params or {}).get("_coins") or {}
    maj, meme = tuple(co.get("X", MAJ)), tuple(co.get("M", MEME))
    for c in tuple(dict.fromkeys(maj + meme)):
        B = bars.get(c, [])
        lt = last.get(c, start - step)
        new = [b for b in B if b["t"] > lt]
        gap = bool(new) and c in last and new[0]["t"] - lt > step
        coverage[c] = {"new_bars": len(new), "warmup_bars": len(B) - len(new), "gap_bars": (new[0]["t"] - lt) // step - 1 if gap else 0}
        if not B: continue
        if c in maj: run_x(c, B, st, lt, start, closed, params, step)
        if c in meme: run_m(c, B, btc, st, lt, start, closed, params, step)
        if new: last[c] = new[-1]["t"]
    openp = []
    for k, p in st.items():
        if not p: continue
        sym = k.split("|")[0]; B = bars.get(sym, [])
        if p["st"] == "pending": openp.append({"strategy": p["s"], "symbol": sym, "status": "pending (fills next bar)"}); continue
        if B: openp.append(rec(sym, p, B[-1]["c"], B[-1]["t"] + step, "open (marked at last close)", "open"))
    st = {k: v for k, v in st.items() if v}
    return {"closed": sorted(closed, key=lambda r: r["exit_time"]), "open": openp, "coverage": coverage,
            "state": {"start": start, "last_t": last, "pos": st}}


def backtest(bars, btc, s, params, step, since=0):
    closed = []
    for c in (MAJ if s[0] == "X" else MEME):
        B = bars.get(c, [])
        if len(B) <= WARMUP: continue
        start = max(B[WARMUP]["t"], since // step * step); st = {}
        (run_x if s[0] == "X" else run_m)(*((c, B, st, start - step, start, closed, params, step) if s[0] == "X"
                                           else (c, B, btc, st, start - step, start, closed, params, step)), only={s})
    n = len(closed); w = sum(1 for r in closed if r["pct"] > 0)
    return {"trades": n, "win_rate": round(100 * w / n, 1) if n else None,
            "avg_net_pct": round(sum(r["pct"] for r in closed) / n, 4) if n else None}


def search(bars, btc, s, cur, step):
    """Grid search on the whole window: best win rate among settings with enough trades whose avg net % is no worse
    than the current settings' on the same bars, and only if the win rate rises by MIN_GAIN points."""
    base = backtest(bars, btc, s, {s: cur}, step); cands = []
    for knob, k, tr, me in itertools.product(GRID[s], (1.5, 2, 3), (None, 1, 2), (None, 3)):
        ov = dict(cur); ov.update(knob); ov["stop_atr"] = k; ov["target_r"] = tr; ov["min_edge"] = me
        r = backtest(bars, btc, s, {s: ov}, step)
        if r["trades"] >= MIN_TRADES: cands.append((r, ov))
    guard = base["avg_net_pct"] if base["trades"] >= MIN_TRADES else None
    ok = [c for c in cands if guard is None or c[0]["avg_net_pct"] >= guard]
    best = max(ok, key=lambda c: (c[0]["win_rate"], c[0]["avg_net_pct"])) if ok else None
    cur_wr = base["win_rate"] if base["trades"] >= MIN_TRADES else -1
    if best and best[0]["win_rate"] >= cur_wr + MIN_GAIN and P({s: best[1]}, s) != P({s: cur}, s):
        return best[1], base, best[0], len(cands), len(ok)
    return None, base, None, len(cands), len(ok)


def optimize(data, now, step, current, challengers=None):
    """Champion/challenger. The live (champion) settings change ONLY when a challenger, proposed earlier, beats them on
    trades entered AFTER it was proposed (fresh, out-of-sample bars): >= MIN_OOS trades, win rate >= champion's + MIN_GAIN
    and avg net % >= champion's on those same trades. A challenger is dropped after MAX_OOS fresh trades or MAX_AGE_DAYS
    without winning. When no challenger is pending, a new one is chosen by grid search on the whole window."""
    bars = {c: norm(data[c], now, step) for c in data}
    btc = {b["t"]: b["c"] for b in bars.get("BTC", [])}
    challengers = dict(challengers or {})
    live, chal_out, report = {}, {}, {}
    for s in DEFAULTS:
        cur = dict(current.get(s, {})); ch = challengers.get(s); rep = {"live_before": P({s: cur}, s)}
        if ch:
            since = int(ch["since"]); champ = backtest(bars, btc, s, {s: cur}, step, since)
            chal = backtest(bars, btc, s, {s: ch["params"]}, step, since)
            rep.update(challenger=P({s: ch["params"]}, s), challenger_since=et(since), fresh_champion=champ, fresh_challenger=chal)
            if chal["trades"] >= MIN_OOS and champ["trades"] > 0 and chal["win_rate"] >= champ["win_rate"] + MIN_GAIN \
                    and chal["avg_net_pct"] >= champ["avg_net_pct"]:
                cur = dict(ch["params"]); ch = None; rep["decision"] = "challenger PROMOTED to live"
            elif chal["trades"] >= MIN_OOS and champ["trades"] == 0 and chal["avg_net_pct"] > 0 and chal["win_rate"] >= 50:
                cur = dict(ch["params"]); ch = None; rep["decision"] = "challenger PROMOTED (live took no fresh trades)"
            elif chal["trades"] >= MAX_OOS or now - since > MAX_AGE_DAYS * 86400:
                ch = None; rep["decision"] = "challenger dropped (did not beat live)"
            else:
                rep["decision"] = "challenger still on trial"
        if not ch:
            new, base, res, nc, nok = search(bars, btc, s, cur, step)
            rep.update(window_live=base, candidates_with_enough_trades=nc, passed_profit_guard=nok)
            if new:
                ch = {"params": new, "since": int(now)}; rep["new_challenger"] = P({s: new}, s); rep["new_challenger_backtest"] = res
                rep["decision"] = (rep.get("decision", "") + "; new challenger proposed").lstrip("; ")
            else:
                rep["decision"] = (rep.get("decision", "") + "; no better settings found").lstrip("; ")
        live[s] = cur
        if ch: chal_out[s] = ch
        rep["live_after"] = P({s: cur}, s); report[s] = rep
    return {"params": live, "challengers": chal_out, "report": report,
            "window": {c: [et(bars[c][WARMUP]["t"]) if len(bars[c]) > WARMUP else None, et(bars[c][-1]["t"]) if bars[c] else None] for c in bars}}


def main():
    a = sys.argv
    if a[1] == "stream":
        state = json.load(open(a[2])) or {}; data = json.load(open(a[3])); params = json.load(open(a[6])) if len(a) > 6 else {}
        print(json.dumps(stream(state, data, int(a[4]), int(a[5]), params), indent=1))
    elif a[1] == "optimize":
        data = json.load(open(a[2])); cur = json.load(open(a[5])) if len(a) > 5 else {}
        ch = json.load(open(a[6])) if len(a) > 6 else {}
        print(json.dumps(optimize(data, int(a[3]), int(a[4]), cur, ch), indent=1))


if __name__ == "__main__":
    main()
