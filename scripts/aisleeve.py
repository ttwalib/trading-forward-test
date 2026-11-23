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
Testing only, not financial advice.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, registry
SLEEVE = "AS AI strategies (lab, approved)"


def build(repo, day=None):
    day = day or dt.datetime.now(tcal.NY).date().isoformat()
    days = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]
    reg = registry.load(repo); per, errors = {}, {}
    for eid, e in sorted(reg["entries"].items()):
        if e.get("source") != "strategy_lab" or e.get("status") == "retired": continue
        start = e["versions"][-1]["forward_from"]
        try: per[eid] = {d: round(v, 5) for d, v in registry.series(repo, e, start, days, {}, {}).items()}
        except BaseException as x: errors[eid] = "%s: %s" % (type(x).__name__, x)
    pooled = {}
    for d in days:
        xs = [s[d] for s in per.values() if d in s]
        if xs: pooled[d] = round(sum(xs) / len(xs), 5)
    os.makedirs(os.path.join(repo, "data", "ai"), exist_ok=True)
    json.dump({SLEEVE: pooled} if pooled else {}, open(os.path.join(repo, "data", "ai", "daily.json"), "w"), separators=(",", ":"))
    json.dump(per, open(os.path.join(repo, "data", "ai", "strategies.json"), "w"), separators=(",", ":"))
    return {"strategies": sorted(per), "sleeve_days": len(pooled), "errors": errors}


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None), indent=1))
