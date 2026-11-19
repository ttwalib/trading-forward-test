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
import json, os, sys, math, random, subprocess, tempfile, re
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


def gate(repo, c):
    day = dt.datetime.now(stats.NY).date().isoformat()
    if tcal.phase(day) == "holdout":
        return {"id": c.get("id"), "verdict": "HOLD", "why": "frozen holdout (%s..%s): no new strategies or rule changes"
                % tuple(str(x) for x in tcal.PHASES["holdout"])}
    try:
        import checks as _ck; _ck.trial(repo, "strategy_lab", str(c.get("id") or c.get("name") or "unnamed"), max(1, int(c.get("n_configs_tried", 1))))
    except Exception: pass
    xs = [float(x) for x in c.get("oos_results", [])]; n = len(xs); checks = {}
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
    rv = reviewer(c["draft"]) if c.get("draft") else {"verdict": "n/a", "note": "no draft given"}
    checks["edge_reviewer_PASS"] = rv.get("verdict") == "PASS"
    if all(checks.values()): v = "PASS"
    elif mean <= 0 or rv.get("verdict") == "REJECT": v = "REJECT"
    else: v = "REVISE"
    return {"id": c.get("id"), "verdict": v, "n_oos": n, "oos_mean": round(mean, 4), "p_gt0": round(p, 3),
            "dsr": round(dsr, 3) if dsr is not None else None, "luck_sharpe": round(sr0, 4), "checks": checks, "reviewer": rv}


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
