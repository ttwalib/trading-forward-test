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
    if day > now.date().isoformat() or (day == now.date().isoformat() and now.strftime("%H:%M") < "16:05"):
        return {"day": day, "status": "session not closed yet"}
    U = jload(os.path.join(repo, "data", "universe.json"), {}); here = os.path.dirname(os.path.abspath(__file__)); res = {"day": day}
    for name, syms in (("watchlist", U["watchlist"]), ("control", U["control"])):
        bars = _day_bars(repo, syms, day)
        if not bars: return {"day": day, "status": "no stored bars for the %s yet" % name}
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


SYMS_ADAPTIVE = lambda U: ["SPY"] + list(U["watchlist"])


def adaptive(repo, day=None, check_only=False):
    """The adaptive stock review that the 17:20 AI task ran until 2026-11-25 (runbook ADAPTIVE STOCKS), with the same
    scripts and inputs: orb_adaptive.py score DAY with the live settings (rows to AdaptiveStocks), then orb_adaptive.py
    optimize over the last 3 stored trading days (champion/challenger; the new settings to data/state/stocks.json, one
    row to AdaptiveLog). Bars: the last 240 stored 5-minute bars of SPY and the 22 watchlist stocks that closed by 16:00
    New York on DAY (the store holds regular hours only, so that is DAY and the two trading days before it).
    If the ledgers already hold rows for DAY (for example from the AI run), it compares instead of writing (parity).
    Run report: ops/diag/daily_adaptive.json."""
    import subprocess, tempfile
    now = dt.datetime.now(NY); day = day or now.date().isoformat(); res = {"day": day}
    info = tcal.info(day)
    if not info.get("full_trading_day"): return {"day": day, "status": "not a full trading day"}
    if day > now.date().isoformat() or (day == now.date().isoformat() and now.strftime("%H:%M") < "16:05"):
        return {"day": day, "status": "session not closed yet"}
    U = jload(os.path.join(repo, "data", "universe.json"), {}); syms = SYMS_ADAPTIVE(U)
    close = int(dt.datetime.fromisoformat(day).replace(tzinfo=NY, hour=16).timestamp())
    bars = export(repo, "5m", close, syms, 240)
    spy_days = sorted({dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY).date().isoformat() for t in bars["SPY"]["time"]})
    if not spy_days or spy_days[-1] != day: return {"day": day, "status": "no stored bars for the day yet"}
    missing = [s for s in syms if not any(t.startswith(day) or dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(NY).date().isoformat() == day for t in bars[s]["time"])]
    days = spy_days[-3:]
    spath = os.path.join(repo, "data", "state", "stocks.json"); S = jload(spath, None)
    if S is None: raise SystemExit("data/state/stocks.json is missing: refusing to start the adaptive settings from nothing")
    live, chal = S.get("live") or {}, S.get("challenger") or {}
    here = os.path.dirname(os.path.abspath(__file__)); tmp = {}
    for k, v in (("bars", bars), ("live", live), ("chal", chal)):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t: json.dump(v, t); tmp[k] = t.name
    def run(*args):
        p = subprocess.run([sys.executable, "-I", os.path.join(here, "orb_adaptive.py")] + list(args), capture_output=True, text=True)
        if p.returncode: raise SystemExit("orb_adaptive failed: " + p.stderr[-300:])
        return json.loads(p.stdout)
    have_t = [r for r in ledger.load(repo, "AdaptiveStocks") if r.get("date") == day]
    have_l = [r for r in ledger.load(repo, "AdaptiveLog") if r.get("segment") == "stocks" and str(r.get("review_time", "")).startswith(day)]
    if have_l:                                  # the retune already ran: score with the settings it started from
        try: live_used = json.loads(have_l[-1]["old_settings"])
        except Exception: live_used = live
        with open(tmp["live"], "w") as f: json.dump(live_used, f)
    sc = run("score", tmp["bars"], day, tmp["live"])
    trades = [{"date": day, "symbol": t["symbol"], "outcome": t["outcome"], "r_net": t["r_net"],
               "entry_time": t["entry_time"], "params": t["params"]} for t in sc["trades"]]
    diffs = []
    if have_t:
        o = {r["symbol"]: r for r in have_t}; n = {t["symbol"]: t for t in trades}
        for s in sorted(set(o) | set(n)):
            a, b = o.get(s), n.get(s)
            if a is None or b is None or a["outcome"] != b["outcome"] or abs(float(a["r_net"]) - b["r_net"]) > 0.005 \
                    or a.get("params") != b.get("params"):
                diffs.append("%s: ledger %s vs script %s" % (s, a and (a["outcome"], a["r_net"], a.get("params")), b and (b["outcome"], b["r_net"], b["params"])))
    res.update(label=sc["label"], summary=sc["summary"], missing=missing, days=days)
    nowny = now.strftime("%Y-%m-%d %H:%M"); log_row = None
    if not have_l:
        opt = run("optimize", tmp["bars"], ",".join(days), tmp["live"], tmp["chal"]); rep = opt["report"]
        dec = rep.get("decision", "") + ((" | new challenger: " + C(rep["new_challenger"])) if rep.get("new_challenger") else "")
        lr = rep.get("fresh_live") or rep.get("window_live") or {}
        cr = rep.get("fresh_challenger") or rep.get("new_challenger_backtest") or {}
        log_row = {"review_time": nowny, "segment": "stocks", "track": "adaptive ORB", "strategy": "ORB", "changed": dec,
                   "old_settings": C(rep.get("live_before")), "new_settings": C(opt["params"]),
                   "lookback": ",".join(days) + (("; challenger since " + rep["challenger_since"]) if rep.get("challenger_since") else ""),
                   "trades_old": lr.get("trades"), "win_old": lr.get("win_rate"), "avg_old": lr.get("avg_r_net"),
                   "trades_new": cr.get("trades"), "win_new": cr.get("win_rate"), "avg_new": cr.get("avg_r_net"), "unit": "net R per trade"}
        res["retune"] = {"decision": dec, "live_after": opt["params"], "challenger": opt["challenger"]}
    else:
        res["retune"] = {"decision": "already logged: " + str(have_l[-1].get("changed"))}
    for f in tmp.values(): os.remove(f)
    res["parity"] = {"compared": bool(have_t), "identical": not diffs, "diffs": diffs[:20]}
    if not check_only:
        if not have_t and trades: ledger.add(repo, "AdaptiveStocks", trades)
        if log_row:
            S.update(live=opt["params"], challenger=opt["challenger"] or {}); jsave(spath, S)
            ledger.add(repo, "AdaptiveLog", [log_row])
        res["written"] = {"trades": 0 if have_t else len(trades), "log_row": bool(log_row)}
    jsave(os.path.join(repo, "ops", "diag", "daily_adaptive.json"), {"day": day, "at": nowny, "ok": True, "check_only": check_only,
          "label": sc["label"], "summary": sc["summary"], "days": days, "missing": missing, "parity": res["parity"],
          "retune": res["retune"], "written": res.get("written")})
    return res


def picks_evening(repo, day=None, check_only=False):
    """The stock half of the 20:20 evening scoring AI task (runbook AGENT EVENING), moved to GitHub on 2026-11-25:
    the morning's stock picks (AgentPicks asset "stock", status "picked", picked that day) traded under the baseline-A
    rule and under the adaptive settings used that day (the old_settings of the day's AdaptiveLog "stocks" row, else
    data/state/stocks.json "live") with the frozen agent_score.py on the stored 5-minute bars, written to AgentTrades
    exactly as the task wrote them (rules "baseline A <label>" / "adaptive <label>", and "no trade" rows for picks
    without a baseline trade). The option replays of those trades (ATM call, smart call) stay with the AI task, which
    reads these rows. If the ledger already holds stock rows for the day, it compares instead of writing (parity).
    Run report: ops/diag/daily_picks_evening.json."""
    import subprocess, tempfile
    now = dt.datetime.now(NY); day = day or now.date().isoformat(); nowny = now.strftime("%Y-%m-%d %H:%M")
    if not tcal.info(day).get("full_trading_day"): return {"day": day, "status": "not a full trading day"}
    if day > now.date().isoformat() or (day == now.date().isoformat() and now.strftime("%H:%M") < "16:05"):
        return {"day": day, "status": "session not closed yet"}
    picks = []
    for r in ledger.load(repo, "AgentPicks"):
        if r.get("asset") == "stock" and r.get("status") == "picked" and str(r.get("picked_at", ""))[:10] == day \
                and r.get("symbol") not in picks: picks.append(r.get("symbol"))
    dpath = os.path.join(repo, "ops", "diag", "daily_picks_evening.json")
    if not picks:
        out = {"day": day, "at": nowny, "ok": True, "status": "no agent stock picks today"}; jsave(dpath, out); return out
    bars = _day_bars(repo, ["SPY"] + picks, day)
    missing = [s for s in ["SPY"] + picks if s not in bars or len(bars[s]["time"]) < 70]
    if missing:
        out = {"day": day, "at": nowny, "ok": False, "status": "no complete stored 5-minute bars yet", "missing": missing}
        jsave(dpath, out); return out
    lg = [r for r in ledger.load(repo, "AdaptiveLog") if r.get("segment") == "stocks" and str(r.get("review_time", "")).startswith(day)]
    try: adaptive_p = json.loads(lg[-1]["old_settings"]) if lg else (jload(os.path.join(repo, "data", "state", "stocks.json"), {}).get("live") or {})
    except Exception: adaptive_p = jload(os.path.join(repo, "data", "state", "stocks.json"), {}).get("live") or {}
    here = os.path.dirname(os.path.abspath(__file__)); tmp = {}
    for k, v in (("bars", bars), ("p0", {}), ("pa", adaptive_p)):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t: json.dump(v, t); tmp[k] = t.name
    def run(pf):
        p = subprocess.run([sys.executable, "-I", os.path.join(here, "agent_score.py"), tmp["bars"], day, tmp[pf]], capture_output=True, text=True)
        if p.returncode: raise SystemExit("agent_score failed: " + p.stderr[-300:])
        return json.loads(p.stdout)
    sa, sb = run("p0"), run("pa")
    for f in tmp.values(): os.remove(f)
    def row(t, name):
        return {"date": day, "segment": "stock", "rules": name + " " + t["rules"], "symbol": t["symbol"], "outcome": t["outcome"],
                "entry_time": t["entry_time"], "entry": t["entry"], "exit_time": t["exit_time"], "exit": t["exit"], "r_net": t["r_net"],
                "return_pct": round(100 * (float(t["exit"]) / float(t["entry"]) - 1) - 0.04, 3), "note": "stop %s, target %s" % (t["stop"], t["target"])}
    rows = [row(t, "baseline A") for t in sa["trades"]] + [row(t, "adaptive") for t in sb["trades"]]
    traded = {t["symbol"] for t in sa["trades"]}
    rows += [{"date": day, "segment": "stock", "rules": "no trade", "symbol": s, "outcome": sa["skipped"].get(s, "no breakout"),
              "entry_time": "", "entry": "", "exit_time": "", "exit": "", "r_net": "", "return_pct": "", "note": ""}
             for s in picks if s not in traded]
    old = [r for r in ledger.load(repo, "AgentTrades") if r.get("date") == day and r.get("segment") == "stock"]
    diffs = []
    if old:
        key = lambda r: (str(r.get("rules")).split(" ")[0], r.get("symbol"))
        o = {key(r): r for r in old}; n = {key(r): r for r in rows}
        for k in sorted(set(o) | set(n)):
            a, b = o.get(k), n.get(k)
            if a is None or b is None or a.get("outcome") != b.get("outcome") or a.get("rules") != b.get("rules") or \
                    (b.get("r_net") not in ("", None) and abs(float(a.get("r_net") or 0) - float(b["r_net"])) > 0.005):
                diffs.append("%s %s: ledger %s vs script %s" % (k[0], k[1], a and (a.get("rules"), a.get("outcome"), a.get("r_net")), b and (b.get("rules"), b.get("outcome"), b.get("r_net"))))
    res = {"day": day, "at": nowny, "ok": True, "picks": picks, "baseline": {"rules": sa["rules"], "trades": sa["count"], "wins": sa["wins"], "total_r": sa["total_r_net"]},
           "adaptive": {"rules": sb["rules"], "trades": sb["count"], "wins": sb["wins"], "total_r": sb["total_r_net"]},
           "no_trade": sorted(set(picks) - traded), "parity": {"compared": bool(old), "identical": not diffs, "diffs": diffs[:20]}, "check_only": check_only}
    if not check_only and not old:
        ledger.add(repo, "AgentTrades", rows); res["written"] = len(rows)
    jsave(dpath, res); return res


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
    elif a[0] in ("adaptive", "adaptive-check"):
        print(json.dumps(adaptive(a[1], a[2] if len(a) > 2 else None, check_only=a[0] == "adaptive-check"), indent=1, default=str))
    elif a[0] in ("picks-evening", "picks-evening-check"):
        print(json.dumps(picks_evening(a[1], a[2] if len(a) > 2 else None, check_only=a[0] == "picks-evening-check"), indent=1, default=str))
    else: raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
