"""Weekly-option strategies (W1-W4): simulate multi-leg option positions from real 5-minute option bars.

  python3 weekly_opts.py POSITIONS.json BARS.json NOW_EPOCH > out.json

POSITIONS.json: [{"id": "W1 2026-11-18", "strategy": "W1", "day": "2026-11-18", "expiry": "20261120",
                  "underlying": "SPY", "kind": "credit" | "debit", "mode": "rule" | "follow",
                  "legs": [{"cid": 123, "right": "P", "strike": 650, "qty": -1}, ...],
                  "tp": 0.5, "sl": 2.0,                       # rule mode exits (see below)
                  "entry_time": "09:55", "exit_time": "15:50"}]  # bar starts (ET); follow mode uses both
BARS.json: {"SPY": raw 5-min bars, "<cid>": raw 5-min bars, ...} in raw IBKR form {"time","open","high","low","close"}.

Fixed rules:
- Fills: each leg at the close of the entry bar (rule mode: the 09:55 bar of "day", i.e. a 10:00 ET entry), else its
  first bar open up to 30 minutes later. Haircut max(2.5%, $0.01) per leg per side (buy higher, sell lower).
- Entry cost E = paid - received per share (debit > 0, credit < 0). Max risk: debit = E; credit = widest wing - credit.
- Rule mode, marked on every later 5-minute close (each leg carries its last price): credit structures take profit when
  P&L >= tp x credit (tp 0.5) and stop when the loss reaches sl x credit (sl 2.0, i.e. cost to close = 3x credit);
  debit structures take profit at P&L >= tp x debit (tp 1.0) and stop at a loss of sl x debit (sl 0.5).
  Otherwise held to expiry and settled at intrinsic value from the underlying's last regular bar of the expiry day
  (15:55, or 12:55 on the 2026-11-27 half day).
- Follow mode (W4): entry_time / exit_time / stock_outcome are the stock trade's (bar-end times as in the Trades tab);
  the spread fills at the close of the stock's entry bar and closes like options_sim.py: at the close of the bar ending
  at the stock exit for flat exits, of the bar after it for target/stop exits; open stock trades stay open (marked).
- Fees (IBKR, 1 contract per leg): per order max($1, $0.65 x legs) + $0.03 x legs; an opening and a closing order
  (no closing order if every leg expires worthless). Results in % of max risk, before and after fees.
- Entry Greeks (greeks.py): iv_entry_pct, delta (shares), theta_day ($/day), vega_1pct ($ per IV point), gamma; informational
  only, they never change entries or exits. For W4 the stock's own 5-minute bars must be in BARS.json under its symbol.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from greeks import position_greeks
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
LAST_BAR = {"2026-11-27": "12:55"}


def hc(p): return max(0.025 * p, 0.01)
def hm(t): return t.strftime("%H:%M")


def bars(raw):
    out = []
    for i, t in enumerate((raw or {}).get("time", [])):
        if raw["close"][i] is None: continue
        d = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY)
        out.append((d, float(raw["open"][i]), float(raw["close"][i])))
    return sorted(out)


def fee(nlegs): return round(max(1.0, 0.65 * nlegs) + 0.03 * nlegs, 2)


def close_value(legs, px):
    """Per-share cash from closing every leg now: sell longs at bid-ish, buy shorts back at ask-ish."""
    v = 0.0
    for lg in legs:
        p = px[lg["cid"]]
        v += (p - hc(p)) * lg["qty"] if lg["qty"] > 0 else -(p + hc(p)) * -lg["qty"]
    return v


def intrinsic(legs, s):
    v = 0.0
    for lg in legs:
        iv = max(0.0, s - lg["strike"]) if lg["right"] == "C" else max(0.0, lg["strike"] - s)
        v += iv * lg["qty"]
    return v


def sim(p, B, now):
    nowd = dt.datetime.fromtimestamp(now, NY); done = lambda d: d + dt.timedelta(minutes=5) <= nowd
    day, legs = p["day"], p["legs"]
    series = {lg["cid"]: bars(B.get(str(lg["cid"]))) for lg in legs}
    und = bars(B.get(p.get("underlying", "SPY")))
    et = p.get("entry_time", "09:55")
    t_entry = dt.datetime.fromisoformat(day + "T" + et + ":00").replace(tzinfo=NY)
    x_start = None
    if p["mode"] == "follow":  # stock times are bar ENDS (as in the Trades tab); same convention as options_sim.py
        t_entry -= dt.timedelta(minutes=5)
        so = p.get("stock_outcome", "")
        if not so.startswith("open"):
            xe = dt.datetime.fromisoformat(day + "T" + p["exit_time"] + ":00").replace(tzinfo=NY)
            x_start = xe - dt.timedelta(minutes=5) if so.startswith("flat") else xe
    entry = {}
    for cid, S in series.items():
        x = [b for b in S if b[0] == t_entry]
        if x: entry[cid] = x[0][2]; continue
        y = [b for b in S if t_entry < b[0] <= t_entry + dt.timedelta(minutes=30)]
        if not y: return dict(p, status="no option data at entry")
        entry[cid] = y[0][1]
    paid = sum((entry[l["cid"]] + hc(entry[l["cid"]])) * l["qty"] for l in legs if l["qty"] > 0)
    recv = sum((entry[l["cid"]] - hc(entry[l["cid"]])) * -l["qty"] for l in legs if l["qty"] < 0)
    E = paid - recv
    if p["kind"] == "credit":
        credit = -E
        if credit < 0.05: return dict(p, status="skipped: credit under $0.05", entry_value=round(credit, 2))
        wings = []
        for right in ("P", "C"):
            ks = [l["strike"] for l in legs if l["right"] == right]
            if len(ks) >= 2: wings.append(max(ks) - min(ks))
        risk = max(wings) - credit
    else:
        if E <= 0.05: return dict(p, status="skipped: debit under $0.05", entry_value=round(E, 2))
        risk = E
    base = credit if p["kind"] == "credit" else E
    exp = dt.datetime.strptime(p["expiry"], "%Y%m%d").date()
    times = sorted({b[0] for S in series.values() for b in S if b[0] > t_entry and done(b[0])})
    last = dict(entry); px_at = {cid: {b[0]: b[2] for b in S} for cid, S in series.items()}
    res = None
    for t in times:
        if p["mode"] == "rule" and t.date() > exp: break
        for cid in last: last[cid] = px_at[cid].get(t, last[cid])
        pnl = close_value(legs, last) - E
        if p["mode"] == "follow":
            if x_start is not None and t >= x_start:
                res = (pnl, t + dt.timedelta(minutes=5), "with the stock trade"); break
            continue
        if pnl >= p.get("tp", 0.5 if p["kind"] == "credit" else 1.0) * base:
            res = (pnl, t + dt.timedelta(minutes=5), "take profit"); break
        if pnl <= -p.get("sl", 2.0 if p["kind"] == "credit" else 0.5) * base:
            res = (pnl, t + dt.timedelta(minutes=5), "stop"); break
    worthless = False
    if res is None and p["mode"] == "rule":
        lb = LAST_BAR.get(exp.isoformat(), "15:55")
        u = [b for b in und if b[0].date() == exp and hm(b[0]) == lb and done(b[0])]
        if u:
            val = intrinsic(legs, u[0][2]); worthless = all(intrinsic([l], u[0][2]) == 0 for l in legs)
            res = (val - E, u[0][0] + dt.timedelta(minutes=5), "expired (%s %.2f)" % (p.get("underlying", "SPY"), u[0][2]))
    status = "closed" if res else "open"
    if res is None:
        res = (close_value(legs, last) - E, None, "open (marked)")
    pnl, t_exit, why = res
    fees = fee(len(legs)) + (0.0 if worthless else fee(len(legs)))
    return dict(p, status=status, entry_value=round(base, 2), max_risk=round(risk, 2), pnl_per_share=round(pnl, 2),
                exit_time=t_exit.strftime("%Y-%m-%d %H:%M") if t_exit else None, reason=why,
                gross_pct=round(100 * pnl / risk, 1), fees_usd=round(fees, 2),
                pct=round(100 * (pnl * 100 - fees) / (risk * 100), 1))


def main():
    P = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2])); now = int(sys.argv[3])
    rows = []
    for p in P:
        r = sim(p, B, now)
        if "entry_value" in r and "max_risk" in r:
            g = position_greeks(p, B)
            r.update({k: g.get(k) for k in ("iv_entry_pct", "delta", "theta_day", "vega_1pct", "gamma")} if "greeks" not in g
                     else {"greeks": g["greeks"]})
        rows.append(r)
    print(json.dumps({"positions": rows}, indent=1))


if __name__ == "__main__":
    main()
