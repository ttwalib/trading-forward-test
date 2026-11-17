import json, sys, datetime as dt
from zoneinfo import ZoneInfo
# Variant O: express each closed baseline stock trade as a long at-the-money call (nearest expiry after today).
# Fills: option bar close at the stock's entry bar (else the next bar's open within 30 min); exit at the
# option bar where the stock trade exited (stop/target bar, or the 15:50 bar for the 15:55 flat exit).
# Open stock trades are marked at the latest option bar (status "open"), updated on each hourly check.
# Costs: half-spread haircut of 2.5% of the option price per side (minimum $0.02). Result in % of premium.
NY = ZoneInfo("America/New_York")
def hm(t): return t.strftime("%H:%M")
def bars_of(d):
    if "start" in d:
        t0 = dt.datetime.fromisoformat(d["start"].replace("Z", "+00:00")); s = int(d.get("step", 300)); n = len(d["c"])
        assert all(len(d[k]) == n for k in "ohl"), "o/h/l/c lengths differ"
        return [((t0 + dt.timedelta(seconds=s*i)).astimezone(NY), float(d["o"][i]), float(d["c"][i])) for i in range(n)]
    return [(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY), float(d["open"][i]), float(d["close"][i])) for i, t in enumerate(d["time"])]
def haircut(p): return max(0.025 * p, 0.02)
def shift(day, hhmm, minutes):
    t = dt.datetime.strptime(day + " " + hhmm, "%Y-%m-%d %H:%M") + dt.timedelta(minutes=minutes)
    return t.strftime("%H:%M")
trades = json.load(open(sys.argv[1]))["trades"]; opt = json.load(open(sys.argv[2])); day = sys.argv[3]
rows, skipped = [], {}
for t in trades:
    sym = t["symbol"]
    if sym not in opt: skipped[sym] = "no option data"; continue
    o = opt[sym]
    try: bars = [b for b in bars_of(o) if b[0].date().isoformat() == day]
    except Exception as ex: skipped[sym] = "bad option data: %s" % ex; continue
    by = {hm(b[0]): b for b in bars}
    eb_start = shift(day, t["entry_time"], -5)
    if eb_start in by: buy_raw, buy_t = by[eb_start][2], t["entry_time"]
    else:
        nxt = [b for b in bars if eb_start < hm(b[0]) <= shift(day, eb_start, 30)]
        if not nxt: skipped[sym] = "no option trade near entry"; continue
        buy_raw, buy_t = nxt[0][1], hm(nxt[0][0])
    is_open = t["outcome"] == "open"
    # open trades: mark at the latest option bar completed by the stock's last bar (exit_time = that bar's end)
    xb_start = shift(day, t["exit_time"], -5) if (t["outcome"].startswith("flat") or is_open) else t["exit_time"]
    upto = [b for b in bars if hm(b[0]) <= xb_start and hm(b[0]) >= eb_start]
    if not upto: skipped[sym] = "no option bar at exit"; continue
    sell_raw = upto[-1][2]
    buy, sell = buy_raw + haircut(buy_raw), max(sell_raw - haircut(sell_raw), 0.0)
    rows.append({"date": day, "symbol": sym, "contract": o.get("contract", ""), "entry_time": buy_t,
                 "option_entry": round(buy, 2), "exit_time": t["exit_time"], "option_exit": round(sell, 2),
                 "return_pct": round(100 * (sell - buy) / buy, 1), "status": "open" if is_open else "closed",
                 "stock_outcome": t["outcome"], "stock_r_net": t["r_net"]})
rs = [r["return_pct"] for r in rows if r["status"] == "closed"]
print(json.dumps({"date": day, "trades": rows, "skipped": skipped, "closed": len(rs), "open": len(rows) - len(rs),
                  "wins": sum(1 for x in rs if x > 0), "avg_return_pct": round(sum(rs) / len(rs), 1) if rs else None}, indent=1))
