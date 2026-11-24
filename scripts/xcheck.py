"""Independent cross-checks of the bespoke engine against outside libraries (owner "proceed", 2026-11-24; runbook item 51).

  python3 xcheck.py REPO calendar|stats|orb|all OUTDIR

Report-only: nothing here changes a rule, a ledger row or a weight. It runs in its own GitHub workflow
(.github/workflows/xcheck.yml) with read-only repository permission and no secrets, because it installs outside
packages: exchange_calendars, backtesting (backtesting.py), scipy and ml4t-diagnostic. The job uploads OUTDIR as an
artifact; a build session reads it and commits reports/xcheck/<date>.json. Every package version used is recorded.

calendar  Compares scripts/tcal.py (holidays, half days) with exchange_calendars "XNYS" over the whole test, so that a
          wrong date in the frozen calendar is found before 2026-12-07.
stats     Recomputes our deflated Sharpe (review.py gate: stats.psr against the False Strategy Theorem benchmark) with
          an independent scipy implementation and, if it imports, ml4t-diagnostic, on every library sleeve's daily
          returns; and our CPCV overfitting probability (cpcv.py) beside an independent CSCV PBO (Bailey et al. 2015)
          on the same set of sleeves. The two PBO definitions differ (CPCV splits vs CSCV logits), so they are shown
          side by side, not expected to match exactly.
orb       Re-runs baseline A (scripts/orb_daily.py rules) in backtesting.py on the stored 5-minute bars for every
          watchlist day in the Trades ledger and lists every trade where the outside engine disagrees with ours
          (entry, exit, outcome, R).
"""
import datetime as dt, json, math, os, sys
from decimal import Decimal as Dec, ROUND_DOWN, ROUND_HALF_UP
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York"); C = Dec("0.01")


def versions():
    out = {"python": sys.version.split()[0]}
    try:
        from importlib.metadata import version
        for p in ("exchange_calendars", "backtesting", "scipy", "numpy", "pandas", "ml4t-diagnostic"):
            try: out[p] = version(p)
            except Exception: out[p] = None
    except Exception: pass
    return out


# ---------- calendar ----------
def calendar(repo):
    import exchange_calendars as xc, tcal
    cal = xc.get_calendar("XNYS")
    a, b = dt.date(2026, 11, 16), dt.date(2027, 5, 21)
    sessions = {s.date() for s in cal.sessions_in_range(a.isoformat(), b.isoformat())}
    early = {}
    for s in sessions:
        close = cal.session_close(s.isoformat()).tz_convert("America/New_York")
        if close.strftime("%H:%M") != "16:00": early[s] = close.strftime("%H:%M")
    diffs = []; d = a
    while d <= b:
        if d.weekday() < 5:
            ours_open = tcal.is_open(d); theirs_open = d in sessions
            if ours_open != theirs_open: diffs.append({"date": d.isoformat(), "tcal_open": ours_open, "xnys_open": theirs_open})
            elif ours_open:
                oh = tcal.HALF.get(d); th = early.get(d)
                if oh != th: diffs.append({"date": d.isoformat(), "tcal_half": oh, "xnys_early_close": th})
        d += dt.timedelta(days=1)
    return {"range": [a.isoformat(), b.isoformat()], "xnys_sessions": len(sessions),
            "xnys_holidays_on_weekdays": sorted(x.isoformat() for x in _weekdays(a, b) if x not in sessions),
            "xnys_early_closes": {k.isoformat(): v for k, v in sorted(early.items())},
            "differences": diffs, "identical": not diffs}


def _weekdays(a, b):
    d = a
    while d <= b:
        if d.weekday() < 5: yield d
        d += dt.timedelta(days=1)


# ---------- stats ----------
def _dsr_ours(xs, N):
    import stats
    n = len(xs); g = 0.5772156649
    sr0 = math.sqrt(1 / (n - 1)) * ((1 - g) * stats.N01.inv_cdf(1 - 1 / N) + g * stats.N01.inv_cdf(1 - 1 / (N * math.e))) if N > 1 else 0.0
    return stats.psr(xs, sr0), sr0


def _dsr_scipy(xs, N):
    """Bailey and Lopez de Prado (2014), written independently with scipy: PSR of the per-period Sharpe against the
    expected maximum Sharpe of N null trials with variance 1/(n-1)."""
    import numpy as np
    from scipy import stats as ss
    x = np.asarray(xs, float); n = len(x); sr = x.mean() / x.std(ddof=1) if x.std(ddof=1) > 0 else 0.0
    g = np.euler_gamma
    sr0 = math.sqrt(1 / (n - 1)) * ((1 - g) * ss.norm.ppf(1 - 1 / N) + g * ss.norm.ppf(1 - 1 / (N * math.e))) if N > 1 else 0.0
    sk = ss.skew(x, bias=True); ku = ss.kurtosis(x, fisher=False, bias=True)
    den = 1 - sk * sr + (ku - 1) / 4 * sr * sr
    return float(ss.norm.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(max(den, 1e-6)))), float(sr0)


def _dsr_ml4t(xs, N):
    try:
        import numpy as np
        from ml4t.diagnostic.evaluation.stats import deflated_sharpe_ratio
        import inspect
        prm = list(inspect.signature(deflated_sharpe_ratio).parameters)
        kw = {}
        for k in prm:
            if k in ("returns", "strategy_returns", "x"): kw[k] = np.asarray(xs, float) / 100.0
            elif k in ("benchmark_sharpe", "sr_benchmark", "expected_sharpe"): kw[k] = 0.0
            elif k in ("n_trials", "num_trials", "n_strategies", "trials", "k", "n_tests", "effective_trials"): kw[k] = N
            elif k in ("periods_per_year", "annualization", "frequency"): kw[k] = 252
        if not any(k in kw for k in ("returns", "strategy_returns", "x")):
            return {"ok": False, "error": "unknown signature", "params": prm}
        r = deflated_sharpe_ratio(**kw)
        fields = {k: getattr(r, k) for k in dir(r) if not k.startswith("_") and isinstance(getattr(r, k, None), (int, float))}
        if isinstance(r, dict): fields = {k: v for k, v in r.items() if isinstance(v, (int, float))}
        elif isinstance(r, (int, float)): fields = {"value": float(r)}
        return {"ok": True, "fields": fields, "params": prm}
    except Exception as ex:
        return {"ok": False, "error": "%s: %s" % (type(ex).__name__, str(ex)[:200])}


def _pbo_cscv(configs, S=16):
    """Probability of backtest overfitting by CSCV (Bailey, Borwein, Lopez de Prado, Zhu 2015), independent code."""
    import itertools, numpy as np
    days = sorted({d for c in configs.values() for d in c}); names = sorted(configs)
    M = np.array([[configs[n].get(d, 0.0) for n in names] for d in days], float)
    T = (len(days) // S) * S; M = M[:T]; blocks = np.array_split(np.arange(T), S); logits = []
    def sr(a):
        s = a.std(axis=0, ddof=1); s[s == 0] = np.inf; return a.mean(axis=0) / s
    for comb in itertools.combinations(range(S), S // 2):
        tr = np.concatenate([blocks[i] for i in comb]); te = np.concatenate([blocks[i] for i in range(S) if i not in comb])
        best = int(np.argmax(sr(M[tr]))); ranks = sr(M[te]).argsort().argsort()
        w = (ranks[best] + 1) / (len(names) + 1); logits.append(math.log(w / (1 - w)))
    return {"S": S, "splits": len(logits), "pbo": round(float(np.mean(np.array(logits) <= 0)), 3), "n_configs": len(names), "n_days": T}


def stats_check(repo):
    import checks, cpcv
    L = json.load(open(os.path.join(repo, "data", "library", "daily.json")))
    N = max(2, int(checks.n_trials(repo))) if hasattr(checks, "n_trials") else 50
    rows = []
    for name, ser in sorted(L.items()):
        xs = [float(v) for _, v in sorted(ser.items())]
        if len(xs) < 30 or len(set(xs)) < 3: continue
        o, sr0 = _dsr_ours(xs, N); s, sr0s = _dsr_scipy(xs, N)
        rows.append({"sleeve": name, "n": len(xs), "ours": round(o, 6) if o is not None else None, "scipy": round(s, 6),
                     "diff": round(abs((o or 0) - s), 6), "sr0_ours": round(sr0, 6), "sr0_scipy": round(sr0s, 6),
                     "ml4t": _dsr_ml4t(xs, N)})
    configs = {k: {d: float(v) for d, v in s.items()} for k, s in L.items() if len(s) >= 200}
    ours_pbo = cpcv.cpcv(configs)
    return {"n_trials_used": N, "dsr": rows, "max_dsr_diff_ours_vs_scipy": max((r["diff"] for r in rows), default=None),
            "pbo": {"ours_cpcv": {k: ours_pbo.get(k) for k in ("pbo", "median_sharpe", "share_positive", "pass", "error") if k in ours_pbo},
                    "independent_cscv": _pbo_cscv(configs)},
            "note": "DSR: same formula written twice. Ours standardises skewness and kurtosis with the sample standard "
                    "deviation, scipy with the population one, so differences of about 1e-4 are that convention; larger ones "
                    "would mean an implementation error. ml4t-diagnostic may use a different benchmark (correlation-adjusted trial count), so its value "
                    "is a third opinion, not a match target. PBO: different split designs, compare the size, not the digits."}


# ---------- orb (backtesting.py) ----------
def _q(v): return float(Dec(str(v)).quantize(C, rounding=ROUND_HALF_UP))


def orb(repo):
    import pandas as pd
    from backtesting import Backtest, Strategy
    T = [json.loads(l) for l in open(os.path.join(repo, "data", "ledger", "Trades.jsonl")) if l.strip()]
    T = [t for t in T if t.get("date", "") >= "2026-11-16" and t.get("symbol")]
    days = sorted({t["date"] for t in T}); U = json.load(open(os.path.join(repo, "data", "universe.json")))["watchlist"]
    ours = {(t["date"], t["symbol"]): t for t in T}

    class ORB(Strategy):
        def init(self): self.hi = self.lo = None; self.done = False; self.plan = None
        def next(self):
            t = self.data.index[-1]; hm = t.strftime("%H:%M"); end = (t + pd.Timedelta(minutes=5)).strftime("%H:%M")
            h, l, c = Dec(str(self.data.High[-1])), Dec(str(self.data.Low[-1])), Dec(str(self.data.Close[-1]))
            if hm < "09:30": return
            if hm in ("09:30", "09:35", "09:40"):
                self.hi = h if self.hi is None else max(self.hi, h); self.lo = l if self.lo is None else min(self.lo, l); return
            if self.position:
                if hm >= "15:50": self.position.close()
                return
            if self.done or self.hi is None or hm < "09:45" or end > "15:30": return
            if c > self.hi:
                self.done = True; e = c
                if e < 5: return
                stop = ((self.hi + self.lo) / 2).quantize(C, rounding=ROUND_DOWN); r = e - stop
                if r <= 0 or r / e * 100 < Dec("0.05"): return
                tgt = (e + 2 * r).quantize(C, rounding=ROUND_HALF_UP)
                self.plan = (float(e), float(stop), float(tgt)); self.buy(size=1, sl=float(stop), tp=float(tgt))

    out, diffs, n_cmp = [], [], 0
    for sym in U:
        p = os.path.join(repo, "data", "bars", "5m", sym + ".jsonl")
        if not os.path.exists(p): continue
        B = [json.loads(l) for l in open(p) if l.strip()]
        for day in days:
            rows = [b for b in B if dt.datetime.fromtimestamp(b["t"], NY).date().isoformat() == day]
            rows = [b for b in rows if "09:30" <= dt.datetime.fromtimestamp(b["t"], NY).strftime("%H:%M") < "16:00"]
            if len(rows) < 4: continue
            # backtesting.py calls next() from the SECOND bar on, so a copy of the first bar stamped 09:25 is put in
            # front; the strategy ignores any bar before 09:30.
            rows = sorted(rows, key=lambda b: b["t"]); rows = [dict(rows[0], t=rows[0]["t"] - 300)] + rows
            idx = pd.DatetimeIndex([dt.datetime.fromtimestamp(b["t"], NY).replace(tzinfo=None) for b in rows])
            df = pd.DataFrame({"Open": [b["o"] for b in rows], "High": [b["h"] for b in rows], "Low": [b["l"] for b in rows],
                               "Close": [b["c"] for b in rows], "Volume": [b.get("v", 0) for b in rows]}, index=idx).sort_index()
            bt = Backtest(df, ORB, cash=1e7, commission=0.0, trade_on_close=True, exclusive_orders=False, finalize_trades=True)
            res = bt.run(); tr = res._trades; theirs = None
            if len(tr):
                x = tr.iloc[0]; e, xp = float(x.EntryPrice), float(x.ExitPrice); st_ = res._strategy.plan
                r = e - st_[1]; cost = (e + xp) * 0.02 / 100
                theirs = {"entry": _q(e), "exit": _q(xp), "exit_time": (x.ExitTime + pd.Timedelta(minutes=5)).strftime("%H:%M"),
                          "r_net": round((xp - e - cost) / r, 2)}
            mine = ours.get((day, sym)); n_cmp += 1
            if mine is None and theirs is None: continue
            bad = (mine is None) != (theirs is None) or (mine and theirs and (abs(mine["entry"] - theirs["entry"]) > 0.015
                    or abs(mine["exit"] - theirs["exit"]) > 0.015 or abs(float(mine["r_net"]) - theirs["r_net"]) > 0.02))
            if bad: diffs.append({"date": day, "symbol": sym, "ours": mine and {k: mine.get(k) for k in ("entry", "exit", "exit_time", "outcome", "r_net")}, "backtesting_py": theirs})
            else: out.append((day, sym))
    first = min((d for d in days if d >= "2026-11-18"), default=None)
    late = [x for x in diffs if first and x["date"] >= first]
    return {"days": days, "symbol_days_compared": n_cmp, "differences_from_2026_11_18": len(late), "trades_matched": len(out), "differences": diffs,
            "note": "backtesting.py fills the breakout at the signal bar's close (trade_on_close) with a stop-loss and a "
                    "take-profit, and closes at the 15:50 bar's close; our engine does the same by hand. A difference is "
                    "most likely a bar where both the stop and the target were touched (each engine has its own rule) or "
                    "a gap through the stop; each one is listed for review, none is corrected automatically."}


def main():
    repo, mode, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, os.path.join(repo, "scripts")); os.makedirs(outdir, exist_ok=True)
    res = {"at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "versions": versions()}
    for m, f in (("calendar", calendar), ("stats", stats_check), ("orb", orb)):
        if mode in (m, "all"):
            try: res[m] = f(repo)
            except Exception as ex:
                import traceback; res[m] = {"error": "%s: %s" % (type(ex).__name__, ex), "trace": traceback.format_exc()[-1500:]}
    json.dump(res, open(os.path.join(outdir, "xcheck.json"), "w"), indent=1, default=str)
    print(json.dumps({k: (v if k in ("versions", "at_utc") else {kk: vv for kk, vv in v.items() if kk in ("identical", "differences", "max_dsr_diff_ours_vs_scipy", "trades_matched", "error")} if isinstance(v, dict) else v) for k, v in res.items()}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
