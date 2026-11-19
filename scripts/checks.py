"""Integrity checks against look-ahead, bad data and self-deception (run by the orchestrator; findings go to dq and
the weekly report).

  python3 checks.py bar-timing REPO              -> confirms the 5m timestamp convention (bar START) and that 5m
                                                   bars agree with the daily bars (high/low/close within 0.2%)
  python3 checks.py xcheck-plan REPO DAY         -> the 9 symbols to cross-check tonight (SPY + 8 rotating by date)
  python3 checks.py xcheck REPO FILE.json        -> FILE = {"SYM": Twelve Data get_time_series 1day response, ...};
                                                   compares closes with the stored IBKR daily bars; > 0.5% apart ->
                                                   data/quality/excluded.jsonl (decisions.py / ml.py skip that day)
  python3 checks.py live-save REPO CANDS.json NOW -> keeps the live run's candidates (features as seen live) in
                                                   data/decisions/live/DAY.jsonl
  python3 checks.py parity REPO DAY              -> rebuilds DAY's candidates from the final stored bars and compares
                                                   them with what the live runs saw. A replay that looks better than
                                                   live (more winners, earlier entries, features that moved) means
                                                   look-ahead somewhere: reported as an issue.
  python3 checks.py trial REPO SOURCE NAME [N]   -> adds N (default 1) entries to the trial ledger data/trials.jsonl
  python3 checks.py trials REPO                  -> total trials so far (stats.py uses it as N for the deflated Sharpe)
  python3 checks.py stamp REPO                   -> commit, data hash and package versions (every report carries it)
  python3 checks.py fresh REPO TF [NOW]          -> are the free-feed bars (GitHub Actions + Alpaca, fetch_free.py)
                                                   current? 5m: every intraday symbol has a bar starting within the last
                                                   45 minutes of the session; 1d: every stock/ETF has the last
                                                   finished trading day. {"fresh": bool, "stale": [...]}. Tasks fetch
                                                   bars from IBKR only for the stale symbols.
"""
import json, os, sys, hashlib, subprocess, platform, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal
NY = ZoneInfo("America/New_York")


def jl(path): return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def ajl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for r in rows: f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")


def U(repo): return json.load(open(os.path.join(repo, "data", "universe.json")))


# ---------- bar timing ----------
def bar_timing(repo):
    u = U(repo); syms = ["SPY"] + u["watchlist"] + u["control"]; issues = []; votes = {"start": 0, "end": 0}; checked = 0
    for s in syms:
        b5 = jl(os.path.join(repo, "data", "bars", "5m", s + ".jsonl"))
        if not b5: continue
        b1 = {dt.datetime.fromtimestamp(b["t"], NY).date().isoformat(): b for b in jl(os.path.join(repo, "data", "bars", "1d", s + ".jsonl"))}
        days = {}
        for b in b5:
            if b["t"] % 300: issues.append("%s 5m bar not on a 5-minute boundary: %s" % (s, b["t"])); continue
            t = dt.datetime.fromtimestamp(b["t"], NY); days.setdefault(t.date().isoformat(), []).append((t.strftime("%H:%M"), b))
        for d, L in days.items():
            L.sort(); hms = [h for h, _ in L if "09:25" <= h <= "16:00"]
            if not hms: continue
            if hms[0] == "09:30": votes["start"] += 1
            elif hms[0] == "09:35": votes["end"] += 1
            last_ok = "12:55" if tcal.is_half(d) else "15:55"
            if hms[-1] == ("13:00" if tcal.is_half(d) else "16:00"): votes["end"] += 1
            rth = [b for h, b in L if "09:30" <= h <= last_ok]
            if d in b1 and len(rth) >= (42 if tcal.is_half(d) else 78):
                checked += 1; D = b1[d]
                hi, lo, cl = max(b["h"] for b in rth), min(b["l"] for b in rth), rth[-1]["c"]
                for name, a, z in (("high", hi, D["h"]), ("low", lo, D["l"]), ("close", cl, D["c"])):
                    if z and abs(a / z - 1) > 0.002: issues.append("%s %s: 5m %s %.4f vs daily %.4f" % (s, d, name, a, z))
    conv = "start" if votes["start"] and not votes["end"] else ("end" if votes["end"] and not votes["start"] else ("mixed" if votes["start"] else "unknown"))
    if conv in ("end", "mixed"): issues.insert(0, "5m timestamps are not all bar START times (%s): every intraday rule assumes start; fix before trusting intraday results" % votes)
    return {"convention": conv, "votes": votes, "days_compared_with_daily": checked, "ok": conv in ("start", "unknown") and not issues,
            "issues": issues[:40], "n_issues": len(issues)}


# ---------- cross-source check ----------
def xcheck_plan(repo, day):
    u = U(repo); pool = sorted(set(u["watchlist"] + u["control"] + [e for e in u.get("etfs", []) if not e.startswith("VIX")]) - {"SPY"})
    h = int(hashlib.sha1(day.encode()).hexdigest()[:8], 16); k = h % len(pool)
    pick = [pool[(k + i * 7) % len(pool)] for i in range(8)]
    return {"symbols": ["SPY"] + sorted(set(pick)), "tool": "Twelve Data get_time_series interval 1day outputsize 5"}


def xcheck(repo, path):
    data = json.load(open(path)); out = []; bad = []
    for sym, r in data.items():
        vals = r.get("values") if isinstance(r, dict) else r
        if not vals: out.append({"symbol": sym, "status": "no data"}); continue
        b1 = {dt.datetime.fromtimestamp(b["t"], NY).date().isoformat(): b["c"] for b in jl(os.path.join(repo, "data", "bars", "1d", sym + ".jsonl"))}
        for v in vals:
            d = str(v.get("datetime", ""))[:10]
            try: td = float(v.get("close"))
            except (TypeError, ValueError): continue
            ib = b1.get(d)
            if ib is None: continue
            diff = round(100 * (ib / td - 1), 3); row = {"symbol": sym, "date": d, "ibkr": ib, "twelve_data": td, "diff_pct": diff}
            out.append(row)
            if abs(diff) > 0.5: bad.append(row)
    now = dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M")
    ajl(os.path.join(repo, "data", "quality", "xcheck.jsonl"), [dict(r, checked_at=now) for r in out])
    have = {(r["symbol"], r["date"]) for r in jl(os.path.join(repo, "data", "quality", "excluded.jsonl"))}
    ajl(os.path.join(repo, "data", "quality", "excluded.jsonl"), [dict(r, why="IBKR vs Twelve Data close > 0.5%") for r in bad if (r["symbol"], r["date"]) not in have])
    return {"compared": sum(1 for r in out if "diff_pct" in r), "flagged": bad, "max_abs_diff_pct": max([abs(r["diff_pct"]) for r in out if "diff_pct" in r], default=None)}


def excluded(repo):
    return {(r["symbol"], r["date"]) for r in jl(os.path.join(repo, "data", "quality", "excluded.jsonl"))}


# ---------- live vs replay ----------
def live_save(repo, path, now):
    rows = json.load(open(path)); rows = rows if isinstance(rows, list) else [rows]
    by_day = {}
    for r in rows: by_day.setdefault(r.get("date") or now[:10], []).append(dict(r, seen_live_at=now))
    for d, L in by_day.items(): ajl(os.path.join(repo, "data", "decisions", "live", d + ".jsonl"), L)
    return {"saved": len(rows)}


def parity(repo, day):
    import decisions
    live = jl(os.path.join(repo, "data", "decisions", "live", day + ".jsonl"))
    if not live: return {"day": day, "status": "no live candidates saved"}
    first = {}
    for r in live: first.setdefault((r["symbol"], r["trade"]["entry_time"]), r)
    replay = decisions.candidates(repo, day, "16:00")
    rp = {(r["symbol"], r["trade"]["entry_time"]): r for r in replay}
    issues = []; feat_moved = 0; compared = 0
    for k, r in first.items():
        q = rp.get(k)
        if q is None: issues.append("%s %s seen live, missing in replay" % k); continue
        compared += 1
        if abs(q["trade"]["entry"] / r["trade"]["entry"] - 1) > 0.001: issues.append("%s %s entry live %.4f vs replay %.4f" % (k + (r["trade"]["entry"], q["trade"]["entry"])))
        moved = [f for f, v in r.get("x", {}).items() if isinstance(v, (int, float)) and isinstance(q["x"].get(f), (int, float))
                 and abs(v - q["x"][f]) > 1e-3 * max(1.0, abs(v))]
        if moved: feat_moved += 1; issues.append("%s %s features changed after the fact: %s" % (k + (",".join(moved[:6]),)))
    # signals the replay finds that no live run saw while it could have (entries up to 15:00; the 15:05 run is the last)
    late = [k for k, q in rp.items() if k not in first and q["trade"]["entry_time"] <= "15:00"]
    for k in late: issues.append("%s %s in replay but never seen live" % k)
    rr = [q["y"].get("y_stock") for k, q in rp.items() if q["y"].get("y_stock") is not None]
    lr = [rp[k]["y"].get("y_stock") for k in first if k in rp and rp[k]["y"].get("y_stock") is not None]
    res = {"day": day, "live": len(first), "replay": len(rp), "compared": compared, "features_moved": feat_moved,
           "replay_only": len(late), "mean_r_replay": round(sum(rr) / len(rr), 4) if rr else None,
           "mean_r_live_set": round(sum(lr) / len(lr), 4) if lr else None, "issues": issues[:30]}
    res["ok"] = not issues
    ajl(os.path.join(repo, "data", "quality", "parity.jsonl"), [{k: v for k, v in res.items() if k != "issues"}])
    return res


# ---------- trial ledger ----------
def trial(repo, source, name, n=1):
    ajl(os.path.join(repo, "data", "trials.jsonl"), [{"at": dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M"), "source": source, "name": name, "n": int(n)}])
    return {"logged": int(n)}


def trials(repo):
    rows = jl(os.path.join(repo, "data", "trials.jsonl")); per = {}
    for r in rows: per[r["source"]] = per.get(r["source"], 0) + r["n"]
    # unique names: re-evaluating the same config nightly is one trial, not one per night
    uniq = {(r["source"], r["name"]) for r in rows}
    return {"total_logged": sum(per.values()), "unique_trials": len(uniq), "by_source": per}


def n_trials(repo):
    return trials(repo)["unique_trials"]


# ---------- reproducibility ----------
def stamp(repo):
    try: commit = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception: commit = None
    h = hashlib.sha256(); nfiles = 0
    for sub in ("data/bars", "data/corp", "data/events", "data/snap", "data/macro.json", "data/universe.json"):
        p = os.path.join(repo, sub)
        files = [p] if os.path.isfile(p) else sorted(os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs) if os.path.isdir(p) else []
        for f in files:
            h.update(os.path.relpath(f, repo).encode()); h.update(open(f, "rb").read()); nfiles += 1
    vers = {"python": platform.python_version()}
    for m in ("numpy", "pandas", "sklearn", "scipy"):
        try: vers[m] = __import__(m).__version__
        except Exception: vers[m] = None
    return {"commit": commit, "data_sha256": h.hexdigest()[:16], "data_files": nfiles, "versions": vers,
            "at": dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M")}


def fresh(repo, tf, now=None):
    now = dt.datetime.fromisoformat(now).astimezone(NY) if now else dt.datetime.now(NY)
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); stocks = U["watchlist"] + U["control"]
    if tf == "5m":
        syms = stocks + ["SPY", "QQQ", "IWM"]
        close = now.replace(hour=13 if tcal.is_half(now.date()) else 16, minute=0, second=0, microsecond=0)
        ref = min(now, close)
        if not tcal.is_open(now.date()) or now.hour * 60 + now.minute < 615:   # before 10:15: last session's close
            d = now.date() - dt.timedelta(days=1)
            while not tcal.is_open(d): d -= dt.timedelta(days=1)
            ref = dt.datetime.combine(d, dt.time(16, 0), NY)
        need = ref - dt.timedelta(minutes=45)
    else:
        syms = stocks + U["etfs"]; d = now.date() - dt.timedelta(days=1 if now.hour < 17 else 0)
        while not tcal.is_open(d): d -= dt.timedelta(days=1)
        need = None
    stale = []
    for s in syms:
        B = jl(os.path.join(repo, "data", "bars", tf, s + ".jsonl"))
        if not B: stale.append(s); continue
        t = dt.datetime.fromtimestamp(max(b["t"] for b in B[-50:]), NY)
        if tf == "5m" and t < need: stale.append(s)
        if tf != "5m" and t.date() < d: stale.append(s)
    return {"tf": tf, "fresh": not stale, "stale": stale, "checked": len(syms), "at": now.strftime("%Y-%m-%d %H:%M")}


if __name__ == "__main__":
    a = sys.argv[1:]
    fn = {"bar-timing": lambda: bar_timing(a[1]), "xcheck-plan": lambda: xcheck_plan(a[1], a[2]), "xcheck": lambda: xcheck(a[1], a[2]),
          "live-save": lambda: live_save(a[1], a[2], a[3]), "parity": lambda: parity(a[1], a[2]),
          "trial": lambda: trial(a[1], a[2], a[3], a[4] if len(a) > 4 else 1), "trials": lambda: trials(a[1]), "stamp": lambda: stamp(a[1]),
          "fresh": lambda: fresh(a[1], a[2], a[3] if len(a) > 3 else None)}[a[0]]
    print(json.dumps(fn(), indent=1))
