import json, sys, datetime as dt
from decimal import Decimal as Dec, ROUND_DOWN, ROUND_HALF_UP
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York"); C = Dec("0.01")
def D(x): return Dec(str(x)).quantize(C, rounding=ROUND_HALF_UP)
def hm(t): return t.strftime("%H:%M")
def bars_of(d):
    if "start" in d:
        t0 = dt.datetime.fromisoformat(d["start"].replace("Z", "+00:00")); s = int(d.get("step", 300))
        n = len(d["c"]); assert all(len(d[k]) == n for k in "ohl"), "o/h/l/c lengths differ"
        return [((t0 + dt.timedelta(seconds=s*i)).astimezone(NY), D(d["o"][i]), D(d["h"][i]), D(d["l"][i]), D(d["c"][i])) for i in range(n)]
    return [(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY), D(d["open"][i]), D(d["high"][i]), D(d["low"][i]), D(d["close"][i])) for i, t in enumerate(d["time"])]
def sim(sym, bars, day, now):
    bars = [b for b in bars if b[0].date().isoformat() == day and b[0].minute % 5 == 0 and "09:30" <= hm(b[0]) < "16:00"
            and hm(b[0] + dt.timedelta(minutes=5)) <= now]
    by = {hm(b[0]): b for b in bars}
    if not all(s in by for s in ("09:30", "09:35", "09:40")): return None, "no opening range"
    rng = [by[s] for s in ("09:30", "09:35", "09:40")]
    hi = max(b[2] for b in rng); lo = min(b[3] for b in rng); eb = None
    for b in bars:
        if hm(b[0]) < "09:45": continue
        if hm(b[0] + dt.timedelta(minutes=5)) > "15:30": break
        if b[4] > hi: eb = b; break
    if not eb: return None, "no breakout"
    e = eb[4]
    if e < 5: return None, "under $5"
    stop = ((hi + lo) / 2).quantize(C, rounding=ROUND_DOWN); r = e - stop
    if r <= 0 or r / e * 100 < Dec("0.05"): return None, "stop too tight"
    tgt = (e + 2 * r).quantize(C, rounding=ROUND_HALF_UP); x = None
    for t, o, h, l, c in bars:
        if t <= eb[0]: continue
        if o <= stop: x = (o, t, "stop (gap)"); break
        if l <= stop: x = (stop, t, "stop"); break
        if o >= tgt: x = (o, t, "target (gap)"); break
        if h >= tgt: x = (tgt, t, "target"); break
        if hm(t) >= "15:50": x = (c, t + dt.timedelta(minutes=5), "flat by close"); break
    if not x:
        last_end = hm(bars[-1][0] + dt.timedelta(minutes=5))
        x = (bars[-1][4], bars[-1][0] + dt.timedelta(minutes=5), "open" if last_end < "15:55" else "flat (last bar)")
    px, xt, out = x; cost = (e + px) * Dec("0.02") / 100
    q = lambda v: float(v.quantize(C))
    return {"date": day, "symbol": sym, "outcome": out, "r_net": q((px - e - cost) / r),
            "entry_time": hm(eb[0] + dt.timedelta(minutes=5)), "entry": q(e), "stop": q(stop), "target": q(tgt),
            "exit_time": hm(xt), "exit": q(px), "or_low": q(lo), "or_high": q(hi), "r_gross": q((px - e) / r)}, None
data = json.load(open(sys.argv[1])); day = sys.argv[2]; now = sys.argv[3] if len(sys.argv) > 3 else "16:00"
trades, skipped = [], {}
for sym, d in sorted(data.items()):
    try: t, why = sim(sym, bars_of(d), day, now)
    except Exception as ex: t, why = None, "bad data: %s" % ex
    if t: trades.append(t)
    else: skipped[sym] = why
print(json.dumps({"date": day, "checked": len(data), "trades": trades, "skipped": skipped,
                  "day_total_r_net": round(sum(t["r_net"] for t in trades), 2)}, indent=1))
