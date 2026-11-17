"""Streaming crypto forward test on 1-minute IBKR bars: X1-X3 (BTC, ETH, SOL) and M1-M3 (DOGE, SHIB, AVAX, LINK).

Usage: python3 crypto_stream.py state.json bars.json NOW_EPOCH > out.json
state.json: {} on the first run, then the "state" object this script printed last time.
bars.json : {"BTC": raw, "ETH": raw, ...} raw IBKR get_price_history arrays {"time","open","high","low","close","volume"}
            with step ONE_MIN. Each run passes the last ~200 bars before the previous run (indicator warm-up) plus
            every bar since. Only fully completed bars (bar start + 60 s <= NOW) are used, and each bar is
            processed exactly once (bars at or before state.last_t[coin] are warm-up only).
Rules are the hourly-bar rules unchanged, applied bar by bar on 1-minute bars (so "48 bars" = 48 minutes):
X1 EMA20 crosses above EMA50 while close > EMA100; exit on the cross down or a 2xATR14 stop.
X2 close < lower Bollinger(20,2) and RSI14 < 30; exit at the middle band, a 2xATR14 stop, or after 48 bars.
X3 close > prior 20-bar high; exit on close < prior 10-bar low or a 2xATR14 stop.
M1 volume >= 3x prior 24-bar average on a green bar closing in its top third and above the prior 12-bar high;
   2xATR stop then 3xATR chandelier trail; out after 24 bars.
M2 BTC up >= 1.5% over 4 bars while the coin moved less than half as much; target 3xATR, stop 2xATR, out after 12 bars.
M3 close above the prior 72-bar high and up >= 5% over 24 bars; 2xATR stop then 3xATR trail; out after 72 bars.
Signal on a bar's close, fill at the next bar's open; stops/targets checked inside each bar (stop first).
Costs per side: 0.2% majors, 0.3% meme/small caps. R is measured against the first stop.
"""
import json, sys, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
STEP = 60
MAJ, MEME = ("BTC", "ETH", "SOL"), ("DOGE", "SHIB", "AVAX", "LINK")
COST = {"X": 0.002, "M": 0.003}
MR = {"M1": (3, None, 24), "M2": (None, 3, 12), "M3": (3, None, 72)}  # trail xATR, target xATR, time stop bars


def et(t): return dt.datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d %H:%M")


def norm(raw, now):
    out = {}
    n = len(raw.get("close", [])); vol = raw.get("volume") or [0] * n
    for i in range(n):
        if raw["close"][i] is None: continue
        t = dt.datetime.strptime(raw["time"][i].replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
        t = int(t.timestamp()) // STEP * STEP
        if t + STEP > now: continue
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
    fam = p["s"][0]; c = COST[fam]; risk = p["entry"] - p["stop0"]
    net = px * (1 - c) - p["entry"] * (1 + c)
    return {"strategy": p["s"], "symbol": sym, "status": status, "entry_time": et(p["et"]), "entry": float("%.6g" % p["entry"]),
            "stop": float("%.6g" % p["stop0"]), "exit_time": et(t_exit), "exit_or_mark": float("%.6g" % px), "reason": why,
            "r": round(net / risk, 2), "pct": round(100 * net / p["entry"], 3), "gross_pct": round(100 * (px / p["entry"] - 1), 3)}


def run_x(sym, B, st, last_t, start, closed):
    cl = [b["c"] for b in B]; atr = atr14(B)
    e20, e50, e100 = ema(cl, 20), ema(cl, 50), ema(cl, 100); r14 = rsi14(cl); mid, lo = boll(cl)
    for s in ("X1", "X2", "X3"):
        k = sym + "|" + s; p = st.get(k)
        for i, b in enumerate(B):
            if b["t"] <= last_t: continue
            if p and p["st"] == "pending":
                p.update(st="open", entry=b["o"], stop0=b["o"] - 2 * p["a"], et=b["t"])
            if p and p["st"] == "open" and p.get("xn"):
                closed.append(rec(sym, p, b["o"], b["t"], p["why"], "closed")); p = None
            elif p and p["st"] == "open":
                why = "stop (gap)" if b["o"] <= p["stop0"] else "stop" if b["l"] <= p["stop0"] else None
                if why:
                    closed.append(rec(sym, p, b["o"] if why == "stop (gap)" else p["stop0"], b["t"], why, "closed")); p = None
                    continue
            if p: p["n"] = p.get("n", 0) + 1
            if atr[i] is None or i == 0: continue
            if p:
                why = None
                if s == "X1" and e20[i] is not None and e20[i-1] is not None and e20[i] < e50[i] and e20[i-1] >= e50[i-1]: why = "EMA cross down"
                if s == "X2":
                    if mid[i] is not None and b["c"] >= mid[i]: why = "middle band"
                    elif p["n"] >= 48: why = "48-bar time stop"
                if s == "X3" and i >= 10 and b["c"] < min(x["l"] for x in B[i-10:i]): why = "10-bar low"
                if why: p["xn"], p["why"] = True, why
                continue
            if b["t"] + STEP <= start: continue
            sig = False
            if s == "X1" and e100[i] is not None and e20[i-1] is not None and e50[i-1] is not None:
                sig = e20[i] > e50[i] and e20[i-1] <= e50[i-1] and b["c"] > e100[i]
            if s == "X2" and lo[i] is not None and r14[i] is not None: sig = b["c"] < lo[i] and r14[i] < 30
            if s == "X3" and i >= 20: sig = b["c"] > max(x["h"] for x in B[i-20:i])
            if sig: p = {"s": s, "st": "pending", "a": atr[i], "n": 0}
        st[k] = p


def run_m(sym, B, btc, st, last_t, start, closed):
    atr = atr14(B)
    for s in ("M1", "M2", "M3"):
        trail, tgt, tstop = MR[s]; k = sym + "|" + s; p = st.get(k)
        for i, b in enumerate(B):
            if b["t"] <= last_t: continue
            if p and p["st"] == "pending":
                e = b["o"]; a = p["a"]
                p.update(st="open", entry=e, stop0=e - 2 * a, stop=e - 2 * a, hh=e, tg=e + tgt * a if tgt else None, et=b["t"], n=0)
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
                if p["n"] >= tstop: p["xn"], p["why"] = True, "%d-bar time stop" % tstop
                continue
            if p or atr[i] is None or b["t"] + STEP <= start: continue
            sig = False
            if s == "M1" and i >= 24:
                avg = sum(x["v"] for x in B[i-24:i]) / 24; rng = b["h"] - b["l"]
                sig = (avg > 0 and b["v"] >= 3 * avg and b["c"] > b["o"] and rng > 0 and (b["c"] - b["l"]) / rng >= 2 / 3
                       and b["c"] > max(x["h"] for x in B[i-12:i]))
            if s == "M2" and i >= 4 and btc:
                t, t4 = b["t"], B[i-4]["t"]
                if t in btc and t4 in btc and t - t4 == 4 * STEP:
                    br = btc[t] / btc[t4] - 1; cr = b["c"] / B[i-4]["c"] - 1; sig = br >= 0.015 and cr < 0.5 * br
            if s == "M3" and i >= 72:
                sig = b["c"] > max(x["h"] for x in B[i-72:i]) and b["c"] / B[i-24]["c"] - 1 >= 0.05
            if sig: p = {"s": s, "st": "pending", "a": atr[i]}
        st[k] = p


def main():
    state = json.load(open(sys.argv[1])) or {}
    data = json.load(open(sys.argv[2])); now = int(sys.argv[3])
    st = state.get("pos", {}); last = state.get("last_t", {})
    start = state.get("start") or (now // STEP * STEP - STEP)
    closed, coverage = [], {}
    bars = {c: norm(data[c], now) for c in data}
    btc = {b["t"]: b["c"] for b in bars.get("BTC", [])}
    for c in MAJ + MEME:
        B = bars.get(c, [])
        lt = last.get(c, start - STEP)
        new = [b for b in B if b["t"] > lt]
        gap = bool(new) and new[0]["t"] - lt > 30 * 60 and c in last
        coverage[c] = {"new_bars": len(new), "warmup_bars": len(B) - len(new), "gap_minutes": (new[0]["t"] - lt) // 60 if gap else 0}
        if not B: continue
        if c in MAJ: run_x(c, B, st, lt, start, closed)
        else: run_m(c, B, btc, st, lt, start, closed)
        if new: last[c] = new[-1]["t"]
    openp = []
    for k, p in st.items():
        if not p: continue
        sym = k.split("|")[0]; B = bars.get(sym, [])
        if p["st"] == "pending": openp.append({"strategy": p["s"], "symbol": sym, "status": "pending (fills next bar)"}); continue
        if B: openp.append(rec(sym, p, B[-1]["c"], B[-1]["t"] + STEP, "open (marked at last close)", "open"))
    st = {k: v for k, v in st.items() if v}
    print(json.dumps({"closed": sorted(closed, key=lambda r: r["exit_time"]), "open": openp, "coverage": coverage,
                      "state": {"start": start, "last_t": last, "pos": st}}, indent=1))


if __name__ == "__main__":
    main()
