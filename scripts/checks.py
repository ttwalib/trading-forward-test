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
  python3 checks.py slip-save REPO CANDS.json QUOTES.json NOW
                                                -> slippage tracking without orders. QUOTES = {SYM: get_price_snapshot
                                                   response with bid_ask}, taken right after the live run picks its
                                                   candidates. Per candidate: the fill a real market order would get now
                                                   (ask for a long entry, bid for a short), the simulated fill (bar-close
                                                   entry), spread cost (half-spread %), drift (mid now vs simulated entry,
                                                   signed so positive = worse) and the delay in minutes. Rows go to
                                                   data/quality/slippage.jsonl; quotes also feed the per-symbol spread
                                                   model (corp.ingest_snap).
  python3 checks.py engine-report REPO [FROM]    -> engine detection price vs the 5-minute-lag price (measurement only)
  python3 checks.py health REPO [NOW]            -> ticks today, tick seconds, Actions minutes vs quota, token expiry, alerts
  python3 checks.py slip-report REPO [FROM]      -> medians of spread cost, drift by delay bucket and total vs the cost
                                                   the simulation charges (library.side_cost); flags a model that is
                                                   cheaper than reality
  python3 checks.py fresh REPO TF [NOW]          -> are the free-feed bars (GitHub Actions + Alpaca, fetch_free.py)
                                                   current? 5m: every intraday symbol has a bar starting within the last
                                                   45 minutes of the session; 1d: every stock/ETF has the last
                                                   finished trading day. {"fresh": bool, "stale": [...]}. Tasks fetch
                                                   bars from IBKR only for the stale symbols.
"""
import math
import glob, json, os, sys, hashlib, subprocess, platform, datetime as dt
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
                # close: the daily bar holds the official closing-auction price, the last 5m bar the last trade before
                # 16:00, so up to 0.6% (or 3 cents on cheap stocks) is normal (changed 2026-11-20; high/low stay at 0.2%)
                for name, a, z, tol in (("high", hi, D["h"], 0.002), ("low", lo, D["l"], 0.002), ("close", cl, D["c"], 0.006)):
                    if z and abs(a / z - 1) > tol and abs(a - z) > 0.03: issues.append("%s %s: 5m %s %.4f vs daily %.4f" % (s, d, name, a, z))
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


FEAT_TOL, FEAT_SHARE, ENTRY_TOL = 0.02, 0.10, 0.003


def parity(repo, day, replay=None, save=True):
    """Live candidates (saved before the outcome was known) against the end-of-day replay of the same day.

    Since 2026-11-21 the flags come in two kinds, so that a routine day raises none and every flag needs action:
    OUTCOME flags (always a failure): a candidate seen live that the replay does not have, a replay candidate that no
    live run saw while it could have, or an entry price more than 0.3% apart. FEATURE flags: a feature that differs by
    more than 2% (0.02 for values near zero) between the live row and the replay. A few of those are data revisions
    (late-reported volume); the day fails only when more than 10% of the compared candidates carry one, which is what
    a look-ahead leak would produce (checks.py leaktest plants one to prove it)."""
    import decisions
    live = jl(os.path.join(repo, "data", "decisions", "live", day + ".jsonl"))
    if not live: return {"day": day, "status": "no live candidates saved"}
    first = {}
    for r in live: first.setdefault((r["symbol"], r["trade"]["entry_time"]), r)
    replay = decisions.candidates(repo, day, "16:00") if replay is None else replay
    rp = {(r["symbol"], r["trade"]["entry_time"]): r for r in replay}
    outcome = []; feature = []; compared = 0
    for k, r in first.items():
        q = rp.get(k)
        if q is None: outcome.append("%s %s seen live, missing in replay" % k); continue
        compared += 1
        if abs(q["trade"]["entry"] / r["trade"]["entry"] - 1) > ENTRY_TOL: outcome.append("%s %s entry live %.4f vs replay %.4f" % (k + (r["trade"]["entry"], q["trade"]["entry"])))
        moved = [f for f, v in r.get("x", {}).items() if isinstance(v, (int, float)) and isinstance(q["x"].get(f), (int, float))
                 and abs(v - q["x"][f]) > FEAT_TOL * max(1.0, abs(v))]
        if moved: feature.append("%s %s features changed after the fact: %s" % (k + (",".join(moved[:6]),)))
    # signals the replay finds that no live run saw while it could have (entries up to 15:00; the 15:05 run is the last)
    late = [k for k, q in rp.items() if k not in first and q["trade"]["entry_time"] <= "15:00"]
    for k in late: outcome.append("%s %s in replay but never seen live" % k)
    rr = [q["y"].get("y_stock") for k, q in rp.items() if q["y"].get("y_stock") is not None]
    lr = [rp[k]["y"].get("y_stock") for k in first if k in rp and rp[k]["y"].get("y_stock") is not None]
    share = round(len(feature) / compared, 3) if compared else 0.0
    res = {"day": day, "live": len(first), "replay": len(rp), "compared": compared, "outcome_flags": len(outcome),
           "features_moved": len(feature), "feature_share": share,
           "replay_only": len(late), "mean_r_replay": round(sum(rr) / len(rr), 4) if rr else None,
           "mean_r_live_set": round(sum(lr) / len(lr), 4) if lr else None, "issues": (outcome + feature)[:30]}
    res["ok"] = not outcome and share <= FEAT_SHARE
    if save: ajl(os.path.join(repo, "data", "quality", "parity.jsonl"), [{k: v for k, v in res.items() if k != "issues"}])
    return res


def leaktest(repo, day):
    """Plants a look-ahead leak in a copy of the replay (one feature is nudged by the trade's own outcome, which is
    what a feature built with future bars looks like) and confirms that parity() fails. Writes nothing to the repo's
    quality log. Used by the independent audit; passed means the check can see a leak."""
    import decisions, copy
    clean = decisions.candidates(repo, day, "16:00"); base = parity(repo, day, replay=clean, save=False)
    if base.get("status"): return {"day": day, "status": base["status"]}
    leaky = copy.deepcopy(clean); planted = 0
    for q in leaky:
        y = q["y"].get("y_stock")
        if y is None or "or_vol_rel" not in q["x"]: continue
        q["x"]["or_vol_rel"] = q["x"]["or_vol_rel"] * (1.25 if y > 0 else 0.75); planted += 1
    hit = parity(repo, day, replay=leaky, save=False)
    return {"day": day, "planted_in": planted, "clean_ok": base["ok"], "clean_feature_share": base["feature_share"],
            "leak_ok": hit["ok"], "leak_feature_share": hit["feature_share"],
            "passed": planted > 0 and base["ok"] and not hit["ok"],
            "note": None if base["ok"] else "the clean replay already fails on this day: pick a day whose parity is ok"}


def verdict_leaktest(repo):
    """Planted late and edited objects on the VERDICT path (review N5, 2026-11-24), run every night on a throw-away copy
    of the repository; writes nothing to the repo. It plants, with GitHub sightings at chosen times: (1) a weekly seal
    whose own sealed_at says 09:00 but which GitHub first saw at 10:00 -> allocator.judge_seals must drop it, while an
    on-time control seal must count; (2) a ranking first seen at 09:45 -> rank.score must drop it and count the day as
    missed; (3) a pick first seen at 09:40 -> it must not count; (4) a pick whose ledger row was edited after it was
    witnessed -> scored with the first-seen sizing; (5) a witnessed pick deleted from the ledger -> still scored.
    Also runs the ML parity leak test (leaktest) on the latest day with live candidates. passed = every plant caught."""
    import shutil, tempfile, witness, importlib
    out = {"plants": {}}
    with tempfile.TemporaryDirectory() as T:
        dst = os.path.join(T, "r")
        shutil.copytree(repo, dst, ignore=shutil.ignore_patterns(".git", "hist", "optarch", "5m", "15m", "1h", "opt5m", "models", "pit", "decisions"))
        W = importlib.reload(witness); W.ENFORCE_FROM = "2000-01-01"    # the rule applies to every planted day
        days = [d for d in __import__("tcal").trading_days("2026-11-16", dt.datetime.now(NY).date().isoformat())]
        d_late, d_ok = days[-1], days[-2]
        def sight(kind, oid, obj, ny, extra=None):
            t = dt.datetime.fromisoformat(ny).replace(tzinfo=NY)
            w = {"kind": kind, "id": oid, "sha": W.sha(obj), "seen_at_ny": t.strftime("%Y-%m-%d %H:%M:%S"),
                 "seen_at_utc": t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "source": "plant", "grandfathered": False, "altered": False}
            w.update(extra or {}); d = os.path.join(dst, W.OBJ, kind); os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "plant-%s-%s.json" % (kind, W.sha(oid)[:8])), "w").write(json.dumps(w) + "\n")
        # (1) seals: one late, one on time (the planted effective days replace nothing: first valid row per day stands)
        jf = os.path.join(dst, "data", "allocator", "judge.jsonl"); os.makedirs(os.path.dirname(jf), exist_ok=True)
        rows = [{"effective": d_late, "sealed_at": d_late + "T09:00:00-05:00", "weights": {"PLANT late": 1.0}},
                {"effective": d_ok, "sealed_at": d_ok + "T09:00:00-05:00", "weights": {"PLANT ok": 1.0}}]
        keep = [l for l in open(jf)] if os.path.exists(jf) else []
        keep = [l for l in keep if l.strip() and json.loads(l).get("effective") not in (d_late, d_ok)]
        open(jf, "w").write("".join(keep) + "".join(json.dumps(r) + "\n" for r in rows))
        sight("seal", "judge.jsonl|%s|%s" % (d_late, rows[0]["sealed_at"]), rows[0], d_late + " 10:00:00")
        sight("seal", "judge.jsonl|%s|%s" % (d_ok, rows[1]["sealed_at"]), rows[1], d_ok + " 09:00:00")
        import allocator as A; A = importlib.reload(A)
        js = A.judge_seals(dst)
        out["plants"]["late_seal_dropped"] = "PLANT late" not in (js.get(d_late) or {})
        out["plants"]["on_time_seal_kept"] = "PLANT ok" in (js.get(d_ok) or {})
        # (2) ranking first seen at 09:45
        rd = os.path.join(dst, "data", "picks", "rank"); os.makedirs(rd, exist_ok=True)
        R = {"date": d_late, "sealed_at": d_late + "T09:10:00-05:00", "scores": {"AAPL": 1}, "model": "plant"}
        json.dump(R, open(os.path.join(rd, d_late + ".json"), "w"))
        sight("rank", "rank|%s|%s" % (d_late, R["sealed_at"]), R, d_late + " 09:45:00")
        import rank as RK; RK = importlib.reload(RK); RK.score(dst, d_late)
        rs = json.load(open(os.path.join(dst, "data", "picks", "rank_score.json")))
        row = [r for r in rs["rows"] if r["date"] == d_late]
        out["plants"]["late_ranking_counted_as_missed"] = bool(row) and bool(row[0].get("missed"))
        # (3)-(5) picks
        lp = os.path.join(dst, "data", "ledger", "AgentPicks.jsonl")
        late = {"picked_at": d_late + " 09:00", "asset": "stock", "symbol": "PLNTL", "status": "picked", "checks": "w=0.30 | hold=1"}
        edit = {"picked_at": d_late + " 08:50", "asset": "stock", "symbol": "PLNTE", "status": "picked", "checks": "w=0.10 | hold=1"}
        gone = {"picked_at": d_late + " 08:55", "asset": "stock", "symbol": "PLNTG", "status": "picked", "checks": "w=0.20 | hold=1"}
        with open(lp, "a") as f:
            for r in (late, dict(edit, checks="w=0.40 | hold=1")): f.write(json.dumps(r) + "\n")
        cp = W._pick_copy
        sight("pick", W.row_id(late), cp(late), d_late + " 09:40:00", {"row": cp(late)})
        sight("pick", W.row_id(edit), cp(edit), d_late + " 09:00:00", {"row": cp(edit)})
        sight("pick", W.row_id(gone), cp(gone), d_late + " 09:00:00", {"row": cp(gone)})
        PR, WW = W.pick_rows(dst); by = {r["symbol"]: r for r in PR}
        out["plants"]["late_pick_not_counted"] = not W.counts(WW.get(W.row_id(late)), d_late)
        out["plants"]["edited_pick_scored_as_first_seen"] = "w=0.10" in str(by.get("PLNTE", {}).get("checks"))
        out["plants"]["deleted_pick_still_scored"] = "PLNTG" in by and W.counts(WW.get(W.row_id(gone)), d_late)
        ig = W.integrity(dst)
        out["plants"]["integrity_flags_edit_and_delete"] = (any(x["id"] == W.row_id(edit) for x in ig["altered"])
                                                             and any(x["id"] == W.row_id(gone) for x in ig["missing"]))
    importlib.reload(witness)
    try:      # the ML parity leak test on the latest day with live candidates
        lv = sorted(f[:-6] for f in os.listdir(os.path.join(repo, "data", "decisions", "live")) if f.endswith(".jsonl"))
        out["ml_parity"] = {"status": "no live day with a clean parity"}
        for d in reversed(lv[-8:]):           # the latest day whose clean replay passes parity (else the test proves nothing)
            r = leaktest(repo, d)
            if r.get("clean_ok"): out["ml_parity"] = r; break
    except Exception as e: out["ml_parity"] = {"error": str(e)[:200]}
    ml_ok = out["ml_parity"].get("passed") is not False
    out["passed"] = all(out["plants"].values()) and ml_ok
    return out


# ---------- weekly random-day replay ----------
def replay_days(repo, n=5):
    """Five random past days a night instead of one (2026-11-23, after the GitHub budget rise): distinct days, drawn
    with seeds from the ISO week, each re-run with replay_day."""
    import random
    T = jl(os.path.join(repo, "data", "ledger", "Trades.jsonl")); today = dt.datetime.now(NY).date().isoformat()
    days = sorted({r["date"] for r in T if r["date"] < today})
    if not days: return {"status": "no past days"}
    iso = dt.datetime.now(NY).isocalendar(); pick = random.Random(iso[0] * 100 + iso[1]).sample(days, min(n, len(days)))
    res = [replay_day(repo, d) for d in sorted(pick)]
    return {"days": [r.get("day") for r in res], "identical": all(r.get("identical") for r in res),
            "diffs": [x for r in res for x in r.get("diffs", [])][:30], "checked": len(res)}


def replay_day(repo, day=None, seed=None):
    """Re-runs the baseline-A rules (orb_daily.py) on the stored 5-minute bars of one past test day and compares the
    trades with the ledger (watchlist "Trades" and the control list in "VariantTrades"). The day is drawn at random
    from the test days that have ledger rows, seeded by the ISO week, so the same week always checks the same day."""
    import subprocess, random, tempfile, tcal
    T = jl(os.path.join(repo, "data", "ledger", "Trades.jsonl")); days = sorted({r["date"] for r in T})
    today = dt.datetime.now(NY).date().isoformat(); days = [d for d in days if d < today]
    if not days: return {"status": "no past days"}
    if day is None:
        iso = dt.datetime.now(NY).isocalendar(); seed = seed if seed is not None else iso[0] * 100 + iso[1]
        day = random.Random(seed).choice(days)
    u = U(repo); here = os.path.dirname(os.path.abspath(__file__)); out = {"day": day, "sets": {}, "diffs": []}
    d0 = int(dt.datetime.fromisoformat(day).replace(tzinfo=NY, hour=9, minute=30).timestamp())
    ctl = [r for r in jl(os.path.join(repo, "data", "ledger", "VariantTrades.jsonl")) if r["date"] == day and "control" in str(r["variant"]).lower()]
    for name, syms, led in (("watchlist", u["watchlist"], [r for r in T if r["date"] == day]), ("control", u["control"], ctl)):
        if name == "control" and day < "2026-11-19": continue          # the control list started on 2026-11-19
        bars = {}
        for s in syms:
            B = [b for b in jl(os.path.join(repo, "data", "bars", "5m", s + ".jsonl")) if d0 <= b["t"] < d0 + 23400]
            if B: bars[s] = {"time": [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
                             "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B], "close": [b["c"] for b in B]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f: json.dump(bars, f); tmp = f.name
        p = subprocess.run([sys.executable, os.path.join(here, "orb_daily.py"), tmp, day, "16:00"], capture_output=True, text=True); os.remove(tmp)
        if p.returncode: out["diffs"].append("%s: orb_daily failed: %s" % (name, p.stderr[-200:])); continue
        new = {t["symbol"]: t for t in json.loads(p.stdout)["trades"]}; old = {r["symbol"]: r for r in led}
        out["sets"][name] = {"ledger": len(old), "replay": len(new), "bars_for": len(bars)}
        for s in sorted(set(new) | set(old)):
            a, b = old.get(s), new.get(s)
            if a is None: out["diffs"].append("%s %s: replay has a trade (%s %.2fR), ledger has none" % (name, s, b["outcome"], b["r_net"]))
            elif b is None: out["diffs"].append("%s %s: ledger has a trade (%s), replay has none" % (name, s, a["outcome"]))
            elif a["outcome"] != b["outcome"] or abs(float(a["r_net"]) - b["r_net"]) > 0.05:
                out["diffs"].append("%s %s: ledger %s %.2fR vs replay %s %.2fR" % (name, s, a["outcome"], float(a["r_net"]), b["outcome"], b["r_net"]))
    out["identical"] = not out["diffs"]; out["diffs"] = out["diffs"][:30]
    ajl(os.path.join(repo, "data", "quality", "replay_day.jsonl"), [{"day": day, "at": today, "identical": out["identical"], "n_diffs": len(out["diffs"])}])
    return out


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


def slip_save(repo, cands_path, quotes_path, now):
    import corp
    C = json.load(open(cands_path)); Q = json.load(open(quotes_path)); t_now = dt.datetime.fromisoformat(now[:16])
    out = []; seen = {(r["id"], r["at"][:13]) for r in jl(os.path.join(repo, "data", "quality", "slippage.jsonl"))}
    for c in (C if isinstance(C, list) else C.get("candidates", [])):
        tr = c.get("trade") or {}; sym = c.get("symbol"); q = Q.get(sym) or {}
        ba = q.get("bid-ask") or q.get("bid_ask") or {}; bid, ask = ba.get("bid"), ba.get("ask")
        e = tr.get("entry")
        if not (bid and ask and ask > bid > 0 and e): continue
        long = str(tr.get("side", "long")).lower() not in ("short", "sell"); mid = (bid + ask) / 2; sg = 1 if long else -1
        fill = ask if long else bid
        try: delay = (t_now - dt.datetime.fromisoformat(str(c["decided_at"])[:16])).total_seconds() / 60
        except (KeyError, ValueError): delay = None
        row = {"id": c.get("id"), "symbol": sym, "at": now[:16], "decided_at": c.get("decided_at"), "side": "long" if long else "short",
               "delay_min": round(delay, 1) if delay is not None else None, "sim_entry": e, "bid": bid, "ask": ask,
               "spread_pct": round(50 * (ask - bid) / mid, 5), "drift_pct": round(sg * (mid / e - 1) * 100, 5),
               "total_pct": round(sg * (fill / e - 1) * 100, 5), "outcome_open": tr.get("outcome") == "open"}
        if (row["id"], row["at"][:13]) in seen: continue
        out.append(row)
    if out: ajl(os.path.join(repo, "data", "quality", "slippage.jsonl"), out)
    corp.ingest_snap(repo, quotes_path, now[:16])
    return {"saved": len(out), "rows": [{k: r[k] for k in ("symbol", "delay_min", "spread_pct", "drift_pct")} for r in out]}


def slip_report(repo, start=None):
    import statistics as st, library
    R = [r for r in jl(os.path.join(repo, "data", "quality", "slippage.jsonl")) if not start or r["at"] >= start]
    if not R: return {"n": 0, "note": "no slippage rows yet"}
    med = lambda xs: round(st.median(xs), 4) if xs else None
    buckets = {"0-15": (0, 15), "15-30": (15, 30), "30-65": (30, 65), "65+": (65, 1e9)}
    by = {k: [r["drift_pct"] for r in R if r["delay_min"] is not None and a <= r["delay_min"] < b] for k, (a, b) in buckets.items()}
    model = []
    for r in R:
        try: model.append(library.side_cost(repo, r["symbol"], r["at"][:10], 0.03))
        except Exception: pass
    out = {"n": len(R), "from": R[0]["at"], "to": R[-1]["at"], "spread_pct_median": med([r["spread_pct"] for r in R]),
           "drift_pct_median_by_delay": {k: {"n": len(v), "median": med(v)} for k, v in by.items()},
           "total_pct_median": med([r["total_pct"] for r in R]), "model_side_cost_pct_median": med(model),
           "worst": sorted(R, key=lambda r: -r["total_pct"])[:3]}
    out["model_cheaper_than_spread"] = bool(model) and out["spread_pct_median"] > out["model_side_cost_pct_median"]
    out["note"] = ("spread = what a market order pays now; drift = price move between the simulated fill and the quote "
                   "(mostly the hourly-run delay); the simulation charges model_side_cost per side")
    return out


# ---------- cost reality check (report only, added 2026-11-24, runbook item 51) ----------
def cost_check(repo):
    """Are the costs the simulation charges at least what the market would really have charged? Per side, measured =
    half the quoted bid/ask spread at our signals (slip-report) plus the median price difference between the engine's
    detection fill and the 5-minute rule (engine-report, positive = the engine fill was worse). Assumed = the median
    per-side cost the library model charges for the same symbols and days. Verdict "conservative" when assumed >=
    measured, "too cheap" otherwise. Becomes meaningful after about 100 measured rows; nothing is changed by it."""
    sr, er = slip_report(repo), engine_report(repo)
    if not sr.get("n"): return {"n": 0, "note": "no slippage rows yet"}
    half = sr["spread_pct_median"] / 2; fillgap = max(0.0, (er.get("baseline") or {}).get("median_cost_vs_lag_pct") or 0.0)
    measured = round(half + fillgap, 4); assumed = sr.get("model_side_cost_pct_median")
    return {"n_quotes": sr["n"], "n_engine_fills": (er.get("baseline") or {}).get("n"), "half_spread_pct": round(half, 4),
            "engine_fill_gap_pct": round(fillgap, 4), "measured_side_cost_pct": measured, "assumed_side_cost_pct": assumed,
            "ratio_assumed_to_measured": round(assumed / measured, 2) if assumed and measured else None,
            "verdict": None if assumed is None else ("conservative" if assumed >= measured else "too cheap"),
            "enough_data": sr["n"] >= 100,
            "note": "per side, in percent of price; the delay drift of the hourly AI runs is left out because the engine, "
                    "not the hourly run, sets fills since 2026-11-19"}


# ---------- engine fill vs the 5-minute rule (measurement only, added 2026-11-20) ----------
def engine_report(repo, start=None):
    """For every engine detection made within 20 minutes of its signal: the engine's detection price against the price
    the 5-minute-lag rule would have used (open of the bar that starts 5 minutes after the signal bar ends). Positive
    cost_vs_lag_pct = the engine fill was worse than the 5-minute rule (longs paid more, shorts received less).
    Baseline rows are the ones fills.py uses; library rows (with "strategy") are sealed for this comparison only."""
    import statistics as st, fills
    out = {"baseline": [], "library": []}
    for f in sorted(glob.glob(os.path.join(repo, "data", "decisions", "engine", "*.jsonl"))):
        day = os.path.basename(f)[:10]
        if start and day < start: continue
        for r in jl(f):
            if not r.get("fill_price") or r.get("delay_min") is None or r["delay_min"] > 20 or not r.get("signal_end"): continue
            b = fills._bars5(repo, r["symbol"]).get((day, fills.plus(r["signal_end"], fills.LAG_MIN)))
            if not b or not b.get("o"): continue
            if r.get("revision"): continue      # same breakout re-sealed under another bar: counted once
            sign = -1 if r.get("side") == "short" else 1
            out["library" if r.get("strategy") else "baseline"].append(
                {"day": day, "symbol": r["symbol"], "delay_min": r["delay_min"], "cost_vs_lag_pct": round(sign * (float(r["fill_price"]) / b["o"] - 1) * 100, 4)})
    rep = {}
    for k, R in out.items():
        x = [q["cost_vs_lag_pct"] for q in R]
        rep[k] = {"n": len(R), "median_cost_vs_lag_pct": round(st.median(x), 4) if x else None, "mean_cost_vs_lag_pct": round(sum(x) / len(x), 4) if x else None,
                  "worse_than_lag": sum(1 for v in x if v > 0), "median_delay_min": round(st.median([q["delay_min"] for q in R]), 1) if R else None}
    rep["note"] = ("measurement only: fills.py keeps using engine prices for baseline rows detected within 20 minutes; a mean cost "
                   "clearly above 0 over 100+ rows would mean the engine fill is harsher than the 5-minute rule, a mean below 0 that it flatters")
    return rep


# ---------- health line (added 2026-11-20) ----------
TOKEN_EXPIRY = "2027-06-15"      # the pinger's GitHub token (owner's cron-job.org account); renew before this date
MINUTES_QUOTA = 3000             # GitHub Pro Actions minutes per month (owner upgraded 2026-11-20)


def tick_log(repo, mode, secs=None):
    """Called by fetch_free.py after every run: ops/diag/ticks.json keeps {day: {mode: [HH:MM, ...]}} and seconds."""
    p = os.path.join(repo, "ops", "diag", "ticks.json")
    try: T = json.load(open(p))
    except Exception: T = {}
    now = dt.datetime.now(NY); d = T.setdefault(now.date().isoformat(), {})
    d.setdefault(mode, []).append(now.strftime("%H:%M"))
    if secs is not None: d.setdefault("secs" if mode == "tick" else "secs_other", []).append(round(secs, 1))
    for k in sorted(T)[:-45]: T.pop(k)
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(T, open(p, "w"), separators=(",", ":"))


def health(repo, now=None):
    """One line of plumbing health: are the ticks arriving, how long do they take, are the minutes inside the quota,
    how long until the pinger's token expires. alerts lists what needs the owner or the orchestrator."""
    import statistics as st
    now = dt.datetime.fromisoformat(now).astimezone(NY) if now else dt.datetime.now(NY)
    try: T = json.load(open(os.path.join(repo, "ops", "diag", "ticks.json")))
    except Exception: T = {}
    day = now.date().isoformat(); td = T.get(day, {}); ticks = td.get("tick", [])
    hm = now.hour * 60 + now.minute; mins = lambda x: int(x[:2]) * 60 + int(x[3:])
    open_now = tcal.is_open(now.date()) and 9 * 60 + 40 <= hm <= (13 if tcal.is_half(now.date()) else 16) * 60
    last_age = hm - mins(ticks[-1]) if ticks else None
    gaps = [mins(b) - mins(a) for a, b in zip(ticks, ticks[1:])]
    month = day[:7]; used = 0
    for d, v in T.items():
        if d[:7] != month: continue
        runs = sum(len(x) for k, x in v.items() if not k.startswith("secs")); secs = v.get("secs", []) + v.get("secs_other", [])
        used += sum(max(1, math.ceil(x / 60 + 0.25)) for x in secs) + max(0, runs - len(secs))   # +15 s: checkout and commit
    dom = now.day; days_in_month = (dt.date(now.year + (now.month == 12), now.month % 12 + 1, 1) - dt.timedelta(days=1)).day
    tracked_days = max(1, sum(1 for d in T if d[:7] == month))
    left = sum(1 for k in range(dom + 1, days_in_month + 1) if tcal.is_open(dt.date(now.year, now.month, k)))
    proj = used + round(used / tracked_days * left)
    # FULL-MONTH projection (2026-11-23, external review 3.8): the figure above under-reads a month in which the 5-minute
    # ticks only started part-way. This one prices a whole month at the busiest recent day's rate.
    per_day = {}
    for d, v in T.items():
        sc = v.get("secs", []) + v.get("secs_other", []); rn = sum(len(x) for k, x in v.items() if not k.startswith("secs"))
        per_day[d] = sum(max(1, math.ceil(x / 60 + 0.25)) for x in sc) + max(0, rn - len(sc))
    open_days = [d for d in sorted(per_day) if tcal.is_open(d)][-5:]
    rate_open = max((per_day[d] for d in open_days), default=0)
    closed = [per_day[d] for d in sorted(per_day) if not tcal.is_open(d)][-4:]
    rate_closed = max(closed, default=0)
    full_month = rate_open * 22 + rate_closed * 9
    secs_today = td.get("secs", [])
    size_mb = None
    try:
        size_mb = round(sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.join(repo, "data")) for f in fs) / 1e6, 1)
    except Exception: pass
    days_to_expiry = (dt.date.fromisoformat(TOKEN_EXPIRY) - now.date()).days
    H = {"at": now.strftime("%Y-%m-%d %H:%M"), "ticks_today": len(ticks), "last_tick": ticks[-1] if ticks else None,
         "last_tick_age_min": last_age, "max_gap_min": max(gaps) if gaps else None,
         "tick_seconds_median": round(st.median(secs_today), 1) if secs_today else None, "tick_seconds_max": max(secs_today) if secs_today else None,
         "minutes_month_so_far": used, "minutes_month_projected": proj, "minutes_full_month_estimate": full_month, "minutes_quota": MINUTES_QUOTA,
         "token_expiry": TOKEN_EXPIRY, "token_days_left": days_to_expiry, "data_size_mb": size_mb, "alerts": []}
    # The hourly backup tick logs itself just before this check, so the gap before the latest tick counts too.
    worst = max([x for x in (last_age, gaps[-1] if gaps else None) if x is not None], default=None)
    if open_now and ((worst is None and hm > 600) or (worst is not None and worst > 20) or (len(ticks) < 2 and hm > 600)):
        H["alerts"].append("PINGER: gap of %s minutes between ticks in market hours (the external pinger may be down)" % (worst if worst is not None else "all"))
    if secs_today and max(secs_today) > 45: H["alerts"].append("TICK SLOW: a tick took %.0f s (over 60 s doubles the minutes)" % max(secs_today))
    try:                                   # tamper-evident chain (scripts/chain.py, 2026-11-23)
        C = json.load(open(os.path.join(repo, "data", "nightly", "chain.json")))
        if not C.get("ok", True): H["alerts"].append("CHAIN BROKEN: %d append-only evidence line(s) changed after sealing (data/nightly/chain.json)" % len(C.get("broken", [])))
    except Exception: pass
    try:      # the nightly planted-leak test on the verdict path (review N5)
        L = json.load(open(os.path.join(repo, "data", "nightly", "leaktest.json")))
        if L.get("passed") is False: H["alerts"].append("LEAK TEST FAILED: a planted late or edited seal, ranking or pick was not caught (data/nightly/leaktest.json)")
    except Exception: pass
    try:      # witnessed objects edited or deleted afterwards (review N3)
        G = json.load(open(os.path.join(repo, "data", "nightly", "witness.json"))).get("integrity", {})
        if G.get("altered") or G.get("missing"): H["alerts"].append("WITNESS: %d witnessed object(s) altered and %d missing after they were first seen (python3 scripts/witness.py . --report)" % (G.get("altered", 0), G.get("missing", 0)))
    except Exception: pass
    if proj > 0.8 * MINUTES_QUOTA: H["alerts"].append("MINUTES: projected %d of %d this month" % (proj, MINUTES_QUOTA))
    if days_to_expiry <= 21: H["alerts"].append("TOKEN: the pinger token expires in %d days (%s)" % (days_to_expiry, TOKEN_EXPIRY))
    if size_mb and size_mb > 700: H["alerts"].append("REPO: data is %.0f MB (GitHub soft limit 1 GB)" % size_mb)
    return H


def fresh(repo, tf, now=None):
    now = dt.datetime.fromisoformat(now).astimezone(NY) if now else dt.datetime.now(NY)
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); stocks = U["watchlist"] + U["control"]
    if tf == "5m":
        wide = sorted(set(stocks) | {x for x in U.get("universe", []) if x != "GOOG"}) if (U.get("intraday_wide") or U.get("intraday_wide_data")) else stocks
        syms = wide + ["SPY", "QQQ", "IWM"]
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
          "leaktest": lambda: leaktest(a[1], a[2]), "verdict-leaktest": lambda: verdict_leaktest(a[1]), "replay-day": lambda: replay_day(a[1], a[2] if len(a) > 2 else None), "replay-days": lambda: replay_days(a[1], int(a[2]) if len(a) > 2 else 5),
          "engine-report": lambda: engine_report(a[1], a[2] if len(a) > 2 else None), "health": lambda: health(a[1], a[2] if len(a) > 2 else None),
          "trial": lambda: trial(a[1], a[2], a[3], a[4] if len(a) > 4 else 1), "trials": lambda: trials(a[1]), "stamp": lambda: stamp(a[1]),
          "slip-save": lambda: slip_save(a[1], a[2], a[3], a[4]), "slip-report": lambda: slip_report(a[1], a[2] if len(a) > 2 else None), "cost-check": lambda: cost_check(a[1]),
          "fresh": lambda: fresh(a[1], a[2], a[3] if len(a) > 3 else None)}[a[0]]
    print(json.dumps(fn(), indent=1))
