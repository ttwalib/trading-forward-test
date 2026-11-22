"""Scripted daily work that runs on GitHub with no AI in the loop (added 2026-11-22, runbook CHANGES 2026-11-22 item 30).

  python3 daily.py crypto REPO [NOW]    one crypto-tracks checkpoint: the four tracks, the ledger, the ML shadow
                                        predictions and (first run at or after 16:00 New York) the daily review

Until 2026-11-22 an AI task did these steps by hand eight times a day: it read the state from the sheet, ran the same
scripts and wrote the rows back. Nothing in the rules changed: this file only calls the existing scripts
(crypto_tracks.py, ledger.py, ml.py) in the same order with the same inputs. The state now lives in the repo:

  data/state/crypto.json       {"tracks": {track: state}, "live": {"15m": {}, "1h": {}}, "challengers": {...},
                                "last_review": "YYYY-MM-DD"}
  data/state/crypto_log.jsonl  one line per strategy and bar size at each daily review (the old "Adaptive" change log)
  data/state/crypto_open.json  open and pending positions after the last run (for the sheet and the dashboard)
  ops/diag/daily_crypto.json   what the last run did

The repo ledger (data/ledger) is the record; an evening task copies it into the sheet for reading.
"""
import json, os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crypto_tracks, hist, ledger, tcal

COINS = ["BTC", "ETH", "SOL", "DOGE", "SHIB", "AVAX", "LINK"]
TRACKS = [("15m fixed", "15m", 900, 400), ("15m adaptive", "15m", 900, 400),
          ("1h fixed", "1h", 3600, 300), ("1h adaptive", "1h", 3600, 300)]
C = lambda x: json.dumps(x, separators=(",", ":"))


def jload(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), indent=1); os.replace(tmp, path)


def export(repo, tf, now, syms, n):
    """The same bars hist.py export gives: the last n bars that closed before now, in the raw form the scripts read."""
    step = hist.SECS[tf]; out = {}
    for s in syms:
        B = [b for b in hist.load(repo, tf, s) if b["t"] + step <= now][-n:]
        out[s] = {"time": [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
                  "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B],
                  "close": [b["c"] for b in B], "volume": [b.get("v", 0) for b in B]}
    return out


def label(track, live, tf, strat):
    if track.endswith("fixed"): return "original"
    o = (live.get(tf) or {}).get(strat) or {}
    return C(o) if o else "original"


def crypto(repo, now=None):
    now = int(now or time.time()); ny = dt.datetime.fromtimestamp(now, tcal.NY)
    day = ny.date().isoformat(); nowny = ny.strftime("%Y-%m-%d %H:%M"); info = tcal.info(day)
    diag = {"at": dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nowny": nowny, "ok": False}
    dpath = os.path.join(repo, "ops", "diag", "daily_crypto.json")
    if not info["crypto_test_active"]:
        diag.update(ok=True, note="crypto tracks are over"); jsave(dpath, diag); return diag
    spath = os.path.join(repo, "data", "state", "crypto.json"); S = jload(spath, None)
    if S is None: raise SystemExit("data/state/crypto.json is missing: refusing to start the tracks from nothing")
    live, chal = S.get("live") or {"15m": {}, "1h": {}}, S.get("challengers") or {"15m": {}, "1h": {}}
    bars = {"15m": export(repo, "15m", now, COINS, 400), "1h": export(repo, "1h", now, COINS, 300)}
    rows, openp, per, gaps = [], [], {}, {}
    for track, tf, step, _ in TRACKS:
        params = {} if track.endswith("fixed") else (live.get(tf) or {})
        o = crypto_tracks.stream(S["tracks"].get(track) or {}, bars[tf], now, step, params)
        S["tracks"][track] = o["state"]
        for r in o["closed"] + [p for p in o["open"] if p.get("entry_time")]:
            rows.append({"track": track, "strategy": r["strategy"], "symbol": r["symbol"], "status": r["status"],
                         "entry_time": r["entry_time"], "entry": r["entry"], "stop": r["stop"], "exit_time": r["exit_time"],
                         "exit": r["exit_or_mark"], "reason": r["reason"], "r": r["r"], "pct": r["pct"],
                         "gross_pct": r["gross_pct"], "settings": label(track, live, tf, r["strategy"])})
        openp += [dict(p, track=track) for p in o["open"]]
        cl = o["closed"]; per[track] = {"closed": len(cl), "wins": sum(1 for r in cl if r["r"] > 0),
                                         "total_r": round(sum(r["r"] for r in cl), 2), "open": len(o["open"])}
        g = {c: v["gap_bars"] for c, v in o["coverage"].items() if v["gap_bars"]}
        if g: gaps[track] = g
    if rows: ledger.add(repo, "CryptoTracks", rows)
    jsave(spath, S)                       # state and ledger are saved together, before the optional steps below
    jsave(os.path.join(repo, "data", "state", "crypto_open.json"), {"at": nowny, "open": openp})
    diag.update(tracks=per, gaps=gaps, ledger_rows=len(rows))
    try:                                  # ML shadow: predictions for newly opened trades, before their outcome
        import ml
        pr = ml.predict_crypto(repo, nowny)
        if pr: ledger.add(repo, "MLShadow", pr)
        diag["ml_predictions"] = len(pr)
    except Exception as e:
        diag["ml_error"] = "%s: %s" % (type(e).__name__, e)
    if ny.hour >= 16 and S.get("last_review") != day:        # daily review: champion / challenger, never in the holdout
        log = []
        if info["frozen"]:
            log = [{"at": nowny, "track": tf + " adaptive", "decision": "frozen holdout: no retune"} for tf in ("15m", "1h")]
        else:
            for tf, step in (("15m", 900), ("1h", 3600)):
                opt = crypto_tracks.optimize(bars[tf], now, step, live.get(tf) or {}, chal.get(tf) or {})
                live[tf], chal[tf] = opt["params"], opt["challengers"]
                win = [w for v in opt["window"].values() for w in v if w]
                for s, rep in opt["report"].items():
                    log.append({"at": nowny, "track": tf + " adaptive", "strategy": s, "decision": rep.get("decision"),
                                "new_challenger": rep.get("new_challenger"), "live_before": rep.get("live_before"),
                                "live_after": rep.get("live_after"), "window": [min(win), max(win)] if win else None,
                                "challenger_since": rep.get("challenger_since"),
                                "live_result": rep.get("fresh_champion") or rep.get("window_live"),
                                "challenger_result": rep.get("fresh_challenger") or rep.get("new_challenger_backtest")})
        S.update(live=live, challengers=chal, last_review=day); jsave(spath, S)
        with open(os.path.join(repo, "data", "state", "crypto_log.jsonl"), "a") as f:
            for r in log: f.write(C(r) + "\n")
        diag["review"] = [{"track": r["track"], "strategy": r.get("strategy"), "decision": r["decision"]} for r in log]
    diag["ok"] = True; jsave(dpath, diag); return diag


def main():
    a = sys.argv[1:]
    if a[0] == "crypto": print(json.dumps(crypto(a[1], a[2] if len(a) > 2 else None), indent=1))
    else: raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
