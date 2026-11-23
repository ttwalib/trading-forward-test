"""Scores sealed weights the way the allocator scores Quantavius's weekly book (added 2026-11-23, runbook item 35).

  python3 seals.py REPO [DAY]      (nightly step "seals", before "lane")

Seal files and the lane series they become (data/lane/series/<id>.jsonl, rows {"date", "ret_pct"}):
  data/allocator/judge.jsonl          weekly   -> contest_fable    (the weekly book itself, re-scored here so that the
                                                                     three contestants share one scorer)
  data/allocator/contest_opus.jsonl   weekly   -> contest_opus
  data/allocator/contest_sonnet.jsonl weekly   -> contest_sonnet
  data/allocator/judge_daily.jsonl    daily    -> judge_daily      (the daily challenger)
Method, identical to allocator.simulate for "sh_judge": a seal counts only if sealed before 09:30 New York on its
effective day (allocator.judge_seals rule); a weekly seal applies from its effective day to the end of that ISO week,
a daily seal to its effective day only; a period without a valid seal carries the last weights forward; weights are
water-filled to 100% over the sleeves that exist (allocator.fill_to_one); every change of weights pays
allocator.rebal_cost per unit of turnover. Contestants differ only in their sealed weights.
Testing only, not financial advice.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, allocator as A
NY = tcal.NY
FILES = {"contest_fable": ("judge.jsonl", "week"), "contest_opus": ("contest_opus.jsonl", "week"),
         "contest_sonnet": ("contest_sonnet.jsonl", "week"), "judge_daily": ("judge_daily.jsonl", "day")}


def valid(repo, fn):
    out = {}; f = os.path.join(repo, "data", "allocator", fn)
    if not os.path.exists(f): return out
    for line in open(f):
        if not line.strip(): continue
        try:
            r = json.loads(line); eff = r["effective"]
            sealed = dt.datetime.fromisoformat(r["sealed_at"]).astimezone(NY)
            w = {k: float(v) for k, v in r["weights"].items() if float(v) > 0}
            if sealed < dt.datetime.fromisoformat(eff + "T09:30:00").replace(tzinfo=NY) and w and eff not in out: out[eff] = w
        except Exception: continue
    return out


def score(S, seals, horizon, days):
    cur, out, prev_wk = {}, {}, None
    for d in days:
        wk = dt.date.fromisoformat(d).isocalendar()[:2]
        if horizon == "day": cand = [d] if d in seals else []
        else: cand = sorted(e for e in seals if e <= d and dt.date.fromisoformat(e).isocalendar()[:2] == wk)
        new = None
        if cand and (horizon == "day" or d == cand[-1] or not cur or dt.date.fromisoformat(d).isocalendar()[:2] != prev_wk):
            new = {a: round(b, 4) for a, b in A.fill_to_one([{k: v for k, v in seals[cand[-1]].items() if k in S}]).items() if b > 0.0005}
        cost = 0.0
        if new is not None and new != cur:
            cost = sum(abs(new.get(a, 0.0) - cur.get(a, 0.0)) * A.rebal_cost(a) for a in set(new) | set(cur)); cur = new
        if cur: out[d] = round(sum(b * S[a].get(d, 0.0) for a, b in cur.items()) - cost, 5)
        prev_wk = wk
    return out


def main():
    repo = sys.argv[1]; day = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else dt.datetime.now(NY).date().isoformat()
    S = A.sleeves(repo); days = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]
    res = {}; os.makedirs(os.path.join(repo, "data", "lane", "series"), exist_ok=True)
    for eid, (fn, h) in FILES.items():
        seals = valid(repo, fn)
        if not seals: res[eid] = {"seals": 0}; continue
        ser = score(S, seals, h, [d for d in days if d >= min(seals)])
        with open(os.path.join(repo, "data", "lane", "series", eid + ".jsonl"), "w") as f:
            for d in sorted(ser): f.write(json.dumps({"date": d, "ret_pct": ser[d]}) + "\n")
        res[eid] = {"seals": len(seals), "days": len(ser), "total_pct": round(sum(ser.values()), 3)}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
