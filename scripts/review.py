"""Promotion gates and residual-edge checks (uses MIT code vendored from tradermonty/claude-trading-skills in
vendor/tradermonty, commit 427b1f7d; see vendor/tradermonty/LICENSE).

  python3 review.py gate REPO CANDIDATE.json
      Strategy-lab / learning gate for a NEW strategy or rule change. CANDIDATE.json:
        {"id": "...", "thesis": "...",   (draft exit.stop_loss_pct is a FRACTION, e.g. 0.01 = 1%) "family": "stock|option|crypto", "oos_results": [per-trade results, walk-forward
         out-of-sample only], "n_configs_tried": 12, "pbo": 0.31 or null, "cpcv": cpcv.py output or null,
         "draft": {edge-strategy-reviewer draft fields}}
      PASS only if ALL hold: n_oos >= 30; OOS mean > 0 with bootstrap P(mean > 0) >= 0.9; deflated Sharpe >= 0.9 with
      N = n_configs_tried trials; PBO < 0.5 when given; cpcv "pass" when given (cpcv.py); the vendored edge-strategy-reviewer verdict is PASS (with the
      bias checklist). Otherwise REVISE (fixable) or REJECT (OOS mean <= 0 or reviewer REJECT).
      During the frozen holdout every gate answers HOLD (no new strategies until the final report).
  python3 review.py residual REPO STRATEGY OUTDIR
      Daily strategy returns vs SPY (primary model) and BTC (sensitivity) through the vendored residual-edge analyzer:
      is the edge real alpha or just market exposure? Writes OUTDIR/<slug>.json/.md and prints the verdict.
"""
import hashlib, json, os, sys, math, random, subprocess, tempfile, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats, tcal, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "vendor", "tradermonty")


def reviewer(draft):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "draft.yaml")
        try:
            import yaml
        except ImportError:
            return {"verdict": "n/a", "note": "PyYAML missing"}
        yaml.safe_dump(draft, open(p, "w"))
        r = subprocess.run([sys.executable, "-I", os.path.join(V, "edge-strategy-reviewer", "scripts", "review_strategy_drafts.py"),
                            "--draft", p, "--output-dir", d, "--format", "json", "--bias-checklist"],
                           capture_output=True, text=True, timeout=120)
        outs = [f for f in os.listdir(d) if f.endswith(".json")]
        if not outs: return {"verdict": "n/a", "note": (r.stderr or r.stdout)[-400:]}
        o = json.load(open(os.path.join(d, outs[0])))
        rv = (o.get("reviews") or [{}])[0]
        return {"verdict": rv.get("verdict"), "confidence": rv.get("confidence_score") or rv.get("confidence"),
                "findings": ["%s: %s" % (f.get("criterion"), f.get("reason")) for f in rv.get("findings", [])
                             if isinstance(f, dict) and f.get("severity") != "pass"],
                "revision_instructions": rv.get("revision_instructions")}


def _data_quality(repo, d):
    """Archive coverage for the symbols a candidate used (2026-11-23, idea from smizxe/mt5-agent-toolkit, MIT, ideas only):
    share of trading days in [start, end] that have a daily bar, per symbol. Only 1d is measured; other timeframes return None."""
    import decisions
    if not d or str(d.get("tf", "1d")) != "1d" or not d.get("symbols"): return None
    s0, s1 = str(d.get("start", "2016-01-04")), str(d.get("end", dt.date.today().isoformat()))
    day_of = lambda sym: {dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).date().isoformat() for b in decisions.hist_bars(repo, "1d", sym)}
    days = sorted(x for x in day_of("SPY") if s0 <= x <= s1)     # the market's own calendar (tcal only knows the test's holidays)
    if not days: return None
    per = {}
    for sym in d["symbols"][:150]:
        have = day_of(sym)
        per[sym] = round(sum(1 for x in days if x in have) / len(days), 4)
    worst = min(per.values()) if per else 0.0
    return {"days": len(days), "worst": worst, "worst_symbol": min(per, key=per.get) if per else None,
            "below_0.98": sorted(k for k, v in per.items() if v < 0.98)}


def neighbours(grid, chosen):
    """NEIGHBOUR CHECK (2026-11-24, runbook item 51; idea from the robustness chapters of Jansen's ML for Trading and
    the plateau test of backtesting tools, no code taken). grid = every setting tried, each {"params": {...}, "score": x}
    scored on the TUNING data with the measure used to choose. A neighbour differs from the chosen setting in exactly
    one parameter, by one step in that parameter's sorted list of tried values. Pass when the chosen setting has at
    least one neighbour and the neighbours' median score is above 0 and at least half the chosen score: the chosen
    setting must sit on a plateau, not a lone peak."""
    try:
        G = [g for g in grid if isinstance(g.get("params"), dict)]
        me = next((g for g in G if g["params"] == chosen), None)
        if me is None: return False, {"error": "the declared params are not in the grid"}
        keys = sorted(chosen); vals = {k: sorted({json.dumps(g["params"].get(k), sort_keys=True) for g in G}) for k in keys}
        nb = []
        for g in G:
            diff = [k for k in keys if g["params"].get(k) != chosen.get(k)]
            if len(diff) != 1 or set(g["params"]) != set(chosen): continue
            k = diff[0]; v = vals[k]
            i, j = v.index(json.dumps(chosen[k], sort_keys=True)), v.index(json.dumps(g["params"][k], sort_keys=True))
            try: num = sorted(v, key=lambda x: float(json.loads(x))); i, j = num.index(v[i]), num.index(v[j])
            except Exception: pass
            if abs(i - j) == 1: nb.append(float(g["score"]))
        import statistics; sc = float(me["score"]); med = statistics.median(nb) if nb else None
        ok = bool(nb) and med > 0 and (sc <= 0 or med >= 0.5 * sc)
        return ok, {"chosen_score": sc, "n_neighbours": len(nb), "neighbour_median": med, "neighbour_scores": nb}
    except Exception as ex:
        return False, {"error": "%s: %s" % (type(ex).__name__, ex)}


def gate(repo, c):
    day = dt.datetime.now(stats.NY).date().isoformat()
    if tcal.phase(day) == "holdout":
        return {"id": c.get("id"), "verdict": "HOLD", "why": "frozen holdout (%s..%s): no new strategies or rule changes"
                % tuple(str(x) for x in tcal.PHASES["holdout"])}
    xs = [float(x) for x in c.get("oos_results", [])]; n = len(xs); checks = {}
    # Lab hygiene (2026-11-23, owner "yes"; ideas adapted from smizxe/mt5-agent-toolkit, MIT, no code taken):
    # (1) the exact settings of the tested run must be declared, and their hash goes into the trial log, so a run can
    #     never silently reuse an earlier run's settings; (2) data quality is read FIRST: archive coverage of every
    #     symbol used must be at least 98% of trading days (only measured for daily bars); (3) a held-out profit factor
    #     above 5 is treated as a probable bug until "pf_explained" says why it is not.
    prm = c.get("params")
    checks["params_declared"] = isinstance(prm, dict) and len(prm) > 0
    phash = hashlib.sha256(json.dumps(prm, sort_keys=True).encode()).hexdigest()[:12] if checks["params_declared"] else None
    dq = _data_quality(repo, c.get("data"))
    if dq is not None: checks["data_coverage>=0.98"] = dq["worst"] >= 0.98
    # (4) POINT-IN-TIME UNIVERSE (2026-11-23): an idea that trades individual stocks must pick them with scripts/pitu.py
    #     (cand.json "universe": "pit"); otherwise it must say in "survivorship_note" why today's list is harmless here.
    try:
        U_ = json.load(open(os.path.join(repo, "data", "universe.json"))); single = set(U_.get("universe", [])) | set(U_["watchlist"] + U_["control"])
        uses_stocks = any(x in single for x in ((c.get("data") or {}).get("symbols") or []))
    except Exception: uses_stocks = False
    if uses_stocks: checks["universe_point_in_time"] = c.get("universe") == "pit" or bool(str(c.get("survivorship_note") or "").strip())
    gains, losses = sum(x for x in xs if x > 0), -sum(x for x in xs if x < 0)
    pf = round(gains / losses, 3) if losses > 0 else (None if not gains else float("inf"))
    pf_flag = pf is not None and pf > 5
    if pf_flag: checks["pf<=5_or_explained"] = bool(str(c.get("pf_explained") or "").strip())
    checks["n_oos>=30"] = n >= 30
    mean = sum(xs) / n if n else 0.0
    p = stats.boot(xs, random.Random(stats.SEED))[2] if n >= 2 else 0.0
    checks["oos_mean>0_and_P>=0.9"] = mean > 0 and p >= 0.9
    N = max(1, int(c.get("n_configs_tried", 1)))
    g = 0.5772156649  # expected best Sharpe of N null trials with n observations (False Strategy Theorem)
    sr0 = math.sqrt(1 / (n - 1)) * ((1 - g) * stats.N01.inv_cdf(1 - 1 / N) + g * stats.N01.inv_cdf(1 - 1 / (N * math.e))) \
        if N > 1 and n > 1 else 0.0
    dsr = stats.psr(xs, sr0) if n >= 3 else None
    checks["dsr>=0.9"] = dsr is not None and dsr >= 0.9
    if c.get("pbo") is not None: checks["pbo<0.5"] = float(c["pbo"]) < 0.5
    if c.get("cpcv") is not None:   # cpcv.py output over the long archive (required by the runbook since 2026-11-19)
        checks["cpcv_pass"] = bool(c["cpcv"].get("pass"))
    nbr = None
    if int(c.get("n_configs_tried", 1)) > 1:     # neighbour check (2026-11-24): required whenever settings were tuned
        if c.get("grid"): ok_, nbr = neighbours(c["grid"], prm or {}); checks["neighbours_hold"] = ok_
        else: checks["neighbours_hold"] = False; nbr = {"error": "no grid given (every setting tried, scored on the tuning data)"}
    # OPTIONS TRACK (2026-11-24, item 58): an option idea must also show that its fills are conservative, that no stale
    # price was used, and that its edge is not only earnings jumps. cand.json "options": {"fill": "bidask" (buy at the
    # ask, sell at the bid, from data/optarch snapshots) or "trade_plus_spread" (daily trade bars, allowance per leg per
    # side in "spread_allowance_pct", at least 2.0 like live AP3), "fee_per_contract" (>= 0.65), "stale_excluded": true
    # (optarch.fill gives None for a bar with no volume; those trades are dropped, never marked at an old print),
    # "earnings": "excluded" (no trade spans an earnings date) or "split" with "oos_ex_earnings" (the per-trade results
    # without the trades that span one, whose mean must also be > 0 with n >= 20)}.
    if str(c.get("family") or "") == "option":
        o = c.get("options") or {}
        fl = o.get("fill"); al = o.get("spread_allowance_pct")
        checks["options_fills_conservative"] = fl == "bidask" or (fl == "trade_plus_spread" and isinstance(al, (int, float)) and al >= 2.0)
        checks["options_fees>=0.65"] = isinstance(o.get("fee_per_contract"), (int, float)) and o["fee_per_contract"] >= 0.65
        checks["options_no_stale_prices"] = o.get("stale_excluded") is True
        ex = [float(x) for x in (o.get("oos_ex_earnings") or [])]
        checks["options_earnings_handled"] = o.get("earnings") == "excluded" or (o.get("earnings") == "split" and len(ex) >= 20 and sum(ex) / len(ex) > 0)
    rv = reviewer(c["draft"]) if c.get("draft") else {"verdict": "n/a", "note": "no draft given"}
    checks["edge_reviewer_PASS"] = rv.get("verdict") == "PASS"
    try:     # the trial is logged with the settings hash (a different hash = a different trial)
        import checks as _ck; _ck.trial(repo, "strategy_lab", str(c.get("id") or c.get("name") or "unnamed") + ("#" + phash if phash else ""),
                                        max(1, int(c.get("n_configs_tried", 1))))
    except Exception: pass
    if all(checks.values()): v = "PASS"
    elif mean <= 0 or rv.get("verdict") == "REJECT": v = "REJECT"
    else: v = "REVISE"
    return {"id": c.get("id"), "verdict": v, "n_oos": n, "oos_mean": round(mean, 4), "p_gt0": round(p, 3),
            "dsr": round(dsr, 3) if dsr is not None else None, "luck_sharpe": round(sr0, 4), "checks": checks, "reviewer": rv,
            "read_first": {"data_quality": dq, "n_oos": n, "few_trades": n < 30, "profit_factor": pf, "pf_suspicious": pf_flag, "neighbours": nbr},
            "params_hash": phash}


def residual(repo, strategy, outdir):
    os.makedirs(outdir, exist_ok=True); slug = re.sub(r"[^a-z0-9]+", "_", strategy.lower()).strip("_")
    csv = os.path.join(outdir, slug + ".csv"); open(csv, "w").write(stats.series(repo, strategy) + "\n")
    n = sum(1 for _ in open(csv)) - 1
    cfg = {"schema_version": "1.0", "date_column": "date", "strategy_column": "strategy_return", "return_unit": "decimal",
           "frequency": "daily", "primary_model": {"name": "spy", "baseline_columns": ["spy_return"]},
           "sensitivity_models": [{"name": "spy_plus_btc", "baseline_columns": ["spy_return", "btc_return"]}],
           "regime_columns": [], "rolling_window": 20, "minimum_observations": 40, "minimum_regime_observations": 20,
           "minimum_rolling_windows": 12, "hac_lags": "auto", "include_series": False,
           "data_declarations": {"baseline_selection": "predeclared", "strategy_return_basis": "net",
                                 "baseline_return_basis": "net", "analysis_scope": "out_of_sample",
                                 "universe_data": "point_in_time"}}
    cf = os.path.join(outdir, slug + "_config.json"); json.dump(cfg, open(cf, "w"), indent=1)
    oj, om = os.path.join(outdir, slug + ".json"), os.path.join(outdir, slug + ".md")
    r = subprocess.run([sys.executable, "-I", os.path.join(V, "residual-edge-analyzer", "scripts", "analyze_residual_edge.py"),
                        "--input", csv, "--config", cf, "--output-json", oj, "--output-markdown", om],
                       capture_output=True, text=True, timeout=300)
    if not os.path.exists(oj): return {"strategy": strategy, "days": n, "error": (r.stderr or r.stdout)[-600:]}
    o = json.load(open(oj))
    v = o.get("verdict") or {}
    return {"strategy": strategy, "days": n, "status": v.get("status"), "reasons": v.get("reasons"),
            "trade_authorization": v.get("trade_authorization"), "json": oj, "markdown": om}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "gate": print(json.dumps(gate(a[1], json.load(open(a[2]))), indent=1))
    elif a[0] == "residual": print(json.dumps(residual(a[1], a[2], a[3]), indent=1, default=str))
