"""How well Quantavius's stated confidence matches what happened (added 2026-11-23, runbook item 35c; report only).

  python3 calib.py REPO      (nightly step "calib" -> data/nightly/calib.json)

Two kinds of sealed forecasts are scored:
  - picks: each stock pick may carry "p=0.62" in its checks cell = the stated chance that the pick beats the random
    control list's average from open to close that day (data/picks/calib_picks.json, written by picks.py);
  - books: each seal (weekly book, contest, daily challenger) may carry "p_beat_equal" = the stated chance that the
    book beats the equal-weight foundation over the period it applies to (sealed weights, scored by seals.py logic).
Brier score = mean of (p - outcome)^2: 0.25 is what always saying 0.5 earns, lower is better. Calibration table: the
forecasts in bands of 0.1 with the share that came true. Good judgment shows up here before returns can prove it.
Testing only, not financial advice.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seals, allocator as A, tcal


def summary(F):
    if not F: return {"n": 0}
    b = sum((f["p"] - (1.0 if f["hit"] else 0.0)) ** 2 for f in F) / len(F); bands = {}
    for f in F:
        k = "%.1f-%.1f" % (min(int(f["p"] * 10), 9) / 10, min(int(f["p"] * 10), 9) / 10 + 0.1)
        bands.setdefault(k, []).append(1 if f["hit"] else 0)
    return {"n": len(F), "brier": round(b, 4), "coin_flip_brier": 0.25, "skill_vs_coin_flip": round(1 - b / 0.25, 3),
            "bands": {k: {"n": len(v), "came_true": round(sum(v) / len(v), 3)} for k, v in sorted(bands.items())}}


def books(repo):
    S = A.sleeves(repo); F = []
    P = {r["date"]: r for r in (json.loads(l) for l in open(os.path.join(repo, "data", "allocator", "portfolio.jsonl")) if l.strip())}
    for eid, (fn, h) in seals.FILES.items():
        f = os.path.join(repo, "data", "allocator", fn)
        if not os.path.exists(f): continue
        rows = [json.loads(l) for l in open(f) if l.strip()]
        for r in rows:
            if r.get("p_beat_equal") is None: continue
            eff = r["effective"]; wk = dt.date.fromisoformat(eff).isocalendar()[:2]
            days = [d for d in sorted(P) if (d == eff if h == "day" else dt.date.fromisoformat(d).isocalendar()[:2] == wk and d >= eff)]
            if not days or days[-1] >= dt.datetime.now(tcal.NY).date().isoformat(): continue      # period not finished
            w = {k: v for k, v in r["weights"].items() if k in S}; tot = sum(w.values()) or 1
            book = sum(sum(v / tot * S[k].get(d, 0.0) for k, v in w.items()) for d in days)
            eq = sum(P[d]["equal"] for d in days)
            F.append({"date": eff, "kind": eid, "p": float(r["p_beat_equal"]), "hit": book > eq})
    return F


def main():
    repo = sys.argv[1]
    f = os.path.join(repo, "data", "picks", "calib_picks.json")
    pk = json.load(open(f)) if os.path.exists(f) else []
    bk = books(repo)
    print(json.dumps({"note": "Report only. Brier below 0.25 = better than a coin flip.", "picks": summary(pk),
                      "books": summary(bk), "books_by_kind": {k: summary([x for x in bk if x["kind"] == k]) for k in seals.FILES}}, indent=1))


if __name__ == "__main__":
    main()
