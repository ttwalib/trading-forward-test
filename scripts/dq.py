"""Data-quality and staleness checks on the stored bars (run by the orchestrator and the watchdog).

  python3 dq.py REPO [DAY]     -> JSON {"ok": bool, "issues": [...], "per_tf": {...}}

Checks per data/bars/<tf>/<SYM>.jsonl:
- OHLC sanity: high >= max(open, close), low <= min(open, close), all prices > 0.
- Jumps: a close-to-close move above 25% (stocks, 5m/1d) or 15% (crypto, 1h/15m) between consecutive bars = suspect.
- Session gaps (5m): on each stored trading day of the test, regular-session bars 09:30-15:55 must all be present
  (78 per full day, 42 on half days); missing bars are listed, never filled.
- Staleness: on a trading day after 16:30 New York, the 5m files of the watchlist and SPY must hold that day;
  the crypto 1h files must have a bar that started within the last 3 hours.
- Splits (added 2026-11-19): an overnight daily move whose ratio is close to a common split ratio (2, 3, 4, 5, 10,
  1.5 or the inverses) and that data/corp has no split for = suspected unrecorded split.
- Bar timing and source agreement: checks.bar_timing (5m convention + 5m vs daily), the last IBKR vs Twelve Data
  cross-check and the last live-vs-replay parity result are folded in.
An issue never stops the test: reports show it, and decisions.py / ml.py skip days with missing opening-range bars.
"""
import json, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal
NY = ZoneInfo("America/New_York"); CRYPTO = {"BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE", "SHIB"}


def load(f):
    return [json.loads(l) for l in open(f) if l.strip()]


def run(repo, day=None):
    now = dt.datetime.now(NY); day = day or now.date().isoformat(); issues = []; per = {}
    base = os.path.join(repo, "data", "bars")
    for tf in sorted(os.listdir(base)):
        d = os.path.join(base, tf)
        if not os.path.isdir(d): continue
        per[tf] = 0
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".jsonl"): continue
            sym = fn[:-6]; B = load(os.path.join(d, fn)); per[tf] += 1
            lim = 0.15 if sym in CRYPTO else 0.25
            for i, b in enumerate(B):
                if min(b["o"], b["h"], b["l"], b["c"]) <= 0 or b["h"] < max(b["o"], b["c"]) - 1e-9 or b["l"] > min(b["o"], b["c"]) + 1e-9:
                    issues.append({"tf": tf, "sym": sym, "t": b["t"], "issue": "bad OHLC"})
                if tf == "1d" and i and B[i - 1]["c"] > 0 and sym not in CRYPTO and not sym.startswith("VIX"):
                    r = B[i - 1]["c"] / b["o"] if b["o"] else 1
                    for q in (2, 3, 4, 5, 10, 1.5, 0.5, 1 / 3, 0.25, 0.2, 0.1):
                        if abs(r / q - 1) < 0.03:
                            dd = dt.datetime.fromtimestamp(b["t"], NY).date().isoformat()
                            cf = os.path.join(repo, "data", "corp", sym + ".json")
                            known = json.load(open(cf)).get("splits", []) if os.path.exists(cf) else []
                            if not any(x["date"] == dd for x in known):
                                issues.append({"tf": tf, "sym": sym, "day": dd, "issue": "suspected unrecorded split (prev close / open = %.3f)" % r})
                if i and B[i - 1]["c"] >= 1 and abs(b["c"] / B[i - 1]["c"] - 1) > lim and not (tf == "1d" and sym.startswith("VIX")):
                    issues.append({"tf": tf, "sym": sym, "t": b["t"], "issue": "jump %.1f%%" % (100 * (b["c"] / B[i - 1]["c"] - 1))})
            if tf == "5m":
                by = {}
                for b in B:
                    t = dt.datetime.fromtimestamp(b["t"], NY); by.setdefault(t.date().isoformat(), set()).add(t.strftime("%H:%M"))
                for dd, hs in by.items():
                    if dd < str(tcal.START) or not tcal.is_open(dd) or dd > day: continue
                    end = "12:55" if tcal.is_half(dd) else "15:55"
                    exp = []; t = dt.datetime(2000, 1, 1, 9, 30)
                    while t.strftime("%H:%M") <= end: exp.append(t.strftime("%H:%M")); t += dt.timedelta(minutes=5)
                    if dd == day and now.date().isoformat() == day: exp = [h for h in exp if h <= (now - dt.timedelta(minutes=10)).strftime("%H:%M")]
                    miss = [h for h in exp if h not in hs]
                    if miss: issues.append({"tf": tf, "sym": sym, "day": dd, "issue": "missing %d bars" % len(miss), "first": miss[:5]})
            if tf == "1h" and sym in CRYPTO and B and day == now.date().isoformat() and time.time() - B[-1]["t"] > 3 * 3600 + 3600:
                issues.append({"tf": tf, "sym": sym, "issue": "stale: last bar %s" % dt.datetime.fromtimestamp(B[-1]["t"], NY).strftime("%m-%d %H:%M")})
    if tcal.is_open(day) and day == now.date().isoformat() and now.strftime("%H:%M") >= "16:30":
        U = json.load(open(os.path.join(repo, "data", "universe.json")))
        for s in U["watchlist"] + ["SPY"]:
            f = os.path.join(base, "5m", s + ".jsonl")
            if not os.path.exists(f) or not any(dt.datetime.fromtimestamp(b["t"], NY).date().isoformat() == day for b in load(f)[-100:]):
                issues.append({"tf": "5m", "sym": s, "issue": "stale: no bars for %s" % day})
    extra = {}
    try:
        import checks
        bt = checks.bar_timing(repo); extra["bar_timing"] = {k: bt[k] for k in ("convention", "days_compared_with_daily", "n_issues")}
        issues += [{"issue": "bar timing: " + x} for x in bt["issues"][:10]]
        xc = checks.jl(os.path.join(repo, "data", "quality", "xcheck.jsonl"))
        if xc:
            last = max(r["checked_at"] for r in xc); bad = [r for r in xc if r["checked_at"] == last and abs(r.get("diff_pct", 0) or 0) > 0.5]
            extra["xcheck"] = {"last": last, "flagged": len(bad)}
            issues += [{"sym": r["symbol"], "day": r["date"], "issue": "IBKR vs Twelve Data close differ %.2f%% (excluded from ML)" % r["diff_pct"]} for r in bad]
        pa = checks.jl(os.path.join(repo, "data", "quality", "parity.jsonl"))
        if pa:
            extra["parity_last"] = pa[-1]
            if not pa[-1].get("ok", True): issues.append({"day": pa[-1]["day"], "issue": "live vs replay mismatch: possible look-ahead (see checks.py parity)"})
    except Exception as e: extra["checks_error"] = str(e)[:160]
    return {"date": day, "ok": not issues, "issue_count": len(issues), "issues": issues[:80], "files_per_tf": per, **extra}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
