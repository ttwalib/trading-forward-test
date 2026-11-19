"""Deep-OTM SPY credit spreads (D2 put side, D3 call side): simulate open and closed spreads from real option bars.

Usage: python3 deep_otm.py spreads.json bars.json NOW_EPOCH
spreads.json: [{"day":"2026-11-16","side":"put"|"call","expiry":"20261118","short_id":..,"long_id":..,
                "short_strike":..,"long_strike":..}]  (written when each spread is opened at 10:00 ET)
bars.json: {"SPY": <raw 5-min bars>, "<contract id>": <raw 5-min bars>, ...}  raw IBKR form {"time","open","high","low","close"}

Rules (fixed in advance):
- Open at 10:00 ET: credit = short leg close of the 09:55 bar minus long leg close of the 09:55 bar, after a haircut of
  max(2.5%, $0.01) per leg (sell lower, buy higher). If either leg has no 09:55 bar, use its first bar up to 10:30 (open price).
  Skip the spread if the credit is under $0.05.
- Max risk = strike width - credit. Results are in % of max risk.
- Marked on every later 5-min bar close (each leg carries its last traded price forward); cost to close = short + haircut
  - (long - haircut), floored at 0.
- Take profit when the cost to close is <= 50% of the credit; stop when it is >= 3x the credit (a loss of 2x the credit).
- Otherwise hold to expiry: settle at intrinsic value from SPY's last regular bar on the expiry day (the 15:55 bar, or the
  12:55 bar on the 2026-11-27 half day), capped at the width.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import tcal as _tcal
import json, sys, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
LAST_BAR = {d.isoformat(): "%02d:%02d" % divmod(int(t[:2]) * 60 + int(t[3:]) - 5, 60) for d, t in _tcal.HALF.items()}  # early-close days (from tcal.py)


def hc(p): return max(0.025 * p, 0.01)


def bars(raw):
    out = []
    for i, t in enumerate(raw.get("time", [])):
        if raw["close"][i] is None: continue
        d = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY)
        out.append((d, float(raw["open"][i]), float(raw["close"][i])))
    return sorted(out)


def sim(sp, B, now):
    S, L = bars(B.get(str(sp["short_id"]), {})), bars(B.get(str(sp["long_id"]), {}))
    spy = bars(B.get("SPY", {}))
    nowd = dt.datetime.fromtimestamp(now, NY)
    done = lambda d: d + dt.timedelta(minutes=5) <= nowd
    day = sp["day"]; width = abs(sp["short_strike"] - sp["long_strike"])
    base = dict(sp, width=width)
    def at_open(series):
        same = [b for b in series if b[0].date().isoformat() == day]
        x = [b for b in same if b[0].strftime("%H:%M") == "09:55"]
        if x: return x[0][2]
        y = [b for b in same if "10:00" <= b[0].strftime("%H:%M") <= "10:30"]
        return y[0][1] if y else None
    s0, l0 = at_open(S), at_open(L)
    if s0 is None or l0 is None: return dict(base, status="no option data at open")
    credit = (s0 - hc(s0)) - (l0 + hc(l0))
    if credit < 0.05: return dict(base, status="skipped: credit under $0.05", credit=round(credit, 2))
    maxrisk = width - credit
    start = dt.datetime.fromisoformat(day + "T10:00:00").replace(tzinfo=NY)
    times = sorted({b[0] for b in S + L if b[0] >= start and done(b[0])})
    si = {b[0]: b[2] for b in S}; li = {b[0]: b[2] for b in L}
    sp_last, lp_last = s0, l0
    exp = dt.datetime.strptime(sp["expiry"], "%Y%m%d").date()
    res = None
    for t in times:
        if t.date() > exp: break
        sp_last = si.get(t, sp_last); lp_last = li.get(t, lp_last)
        cost = max((sp_last + hc(sp_last)) - max(lp_last - hc(lp_last), 0), 0.0)
        if cost <= 0.5 * credit: res = (cost, t, "take profit (50%)"); break
        if cost >= 3 * credit: res = (cost, t, "stop (2x credit)"); break
    if res is None:
        lb = LAST_BAR.get(exp.isoformat(), "15:55")
        last = [b for b in spy if b[0].date() == exp and b[0].strftime("%H:%M") == lb and done(b[0])]
        if last:
            px = last[0][2]
            k_s, k_l = sp["short_strike"], sp["long_strike"]
            if sp["side"] == "put": val = max(0, k_s - px) - max(0, k_l - px)
            else: val = max(0, px - k_s) - max(0, px - k_l)
            res = (min(max(val, 0), width), last[0][0] + dt.timedelta(minutes=5), "expired (SPY %.2f)" % px)
    if res is None:
        cost = max((sp_last + hc(sp_last)) - max(lp_last - hc(lp_last), 0), 0.0)
        return dict(base, status="open", credit=round(credit, 2), max_risk=round(maxrisk, 2), mark=round(cost, 2),
                    pct=round(100 * (credit - cost) / maxrisk, 1))
    cost, t, why = res
    return dict(base, status="closed", credit=round(credit, 2), max_risk=round(maxrisk, 2), exit_cost=round(cost, 2),
                exit_time=t.strftime("%Y-%m-%d %H:%M"), reason=why, pct=round(100 * (credit - cost) / maxrisk, 1))


def main():
    sps = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2])); now = int(sys.argv[3])
    rows = [sim(s, B, now) for s in sps]
    summ = {}
    for side, name in (("put", "D2 SPY put credit spread"), ("call", "D3 SPY call credit spread")):
        c = [r for r in rows if r["side"] == side and r["status"] == "closed"]
        summ[name] = {"closed": len(c), "wins": sum(r["pct"] > 0 for r in c),
                      "avg_pct_of_risk": round(sum(r["pct"] for r in c) / len(c), 1) if c else None,
                      "open": sum(1 for r in rows if r["side"] == side and r["status"] == "open")}
    print(json.dumps({"summary": summ, "spreads": rows}, indent=1))


if __name__ == "__main__":
    main()
