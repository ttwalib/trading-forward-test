"""The sleeve of the AI's own strategies (added 2026-11-23, runbook item 33a).

  python3 aisleeve.py REPO [DAY]      (nightly step "aisleeve", before the allocator)

Every strategy the strategy lab invented and the promotion gate approved is registered in the lane
(strategies/registry.json, source "strategy_lab") with a forward start: the first full trading day after its
registration. This script pools them, equal weight, into ONE sleeve, "AS AI strategies (lab, approved)", in
data/ai/daily.json: the day's return is the average of the day's returns of every strategy whose forward start has
passed and that the lane has not retired. Only forward days count: nothing from the test that approved a strategy
enters. The allocator reads the sleeve like any other (25% cap, same evidence rules), so what the AI invents can earn
weight in the judged book from its approval instead of waiting for a lane review. While no strategy is approved the
file is empty and no sleeve exists. Per-strategy series are kept in data/ai/strategies.json for the reports.

LANE ADMISSION (2026-11-24, runbook item 53, owner decision; written down before any lane entry had a scored day).
Lane challengers that are Quantavius's own strategies or models (an ML ranker, a strategy-search survivor, a lab idea
registered by hand) join the same pool, so that they can earn weight in this test without waiting for a lane review.
 - WHEN: only on ADMISSION DAYS, the third Tuesday of every month from 2027-02-16, using data/lane/scores.json as the
   nightly lane step wrote it the night before (never the same day's results).
 - WHO: any entry that is not a seed, not a weekly book (kind "allocator": those hold this sleeve themselves), not
   already pooled as a lab approval, and not retired.
 - BAR: at least ADMIT_DAYS forward days; a block-bootstrap chance of at least ADMIT_P of beating EVERY lane yardstick
   (SPY, equal weight, baseline A, risk parity, the formula); and a deflated-Sharpe chance of at least ADMIT_P with
   the lifetime trial count. Lower than the champion bar (0.98) because entry here only offers the strategy to
   Quantavius's judgment, inside a 25%-capped sleeve; it does not crown it.
 - COUNTS FROM: the first trading day after the admission day. Nothing earlier enters.
 - LEAVES: on a later admission day when its chance of beating the best yardstick over its last 120 forward days is at
   or below 0.10, or at once when the lane retires it. Every admission and exit is a row in
   data/ai/lane_admissions.jsonl (append-only, in the hash chain); data/ai/lane_admitted.json holds the current set.
Testing only, not financial advice.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, registry
SLEEVE = "AS AI strategies (lab, approved)"
ADMIT_FROM = "2027-02-16"; ADMIT_DAYS = 40; ADMIT_P = 0.90; EXIT_P = 0.10


def is_admission_day(d):
    x = dt.date.fromisoformat(d)
    return d >= ADMIT_FROM and x.weekday() == 1 and 15 <= x.day <= 21


def _jl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def admissions(repo, day, dry=False):
    """Apply the admission rule on an admission day; returns the current admitted set {id: {"from": first day}}."""
    cur_p = os.path.join(repo, "data", "ai", "lane_admitted.json"); log_p = os.path.join(repo, "data", "ai", "lane_admissions.jsonl")
    cur = json.load(open(cur_p)) if os.path.exists(cur_p) else {}
    reg = registry.load(repo); changes = []
    for eid in list(cur):        # the lane retired it: out from the next trading day
        e = reg["entries"].get(eid)
        if (e is None or e.get("status") == "retired") and "until" not in cur[eid]:
            cur[eid]["until"] = registry.next_trading_day(day); changes.append({"id": eid, "action": "exit", "reason": "retired by the lane"})
    sp = os.path.join(repo, "data", "lane", "scores.json"); sc = json.load(open(sp)) if os.path.exists(sp) else {}
    fresh = sc.get("day", "9999") < day             # never the same day's results; wait for the next night if so
    if is_admission_day(day) and fresh and not any(r.get("day") == day for r in _jl(log_p)):
        for eid, r in sorted((sc.get("entries") or {}).items()):
            e = reg["entries"].get(eid) or {}
            if eid in cur and "until" not in cur[eid]:
                rv = r.get("recent_vs_best_yardstick")
                if rv is not None and rv <= EXIT_P:
                    cur[eid]["until"] = registry.next_trading_day(day); changes.append({"id": eid, "action": "exit", "reason": "recent chance vs best yardstick %.2f" % rv})
                continue
            if e.get("source") in ("seed", "strategy_lab") or e.get("kind") == "allocator" or e.get("status") == "retired": continue
            vs = r.get("vs") or {}; ys = [vs.get(y) for y in registry.YARDSTICKS]
            ok = (r.get("perf", {}).get("days", 0) >= ADMIT_DAYS and all(v is not None and v >= ADMIT_P for v in ys)
                  and (r.get("deflated_sharpe_p") or 0) >= ADMIT_P)
            if ok:
                cur[eid] = {"from": registry.next_trading_day(day), "version": e["versions"][-1]["v"]}
                changes.append({"id": eid, "action": "admit", "days": r["perf"]["days"], "vs": vs, "dsr": r.get("deflated_sharpe_p")})
        if not dry:
            with open(log_p, "a") as f: f.write(json.dumps({"day": day, "scores_day": sc.get("day"), "changes": changes}) + "\n")
    elif changes and not dry:
        with open(log_p, "a") as f: f.write(json.dumps({"day": day, "changes": changes}) + "\n")
    if not dry:
        os.makedirs(os.path.dirname(cur_p), exist_ok=True); json.dump(cur, open(cur_p, "w"), indent=1, sort_keys=True)
    return cur, changes


def build(repo, day=None):
    day = day or dt.datetime.now(tcal.NY).date().isoformat()
    days = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]
    reg = registry.load(repo); per, errors = {}, {}
    for eid, e in sorted(reg["entries"].items()):
        if e.get("source") != "strategy_lab" or e.get("status") == "retired": continue
        start = e["versions"][-1]["forward_from"]
        try: per[eid] = {d: round(v, 5) for d, v in registry.series(repo, e, start, days, {}, {}).items()}
        except BaseException as x: errors[eid] = "%s: %s" % (type(x).__name__, x)
    admitted, adm_changes = admissions(repo, day)
    port = None
    for eid, a in sorted(admitted.items()):
        e = reg["entries"].get(eid)
        if e is None or eid in per: continue
        if port is None: port = registry.portfolio(repo)
        try:
            ser = registry.series(repo, e, a["from"], days, port, {})
            per["lane:" + eid] = {d: round(v, 5) for d, v in ser.items() if d >= a["from"] and d < a.get("until", "9999")}
        except BaseException as x: errors[eid] = "%s: %s" % (type(x).__name__, x)
    pooled = {}
    for d in days:
        xs = [s[d] for s in per.values() if d in s]
        if xs: pooled[d] = round(sum(xs) / len(xs), 5)
    os.makedirs(os.path.join(repo, "data", "ai"), exist_ok=True)
    json.dump({SLEEVE: pooled} if pooled else {}, open(os.path.join(repo, "data", "ai", "daily.json"), "w"), separators=(",", ":"))
    json.dump(per, open(os.path.join(repo, "data", "ai", "strategies.json"), "w"), separators=(",", ":"))
    return {"strategies": sorted(per), "sleeve_days": len(pooled), "errors": errors, "lane_admitted": sorted(admitted),
            "admission_changes": adm_changes, "next_admission_day": next((d for d in tcal.trading_days(day, "2027-12-31") if is_admission_day(d) and d > day), None)}


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None), indent=1))
