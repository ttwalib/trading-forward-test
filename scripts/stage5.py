"""Report-only readings for the interim and final reports (Dec 8 plan stage 5, built early on 2026-11-25). None of them
changes a score, a weight, a lane decision or a verdict; they are evidence for the reader.

  python3 stage5.py spa REPO        -> data/nightly/spa.json      does the best thing we tried beat luck?
  python3 stage5.py ff-fetch REPO   -> data/ext/ff/factors_daily.csv.gz (GitHub only: needs the network)
  python3 stage5.py ff REPO         -> data/nightly/ffattr.json   where do the A1 book's returns come from?
  python3 stage5.py health REPO     -> data/nightly/lane_health.json and data/lane/health_log.jsonl

SPA. White's Reality Check (2000) and Hansen's test for Superior Predictive Ability (2005) over every daily series we
can test, against a benchmark. Family "forward": every allocator sleeve and every rival book in
data/allocator/portfolio.jsonl, forward days from 2026-11-16, against equal_f (the foundation-only equal weight, A1's
benchmark). Family "lab": every setting of every GitHub lab sweep (strategies/results/*.json, backtest days), against
SPY's daily close-to-close return over the same days (a long-only rule should beat holding the market, not just zero). Stationary bootstrap (Politis-Romano, mean block 5 days, 2,000 draws, seed 20261125). Small p = the best model's
edge is unlikely to be luck after counting every model tried. The trial log (data/trials.jsonl) also lists trials that
left no daily series; their count is shown, but they cannot enter the test, so the p-values are optimistic by that much.

FF. Fama/French five factors plus momentum, daily, from Kenneth French's data library (downloaded on GitHub by
ff-fetch). OLS of the A1 book's daily return minus the risk-free rate on Mkt-RF, SMB, HML, RMW, CMA and Mom, with
Newey-West standard errors (5 lags). The library lags by a month or two, so only days with factor data are used.

HEALTH. A state for each lane entry from its nightly recent_vs_best_yardstick reading (data/lane/scores.json, logged in
data/lane/health_log.jsonl) and its drawdown: "too new" (under 20 forward days), "healthy", "under watch" (the last 5
readings all at or below 0.35, or drawdown 10% or more), "decayed" (the last 10 readings all at or below 0.20, or
drawdown 15% or more), "switched off" (retired). In the style of a decay state machine; it NEVER overrides the
pre-registered retirement rule in scripts/registry.py.
"""
import csv, gzip, io, json, math, os, sys, glob, zipfile, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
try:
    import numpy as np  # noqa: E402  (not needed by ff-fetch, which runs where numpy is not installed)
except ImportError:
    np = None

SEED, B, BLOCK = 20261125, 2000, 5
START = "2026-11-16"


def jl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def stat_boot_idx(n, rng):
    """Politis-Romano stationary bootstrap indices with mean block length BLOCK."""
    idx = np.empty(n, dtype=int); i = rng.integers(n)
    for t in range(n):
        if t > 0 and rng.random() < 1.0 / BLOCK: i = rng.integers(n)
        idx[t] = i; i = (i + 1) % n
    return idx


def rc_spa(D, names):
    """D: n x k matrix of daily excess returns (model minus benchmark). Returns White RC and Hansen SPA (consistent) p."""
    n, k = D.shape
    if n < 20 or k < 1: return {"status": "not enough days", "days": int(n), "models": int(k)}
    m = D.mean(0); rng = np.random.default_rng(SEED)
    boots = np.empty((B, k))
    for b in range(B): boots[b] = D[stat_boot_idx(n, rng)].mean(0)
    sd = np.sqrt(n) * boots.std(0, ddof=1); sd[sd == 0] = np.inf
    rc_stat = np.sqrt(n) * m.max()
    rc_p = float((np.sqrt(n) * (boots - m).max(1) >= rc_stat).mean())
    t_stat = max(0.0, float((np.sqrt(n) * m / sd).max()))
    thr = -sd / np.sqrt(n) * np.sqrt(2 * np.log(np.log(n)))          # Hansen's consistent recentring
    mu_c = np.where(m >= thr, m, 0.0)
    spa_dist = (np.sqrt(n) * (boots - mu_c) / sd).max(1)
    spa_p = float((np.maximum(spa_dist, 0) >= t_stat).mean())
    best = int(m.argmax())
    return {"days": int(n), "models": int(k), "best": names[best], "best_mean_excess_pct_day": round(float(m[best]), 5),
            "white_rc_p": round(rc_p, 4), "hansen_spa_p": round(spa_p, 4),
            "reading": "the best model's edge is unlikely to be luck (p <= 0.10)" if spa_p <= 0.10 else "no evidence the best model beats luck"}


def spa(repo):
    import allocator
    res = {"seed": SEED, "draws": B, "mean_block_days": BLOCK}
    port = {r["date"]: r for r in jl(os.path.join(repo, "data", "allocator", "portfolio.jsonl")) if r["date"] >= START}
    days = sorted(d for d in port if port[d].get("equal_f") is not None)
    S = {k: v for k, v in allocator.sleeves(repo).items()}
    for col in ("ai", "sh_judge", "sh_rp", "sh_mv", "sh_win", "spy", "base_a"):
        S["book: " + col] = {d: port[d][col] for d in days if port[d].get(col) is not None}
    names = sorted(k for k, v in S.items() if sum(1 for d in days if d in v) >= max(5, len(days) // 2))
    D = np.array([[S[k].get(d, 0.0) - port[d]["equal_f"] for k in names] for d in days]) if names and days else np.zeros((0, 0))
    res["forward"] = dict(rc_spa(D, names), benchmark="equal_f (foundation-only equal weight)", first=days[0] if days else None)
    lab, lnames = {}, []
    for f in sorted(glob.glob(os.path.join(repo, "strategies", "results", "*.json"))):
        r = json.load(open(f))
        for k, s in (r.get("configs") or {}).items(): lab["%s:%s" % (r.get("id"), k)] = s
    if lab:
        import decisions
        sb = decisions.hist_bars(repo, "1d", "SPY"); spy = {}
        for i in range(1, len(sb)):
            spy[dt.datetime.fromtimestamp(sb[i]["t"], dt.timezone.utc).date().isoformat()] = (sb[i]["c"] / sb[i - 1]["c"] - 1) * 100
        ld = sorted(d for d in set().union(*[set(s) for s in lab.values()]) if d in spy); lnames = sorted(lab)
        L = np.array([[lab[k].get(d, 0.0) - spy[d] for k in lnames] for d in ld]) if ld else np.zeros((0, 0))
        res["lab"] = dict(rc_spa(L, lnames), benchmark="SPY close to close (backtest days)", first=ld[0] if ld else None, last=ld[-1] if ld else None)
    else: res["lab"] = {"status": "no GitHub lab sweeps yet"}
    tr = jl(os.path.join(repo, "data", "trials.jsonl"))
    res["trial_log"] = {"rows": len(tr), "trials_counted": int(sum(int(t.get("n") or 1) for t in tr)),
                        "note": "trials without a stored daily series cannot enter the test; the p-values above are optimistic by that much"}
    return res


# ---------- Fama/French ----------
FF_URLS = {"ff5": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
           "mom": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"}


def _ff_rows(raw):
    z = zipfile.ZipFile(io.BytesIO(raw)); txt = z.read(z.namelist()[0]).decode("latin-1"); out = {}; hdr = None
    for line in txt.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) > 1 and p[0] == "" and hdr is None: hdr = p[1:]; continue
        if hdr and len(p) == len(hdr) + 1 and p[0].isdigit() and len(p[0]) == 8:
            d = "%s-%s-%s" % (p[0][:4], p[0][4:6], p[0][6:]); out[d] = dict(zip(hdr, (float(x) for x in p[1:])))
        elif hdr and out and not (p[0].isdigit()): break
    return out


def ff_fetch(repo):
    rows = {}
    for key, url in FF_URLS.items():
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "quantavius-forward-test/1.0"}), timeout=60).read()
        for d, v in _ff_rows(raw).items(): rows.setdefault(d, {}).update(v)
    cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom", "RF"]
    od = os.path.join(repo, "data", "ext", "ff"); os.makedirs(od, exist_ok=True)
    keep = sorted(d for d in rows if d >= "2016-01-01" and all(c in rows[d] for c in cols))
    with gzip.open(os.path.join(od, "factors_daily.csv.gz"), "wt") as fh:
        fh.write("date," + ",".join(cols) + "\n")
        for d in keep: fh.write(d + "," + ",".join("%.4f" % rows[d][c] for c in cols) + "\n")
    json.dump({"fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Kenneth R. French data library",
               "rows": len(keep), "last": keep[-1] if keep else None}, open(os.path.join(od, "source.json"), "w"), indent=1)
    return {"rows": len(keep), "last": keep[-1] if keep else None}


def ff(repo, col="sh_judge"):
    f = os.path.join(repo, "data", "ext", "ff", "factors_daily.csv.gz")
    if not os.path.exists(f): return {"status": "no factor file yet (ff-fetch runs on GitHub)"}
    F = {r["date"]: r for r in csv.DictReader(gzip.open(f, "rt"))}
    port = {r["date"]: r for r in jl(os.path.join(repo, "data", "allocator", "portfolio.jsonl"))}
    days = sorted(d for d in port if d >= START and d in F and port[d].get(col) is not None)
    out = {"book": col, "factor_last_day": max(F) if F else None, "days": len(days)}
    if len(days) < 20: out["status"] = "not enough days with factor data (%d of 20)" % len(days); return out
    X = np.array([[1.0] + [float(F[d][c]) for c in ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom")] for d in days])
    y = np.array([port[d][col] - float(F[d]["RF"]) for d in days])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None); e = y - X @ beta; n, k = X.shape
    XtXi = np.linalg.inv(X.T @ X); S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, 6):
        w = 1 - L / 6; G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None]); S += w * (G + G.T)
    se = np.sqrt(np.diag(XtXi @ S @ XtXi))
    names = ["alpha_pct_day", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    out["coef"] = {nm: {"b": round(float(b), 4), "t": round(float(b / s), 2) if s > 0 else None} for nm, b, s in zip(names, beta, se)}
    out["r2"] = round(float(1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))), 3)
    out["alpha_annual_pct"] = round(float(beta[0]) * 252, 2)
    return out


# ---------- lane health ----------
def health(repo):
    sc = json.load(open(os.path.join(repo, "data", "lane", "scores.json")))
    logp = os.path.join(repo, "data", "lane", "health_log.jsonl"); log = jl(logp); day = sc.get("day")
    if day and not any(r.get("day") == day for r in log):
        row = {"day": day, "rv": {k: e.get("recent_vs_best_yardstick") for k, e in sc["entries"].items()}}
        with open(logp, "a") as fh: fh.write(json.dumps(row, sort_keys=True) + "\n")
        log.append(row)
    out = {"day": day, "entries": {}, "note": "report only; never overrides the retirement rule in scripts/registry.py"}
    for k, e in sc["entries"].items():
        p = e.get("perf") or {}; days = p.get("days") or 0; dd = p.get("max_dd_pct") or 0.0
        rv = [r["rv"].get(k) for r in log if k in r.get("rv", {})]; rv = [x for x in rv if x is not None]
        if e.get("status") == "retired": st = "switched off"
        elif days < 20: st = "too new"
        elif (len(rv) >= 10 and all(x <= 0.20 for x in rv[-10:])) or dd >= 15: st = "decayed"
        elif (len(rv) >= 5 and all(x <= 0.35 for x in rv[-5:])) or dd >= 10: st = "under watch"
        else: st = "healthy"
        out["entries"][k] = {"state": st, "forward_days": days, "max_dd_pct": dd, "last_readings": rv[-10:]}
    return out


if __name__ == "__main__":
    a = sys.argv[1:]; cmd, repo = a[0], (a[1] if len(a) > 1 else ".")
    if cmd == "spa": r = spa(repo)
    elif cmd == "ff-fetch": r = ff_fetch(repo)
    elif cmd == "ff": r = ff(repo)
    elif cmd == "health": r = health(repo)
    else: sys.exit("unknown command")
    print(json.dumps(r, indent=1))
