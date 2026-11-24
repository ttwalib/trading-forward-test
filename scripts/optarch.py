#!/usr/bin/env python3
"""Option history archive for Quantavius's own option strategies (added 2026-11-24, runbook item 58).

  python3 optarch.py snap REPO [SYMS]          nightly: today's option chain snapshot per underlying
  python3 optarch.py back REPO SYMS [MONTHS]   one-off backfill: daily bars of past contracts (default 33 months)
  python3 optarch.py chain REPO UND DAY        print one stored snapshot (for the lab and the morning)
  python3 optarch.py series REPO UND           print the stored daily bars of one underlying as JSON

Market data only (data.alpaca.markets, the same free plan and keys as fetch_free.py). Never a trading host, never an
order: scripts/no_orders.py checks it like every script.

SNAPSHOTS (going forward, the honest record of bid and ask): /v1beta1/options/snapshots/<UND> for contracts that expire
within SNAP_DAYS calendar days and have a strike within SNAP_BAND of the underlying's last close. Stored per day as
data/optarch/snap/<UND>/<DAY>.json.gz = {"und", "day", "taken_at_utc", "spot", "feed", "c": {OCC: [bid, ask, last,
iv, delta, gamma, theta, vega]}}. Values are as the feed reported them at taken_at_utc (the free plan's options feed is
"indicative": delayed and possibly wider than the real market; the lab treats it as the cost, not the mid).

BACKFILL (the past, for backtests): the free data host has no list of expired contracts, so candidate OCC symbols are
generated (every Friday expiry for SPY, QQQ and IWM, the third-Friday expiry for stocks; strikes on the exchange's
usual grid within BACK_BAND of the underlying's close about 30 days before expiry, calls and puts) and their daily
bars are requested; symbols that never existed simply return nothing. Stored as data/optarch/hist/<UND>.csv.gz with
columns occ,date,o,h,l,c,v,n,vw (date = New York trading date). Daily bars carry trades only, no bid or ask: a backtest
on them must charge a spread allowance (runbook OPTIONS TRACK).

Coverage, gaps and errors are written to ops/diag/optarch.json. Testing only, not financial advice.
"""
import csv, datetime as dt, gzip, io, json, os, sys, time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
NY = ZoneInfo("America/New_York"); UTC = dt.timezone.utc
SNAP_DAYS, SNAP_BAND, BACK_BAND = 50, 0.15, 0.12
INDEX = ("SPY", "QQQ", "IWM")


def F():
    import fetch_free
    return fetch_free


def universe(repo):
    u = json.load(open(os.path.join(repo, "data", "universe.json")))
    return list(INDEX) + sorted(set(u["watchlist"]) | set(u["control"]))


def closes(repo, sym):
    p = os.path.join(repo, "data", "bars", "1d", sym + ".jsonl"); out = {}
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                b = json.loads(l); out[dt.datetime.fromtimestamp(b["t"], NY).date().isoformat()] = b["c"]
    return dict(sorted(out.items()))


def hist_closes(repo, sym):
    """Daily closes from the archive (data/hist/1d/<SYM>.csv.gz) joined with the stored bars."""
    out = {}
    p = os.path.join(repo, "data", "hist", "1d", sym + ".csv.gz")
    if os.path.exists(p):
        with gzip.open(p, "rt") as f:
            r = csv.reader(f); head = next(r, None) or []
            it = head.index("t") if "t" in head else 0; ic = head.index("c") if "c" in head else 4
            for row in r:
                try: out[dt.datetime.fromtimestamp(int(float(row[it])), NY).date().isoformat()] = float(row[ic])
                except Exception: continue
    out.update(closes(repo, sym))
    return dict(sorted(out.items()))


def occ(und, exp, right, k):
    return "%s%s%s%08d" % (und, exp.strftime("%y%m%d"), right, int(round(k * 1000)))


def step(px, und):
    if und in INDEX: return 5.0   # round five-dollar strikes: the deepest index strikes, and a backfill of a size the free plan can carry
    return 0.5 if px < 25 else 1.0 if px < 100 else 2.5 if px < 250 else 5.0


def fridays(a, b, monthly):
    d = a + dt.timedelta(days=(4 - a.weekday()) % 7)
    while d <= b:
        if not monthly or 15 <= d.day <= 21: yield d
        d += dt.timedelta(days=7)


# ---------- snapshots ----------
def snap(repo, syms=None):
    ff = F(); day = dt.datetime.now(NY).date().isoformat(); res = {"day": day, "ok": [], "errors": {}, "contracts": 0, "bytes": 0}
    for und in syms or universe(repo):
        try:
            c = closes(repo, und); spot = list(c.values())[-1] if c else None
            if not spot: res["errors"][und] = "no close"; continue
            lim = (dt.date.today() + dt.timedelta(days=SNAP_DAYS)).isoformat()
            prm = {"feed": "indicative", "limit": 1000, "expiration_date_lte": lim,
                   "strike_price_gte": round(spot * (1 - SNAP_BAND), 2), "strike_price_lte": round(spot * (1 + SNAP_BAND), 2)}
            rows = {}; p = dict(prm)
            while True:
                j = json.loads(ff.get(ff.DATA + "/v1beta1/options/snapshots/" + und, p)); part = j.get("snapshots") or {}
                for k, v in part.items():
                    q = v.get("latestQuote") or {}; t = v.get("latestTrade") or {}; g = v.get("greeks") or {}
                    rows[k] = [q.get("bp"), q.get("ap"), t.get("p"), v.get("impliedVolatility"), g.get("delta"), g.get("gamma"), g.get("theta"), g.get("vega")]
                tok = j.get("next_page_token")
                if not tok: break
                p["page_token"] = tok; time.sleep(0.3)
            if not rows: res["errors"][und] = "empty chain"; continue
            out = {"und": und, "day": day, "taken_at_utc": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "spot": spot,
                   "feed": "indicative", "fields": ["bid", "ask", "last", "iv", "delta", "gamma", "theta", "vega"], "c": rows}
            d = os.path.join(repo, "data", "optarch", "snap", und); os.makedirs(d, exist_ok=True)
            b = gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 9)
            open(os.path.join(d, day + ".json.gz"), "wb").write(b)
            res["ok"].append(und); res["contracts"] += len(rows); res["bytes"] += len(b)
        except Exception as e: res["errors"][und] = str(e)[:200]
        time.sleep(0.3)
    diag(repo, "snap", res); return res


# ---------- backfill ----------
def back(repo, syms, months=33):
    ff = F(); today = dt.date.today(); a = today - dt.timedelta(days=months * 31); res = {"from": a.isoformat(), "per": {}, "errors": []}
    for und in syms:
        if os.path.exists(os.path.join(repo, "data", "optarch", "hist", und + ".csv.gz")) and not os.environ.get("OPTBACK_FORCE"):
            res["per"][und] = "already archived (set OPTBACK_FORCE=1 to redo)"; continue   # a rerun resumes where a cut-off run stopped
        c = hist_closes(repo, und)
        if not c: res["per"][und] = "no closes"; continue
        days = sorted(c); syms_ = set()
        for exp in fridays(a, today + dt.timedelta(days=45), monthly=und not in INDEX):
            ref = max((d for d in days if d <= (exp - dt.timedelta(days=30)).isoformat()), default=None)
            if not ref: continue
            px = c[ref]; s = step(px, und); lo, hi = px * (1 - BACK_BAND), px * (1 + BACK_BAND); k = (lo // s + 1) * s
            while k <= hi:
                for r in ("C", "P"): syms_.add(occ(und, exp, r, k))
                k += s
        syms_ = sorted(syms_); rows = []
        for i in range(0, len(syms_), 100):
            chunk = syms_[i:i + 100]
            try:
                got = ff.paged(ff.DATA + "/v1beta1/options/bars", {"symbols": ",".join(chunk), "timeframe": "1Day",
                               "start": a.isoformat() + "T00:00:00Z", "end": today.isoformat() + "T23:59:59Z", "limit": 10000, "sort": "asc"}, "bars")
                for o, bs in got.items():
                    for b in bs:
                        d = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(NY).date().isoformat()
                        rows.append([o, d, b.get("o"), b.get("h"), b.get("l"), b.get("c"), b.get("v"), b.get("n"), b.get("vw")])
            except Exception as e: res["errors"].append("%s %s: %s" % (und, chunk[0], str(e)[:160]))
            time.sleep(0.3)
        p = os.path.join(repo, "data", "optarch", "hist", und + ".csv.gz"); os.makedirs(os.path.dirname(p), exist_ok=True)
        old = []
        if os.path.exists(p):
            with gzip.open(p, "rt") as f: old = list(csv.reader(f))[1:]
        keep = {(r[0], r[1]): r for r in old}; keep.update({(r[0], r[1]): [str(x) if x is not None else "" for x in r] for r in rows})
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(["occ", "date", "o", "h", "l", "c", "v", "n", "vw"])
        for k_ in sorted(keep): w.writerow(keep[k_])
        open(p, "wb").write(gzip.compress(buf.getvalue().encode(), 9))
        res["per"][und] = {"candidates": len(syms_), "contracts_with_bars": len({r[0] for r in rows}), "bars": len(rows),
                           "first": min((r[1] for r in rows), default=None), "bytes": os.path.getsize(p)}
    diag(repo, "back", res); return res


def diag(repo, kind, res):
    p = os.path.join(repo, "ops", "diag", "optarch.json"); d = json.load(open(p)) if os.path.exists(p) else {}
    d[kind] = res; d[kind]["at_utc"] = dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(d, open(p, "w"), indent=1)


def chain(repo, und, day):
    return json.loads(gzip.decompress(open(os.path.join(repo, "data", "optarch", "snap", und, day + ".json.gz"), "rb").read()))


def series(repo, und):
    p = os.path.join(repo, "data", "optarch", "hist", und + ".csv.gz"); out = {}
    with gzip.open(p, "rt") as f:
        r = csv.DictReader(f)
        for x in r: out.setdefault(x["occ"], {})[x["date"]] = {k: float(x[k]) if x[k] else None for k in ("o", "h", "l", "c", "v", "vw")}
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "snap": print(json.dumps({k: v for k, v in snap(a[1], a[2].split(",") if len(a) > 2 else None).items() if k != "ok"}, indent=1)[:3000])
    elif a[0] == "back": print(json.dumps(back(a[1], a[2].split(","), int(a[3]) if len(a) > 3 else 33), indent=1)[:4000])
    elif a[0] == "chain": print(json.dumps(chain(a[1], a[2], a[3]), separators=(",", ":")))
    elif a[0] == "series": print(json.dumps(series(a[1], a[2]), separators=(",", ":")))
    else: sys.exit("unknown command")
