"""In-house market regime and breadth (no external CSVs: computed from IBKR bars stored in the repo).

  python3 regime2.py REPO [DAY]      prints one JSON object; the orchestrator writes it to the Regime tab (L:T) and
                                     the ledger (ledger.py add REPO Regime ...)

Inputs: data/bars/1d/<SYM>.jsonl for watchlist + control (44 stocks), SPY, QQQ, IWM, VIX, VIX3M (if fetched), BTC;
        data/bars/1h/<COIN>.jsonl for the 7 crypto (resampled to UTC daily closes).
Outputs (as of the last daily bar on or before DAY):
- breadth20 / breadth50: % of the 44 stocks closing above their 20 / 50-day simple average (50 needs 50 bars,
  otherwise null).
- nh_nl: number of the 44 at a 20-day closing high minus number at a 20-day closing low (52-week needs a year of bars).
- qqq_vs20 / iwm_vs20: % distance of QQQ / IWM from their 20-day average.
- crypto_breadth20: % of the 7 coins above their 20-day average (daily closes from 1h bars).
- btc_rv30: BTC realized volatility, annualized %, from the last 30 daily log returns (365-day year).
- crypto_score: 0-100 (idea from tradermonty crypto-regime-analyzer, simplified): 40 x share of coins above SMA20
  + 30 if BTC above its SMA20 + 30 x (1 - min(1, btc_rv30 / 100)).
- vix_term: VIX / VIX3M (> 1 = backwardation = stress), null when VIX3M is not stored.
- breadth_score: 0-100 = mean of breadth20, breadth50 (if any) and 50 + 2.5 x nh_nl clipped to 0..100.
"""
import json, os, sys, math, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")


def daily(repo, sym):
    f = os.path.join(repo, "data", "bars", "1d", sym + ".jsonl"); out = []
    if os.path.exists(f):
        for line in open(f):
            if line.strip():
                b = json.loads(line); out.append((dt.datetime.fromtimestamp(b["t"], NY).date().isoformat(), b["c"]))
    return out


def daily_from_1h(repo, sym):
    f = os.path.join(repo, "data", "bars", "1h", sym + ".jsonl"); d = {}
    if os.path.exists(f):
        for line in open(f):
            if line.strip():
                b = json.loads(line); d[dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).date().isoformat()] = b["c"]
    return sorted(d.items())


def upto(series, day): return [c for d, c in series if d <= day]


def sma(xs, n): return sum(xs[-n:]) / n if len(xs) >= n else None


def compute(repo, day=None):
    day = day or dt.datetime.now(NY).date().isoformat()
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    names = U["watchlist"] + U["control"]
    a20 = a50 = n20 = n50 = hi = lo = 0
    for s in names:
        xs = upto(daily(repo, s), day)
        if len(xs) >= 20:
            n20 += 1; a20 += xs[-1] > sma(xs, 20)
            hi += xs[-1] >= max(xs[-20:]); lo += xs[-1] <= min(xs[-20:])
        if len(xs) >= 50: n50 += 1; a50 += xs[-1] > sma(xs, 50)
    out = {"date": day, "stocks_with_20d": n20,
           "breadth20": round(100 * a20 / n20, 1) if n20 >= 10 else None,
           "breadth50": round(100 * a50 / n50, 1) if n50 >= 10 else None,
           "nh_nl": hi - lo if n20 >= 10 else None}
    for e in ("QQQ", "IWM"):
        xs = upto(daily(repo, e), day); m = sma(xs, 20)
        out[e.lower() + "_vs20"] = round(100 * (xs[-1] / m - 1), 2) if m else None
    coins = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE", "SHIB"]; above = cnt = 0
    for c in coins:
        xs = upto(daily_from_1h(repo, c), day)
        if len(xs) >= 20: cnt += 1; above += xs[-1] > sma(xs, 20)
    out["crypto_breadth20"] = round(100 * above / cnt, 1) if cnt >= 4 else None
    btc = upto(daily(repo, "BTC"), day) or upto(daily_from_1h(repo, "BTC"), day)
    if len(btc) >= 31:
        r = [math.log(btc[i] / btc[i - 1]) for i in range(len(btc) - 30, len(btc))]
        m = sum(r) / 30; out["btc_rv30"] = round(100 * math.sqrt(sum((x - m) ** 2 for x in r) / 29 * 365), 1)
    else: out["btc_rv30"] = None
    if out["crypto_breadth20"] is not None and len(btc) >= 20:
        rv = out["btc_rv30"] if out["btc_rv30"] is not None else 60
        out["crypto_score"] = round(0.4 * out["crypto_breadth20"] + (30 if btc[-1] > sma(btc, 20) else 0)
                                    + 30 * (1 - min(1, rv / 100)), 1)
    else: out["crypto_score"] = None
    v, v3 = upto(daily(repo, "VIX"), day), upto(daily(repo, "VIX3M"), day)
    out["vix_term"] = round(v[-1] / v3[-1], 3) if v and v3 else None
    parts = [x for x in (out["breadth20"], out["breadth50"]) if x is not None]
    if out["nh_nl"] is not None: parts.append(max(0, min(100, 50 + 2.5 * out["nh_nl"])))
    out["breadth_score"] = round(sum(parts) / len(parts), 1) if parts else None
    out["regime_row_L_T"] = [out["breadth20"], out["breadth50"], out["nh_nl"], out["qqq_vs20"], out["iwm_vs20"],
                             out["crypto_breadth20"], out["btc_rv30"], out["crypto_score"], out["vix_term"]]
    return out


if __name__ == "__main__":
    print(json.dumps(compute(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
