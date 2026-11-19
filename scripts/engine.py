"""5-minute signal engine (added 2026-11-19). Runs on GitHub Actions every 5 minutes in market hours, right after
fetch_free.py, with no AI in the loop: fixed code detects the signals and seals them with a timestamp, the way a real
trading engine works. Nothing is ever traded.

  python3 engine.py REPO [NOW_ISO]

1. Builds a real-time overlay of today's 5-minute bars from Alpaca's free real-time IEX feed (one exchange, so prices
   are close to the consolidated tape but volume is partial). The overlay lives in a temporary folder and is never
   stored as bars: data/bars keeps the consolidated SIP bars.
2. Runs decisions.py candidates (baseline-A breakouts on the watchlist + control list, exact rules) up to now.
3. Every signal not sealed yet is appended to data/decisions/engine/DAY.jsonl with: detected_at, delay_min (detection
   time minus the signal bar's close), the ideal entry (signal close), the fill a real engine would get now
   (fill_price = latest IEX trade; IEX bid/ask beside it), the stop, and the features exactly as seen.
fills.py uses fill_price as the implementable entry for that signal, so the real detection delay is charged.
Keys: env ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY (repo secrets). Outside 09:45-15:35 ET on full trading days it
does nothing.
"""
import json, os, sys, tempfile, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal
from fetch_free import get, paged, DATA, iso, UTC

NY = ZoneInfo("America/New_York")


def main():
    repo = sys.argv[1]
    now = dt.datetime.fromisoformat(sys.argv[2]).astimezone(NY) if len(sys.argv) > 2 else dt.datetime.now(NY)
    day = now.date().isoformat(); hm = now.strftime("%H:%M")
    if not tcal.is_trading(day) or not ("09:45" <= hm <= "15:35"):
        print(json.dumps({"engine": "idle", "at": hm})); return
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); syms = U["watchlist"] + U["control"]
    sess = now.replace(hour=9, minute=30, second=0, microsecond=0)
    ov = tempfile.mkdtemp(prefix="qv_overlay_"); os.makedirs(os.path.join(ov, "5m"))
    log = {"engine": "run", "at": now.isoformat(timespec="seconds"), "errors": []}
    try:
        got = {}
        for i in range(0, len(syms), 30):
            got.update(paged(DATA + "/v2/stocks/bars", {"symbols": ",".join(syms[i:i + 30]), "timeframe": "5Min",
                             "start": iso(sess), "end": iso(now), "limit": 10000, "adjustment": "raw", "feed": "iex",
                             "sort": "asc"}, "bars"))
        cut = int(now.timestamp())
        for s, rows in got.items():
            with open(os.path.join(ov, "5m", s + ".jsonl"), "w") as f:
                for r in rows:
                    t = int(dt.datetime.fromisoformat(r["t"].replace("Z", "+00:00")).timestamp())
                    if t + 300 <= cut:
                        f.write(json.dumps({"t": t, "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": float(r.get("v") or 0),
                                            "src": "iex"}) + "\n")
    except Exception as e: log["errors"].append("iex bars: %s" % e)
    os.environ["QV_OVERLAY_DIR"] = ov
    import decisions
    rnd = now.replace(minute=now.minute - now.minute % 5).strftime("%H:%M")
    cands = [c for c in decisions.candidates(repo, day, rnd) if c.get("trade") and c["trade"].get("entry_time")]
    f = os.path.join(repo, "data", "decisions", "engine", day + ".jsonl"); os.makedirs(os.path.dirname(f), exist_ok=True)
    sealed = set()
    if os.path.exists(f):
        for line in open(f):
            if line.strip(): r = json.loads(line); sealed.add((r["symbol"], r["signal_end"]))
    new = [c for c in cands if (c["symbol"], c["trade"]["entry_time"]) not in sealed]
    if new:
        q = {}
        try:
            tr = json.loads(get(DATA + "/v2/stocks/trades/latest", {"symbols": ",".join(sorted({c["symbol"] for c in new})), "feed": "iex"}))
            qu = json.loads(get(DATA + "/v2/stocks/quotes/latest", {"symbols": ",".join(sorted({c["symbol"] for c in new})), "feed": "iex"}))
            for s in {c["symbol"] for c in new}:
                q[s] = {"p": (tr.get("trades") or {}).get(s, {}).get("p"), "bp": (qu.get("quotes") or {}).get(s, {}).get("bp"),
                        "ap": (qu.get("quotes") or {}).get(s, {}).get("ap")}
        except Exception as e: log["errors"].append("iex latest: %s" % e)
        with open(f, "a") as fh:
            for c in new:
                t = c["trade"]; se = t["entry_time"]
                sig = now.replace(hour=int(se[:2]), minute=int(se[3:]), second=0, microsecond=0)
                x = q.get(c["symbol"], {})
                fh.write(json.dumps({"id": c.get("id"), "symbol": c["symbol"], "list": c.get("list"), "signal_end": se,
                                     "decided_at": c.get("decided_at"), "detected_at": now.isoformat(timespec="seconds"),
                                     "delay_min": round((now - sig).total_seconds() / 60, 1), "ideal_entry": t.get("entry"),
                                     "stop": t.get("stop"), "fill_price": x.get("p"), "iex_bid": x.get("bp"), "iex_ask": x.get("ap"),
                                     "feed": "iex", "x": c.get("x")}, separators=(",", ":")) + "\n")
    log.update({"candidates": len(cands), "new": len(new)})
    os.makedirs(os.path.join(repo, "ops", "diag"), exist_ok=True)
    json.dump(log, open(os.path.join(repo, "ops", "diag", "engine.json"), "w"), indent=1)
    print(json.dumps(log))


if __name__ == "__main__":
    main()
