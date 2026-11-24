#!/usr/bin/env python3
"""The challenger lane: a permanent register of strategies, scored only on days after they were written down.

Added 2026-11-22 (owner decision: the test should keep running and building on new data). It sits OUTSIDE the
frozen scripts and has no weight in the H1 verdict; cycle 1 (to 2027-05-14) is judged exactly as registered.

How it works
- REGISTER: every new idea (strategy-lab approvals, the "version 2" of the simple-rule response, ML models, ideas
  from the owner) is saved in strategies/registry.json with its id, source, rules, a SHA-256 of its code files and the
  time it was registered. It is scored only from FORWARD_FROM, the next full trading day after registration.
  At most MAX_NEW_PER_MONTH new entries per calendar month (seeds excepted); a retrain or fix of an existing entry is a
  new VERSION with its own hash and its own forward start, never a new entry.
- SCORE (nightly, step "lane"): each entry's daily results on its forward days only, against the fixed yardsticks
  (SPY, equal weight, baseline A, risk parity) and the current champion, after costs as the series already carry them.
  Day-block bootstrap (5-day blocks, 10,000 resamples, seed 20261121) for "beats X"; probabilistic Sharpe deflated by
  the LIFETIME count of unique trials (data/trials.jsonl) for "is it luck".
- REVIEW (fixed dates only: the third Tuesday of February, May, August and November, first on 2027-05-18):
  PROMOTE a challenger to champion if it has at least MIN_DAYS forward days, beats the champion AND every yardstick
  with bootstrap chance >= PROMOTE_P, and its deflated Sharpe chance is >= DSR_MIN. The bar is the same at every
  review (a constant boundary for repeated looks), and it is high on purpose: reviews never stop, so a lower bar would
  promote a lucky challenger sooner or later. If several qualify, the highest Sharpe wins.
  RETIRE an entry (challenger or champion) if, over its last RETIRE_WINDOW forward days, the chance that it beats the
  best yardstick is <= RETIRE_P, or its forward drawdown exceeds RETIRE_DD %. A retired champion hands over to the
  best remaining challenger only if that one meets the promotion bar; otherwise the current champion stays (since 2026-11-23 the champion is the AI-judgment allocator, Quantavius's own book; the formula is a yardstick).
- VERSIONS: data/lane/champions.jsonl records every change of champion with the version hash. Nothing is deleted.

Series an entry can point to (field "series"):
  {"type": "portfolio", "col": "ai"}             a column of data/allocator/portfolio.jsonl (daily %)
  {"type": "sleeve", "name": "W1"}               an allocator sleeve (daily % of sleeve capital)
  {"type": "file", "path": "data/lane/series/X.jsonl"}  rows {"date", "ret_pct"} written by the entry's own runner
  {"type": "lab_crypto", "module": "strategies/x.py", "coins": ["BTC", "ETH", "SOL"]}  run nightly on stored 1h bars;
      each coin holds 1/len(coins) of the sleeve; a trade's net % counts on the NY date of its exit (weekend exits on
      the next trading day)

  python3 registry.py register REPO ID SOURCE KIND SERIES_JSON FILES_CSV "RULES" [FORWARD_FROM]
  python3 registry.py version REPO ID FILES_CSV "NOTE"
  python3 registry.py status REPO ID STATUS "REASON"
  python3 registry.py auto REPO          register strategy-lab APPROVED strategies not yet registered
  python3 registry.py score REPO [DAY]   -> data/lane/scores.json (nightly)
  python3 registry.py review REPO DAY [--dry]   apply the review rules (only on a review day unless --dry)
  python3 registry.py list REPO
Testing only, not financial advice. Nothing here places, previews, modifies or cancels an order.
"""
import hashlib, importlib.util, json, math, os, random, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tcal

MAX_NEW_PER_MONTH = 6   # raised from 3 on 2026-11-24 (owner expects 4+ new ideas a month; no lane entry scored yet)
MIN_DAYS, PROMOTE_P, DSR_MIN = 60, 0.98, 0.95
RETIRE_WINDOW, RETIRE_P, RETIRE_DD = 120, 0.10, 20.0
FIRST_REVIEW = dt.date(2027, 5, 18)
YARDSTICKS = ("spy", "equal", "base_a", "sh_rp", "ai")   # "ai" = the cycle-1 formula, a foundation yardstick since 2026-11-23
SEED, B, BLOCK = 20261121, 10000, 5
STATUSES = ("incubating", "challenger", "champion", "retired")


def P(repo, *a): return os.path.join(repo, *a)
def now(): return dt.datetime.now(tcal.NY)


def load(repo):
    f = P(repo, "strategies", "registry.json")
    return json.load(open(f)) if os.path.exists(f) else {"entries": {}, "champion": None}


def save(repo, reg):
    os.makedirs(P(repo, "strategies"), exist_ok=True)
    with open(P(repo, "strategies", "registry.json"), "w") as f: json.dump(reg, f, indent=1, sort_keys=True); f.write("\n")


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def ajl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for r in rows: f.write(json.dumps(r, sort_keys=True) + "\n")


def code_hash(repo, files):
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.encode()); h.update(open(P(repo, f), "rb").read())
    return h.hexdigest()


def next_trading_day(d):
    d = tcal.D(d) + dt.timedelta(days=1)
    while not tcal.is_trading(d): d += dt.timedelta(days=1)
    return d.isoformat()


def register(repo, eid, source, kind, series, files, rules, forward_from=None):
    reg = load(repo); t = now()
    if eid in reg["entries"]: raise SystemExit("%s is already registered: use 'version' for a new version" % eid)
    month = t.strftime("%Y-%m")
    n = sum(1 for e in reg["entries"].values() if e["source"] != "seed" and e["versions"][0]["registered_at"][:7] == month)
    if source != "seed" and n >= MAX_NEW_PER_MONTH:
        raise SystemExit("monthly limit reached: %d new entries in %s (limit %d)" % (n, month, MAX_NEW_PER_MONTH))
    ff = forward_from or next_trading_day(t.date())
    if ff < next_trading_day(t.date()) and source != "seed":
        raise SystemExit("forward_from may not be earlier than the next trading day after registration")
    v = {"v": 1, "hash": code_hash(repo, files), "files": sorted(files), "registered_at": t.strftime("%Y-%m-%d %H:%M"),
         "forward_from": ff, "note": "first version"}
    reg["entries"][eid] = {"id": eid, "source": source, "kind": kind, "series": series, "rules": rules,
                           "status": "champion" if source == "seed" and kind == "champion" else "incubating",
                           "versions": [v], "history": [{"at": v["registered_at"], "status": "registered"}]}
    if reg["entries"][eid]["status"] == "champion":
        reg["champion"] = eid
        ajl(P(repo, "data", "lane", "champions.jsonl"), [{"at": v["registered_at"], "id": eid, "v": 1, "hash": v["hash"], "why": "seed: the cycle-1 formula"}])
    save(repo, reg); return reg["entries"][eid]


def version(repo, eid, files, note):
    reg = load(repo); e = reg["entries"][eid]; t = now(); h = code_hash(repo, files)
    if h == e["versions"][-1]["hash"]: raise SystemExit("code unchanged: same hash as version %d" % e["versions"][-1]["v"])
    v = {"v": e["versions"][-1]["v"] + 1, "hash": h, "files": sorted(files), "registered_at": t.strftime("%Y-%m-%d %H:%M"),
         "forward_from": next_trading_day(t.date()), "note": note}
    e["versions"].append(v); e["history"].append({"at": v["registered_at"], "status": "new version %d" % v["v"]})
    save(repo, reg); return v


def set_status(repo, eid, status, reason, reg=None):
    own = reg is None; reg = reg or load(repo); assert status in STATUSES
    e = reg["entries"][eid]; e["status"] = status
    e["history"].append({"at": now().strftime("%Y-%m-%d %H:%M"), "status": status, "reason": reason})
    if own: save(repo, reg)
    return e


def auto(repo):
    """Registers strategy-lab strategies whose promotion gate said PASS (strategies/<name>.gate.json) and that are
    not registered yet. Rejected ideas are not registered: they are already counted in the trial log."""
    reg = load(repo); out = []; d = P(repo, "strategies")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".gate.json"): continue
        g = json.load(open(os.path.join(d, f))); name = f[:-len(".gate.json")]
        if g.get("verdict") != "PASS" or ("lab_" + name) in reg["entries"]: continue
        mod = "strategies/%s.py" % name
        try: is_daily = "def daily_series" in open(P(repo, mod)).read()      # daily stock / ETF lab strategies (2026-11-23)
        except Exception: is_daily = False
        try:
            register(repo, "lab_" + name, "strategy_lab", "us_daily" if is_daily else "crypto_1h",
                     {"type": "lab_daily", "module": mod} if is_daily else {"type": "lab_crypto", "module": mod, "coins": ["BTC", "ETH", "SOL"]},
                     [mod, "strategies/%s.gate.json" % name], "strategy lab, gate PASS: see %s" % f)
            out.append("lab_" + name)
        except SystemExit as e: out.append("lab_%s: %s" % (name, e))
    return {"registered": out}


# ---------- series ----------
def portfolio(repo):
    return {r["date"]: r for r in jl(P(repo, "data", "allocator", "portfolio.jsonl"))}


def roll_to_trading(by_date, days):
    """Moves results dated on non-trading days to the next trading day in `days`."""
    out = {d: 0.0 for d in days}; ds = sorted(days)
    for d, x in by_date.items():
        nxt = next((t for t in ds if t >= d), None)
        if nxt is not None: out[nxt] += x
    return out


def run_lab_crypto(repo, s, start, days):
    import subprocess
    spec = importlib.util.spec_from_file_location("labmod", P(repo, s["module"])); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    nowts = int(now().timestamp())
    bars = json.loads(subprocess.run([sys.executable, os.path.join(HERE, "hist.py"), "export", repo, "1h", str(nowts), ",".join(s["coins"]), "3000"],
                                     capture_output=True, text=True).stdout or "{}")
    by = {}
    for c in s["coins"]:
        if c not in bars: continue
        for t in m.strategy(bars[c]):
            ent = str(t["entry_time"]); ext = str(t["exit_time"])
            def ny(x):
                x = dt.datetime.fromtimestamp(int(x), dt.timezone.utc) if str(x).isdigit() else dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
                return x.astimezone(tcal.NY).date().isoformat()
            if ny(ent) < start: continue            # only trades entered on or after the forward start
            by[ny(ext)] = by.get(ny(ext), 0.0) + float(t["net_pct"]) / len(s["coins"])
    return roll_to_trading(by, days)


def series(repo, e, start, days, port, sleeves_cache):
    s = e["series"]; days = [d for d in days if d >= start]
    if s["type"] == "portfolio":
        return {d: port[d][s["col"]] for d in days if d in port and port[d].get(s["col"]) is not None}
    if s["type"] == "sleeve":
        if "S" not in sleeves_cache:
            import allocator; sleeves_cache["S"] = allocator.sleeves(repo)
        sl = sleeves_cache["S"].get(s["name"], {}); return {d: sl.get(d, 0.0) for d in days}
    if s["type"] == "file":
        rows = {r["date"]: r["ret_pct"] for r in jl(P(repo, s["path"]))}; return {d: rows[d] for d in days if d in rows}
    if s["type"] == "lab_crypto":
        return run_lab_crypto(repo, s, start, days)
    if s["type"] == "lab_daily":            # the strategy's own daily_series(repo) -> {date: sleeve return %}; forward days only
        spec = importlib.util.spec_from_file_location("labmod_d", P(repo, s["module"])); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); out = m.daily_series(repo)
        return {d: float(out.get(d, 0.0)) for d in days}
    raise SystemExit("unknown series type %s" % s["type"])


# ---------- statistics ----------
def perf(xs):
    n = len(xs)
    if n < 2: return {"days": n}
    m = sum(xs) / n; sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    eq = 1.0; peak = 1.0; dd = 0.0
    for x in xs:
        eq *= 1 + x / 100; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return {"days": n, "return_pct": round((eq - 1) * 100, 3), "mean_pct": round(m, 5),
            "sharpe": round(m / sd * math.sqrt(252), 3) if sd > 0 else None, "max_dd_pct": round(dd * 100, 3)}


def p_beats(a, b, seed=SEED):
    """Day-block bootstrap: chance that a's mean daily result is above b's on the same days."""
    d = [x - y for x, y in zip(a, b)]; n = len(d)
    if n < 2 * BLOCK: return None
    rng = random.Random(seed); k = math.ceil(n / BLOCK); hits = 0
    for _ in range(B):
        s = 0.0; c = 0
        for _ in range(k):
            i = rng.randrange(n - BLOCK + 1); s += sum(d[i:i + BLOCK]); c += BLOCK
        hits += s / c > 0
    return round(hits / B, 4)


def score(repo, day=None):
    import stats, checks
    reg = load(repo); port = portfolio(repo); day = day or now().date().isoformat()
    days = sorted(d for d in port if d <= day); cache = {}; res = {"day": day, "entries": {}, "yardsticks": YARDSTICKS,
                                                                    "lifetime_unique_trials": checks.trials(repo)["unique_trials"]}
    ser = {}
    for eid, e in reg["entries"].items():
        v = e["versions"][-1]; ser[eid] = series(repo, e, v["forward_from"], days, port, cache)
    srs = []
    for eid, x in ser.items():
        p = perf(list(x.values()))
        if p.get("sharpe") is not None: srs.append(p["sharpe"] / math.sqrt(252))
    champ = reg.get("champion")
    for eid, e in reg["entries"].items():
        x = ser[eid]; ds = sorted(x); xs = [x[d] for d in ds]; v = e["versions"][-1]
        r = {"status": e["status"], "version": v["v"], "forward_from": v["forward_from"], "perf": perf(xs), "vs": {}}
        for y in YARDSTICKS:
            yd = [d for d in ds if port.get(d, {}).get(y) is not None]
            r["vs"][y] = p_beats([x[d] for d in yd], [port[d][y] for d in yd])
        if champ and champ != eid and champ in ser:
            cd = [d for d in ds if d in ser[champ]]
            r["vs"]["champion"] = p_beats([x[d] for d in cd], [ser[champ][d] for d in cd])
        tail = ds[-RETIRE_WINDOW:]
        r["recent_vs_best_yardstick"] = min((v2 for v2 in (p_beats([x[d] for d in tail if port.get(d, {}).get(y) is not None],
                                             [port[d][y] for d in tail if port.get(d, {}).get(y) is not None]) for y in YARDSTICKS) if v2 is not None), default=None)
        sr0 = stats.expected_max_sr(srs, res["lifetime_unique_trials"])
        r["deflated_sharpe_p"] = round(stats.psr(xs, sr0), 4) if len(xs) >= 3 else None
        res["entries"][eid] = r
    res["champion"] = champ
    os.makedirs(P(repo, "data", "lane"), exist_ok=True)
    with open(P(repo, "data", "lane", "scores.json"), "w") as f: json.dump(res, f, indent=1, sort_keys=True); f.write("\n")
    return res


# ---------- review ----------
def is_review_day(d):
    d = tcal.D(d)
    if d < FIRST_REVIEW or d.month not in (2, 5, 8, 11) or d.weekday() != 1: return False
    return 15 <= d.day <= 21                       # third Tuesday


def review(repo, day, dry=False):
    if not is_review_day(day) and not dry: return {"day": day, "review": False, "note": "not a review day (third Tuesday of Feb, May, Aug, Nov; first 2027-05-18)"}
    sc = score(repo, day); reg = load(repo); champ = reg.get("champion"); acts = []
    for eid, r in sc["entries"].items():
        e = reg["entries"][eid]
        if e["status"] == "incubating" and r["perf"].get("days", 0) >= 1: acts.append((eid, "challenger", "first forward day scored"))
        rv, dd = r.get("recent_vs_best_yardstick"), r["perf"].get("max_dd_pct")
        if e["status"] in ("challenger", "champion") and r["perf"].get("days", 0) >= MIN_DAYS and (
                (rv is not None and rv <= RETIRE_P) or (dd is not None and dd > RETIRE_DD)):
            acts.append((eid, "retired", "recent chance of beating the best yardstick %s, forward drawdown %s%%" % (rv, dd)))
    ok = []
    for eid, r in sc["entries"].items():
        if eid == champ or reg["entries"][eid]["status"] == "retired": continue
        vs = r["vs"]; need = list(YARDSTICKS) + (["champion"] if champ else [])
        if r["perf"].get("days", 0) >= MIN_DAYS and all(vs.get(k) is not None and vs[k] >= PROMOTE_P for k in need) \
                and (r.get("deflated_sharpe_p") or 0) >= DSR_MIN:
            ok.append((r["perf"].get("sharpe") or 0, eid))
    new_champ = max(ok)[1] if ok else None
    out = {"day": day, "review": True, "dry": dry, "actions": [], "promoted": new_champ, "scores": sc}
    if not dry:
        for eid, st, why in acts:
            if st == "retired" and eid == champ and not new_champ: why += "; no challenger meets the bar, so the champion stays"; continue
            set_status(repo, eid, st, why, reg); out["actions"].append([eid, st, why])
        if new_champ:
            if champ: set_status(repo, champ, "retired" if reg["entries"][champ]["status"] == "retired" else "challenger", "replaced by %s" % new_champ, reg)
            set_status(repo, new_champ, "champion", "promoted at the %s review" % day, reg); reg["champion"] = new_champ
            v = reg["entries"][new_champ]["versions"][-1]
            ajl(P(repo, "data", "lane", "champions.jsonl"), [{"at": day, "id": new_champ, "v": v["v"], "hash": v["hash"], "why": "beat the champion and every yardstick"}])
            out["actions"].append([new_champ, "champion", "promoted"])
        save(repo, reg)
        with open(P(repo, "data", "lane", "review_%s.json" % day), "w") as f: json.dump(out, f, indent=1, sort_keys=True); f.write("\n")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]; cmd, repo = a[0], a[1]
    if cmd == "register":
        print(json.dumps(register(repo, a[2], a[3], a[4], json.loads(a[5]), a[6].split(","), a[7], a[8] if len(a) > 8 else None), indent=1))
    elif cmd == "version": print(json.dumps(version(repo, a[2], a[3].split(","), a[4]), indent=1))
    elif cmd == "status": print(json.dumps(set_status(repo, a[2], a[3], a[4]), indent=1))
    elif cmd == "auto": print(json.dumps(auto(repo)))
    elif cmd == "score": print(json.dumps(score(repo, a[2] if len(a) > 2 else None), indent=1))
    elif cmd == "review": print(json.dumps(review(repo, a[2], "--dry" in a), indent=1))
    elif cmd == "list":
        reg = load(repo)
        for e in reg["entries"].values():
            v = e["versions"][-1]; print("%-28s %-11s v%d  from %s  %s" % (e["id"], e["status"], v["v"], v["forward_from"], e["source"]))
        print("champion:", reg.get("champion"))
    else: sys.exit("unknown command")
