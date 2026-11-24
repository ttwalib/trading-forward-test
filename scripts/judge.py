"""AI-judgment allocator: the evidence pack and the seal (added 2026-11-21, owner decision, before the freeze).

The formula allocator (allocator.py) is fixed code. This is the other half of the question "can an AI manage a mix of
strategies?": once a week a language model reads the same evidence, argues both sides and decides next week's weights.
The decision is SEALED before the week starts and can never be changed; allocator.py then scores it like every other
rival (weekly rebalancing, same costs). Nothing is traded.

  python3 judge.py brief REPO            -> the evidence pack (JSON): rules, eligible sleeves with their record up to
                                            the last closed day, market regime, what the formula and the simple rules
                                            hold, results so far, and the judge's own earlier seals with how they did
  python3 judge.py seal REPO FILE [--dry] [--out data/allocator/X.jsonl] [--daily]
                                         -> validates FILE and appends it to data/allocator/judge.jsonl (Quantavius's
                                            weekly book, the verdict) or, with --out, to a challenger's file
                                            (model contest, daily challenger; 2026-11-23)
        FILE = {"weights": {sleeve: share, ...}, "bull": "...", "bear": "...", "risk": "...", "decision": "...",
                "model": "..."}

Rules the seal enforces (a seal that breaks one is refused, nothing is written):
  - only eligible sleeves (the list in the brief: at least 10 active days in the last 120, duplicates excluded);
  - every share between 0.02 and 0.25, except Quantavius's own sleeves (AP, AP2, AS), which may hold up to 0.50 each
    (OWN_CAP, owner decision 2026-11-24, item 55); shares add up to 1.00 (fully invested, no cash);
  - optional "as_mix": {AS member: share}, shares >= 0 adding up to 1.00, members as listed in the brief's
    your_own_work.as_members; it sets how the AS sleeve weights its strategies from the seal's effective day (weekly
    book only; read by scripts/aisleeve.py). Without it AS weights its members equally;
  - the short-premium option sleeves (W1, W2, D2, D3) together at most 0.25 (allocator.GROUP_CAP, since 2026-11-21);
  - sealed while the stock market is closed, before 09:30 New York of the first trading day it applies to
    ("effective"), and only one seal per effective day;
  - bull, bear and decision texts are present (at least 40 characters each), so the reasoning is on record.
Evidence only reaches the last closed trading day, so the weights cannot see the week they are for.
"""
import json, os, sys, math, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, allocator

NY = ZoneInfo("America/New_York")
LO, HI = 0.02, allocator.CAP
OWN_CAP = 0.50        # cap for Quantavius's own sleeves AP, AP2, AS (owner decision 2026-11-24, item 55); others HI


def cap_of(name):
    return OWN_CAP if name.startswith(OWN) else HI


def _fill(scores):
    """Scale positive scores to 1.00 under each sleeve's own cap (water-filling)."""
    w = {}; free = {k: v for k, v in scores.items() if v > 0}; room = 1.0
    for _ in range(len(free) + 1):
        tot = sum(free.values())
        if tot <= 0 or room <= 1e-12: break
        over = {k for k, v in free.items() if w.get(k, 0.0) + room * v / tot >= cap_of(k) - 1e-12}
        if not over:
            for k, v in free.items(): w[k] = w.get(k, 0.0) + room * v / tot
            break
        for k in over: room -= cap_of(k) - w.get(k, 0.0); w[k] = cap_of(k); free.pop(k)
    return w
FILE = os.path.join("data", "allocator", "judge.jsonl")


def effective_day(now):
    """First full or half trading session that opens after `now`."""
    d = now.date()
    if not (tcal.is_open(d) and now.hour * 60 + now.minute < 9 * 60 + 30): d += dt.timedelta(days=1)
    while not tcal.is_open(d): d += dt.timedelta(days=1)
    return d


def market_closed(now):
    d = now.date(); hm = now.hour * 60 + now.minute
    return not tcal.is_open(d) or hm < 9 * 60 + 25 or hm >= 16 * 60 + 5


OWN = ("AP Agent picks", "AP2 Agent picks", "AS AI strategies")


def context(repo):
    S = allocator.sleeves(repo); spy = allocator.dclose(repo, "SPY", total_return=True); vix = allocator.dclose(repo, "VIX")
    cal = sorted(d for d in set(spy) | {d for s in S.values() for d in s} if tcal.is_open(d))
    hist = cal[-allocator.WIN:]; dup = allocator.duplicates(S, hist); el = {}
    for name, series in S.items():
        if name in dup: continue
        raw = [series.get(x, 0.0) for x in hist if x >= min(series, default="9999")]
        # Quantavius's own sleeves (its picks AP / AP2 and its approved strategies AS) are eligible from their first
        # live day (2026-11-23, item 34): judging its own new work early is part of its autonomy
        if sum(1 for x in raw if x) >= allocator.MIN_DAYS or (name.startswith(OWN) and any(raw)): el[name] = raw
    return S, spy, vix, cal, hist, dup, el


def brief(repo, now=None):
    now = now or dt.datetime.now(NY); S, spy, vix, cal, hist, dup, el = context(repo)
    start = tcal.START.isoformat(); regime = allocator.regime_of(spy, vix, cal)
    J = lambda f: [json.loads(l) for l in open(os.path.join(repo, "data", "allocator", f)) if l.strip()] if os.path.exists(os.path.join(repo, "data", "allocator", f)) else []
    W, PF = J("weights.jsonl"), J("portfolio.jsonl"); lastw = W[-1] if W else {}
    sm = lambda xs: round(sum(xs), 3)
    sleeves = []
    for k in sorted(el):
        s = S[k]; live = [s[d] for d in sorted(s) if d >= start]; prior = [s[d] for d in sorted(s) if d < start][-120:]
        x = el[k]; sd = math.sqrt(allocator.stats(x[-20:])[1]) if len(x) >= 2 else None
        sleeves.append({"sleeve": k, "live_days": len(live), "live_total_pct": sm(live), "last5_pct": sm(x[-5:]), "last20_pct": sm(x[-20:]),
                        "last60_pct": sm(x[-60:]), "daily_vol_20d_pct": round(sd, 3) if sd else None,
                        "backtest_days_before_test": len(prior), "backtest_mean_daily_pct": round(sum(prior) / len(prior), 4) if prior else None,
                        "backtest_is_flattered": k.startswith(allocator.SURV_SLEEVES),
                        "formula_weight": (lastw.get("weights") or {}).get(k, 0.0), "breaker": k in (lastw.get("breakers") or []),
                        "forced_in_formula": k in (lastw.get("forced") or [])})
    cum = {}
    for r in PF:
        for k in ("ai", "equal", "spy", "base_a", "sh_rp", "sh_mv", "sh_win", "sh_judge"):
            if r.get(k) is not None: cum[k] = cum.get(k, 0.0) + r[k]
    seals = []
    for l in (open(os.path.join(repo, FILE)) if os.path.exists(os.path.join(repo, FILE)) else []):
        if not l.strip(): continue
        r = json.loads(l); wk = dt.date.fromisoformat(r["effective"]).isocalendar()[:2]
        days = [p for p in PF if dt.date.fromisoformat(p["date"]).isocalendar()[:2] == wk and p.get("sh_judge") is not None]
        seals.append({"effective": r["effective"], "weights": r["weights"], "decision": r.get("decision"),
                      "p_beat_equal": r.get("p_beat_equal"), "lessons": r.get("lessons"),
                      "week_result_pct": {k: sm([p.get(k) or 0.0 for p in days]) for k in ("sh_judge", "ai", "equal", "spy")} if days else None})
    eff = effective_day(now)
    return {"now_new_york": now.strftime("%Y-%m-%d %H:%M"), "evidence_through": cal[-1] if cal else None, "effective": eff.isoformat(),
            "market_closed_now": market_closed(now), "phase_of_effective_day": tcal.phase(eff),
            "rules": {"min_share": LO, "max_share": HI, "own_sleeves_max_share": OWN_CAP, "own_sleeves": list(OWN),
                      "as_mix": "optional {AS member: share} adding up to 1.00 (weekly book); without it AS is equal weight", "sum": 1.0, "short_premium_group_max": allocator.GROUP_CAP,
                      "short_premium_group": "W1, W2, D2, D3 together", "cash": "not allowed", "only_listed_sleeves": True,
                      "rebalancing": "weekly; changing a share costs 0% (intraday sleeves), 0.05% (daily library), 0.15% (crypto), 0.5% (options) of the amount moved"},
            "regime_last_day": regime.get(cal[-1]) if cal else None,
            "regime_last_10_days": [regime.get(d) for d in cal[-10:]],
            "spy_last5_pct": round((spy[cal[-1]] / spy[cal[-6]] - 1) * 100, 2) if len(cal) > 6 and cal[-1] in spy and cal[-6] in spy else None,
            "vix_last": vix.get(cal[-1]) if cal else None,
            "eligible_sleeves": sleeves, "excluded_duplicates": sorted(dup),
            "rivals_current_weights": lastw.get("shadows"), "formula_current_weights": lastw.get("weights"),
            "results_since_start_sum_of_daily_pct": {k: round(v, 3) for k, v in cum.items()}, "live_days": len(PF),
            "your_earlier_seals": seals[-8:],
            "cautions": ["live samples are tiny: a few days of results are mostly noise",
                         "backtest records are flattered, most of all where backtest_is_flattered is true",
                         "on past data every simple rule (risk parity, minimum variance, equal weight) beat the formula on Sharpe"],
            "market_breadth": breadth_view(repo, cal[-1] if cal else None),
            "market_context": context_view(repo, cal[-1] if cal else None),
            "your_own_work": ai_layer(repo, cal[-1] if cal else None)}


def context_view(repo, through):
    """Since 2026-11-23 the pack shows free outside context fetched on GitHub (scripts/extdata.py; report only): rates
    and credit (FRED), put/call ratios (Cboe), off-exchange short-sale share (FINRA), crypto funding and stablecoin
    supply. Only files fetched on or before `through`, and inside them only rows dated on or before it."""
    if not through: return None
    def latest(src):
        d = os.path.join(repo, "data", "ext", src)
        fs = sorted(f for f in (os.listdir(d) if os.path.isdir(d) else []) if f.endswith(".json") and f[:10] <= through)
        try: return json.load(open(os.path.join(d, fs[-1]))) if fs else None
        except Exception: return None
    out = {}
    x = latest("fred")
    if x:
        out["rates_and_credit"] = {}
        for k, v in x.get("series", {}).items():
            v = [r for r in v if r["date"] <= through]
            if v: out["rates_and_credit"][k] = {"date": v[-1]["date"], "value": v[-1]["value"],
                                                "change_20_obs": round(v[-1]["value"] - v[-21]["value"], 3) if len(v) > 20 else None}
        out["rates_and_credit_legend"] = x.get("legend")
    x = latest("cboe")
    if x:
        ds = {k: v for k, v in x.get("days", {}).items() if k <= through}
        if ds: out["put_call"] = {"date": max(ds), **ds[max(ds)]}
    x = latest("finra")
    if x:
        ds = {k: v for k, v in x.get("days", {}).items() if k <= through}
        if ds: out["short_sale_share_off_exchange_pct"] = {k: ds[k]["market_short_pct"] for k in sorted(ds)}
    x = latest("crypto")
    if x: out["crypto"] = {"fetched": x.get("fetched_at_ny"), "funding_pct_8h": {k: v.get("funding_rate_pct") for k, v in (x.get("funding") or {}).items()},
                           "stablecoins": x.get("stablecoins")}
    if out: out["note"] = "context only: none of this is a rule, and a few readings prove nothing"
    return out or None


def breadth_view(repo, through):
    """Since 2026-11-23 (tools audit) the pack shows market breadth over the point-in-time top 100 (scripts/breadth.py,
    report only): the latest row on or before `through` and the last 10 rows, so a narrow or broad market is visible."""
    f = os.path.join(repo, "data", "nightly", "breadth.json")
    if not (through and os.path.exists(f)): return None
    try: rows = [r for r in json.load(open(f)).get("rows", []) if r["date"] <= through]
    except Exception: return None
    return {"latest": rows[-1] if rows else None, "last_10": rows[-10:]} if rows else None


def ai_layer(repo, through):
    """Since 2026-11-23 (runbook item 34) the pack also shows what Quantavius itself made, so its judgment can use it:
    its stock picks scored against the random control list, its pick playbook version, its approved strategies and
    which sleeves carry the book's risk. Only rows dated on or before `through` (= evidence_through) are included."""
    out = {}
    def L(*p):
        f = os.path.join(repo, *p)
        return json.load(open(f)) if os.path.exists(f) else None
    sc = L("data", "picks", "score.json")
    if sc and through:
        rows = [r for r in sc.get("rows", []) if r["date"] <= through]
        out["picks_vs_control_by_day"] = [{k: r.get(k) for k in ("date", "n", "picks_day", "control_day", "picks_5d", "control_5d")} for r in rows][-20:]
        a = [(r["picks_day"], r["control_day"]) for r in rows if r.get("picks_day") is not None and r.get("control_day") is not None]
        out["picks_summary"] = {"pick_days": len(a), "mean_picks_minus_control_pct": round(sum(x - y for x, y in a) / len(a), 4) if a else None}
    try:
        pb = [l for l in open(os.path.join(repo, "ops", "pick_playbook.md")) if l.startswith("## CURRENT VERSION")]
        out["pick_playbook"] = pb[0].strip("# \n") if pb else None
    except Exception: pass
    st = L("data", "ai", "strategies.json") or {}
    out["approved_strategies_forward"] = {k: {"days": len([d for d in v if d <= through]), "total_pct": round(sum(x for d, x in v.items() if d <= through), 3)}
                                          for k, v in st.items()} if through else {}
    rx = L("data", "nightly", "riskx.json")
    if rx and (rx.get("contributions") or {}).get("date", "9999") <= (through or ""):
        out["risk_share_of_formula_weights"] = rx["contributions"].get("sleeves")
    out["as_members"] = sorted(st)
    # since 2026-11-24 (item 56): what Quantavius's own learning review found and how the lane entries stand, so the
    # book can act on them; only rows dated on or before `through`
    try:
        lf = os.path.join(repo, "data", "ledger", "Learning.jsonl")
        if os.path.exists(lf) and through:
            rows = [json.loads(l) for l in open(lf) if l.strip()]
            rows = [r for r in rows if str(r.get("review_time") or r.get("date") or "9999")[:10] <= through]
            out["learning_findings"] = [{k: (str(v)[:300] if isinstance(v, str) else v) for k, v in r.items()} for r in rows[-8:]]
        ls = L("data", "lane", "scores.json")
        if ls and through and ls.get("day", "9999") <= through:
            out["lane"] = {"day": ls["day"], "champion": ls.get("champion"),
                           "entries": {k: {"status": v.get("status"), "perf": v.get("perf"), "vs": v.get("vs")} for k, v in (ls.get("entries") or {}).items()}}
    except Exception: pass
    out["note"] = ("AP / AP2 are your own stock picks (equal weight one day / your own sizing and holding), AS is your own "
                   "approved strategies and admitted lane entries. They are eligible like any sleeve and may hold up to "
                   "%.2f each; nothing obliges you to hold or avoid them. In the weekly book you may set as_mix to weight "
                   "the AS members yourself." % OWN_CAP)
    return out


DRAFTS = os.path.join("data", "allocator", "drafts")
MOVE_FLAG = 0.05      # a share that moves more than this against the previous seal is listed in the row (never clipped)


def _check(repo, D, now):
    """Rules every seal and every draft must meet. Returns (weights, errors, p_beat_equal)."""
    err = []; _, _, _, _, _, _, el = context(repo); w = {}
    try: w = {str(k): float(v) for k, v in (D.get("weights") or {}).items() if float(v) > 0}
    except Exception: err.append("weights must be a {sleeve: number} object")
    bad = sorted(k for k in w if k not in el)
    if bad: err.append("not eligible: " + ", ".join(bad))
    if any(v < LO - 1e-9 or v > cap_of(k) + 1e-9 for k, v in w.items()):
        err.append("every share must be between %.2f and %.2f (%.2f for your own sleeves AP, AP2, AS)" % (LO, HI, OWN_CAP))
    mix = D.get("as_mix")
    if mix:
        try:
            mix = {str(k): float(v) for k, v in mix.items() if float(v) > 0}
            members = set((json.load(open(os.path.join(repo, "data", "ai", "strategies.json"))) if os.path.exists(os.path.join(repo, "data", "ai", "strategies.json")) else {}))
            if set(mix) - members: err.append("as_mix names strategies that are not AS members: " + ", ".join(sorted(set(mix) - members)))
            if abs(sum(mix.values()) - 1.0) > 0.001: err.append("as_mix shares add up to %.4f, not 1.00" % sum(mix.values()))
        except Exception: err.append("as_mix must be a {member: share} object")
    if abs(sum(w.values()) - 1.0) > 0.001: err.append("shares add up to %.4f, not 1.00" % sum(w.values()))
    sp = sum(v for k, v in w.items() if k.startswith(allocator.SHORT_PREMIUM))
    if sp > allocator.GROUP_CAP + 1e-9: err.append("the short-premium option sleeves (W1, W2, D2, D3) hold %.2f together; the limit is %.2f" % (sp, allocator.GROUP_CAP))
    for k in ("bull", "bear", "decision"):
        if len(str(D.get(k) or "").strip()) < 40: err.append("'%s' text is missing or too short" % k)
    if not market_closed(now): err.append("the stock market is open: seal only while it is closed")
    pb = D.get("p_beat_equal")
    if pb is not None:
        try:
            pb = float(pb)
            if not 0.0 <= pb <= 1.0: err.append("p_beat_equal must be between 0 and 1")
        except (TypeError, ValueError): err.append("p_beat_equal must be a number between 0 and 1")
    return w, err, pb


def draft(repo, path, tag, now=None):
    """An independent sample for the weekly book (2026-11-23, external review 3.2): a separate session judges the same
    evidence pack and files its weights here. The weekly seal then takes the MEDIAN share per sleeve over its own
    weights and the drafts for the same effective day. A draft is never a seal and is never scored on its own."""
    now = now or dt.datetime.now(NY); D = json.load(open(path)); w, err, pb = _check(repo, D, now)
    eff = effective_day(now).isoformat(); tag = "".join(c for c in str(tag) if c.isalnum())[:12] or "x"
    f = os.path.join(repo, DRAFTS, "%s_%s.json" % (eff, tag))
    if os.path.exists(f): err.append("draft %s already filed for %s" % (tag, eff))
    if err: return {"filed": False, "errors": err, "effective": eff}
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump({"effective": eff, "filed_at": now.isoformat(timespec="seconds"), "tag": tag, "model": str(D.get("model") or "")[:60],
               "weights": {k: round(v, 4) for k, v in sorted(w.items())}, "p_beat_equal": pb,
               "decision": str(D["decision"])[:1500]}, open(f, "w"), indent=1)
    return {"filed": True, "effective": eff, "file": os.path.relpath(f, repo)}


def _median_book(samples):
    """Median share per sleeve over the samples (a sleeve a sample leaves out counts as 0), shares under the minimum
    dropped, the rest scaled to 100% under the per-sleeve cap. Also the dispersion: the average, over pairs of samples,
    of half the summed absolute difference of their shares (0 = identical books, 1 = no overlap)."""
    import statistics as st
    keys = sorted({k for s in samples for k in s})
    med = {k: st.median([s.get(k, 0.0) for s in samples]) for k in keys}
    med = {k: v for k, v in med.items() if v >= LO / 2}
    w = _fill(med) if med else {}
    for _ in range(5):
        small = [k for k, v in w.items() if v < LO - 1e-9]
        if not small: break
        med = {k: v for k, v in med.items() if k not in small}; w = _fill(med)
    pairs = [(a, b) for i, a in enumerate(samples) for b in samples[i + 1:]]
    disp = sum(sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys) / 2 for a, b in pairs) / len(pairs) if pairs else None
    return {k: round(v, 4) for k, v in sorted(w.items())}, (round(disp, 4) if disp is not None else None)


def seal(repo, path, dry=False, now=None, out=None, daily=False):
    """out: another seal file (the model contest and the daily challenger, 2026-11-23; never judge.jsonl for those);
    daily: the seal applies to one session only (the daily challenger), else to its ISO week (the weekly book)."""
    now = now or dt.datetime.now(NY); D = json.load(open(path)); w, err, pb = _check(repo, D, now)
    eff = effective_day(now).isoformat(); f = os.path.join(repo, out or FILE)
    if os.path.exists(f) and any(json.loads(l).get("effective") == eff for l in open(f) if l.strip()): err.append("already sealed for " + eff)
    if err: return {"sealed": False, "errors": err, "effective": eff}
    # WEEKLY BOOK ONLY (2026-11-23, external review 3.1-3.3): the sealed shares are the median over this session's own
    # weights and the independent drafts filed for the same effective day (judge.py draft). Fewer than two drafts: the
    # session's own weights are sealed and the row says n_samples 1. Shares that move more than 5 points against the
    # previous seal are listed, never clipped: the code records, Quantavius decides.
    own = {k: round(v, 4) for k, v in sorted(w.items())}; samples = [own]; tags = ["seal"]; disp = None
    if out is None and not daily:
        import glob
        for g in sorted(glob.glob(os.path.join(repo, DRAFTS, eff + "_*.json"))):
            try:
                d = json.load(open(g))
                if d.get("effective") == eff and d.get("weights"): samples.append(d["weights"]); tags.append(str(d.get("tag")))
            except Exception: pass
        if len(samples) >= 3: w, disp = _median_book(samples)
        else: samples, tags = [own], ["seal"]
    prev = None
    if os.path.exists(f):
        rows_ = [json.loads(l) for l in open(f) if l.strip()]
        prev = rows_[-1]["weights"] if rows_ else None
    moves = sorted(([k, round(w.get(k, 0.0) - (prev or {}).get(k, 0.0), 4)] for k in set(w) | set(prev or {})
                    if abs(w.get(k, 0.0) - (prev or {}).get(k, 0.0)) > MOVE_FLAG + 1e-9), key=lambda x: -abs(x[1])) if prev else []
    B = brief(repo, now)
    row = {"effective": eff, "sealed_at": now.isoformat(timespec="seconds"), "evidence_through": B["evidence_through"],
           "weights": {k: round(v, 4) for k, v in sorted(w.items())},
           "n_samples": len(samples), "sample_tags": tags, "samples": samples if len(samples) > 1 else None,
           "sample_dispersion": disp, "moves_over_5pts": moves, "pack_chars": len(json.dumps(B, default=str)), "bull": str(D["bull"])[:1500], "bear": str(D["bear"])[:1500],
           "risk": str(D.get("risk") or "")[:1000], "decision": str(D["decision"])[:1500], "model": str(D.get("model") or "")[:60],
           # since 2026-11-23 (item 35): the stated chance that this book beats the equal-weight foundation over the
           # period it applies to (scored for calibration), the lessons drawn from the earlier seals, and the horizon
           "p_beat_equal": pb, "lessons": str(D.get("lessons") or "")[:1500], "horizon": "day" if daily else "week",
           "as_mix": ({str(k): round(float(v), 4) for k, v in (D.get("as_mix") or {}).items() if float(v) > 0} or None)}
    if not dry:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "a") as fh: fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return {"sealed": not dry, "dry_run": dry, "effective": eff, "sleeves": len(w), "row": row}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "draft":
        o = draft(a[1], a[2], a[3] if len(a) > 3 else "x"); print(json.dumps(o, indent=1)); sys.exit(0 if o.get("filed") else 1)
    if not a or a[0] not in ("brief", "seal"): print(__doc__); sys.exit(2)
    ov = a[a.index("--out") + 1] if "--out" in a else None
    if ov and (os.path.normpath(ov) == os.path.normpath(FILE) or not ov.startswith("data/allocator/") or not ov.endswith(".jsonl")):
        print("--out must be another data/allocator/*.jsonl file"); sys.exit(2)
    out = brief(a[1]) if a[0] == "brief" else seal(a[1], a[2], "--dry" in a, out=ov, daily="--daily" in a)
    print(json.dumps(out, indent=1, default=str)); sys.exit(0 if a[0] == "brief" or out.get("sealed") or out.get("dry_run") else 1)
