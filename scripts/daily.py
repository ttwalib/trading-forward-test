"""Scripted daily work that runs on GitHub with no AI in the loop (added 2026-11-22, runbook CHANGES 2026-11-22 item 30).

  python3 daily.py crypto REPO [NOW]    one crypto-tracks checkpoint: the four tracks, the ledger, the ML shadow
                                        predictions and (first run at or after 16:00 New York) the daily review
  python3 daily.py ml REPO [DAY]        the nightly machine-learning job: rebuild the decision rows, score the shadow
                                        predictions, walk-forward evaluation and refit (never in the frozen holdout),
                                        drift check; summary in data/nightly/ml_report.json

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
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")

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


def ml_night(repo, day=None):
    """The steps the "ML nightly" AI task ran until 2026-11-22, in the same order: decisions.py build, ml.py score
    (results into the MLShadow ledger rows), ml.py train DAY (keeps the saved models in the frozen holdout), ml.py report."""
    import decisions, ml
    day = day or dt.datetime.now(tcal.NY).date().isoformat(); out = {"date": day, "ok": False, "steps": {}}
    path = os.path.join(repo, "data", "nightly", "ml_report.json")
    if tcal.D(day) < tcal.START or tcal.D(day) > tcal.FINAL_REPORT:
        out.update(ok=True, note="no ML work on this date"); jsave(path, out); return out
    try:
        b = decisions.build(repo); out["steps"]["build"] = b if isinstance(b, dict) and len(json.dumps(b, default=str)) < 2000 else "done"
        sc = ml.score(repo)
        if sc: ledger.add(repo, "MLShadow", sc)
        out["steps"]["scored"] = len(sc)
        ml.train(repo, day); out["steps"]["train"] = "done"
        rep = ml.report(repo, day); out["report"] = json.loads(json.dumps(rep, default=str)); out["ok"] = True
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
    jsave(path, out); return out

def _day_bars(repo, syms, day):
    """The day's 5-minute bars 09:30-16:00 New York from the store, in the shape orb_daily.py reads."""
    d0 = int(dt.datetime.fromisoformat(day).replace(tzinfo=NY, hour=9, minute=30).timestamp()); out = {}
    for s in syms:
        B = []
        p = os.path.join(repo, "data", "bars", "5m", s + ".jsonl")
        if os.path.exists(p):
            for line in open(p):
                if line.strip():
                    b = json.loads(line)
                    if d0 <= b["t"] < d0 + 23400: B.append(b)
        B.sort(key=lambda b: b["t"])
        if B and B[0]["t"] == d0:
            out[s] = {"time": [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
                      "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B], "close": [b["c"] for b in B]}
    return out


def sentiment(repo, day=None):
    """Morning Reddit snapshot from the ApeWisdom file GitHub fetched (scripts/ape.py), written to the Sentiment ledger
    with the pre-registered rules of scripts/sentiment.py. Replaces the 09:12 AI run (2026-11-24). Trending contract ids
    come from data/contracts.json when known, otherwise they are left empty."""
    import subprocess, tempfile, ledger
    day = day or dt.datetime.now(NY).date().isoformat()
    have = [r for r in ledger.load(repo, "Sentiment") if r.get("date") == day and r.get("symbol") != "-"]
    if have: return {"day": day, "status": "already logged", "rows": len(have)}
    f = os.path.join(repo, "data", "sentiment", "ape", day + ".json")
    A = jload(f, None)
    if not A or A.get("errors") or not A.get("pages"):
        ledger.add(repo, "Sentiment", [{"date": day, "symbol": "-", "pool": "unavailable"}])
        return {"day": day, "status": "unavailable", "errors": (A or {}).get("errors")}
    tmp = []
    for pg in A["pages"]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t: json.dump(pg, t); tmp.append(t.name)
    here = os.path.dirname(os.path.abspath(__file__))
    p = subprocess.run([sys.executable, "-I", os.path.join(here, "sentiment.py")] + tmp, capture_output=True, text=True)
    for t in tmp: os.remove(t)
    if p.returncode: raise SystemExit("sentiment.py failed: " + p.stderr[-300:])
    S = json.loads(p.stdout); C = jload(os.path.join(repo, "data", "contracts.json"), {}); rows = []
    for sym, r in S["symbols"].items():
        trend = sym in S["trending"]; cid = C.get(sym) if trend else None
        if isinstance(cid, dict): cid = cid.get("conid") or cid.get("contract_id") or cid.get("id")
        rows.append({"date": day, "symbol": sym, "pool": "trending" if trend else "watchlist", "mentions": r["mentions"],
                     "mentions_24h_ago": r["mentions_24h_ago"], "change_pct": r["change_pct"], "rank": r["rank"],
                     "upvotes": r["upvotes"], "rising": "yes" if r["rising"] else "no", "contract_id": cid})
    res = ledger.add(repo, "Sentiment", rows)
    return {"day": day, "status": "logged", "rows": len(rows), "trending": S["trending"], "ledger": res}


def stocks(repo, day=None, check_only=False):
    """16:12 scoring of baseline A on the watchlist and the same rules on the control list, from the stored 5-minute
    bars, with the frozen scripts/orb_daily.py. Replaces the 16:12 AI run (2026-11-24). Only on full trading days.
    If the ledger already has rows for the day (for example from the AI run), it compares instead of writing (parity)."""
    import subprocess, tempfile, ledger, tcal
    now = dt.datetime.now(NY); day = day or now.date().isoformat()
    cal = tcal.info(day) if hasattr(tcal, "info") else None
    full = cal.get("full_trading_day") if isinstance(cal, dict) else None
    if full is False: return {"day": day, "status": "not a full trading day"}
    U = jload(os.path.join(repo, "data", "universe.json"), {}); here = os.path.dirname(os.path.abspath(__file__)); res = {"day": day}
    for name, syms in (("watchlist", U["watchlist"]), ("control", U["control"])):
        bars = _day_bars(repo, syms, day)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t: json.dump(bars, t); tmp = t.name
        p = subprocess.run([sys.executable, "-I", os.path.join(here, "orb_daily.py"), tmp, day, "16:00"], capture_output=True, text=True); os.remove(tmp)
        if p.returncode: raise SystemExit("orb_daily failed: " + p.stderr[-300:])
        R = json.loads(p.stdout); res[name] = {"trades": R["trades"], "no_data": sorted(set(syms) - set(bars)), "total_r": R["day_total_r_net"]}
    old_w = [r for r in ledger.load(repo, "Trades") if r.get("date") == day]
    old_c = [r for r in ledger.load(repo, "VariantTrades") if r.get("date") == day and r.get("variant") == "AC control"]
    diffs = []
    for name, old in (("watchlist", old_w), ("control", old_c)):
        if not old: continue
        o = {r["symbol"]: r for r in old}; n = {t["symbol"]: t for t in res[name]["trades"]}
        for s in sorted(set(o) | set(n)):
            a, b = o.get(s), n.get(s)
            if a is None or b is None or a["outcome"] != b["outcome"] or abs(float(a["r_net"]) - b["r_net"]) > 0.005:
                diffs.append("%s %s: ledger %s vs script %s" % (name, s, a and (a["outcome"], a["r_net"]), b and (b["outcome"], b["r_net"])))
    res["parity"] = {"compared": bool(old_w or old_c), "identical": not diffs, "diffs": diffs[:20]}
    if not check_only and not old_w and not old_c:
        ledger.add(repo, "Trades", res["watchlist"]["trades"])
        ledger.add(repo, "VariantTrades", [{"date": day, "variant": "AC control", "symbol": t["symbol"], "outcome": t["outcome"],
                                            "r_net": t["r_net"], "entry_time": t["entry_time"]} for t in res["control"]["trades"]])
        jsave(os.path.join(repo, "data", "state", "stocks_scored.json"), {"last_day": day, "at": now.strftime("%Y-%m-%d %H:%M"),
              "baseline_trades": len(res["watchlist"]["trades"]), "control_trades": len(res["control"]["trades"]),
              "no_data": res["watchlist"]["no_data"] + res["control"]["no_data"], "by": "github"})
        res["written"] = True
    jsave(os.path.join(repo, "ops", "diag", "daily_stocks.json"), {"day": day, "at": now.strftime("%Y-%m-%d %H:%M"), "ok": True,
          "parity": res["parity"], "baseline_trades": len(res["watchlist"]["trades"]), "control_trades": len(res["control"]["trades"]),
          "no_data": res["watchlist"]["no_data"] + res["control"]["no_data"], "written": res.get("written", False)})
    return res


def main():
    a = sys.argv[1:]
    if a[0] == "crypto": print(json.dumps(crypto(a[1], a[2] if len(a) > 2 else None), indent=1))
    elif a[0] == "ml":
        r = ml_night(a[1], a[2] if len(a) > 2 else None)
        print(json.dumps({k: r[k] for k in r if k != "report"}, indent=1, default=str)[:3000])
    elif a[0] == "sentiment": print(json.dumps(sentiment(a[1], a[2] if len(a) > 2 else None), indent=1))
    elif a[0] in ("stocks", "stocks-check"):
        r = stocks(a[1], a[2] if len(a) > 2 else None, check_only=a[0] == "stocks-check")
        print(json.dumps({k: (v if k in ("day", "parity", "status", "written") else {"n": len(v["trades"]), "total_r": v["total_r"], "no_data": v["no_data"]}) for k, v in r.items()}, indent=1))
    else: raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
