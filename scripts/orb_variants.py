import json, sys, datetime as dt
from decimal import Decimal as Dec, ROUND_DOWN, ROUND_HALF_UP
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York"); C = Dec("0.01")
VARIANTS = {  # name: (opening-range minutes, stop rule, target R, SPY filter)
    "A baseline 15m/mid/2R": (15, "mid", 2, False),
    "B 5m/mid/2R": (5, "mid", 2, False),
    "C 5m/mid/1.5R": (5, "mid", 1.5, False),
    "D baseline + SPY filter": (15, "mid", 2, True),
    "E 5m/mid/2R + SPY filter": (5, "mid", 2, True)}
SENT_VARIANTS = {  # baseline rules, gated by the 9:12 ET Reddit snapshot (watchlist stocks)
    "F baseline, Reddit chatter rising": lambda s: s.get("rising") is True,
    "G baseline, skip Reddit-hyped": lambda s: s.get("rising") is False}
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
        if o <= stop: px, out = o, "stop"; break
        if l <= stop: px, out = stop, "stop"; break
        if o >= tgt: px, out = o, "target"; break
        if h >= tgt: px, out = tgt, "target"; break
        if hm(t) >= "15:50": px, out = c, "flat"; break
    if px is None: px, out = bars[-1][4], "flat (data ended)"
    return {"r_net": float(((px - e - (e + px) * Dec("0.02") / 100) / r).quantize(C)), "outcome": out,
            "entry_time": hm(eb[0] + dt.timedelta(minutes=5))}, None
data = json.load(open(sys.argv[1])); day = sys.argv[2]
sent = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
spy = bars_of(data["SPY"], day) if "SPY" in data else []
trending = set(sent.get("trending", [])) if sent else set()
def run(name, syms, params, gate=None):
    om, sr, tr, f = params; trades = {}
    for sym in syms:
        if gate is not None and not gate(sent["symbols"].get(sym, {})): continue
        try: t, why = sim(bars_of(data[sym], day), om, sr, tr, f, spy)
        except Exception as ex: t, why = None, "bad data: %s" % ex
        if t: trades[sym] = t
    rs = [t["r_net"] for t in trades.values()]
    return {"trades": len(rs), "wins": sum(1 for x in rs if x > 0), "total_r_net": round(sum(rs), 2),
            "targets": sum(1 for t in trades.values() if t["outcome"] == "target"),
            "stops": sum(1 for t in trades.values() if t["outcome"] == "stop"), "detail": trades}
watch = sorted(s for s in data if s != "SPY" and s not in trending)
out = {name: run(name, watch, p) for name, p in VARIANTS.items()}
base = VARIANTS["A baseline 15m/mid/2R"]
if sent:
    for name, gate in SENT_VARIANTS.items(): out[name] = run(name, watch, base, gate)
    out["T Reddit-trending pool, baseline rules"] = run("T", sorted(s for s in data if s in trending), base)
print(json.dumps({"date": day, "spy_bars": len(spy), "sentiment": bool(sent), "trending": sorted(trending), "variants": out}, indent=1))
