"""Builds data/dashboard.json: one compact file with everything the dashboard artifact shows (added 2026-11-20).

  python3 dashboard.py REPO [NOW_ISO]      -> writes data/dashboard.json and prints its size
  python3 dashboard.py html REPO OUT.html  -> the dashboard page (ops/dashboard/index.template.html) with the
                                              current data embedded as its fallback snapshot
  python3 dashboard.py chunks REPO         -> prints the file as a JSON list of <= 20,000-character strings, for the
                                              sheet tab "Dashboard" (cells A2, A3, ...; A1 = generated-at)

It only reads files other scripts wrote (allocator report and portfolio, stats, library, ledger, engine detections,
slippage, freshness, feed log, ML report, regime). No market data is fetched and nothing is computed that changes a
result. Run by the GitHub Actions tick (every 5 minutes), the hourly live runs and the orchestrator.
"""
import glob, json, os, sys, statistics as st, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NY = ZoneInfo("America/New_York")


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def js(p, default=None):
    try: return json.load(open(p))
    except Exception: return default


def r(x, n=4):
    return round(x, n) if isinstance(x, (int, float)) else x


def signal_charts(repo, engine_file, limit=14):
    """Price charts for the dashboard's signal view (added 2026-11-21): the day's 5-minute candles for every symbol the
    engine sealed a signal on, with the sealed detection (ideal entry, engine fill, stop) and, once the 16:12 stock run
    has scored the day, the simulated baseline-A exit from the ledger. Times are shifted to New York wall-clock so the
    chart's axis reads in New York time. Display only."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York"); day = os.path.basename(engine_file)[:10]
    rows = jl(engine_file); syms = []
    for x in rows:
        if x["symbol"] not in syms: syms.append(x["symbol"])
    trades = {}
    for t in jl(os.path.join(repo, "data", "ledger", "Trades.jsonl")) + jl(os.path.join(repo, "data", "ledger", "VariantTrades.jsonl")):
        if t.get("date") == day and ((t.get("variant") is None and t.get("exit_time")) or t.get("variant") == "AC control"):
            trades.setdefault(t["symbol"], t)
    out = []
    for s in syms[:limit]:
        bars = []
        for b in jl(os.path.join(repo, "data", "bars", "5m", s + ".jsonl"))[-400:]:
            t = dt.datetime.fromtimestamp(b["t"], NY)
            if t.date().isoformat() == day and 9 * 60 + 30 <= t.hour * 60 + t.minute < 16 * 60:
                bars.append([b["t"] + int(t.utcoffset().total_seconds()), b["o"], b["h"], b["l"], b["c"]])
        if not bars: continue
        sig = [{"kind": x.get("strategy") or "baseline A", "side": x.get("side") or "long", "signal_end": x.get("signal_end"),
                "delay": x.get("delay_min"), "ideal": x.get("ideal_entry"), "fill": x.get("fill_price"), "stop": x.get("stop"),
                "revision": bool(x.get("revision"))} for x in rows if x["symbol"] == s]
        tr = trades.get(s)
        out.append({"symbol": s, "bars": bars, "signals": sig,
                    "trade": {k: tr.get(k) for k in ("entry_time", "entry", "exit_time", "exit", "outcome", "r_net", "target")} if tr else None})
    off = None
    if out:
        off = int(dt.datetime.fromisoformat(day + "T12:00").replace(tzinfo=NY).utcoffset().total_seconds())
    return {"day": day, "utc_offset_s": off, "symbols": out}


def build(repo, now=None):
    import tcal
    now = dt.datetime.fromisoformat(now).astimezone(NY) if now else dt.datetime.now(NY)
    out = {"generated": now.strftime("%Y-%m-%d %H:%M"), "tz": "America/New_York"}
    try: out["calendar"] = {k: v for k, v in tcal.info(now.date()).items() if not isinstance(v, (list, dict))}
    except Exception as e: out["calendar"] = {"error": str(e)[:80]}
    out["windows"] = {"start": tcal.START.isoformat(), "verdict": [tcal.ALLOC_FREEZE.isoformat(), tcal.END.isoformat()],
                      "holdout": [tcal.HOLDOUT_START.isoformat(), tcal.END.isoformat()], "end": tcal.END.isoformat(),
                      "crypto_end": tcal.CRYPTO_END.isoformat(), "interim_report": "2027-02-16", "final_report": tcal.FINAL_REPORT.isoformat()}
    out["pit"] = (js(os.path.join(repo, "data", "pit", "report.json")) or {}).get("survivorship_measured_on_sp500")
    A = js(os.path.join(repo, "data", "allocator", "report.json"), {}) or {}
    ph = {}
    for k, v in (A.get("phases") or {}).items():
        ph[k] = {b: v.get(b) for b in ("ai", "spy", "spy_vm", "equal", "equal_vm", "base_a", "base_a_vm")}
        ph[k].update({x: v.get(x) for x in ("p_ai_beats", "sharpe_gap_detectable", "turnover_per_day", "rebal_cost_pct_total", "spy_vm_scale", "vm_scales", "avg_invested", "shadows", "forced_fill", "exposure")})
    out["judge"] = {"latest": A.get("judge_latest"), "check": (A.get("judge_check") or {}).get("verdict")}
    jf = jl(os.path.join(repo, "data", "allocator", "judge.jsonl"))
    if jf: out["judge"]["last_seal"] = {k: jf[-1].get(k) for k in ("effective", "sealed_at", "weights", "decision", "bull", "bear")}
    out["nightly"] = js(os.path.join(repo, "data", "nightly", "stamp.json"))
    out["montecarlo"] = js(os.path.join(repo, "data", "nightly", "montecarlo.json"))
    out["crash_drill"] = js(os.path.join(repo, "reports", "replay", "2026-11-20-crash_drill.json"))
    out["allocator"] = {"date": A.get("date"), "sleeves": A.get("sleeves"), "phases": ph, "verdict_check": A.get("verdict_check"),
                        "stress_2x": A.get("stress_2x"), "ideal_fills": A.get("ideal_fills"),
                        "netted": A.get("netted_exploratory"), "freeze": A.get("freeze"), "stamp": A.get("stamp"),
                        "weights": A.get("latest_weights")}
    P = jl(os.path.join(repo, "data", "allocator", "portfolio.jsonl"))
    out["curve"] = [{"d": p["date"], "ai": r(p.get("ai")), "spy": r(p.get("spy")), "eq": r(p.get("equal")), "a": r(p.get("base_a")),
                     "rp": r(p.get("sh_rp")), "mv": r(p.get("sh_mv")), "win": r(p.get("sh_win")),
                     "inv": r(p.get("invested"), 3)} for p in P]
    W = jl(os.path.join(repo, "data", "allocator", "weights.jsonl"))[-30:]
    out["weights_hist"] = [{"d": w["date"], "w": w.get("weights"), "vol": w.get("vol_forecast_pct"), "br": len(w.get("breakers") or []),
                            "dup": len(w.get("duplicates") or []), "fill": w.get("fill")} for w in W]
    sf = sorted(glob.glob(os.path.join(repo, "reports", "stats", "*.json")))
    if sf:
        S = js(sf[-1], {})
        rows = ((S.get("phases") or {}).get("all") or {}).get("rows") or []
        out["stats"] = {"date": os.path.basename(sf[-1])[:10], "trials": S.get("trials"),
                        "rows": [{k: r(x.get(k)) for k in ("strategy", "unit", "n", "mean", "ci_lo", "ci_hi", "p_gt0", "sr", "q_bh", "dsr",
                                                           "verdict", "breaker")} for x in rows]}
    L = js(os.path.join(repo, "data", "library", "daily.json"), {}) or {}
    I = js(os.path.join(repo, "data", "library", "daily_ideal.json"), {}) or {}
    lib = []
    for k, v in sorted(L.items()):
        fw = [x for d, x in v.items() if d >= "2026-11-16"]; bt = [x for d, x in v.items() if d < "2026-11-16"]
        iv = [x for d, x in (I.get(k) or {}).items() if d >= "2026-11-16"]
        lib.append({"name": k, "fwd_days": len(fw), "fwd_sum": r(sum(fw)), "ideal_fwd_sum": r(sum(iv)) if iv else None,
                    "bt_days": len(bt), "bt_mean": r(st.mean(bt)) if bt else None,
                    "bt_sharpe": r(st.mean(bt) / st.pstdev(bt) * 252 ** 0.5, 2) if len(bt) > 20 and st.pstdev(bt) > 0 else None})
    out["library"] = lib
    try:
        import ledger
        T = sorted(ledger.trades(repo), key=lambda t: (t["day"], str(t.get("exit") or "")))
        out["recent_trades"] = [{k: t.get(k) for k in ("day", "strategy", "symbol", "result", "unit", "asset")} for t in T[-25:]]
        out["trade_counts"] = {"closed": len(T), "since": T[0]["day"] if T else None}
    except Exception as e: out["recent_trades"] = []; out["trade_counts"] = {"error": str(e)[:80]}
    ed = sorted(glob.glob(os.path.join(repo, "data", "decisions", "engine", "*.jsonl")))
    eng = {"days": []}
    for f in ed[-10:]:
        R = jl(f); dl = [x["delay_min"] for x in R if x.get("delay_min") is not None]
        eng["days"].append({"d": os.path.basename(f)[:10], "n": len(R), "median_delay": r(st.median(dl), 1) if dl else None,
                            "within20": sum(1 for x in dl if x <= 20)})
    if ed:
        eng["latest"] = [{k: x.get(k) for k in ("strategy", "symbol", "list", "signal_end", "detected_at", "delay_min", "ideal_entry", "fill_price",
                                                 "stop")} for x in jl(ed[-1])][-30:]
    eng["status"] = js(os.path.join(repo, "ops", "diag", "engine.json"), {})
    if ed:   # take-or-skip predictions made at detection (ml.py predict-engine, since 2026-11-20)
        M = jl(os.path.join(repo, "data", "decisions", "engine_ml", os.path.basename(ed[-1])))
        eng["ml_today"] = len(M); eng["ml_take"] = sum(1 for x in M if x.get("take"))
        out["charts"] = signal_charts(repo, ed[-1])
    out["engine"] = eng
    try:
        import checks
        out["health"] = checks.health(repo, now.isoformat())
        out["engine_vs_lag"] = checks.engine_report(repo)
        out["slippage"] = checks.slip_report(repo)
        out["fresh"] = {"5m": checks.fresh(repo, "5m", now.isoformat()), "1d": checks.fresh(repo, "1d", now.isoformat())}
        for v in out["fresh"].values(): v["stale"] = v["stale"][:12]
    except Exception as e: out["slippage"] = {"error": str(e)[:80]}
    F = js(os.path.join(repo, "ops", "diag", "fetch_free.json"), {}) or {}
    out["feed"] = {"mode": F.get("mode"), "finished": F.get("finished"), "errors": (F.get("errors") or [])[:5],
                   "files": len(F.get("files") or {}), "mismatch": len(F.get("mismatch") or [])}
    mf = sorted(glob.glob(os.path.join(repo, "models", "report_*.json")))
    if mf:
        M = js(mf[-1], {}); ml = {"date": M.get("date")}
        for fam in ("stock", "crypto"):
            m = M.get(fam) or {}
            ml[fam] = {k: r(m.get(k)) for k in ("rows", "oos_rows", "oos_days", "always_take_mean", "pbo", "champion", "status")
                       if m.get(k) is not None}
            ch = m.get("champion")
            if isinstance(ch, str) and isinstance(m.get("configs"), dict) and ch in m["configs"]:
                ml[fam]["champion_stats"] = {k: r(v) for k, v in m["configs"][ch].items() if not isinstance(v, (list, dict))}
        out["ml"] = ml
    Rg = jl(os.path.join(repo, "data", "ledger", "Regime.jsonl"))
    out["regime"] = Rg[-1] if Rg else None
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "html":   # dashboard.py html REPO OUT.html: the artifact page with the current data embedded as fallback
        snap = open(os.path.join(a[1], "data", "dashboard.json")).read().replace("</", "<\\/")
        tpl = open(os.path.join(a[1], "ops", "dashboard", "index.template.html")).read()
        open(a[2], "w").write(tpl.replace("__SNAPSHOT__", snap)); print(json.dumps({"written": a[2]}))
    elif a[0] == "chunks":
        s = open(os.path.join(a[1], "data", "dashboard.json")).read()
        print(json.dumps([s[i:i + 20000] for i in range(0, len(s), 20000)]))
    else:
        d = build(a[0], a[1] if len(a) > 1 else None)
        s = json.dumps(d, separators=(",", ":"), default=str)
        open(os.path.join(a[0], "data", "dashboard.json"), "w").write(s)
        print(json.dumps({"bytes": len(s), "chunks": (len(s) + 19999) // 20000}))
