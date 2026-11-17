"""Smart call selection for the agent-pick breakouts (variant "smart call").

  python3 smart_opt.py CAND.json DAY > pick.json

CAND.json: {"SYM": {"S": stock entry price, "entry_time": "HH:MM" (stock entry = end of the entry bar),
                    "expiry": "YYYYMMDD", "earnings_before_expiry": false,
                    "strikes": {"STRIKE": {"time": [...], "open": [...], "high": [...], "low": [...], "close": [...]}}}}
Rules (conventional for short directional option trades):
 - expiry 7-21 calendar days out (chosen before this script; avoids the fastest theta/gamma decay of near weeklies);
 - skip when an earnings date falls on or before expiry (implied-volatility crush risk);
 - strike: implied volatility is solved (Black-Scholes, r = 4%, no dividend) from each candidate's option price at the
   stock entry bar; the strike whose call delta is closest to TARGET_DELTA (0.60, slightly in the money) is chosen;
 - skip when implied volatility is above MAX_IV (150%) or no candidate has a price at entry.
Output: {"picks": {SYM: {"strike", "iv", "delta", "contract"}}, "skipped": {SYM: reason},
         "oopt": {SYM: bars of the chosen strike in options_sim.py format}}.
"""
import json, sys, math, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
TARGET_DELTA, MAX_IV, R = 0.60, 1.5, 0.04


def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_call(S, K, T, v):
    if v <= 0 or T <= 0: return max(S - K, 0.0)
    d1 = (math.log(S / K) + (R + v * v / 2) * T) / (v * math.sqrt(T)); d2 = d1 - v * math.sqrt(T)
    return S * ncdf(d1) - K * math.exp(-R * T) * ncdf(d2)


def implied_vol(price, S, K, T):
    lo, hi = 0.01, 5.0
    if price <= max(S - K * math.exp(-R * T), 0) + 1e-6 or price >= S: return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if bs_call(S, K, T, mid) > price: hi = mid
        else: lo = mid
    return (lo + hi) / 2


def delta(S, K, T, v):
    d1 = (math.log(S / K) + (R + v * v / 2) * T) / (v * math.sqrt(T)); return ncdf(d1)


def price_at_entry(b, day, entry_time):
    """Option bar close at the stock's entry bar (bar starting 5 minutes before entry_time), else next open within 30 min."""
    t_end = dt.datetime.strptime(day + " " + entry_time, "%Y-%m-%d %H:%M").replace(tzinfo=NY)
    start = t_end - dt.timedelta(minutes=5)
    bars = []
    for i, t in enumerate(b["time"]):
        tt = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY)
        if tt.date().isoformat() == day: bars.append((tt, float(b["open"][i]), float(b["close"][i])))
    for tt, o, c in bars:
        if tt == start: return c, t_end
    for tt, o, c in bars:
        if start < tt <= start + dt.timedelta(minutes=30): return o, tt
    return None, None


def main():
    cand = json.load(open(sys.argv[1])); day = sys.argv[2]
    picks, skipped, oopt = {}, {}, {}
    for sym, c in cand.items():
        if c.get("earnings_before_expiry"): skipped[sym] = "earnings on or before expiry"; continue
        exp = dt.datetime.strptime(c["expiry"] + " 16:00", "%Y%m%d %H:%M").replace(tzinfo=NY)
        best = None
        for ks, b in c.get("strikes", {}).items():
            K = float(ks); px, t0 = price_at_entry(b, day, c["entry_time"])
            if not px: continue
            T = (exp - t0).total_seconds() / (365 * 86400)
            v = implied_vol(px, float(c["S"]), K, T)
            if v is None: continue
            d = delta(float(c["S"]), K, T, v)
            if best is None or abs(d - TARGET_DELTA) < abs(best[2] - TARGET_DELTA): best = (ks, v, d)
        if not best: skipped[sym] = "no priced strike at entry"; continue
        if best[1] > MAX_IV: skipped[sym] = "implied volatility %.0f%% above cap" % (100 * best[1]); continue
        ks = best[0]; contract = "%s %s C %s" % (sym, c["expiry"], ks)
        picks[sym] = {"strike": float(ks), "iv": round(best[1], 3), "delta": round(best[2], 2), "contract": contract}
        oopt[sym] = dict(c["strikes"][ks]); oopt[sym]["contract"] = contract + " (d%.2f)" % best[2]
    print(json.dumps({"picks": picks, "skipped": skipped, "oopt": oopt}, indent=1))


if __name__ == "__main__":
    main()
