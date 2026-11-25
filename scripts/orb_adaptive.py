"""Adaptive opening-range breakout (stocks): score a day with the current settings, and tune them for the next day.

  score:    python3 orb_adaptive.py score BARS.json DAY PARAMS.json > score.json
  optimize: python3 orb_adaptive.py optimize BARS.json DAYS LIVE.json CHALLENGER.json > opt.json   (DAYS = comma-separated dates)

BARS.json: {"SPY": raw, "AAPL": raw, ...} raw IBKR 5-minute bars {"time","open","high","low","close"} (regular hours).
PARAMS.json: {"or_min": 15, "stop": "mid", "target_r": 2, "spy": false} ({} = the baseline A rules).
Same simulation as the fixed variants (orb_variants.py): first 5-minute close above the opening-range high, long only,
stop at the range midpoint or low, target at target_r x risk, flat by 15:55, 0.02% costs per side, one trade per stock a day.
optimize is champion/challenger: the live settings change ONLY when a challenger proposed on an earlier day beats them on
the days AFTER it was proposed (>= MIN_OOS trades, win rate +3 points, avg net R no worse). With no challenger pending, a
new one is picked from or_min (5, 10, 15, 30) x stop (mid, low) x target_r (1, 1.5, 2, 3) x SPY filter (off, on): the
highest win rate among settings with >= MIN_TRADES trades whose avg net R is no worse than live's (profit guard).
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
        if o <= stop: px, out = o, "stop"; break
        if l <= stop: px, out = stop, "stop"; break
        if o >= tgt: px, out = o, "target"; break
        if h >= tgt: px, out = tgt, "target"; break
        if hm(t) >= "15:50": px, out = c, "flat"; break
    if px is None: px, out = bars[-1][4], "flat (data ended)"
    return {"r_net": float(((px - e - (e + px) * Dec("0.02") / 100) / r).quantize(C)), "outcome": out,
            "entry_time": hm(eb[0] + dt.timedelta(minutes=5))}, None

DEFAULT = {"or_min": 15, "stop": "mid", "target_r": 2, "spy": False}
MIN_TRADES, MIN_GAIN = 10, 3.0
MIN_OOS, MAX_OOS, MAX_DAYS = 8, 25, 4  # challenger: promote after >= MIN_OOS fresh trades; drop after MAX_OOS trades or MAX_DAYS fresh days


def full(p): q = dict(DEFAULT); q.update(p or {}); return q


def label(p): q = full(p); return "%dm/%s/%sR%s" % (q["or_min"], q["stop"], q["target_r"], "/SPY" if q["spy"] else "")


def run_days(data, days, p):
    q = full(p); trades = []
    for day in days:
        spy = bars_of(data["SPY"], day) if "SPY" in data else []
        for sym in sorted(s for s in data if s != "SPY"):
            try: t, why = sim(bars_of(data[sym], day), q["or_min"], q["stop"], q["target_r"], q["spy"], spy)
            except Exception: t = None
            if t: t.update(date=day, symbol=sym, params=label(q)); trades.append(t)
    n = len(trades); w = sum(1 for t in trades if t["r_net"] > 0)
    return trades, {"trades": n, "win_rate": round(100 * w / n, 1) if n else None,
                    "avg_r_net": round(sum(t["r_net"] for t in trades) / n, 3) if n else None}


def main():
    import itertools
    a = sys.argv; data = json.load(open(a[2])); p = json.load(open(a[4])) if len(a) > 4 else {}
    if a[1] == "score":
        trades, summ = run_days(data, [a[3]], p)
        print(json.dumps({"params": full(p), "label": label(p), "summary": summ, "trades": trades}, indent=1)); return
    days = [d for d in a[3].split(",") if d]
    ch = json.load(open(a[5])) if len(a) > 5 else {}
    live, rep = full(p), {"live_before": full(p)}
    if ch.get("params"):
        fresh = [d for d in days if d > ch["since"]]
        _, champ = run_days(data, fresh, live); _, chal = run_days(data, fresh, ch["params"])
        rep.update(challenger=full(ch["params"]), challenger_since=ch["since"], fresh_days=fresh, fresh_live=champ, fresh_challenger=chal)
        if chal["trades"] >= MIN_OOS and champ["trades"] > 0 and chal["win_rate"] >= champ["win_rate"] + MIN_GAIN \
                and chal["avg_r_net"] >= champ["avg_r_net"]:
            live = full(ch["params"]); ch = {}; rep["decision"] = "challenger PROMOTED to live"
        elif chal["trades"] >= MAX_OOS or len(fresh) >= MAX_DAYS or ch["since"] < days[0]:
            ch = {}; rep["decision"] = "challenger dropped (did not beat live)"
        else:
            rep["decision"] = "challenger still on trial"
    if not ch.get("params"):
        _, base = run_days(data, days, live); cands = []
        for om, sr, tr, f in itertools.product((5, 10, 15, 30), ("mid", "low"), (1, 1.5, 2, 3), (False, True)):
            c = {"or_min": om, "stop": sr, "target_r": tr, "spy": f}; _, r = run_days(data, days, c)
            if r["trades"] >= MIN_TRADES: cands.append((r, c))
        guard = base["avg_r_net"] if base["trades"] >= MIN_TRADES else None
        ok = [c for c in cands if guard is None or c[0]["avg_r_net"] >= guard]
        best = max(ok, key=lambda c: (c[0]["win_rate"], c[0]["avg_r_net"])) if ok else None
        cur_wr = base["win_rate"] if base["trades"] >= MIN_TRADES else -1
        rep.update(window_live=base, candidates_with_enough_trades=len(cands), passed_profit_guard=len(ok))
        if best and best[0]["win_rate"] >= cur_wr + MIN_GAIN and full(best[1]) != live:
            ch = {"params": full(best[1]), "since": days[-1]}; rep["new_challenger"] = ch["params"]; rep["new_challenger_backtest"] = best[0]
            rep["decision"] = (rep.get("decision", "") + "; new challenger proposed").lstrip("; ")
        else:
            rep["decision"] = (rep.get("decision", "") + "; no better settings found").lstrip("; ")
    print(json.dumps({"params": live, "label": label(live), "challenger": ch, "report": rep, "days": days}, indent=1))


if __name__ == "__main__":
    main()
