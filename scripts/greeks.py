"""Entry Greeks for multi-leg option positions (Black-Scholes, implied volatility solved from each leg's entry price).

Library use: from greeks import position_greeks
CLI:         python3 greeks.py POSITIONS.json BARS.json > out.json

POSITIONS.json / BARS.json use the same format as weekly_opts.py (legs [{cid, right, strike, qty}], day, expiry, underlying,
entry_time = start of the bar whose close is the fill; for mode "follow" entry_time is the stock's bar END, as in weekly_opts).
Fixed assumptions: r = 4%, no dividends, calendar-day time to the expiry close (16:00 ET; 13:00 ET on 2026-11-27),
leg price = the entry bar close (no haircut), underlying = the underlying's close on the same bar.
Output per position (1 contract per leg, x100 multiplier):
  iv_entry_pct  mean IV of the short legs (credit structures) or long legs (debit structures), in %
  delta         net delta in shares (e.g. -12.3 = short ~12 shares of exposure)
  theta_day     net theta in $ per calendar day (positive = time decay earns)
  vega_1pct     net vega in $ per +1 percentage-point IV change
  gamma         net gamma in shares per $1 move
Legs whose price is below intrinsic or whose IV cannot be solved make the position "greeks: n/a".
"""
import json, math, sys, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
R = 0.04
CLOSE = {"2026-11-27": (13, 0)}


def _n(x): return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
def _N(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, v, right):
    if T <= 0 or v <= 0:
        return max(0.0, S - K) if right == "C" else max(0.0, K - S), 0, 0, 0, 0
    sq = v * math.sqrt(T); d1 = (math.log(S / K) + (R + 0.5 * v * v) * T) / sq; d2 = d1 - sq
    disc = math.exp(-R * T)
    if right == "C":
        price = S * _N(d1) - K * disc * _N(d2); delta = _N(d1)
        theta = -S * _n(d1) * v / (2 * math.sqrt(T)) - R * K * disc * _N(d2)
    else:
        price = K * disc * _N(-d2) - S * _N(-d1); delta = _N(d1) - 1
        theta = -S * _n(d1) * v / (2 * math.sqrt(T)) + R * K * disc * _N(-d2)
    gamma = _n(d1) / (S * sq); vega = S * _n(d1) * math.sqrt(T)
    return price, delta, gamma, theta / 365.0, vega


def implied_vol(price, S, K, T, right):
    intrinsic = max(0.0, S - K * math.exp(-R * T)) if right == "C" else max(0.0, K * math.exp(-R * T) - S)
    if T <= 0 or price <= intrinsic + 1e-6: return None
    lo, hi = 1e-3, 5.0
    if bs(S, K, T, hi, right)[0] < price: return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if bs(S, K, T, mid, right)[0] < price: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


def _bars(raw):
    out = {}
    for i, t in enumerate((raw or {}).get("time", [])):
        if raw["close"][i] is None: continue
        d = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY)
        out[d] = float(raw["close"][i])
    return out


def position_greeks(p, B):
    day = p["day"]; et = p.get("entry_time", "09:55")
    t0 = dt.datetime.fromisoformat(day + "T" + et + ":00").replace(tzinfo=NY)
    if p.get("mode") == "follow": t0 -= dt.timedelta(minutes=5)
    und = _bars(B.get(p.get("underlying", "SPY")))
    S = und.get(t0) or next((und[k] for k in sorted(und) if t0 <= k <= t0 + dt.timedelta(minutes=30)), None)
    if not S: return {"greeks": "n/a (no underlying price at entry)"}
    exp = dt.datetime.strptime(p["expiry"], "%Y%m%d")
    hh, mm = CLOSE.get(exp.date().isoformat(), (16, 0))
    T = ((exp.replace(hour=hh, minute=mm, tzinfo=NY) - (t0 + dt.timedelta(minutes=5))).total_seconds()) / (365 * 86400)
    tot = {"delta": 0.0, "gamma": 0.0, "theta_day": 0.0, "vega_1pct": 0.0}; ivs = []
    for lg in p["legs"]:
        px = _bars(B.get(str(lg["cid"])))
        price = px.get(t0) or next((px[k] for k in sorted(px) if t0 < k <= t0 + dt.timedelta(minutes=30)), None)
        if price is None: return {"greeks": "n/a (no option price at entry)"}
        iv = implied_vol(price, S, lg["strike"], T, lg["right"])
        if iv is None: return {"greeks": "n/a (IV not solvable)"}
        _, d, g, th, ve = bs(S, lg["strike"], T, iv, lg["right"])
        q = lg["qty"]
        tot["delta"] += q * d * 100; tot["gamma"] += q * g * 100
        tot["theta_day"] += q * th * 100; tot["vega_1pct"] += q * ve  # ve per 1.00 IV x100 multiplier /100 = per 1 pt
        if (p.get("kind") == "credit" and q < 0) or (p.get("kind") != "credit" and q > 0): ivs.append(iv)
    out = {k: round(v, 2) for k, v in tot.items()}
    out["iv_entry_pct"] = round(100 * sum(ivs) / len(ivs), 1) if ivs else None
    out["underlying_entry"] = round(S, 2); out["years_to_expiry"] = round(T, 5)
    return out


def main():
    P = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2]))
    print(json.dumps({"positions": [dict(id=p.get("id"), **position_greeks(p, B)) for p in P]}, indent=1))


if __name__ == "__main__":
    main()
