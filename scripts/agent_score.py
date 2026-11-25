"""Agent-picked stocks: score one day of opening-range breakout trades on the agent's own picks.

Usage: python3 agent_score.py BARS.json DAY PARAMS.json > out.json
BARS.json: {"SPY": raw, "SYM": raw, ...} raw IBKR 5-minute bars {"time","open","high","low","close"} (regular hours) for
SPY and every stock the morning research picked for DAY. PARAMS.json: {} = baseline A (15-minute range, midpoint stop,
2R target, no SPY filter), or the adaptive settings {"or_min","stop","target_r","spy"}. Same simulation as the
watchlist variants: first 5-minute close above the opening-range high, long only, flat by 15:55, 0.02% costs per side,
one trade per stock a day. Each trade carries entry/exit times (exit_time = start of the exit bar, or 15:55 when flat),
in the form options_sim.py expects.
"""
import json, sys, datetime as dt
from decimal import Decimal as Dec, ROUND_DOWN, ROUND_HALF_UP
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York"); C = Dec("0.01")
def D(x): return Dec(str(x)).quantize(C, rounding=ROUND_HALF_UP)
def hm(t): return t.strftime("%H:%M")
def bars_of(d, day):
    if "start" in d:
        t0 = dt.datetime.fromisoformat(d["start"].replace("Z", "+00:00")); s = int(d.get("step", 300)); n = len(d["c"])
        assert all(len(d[k]) == n for k in "ohl"), "o/h/l/c lengths differ"
        b = [((t0 + dt.timedelta(seconds=s*i)).astimezone(NY), D(d["o"][i]), D(d["h"][i]), D(d["l"][i]), D(d["c"][i])) for i in range(n)]
    else:
        b = [(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY), D(d["open"][i]), D(d["high"][i]), D(d["low"][i]), D(d["close"][i])) for i, t in enumerate(d["time"])]
    return [x for x in b if x[0].date().isoformat() == day and x[0].minute % 5 == 0 and "09:30" <= hm(x[0]) < "16:00"]
def spy_ok(spy, entry_bar_start):
    """SPY filter: at the entry bar's close, SPY's matching bar closed above SPY's 9:30 open."""
    if not spy or hm(spy[0][0]) != "09:30": return None
    m = [b for b in spy if b[0] == entry_bar_start]
    return None if not m else m[0][4] > spy[0][1]
def sim(bars, or_min, stop_rule, tgt_r, use_filter, spy):
    n = or_min // 5
    if len(bars) <= n or hm(bars[0][0]) != "09:30" or any(hm(bars[i][0]) != hm(bars[0][0] + dt.timedelta(minutes=5*i)) for i in range(n)):
        return None, "no opening range"
    hi = max(b[2] for b in bars[:n]); lo = min(b[3] for b in bars[:n]); eb = None
    for b in bars[n:]:
        if hm(b[0] + dt.timedelta(minutes=5)) > "15:30": break
        if b[4] > hi: eb = b; break
    if not eb: return None, "no breakout"
    if use_filter:
        ok = spy_ok(spy, eb[0])
        if ok is None: return None, "no SPY data"
        if not ok: return None, "SPY filter blocked"
    e = eb[4]
    if e < 5: return None, "under $5"
    stop = ((hi + lo) / 2 if stop_rule == "mid" else lo).quantize(C, rounding=ROUND_DOWN); r = e - stop
    if r <= 0 or r / e * 100 < Dec("0.05"): return None, "stop too tight"
    tgt = (e + Dec(str(tgt_r)) * r).quantize(C, rounding=ROUND_HALF_UP); px = out = None
    for t, o, h, l, c in bars:
        if t <= eb[0]: continue
        if o <= stop: px, out, xt = o, "stop", hm(t); break
        if l <= stop: px, out, xt = stop, "stop", hm(t); break
        if o >= tgt: px, out, xt = o, "target", hm(t); break
        if h >= tgt: px, out, xt = tgt, "target", hm(t); break
        if hm(t) >= "15:50": px, out, xt = c, "flat", "15:55"; break
    if px is None: px, out, xt = bars[-1][4], "flat (data ended)", hm(bars[-1][0] + dt.timedelta(minutes=5))
    return {"r_net": float(((px - e - (e + px) * Dec("0.02") / 100) / r).quantize(C)), "outcome": out,
            "entry_time": hm(eb[0] + dt.timedelta(minutes=5)), "exit_time": xt, "entry": float(e), "exit": float(px),
            "stop": float(stop), "target": float(tgt)}, None


DEFAULT = {"or_min": 15, "stop": "mid", "target_r": 2, "spy": False}


def main():
    data = json.load(open(sys.argv[1])); day = sys.argv[2]; p = dict(DEFAULT); p.update(json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {})
    spy = bars_of(data["SPY"], day) if "SPY" in data else []
    label = "%dm/%s/%sR%s" % (p["or_min"], p["stop"], p["target_r"], "/SPY" if p["spy"] else "")
    trades, skipped = [], {}
    for sym in sorted(s for s in data if s != "SPY"):
        try: t, why = sim(bars_of(data[sym], day), p["or_min"], p["stop"], p["target_r"], p["spy"], spy)
        except Exception as ex: t, why = None, "bad data: %s" % ex
        if t: t.update(symbol=sym, date=day, rules=label); trades.append(t)
        else: skipped[sym] = why
    rs = [t["r_net"] for t in trades]
    print(json.dumps({"rules": label, "trades": trades, "skipped": skipped, "count": len(rs),
                      "wins": sum(1 for x in rs if x > 0), "total_r_net": round(sum(rs), 2)}, indent=1))


if __name__ == "__main__":
    main()
