"""Server-side witness for the morning picks (owner-approved integrity fix, 2026-11-23).

A pick row carries a "picked_at" time that the morning task writes itself, so on its own it proves nothing about when the
pick was made. This script runs on GitHub's servers (every tick, and in the nightly maths) and records the FIRST time each
AgentPicks row was seen in the repository, using the runner's clock, in data/witness/picks.jsonl (append only, in the hash
chain). It also keeps a copy of the row's "checks" cell as first seen, so sizing, holding period and stated confidence cannot
be edited after the fact.

Rule used by picks.py from ENFORCE_FROM: a pick counts only if it was first seen before 09:30 New York on its pick day
and its sizing and confidence come from the first-seen copy. Rows that already existed when this script first ran are
marked "grandfathered" (they are warm-up days before the window).

Usage: python3 witness.py REPO
"""
import datetime as dt, hashlib, json, os, sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger

NY = ZoneInfo("America/New_York")
ENFORCE_FROM = "2026-11-30"          # first shakedown day; earlier pick days are accepted on their own stamp
REL = os.path.join("data", "witness", "picks.jsonl")


def row_id(r):
    return "%s|%s|%s" % (r.get("picked_at"), r.get("asset"), r.get("symbol"))


def load(repo):
    p = os.path.join(repo, REL)
    out = {}
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                w = json.loads(l); out[w["id"]] = w
    return out


def run(repo, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    seen = load(repo); first_run = not seen
    new = []
    for r in ledger.load(repo, "AgentPicks"):
        i = row_id(r)
        if i in seen or not r.get("picked_at"): continue
        w = {"id": i, "seen_at_utc": now.strftime("%Y-%m-%d %H:%M:%S"), "seen_at_ny": now.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S"),
             "grandfathered": bool(first_run), "checks": str(r.get("checks") or ""),
             "why_sha": hashlib.sha256(str(r.get("why") or "").encode()).hexdigest()[:16]}
        seen[i] = w; new.append(w)
    if new:
        os.makedirs(os.path.dirname(os.path.join(repo, REL)), exist_ok=True)
        with open(os.path.join(repo, REL), "a") as f:
            for w in new: f.write(json.dumps(w, sort_keys=True) + "\n")
    return {"new": len(new), "total": len(seen), "first_run": first_run}


def counts(w, pick_day):
    """True if this witnessed row may count for pick_day under the rule."""
    if pick_day < ENFORCE_FROM: return True
    if not w or w.get("grandfathered"): return bool(w and w.get("grandfathered"))
    return w["seen_at_ny"][:10] < pick_day or (w["seen_at_ny"][:10] == pick_day and w["seen_at_ny"][11:16] < "09:30")


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else ".")))
