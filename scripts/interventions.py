"""Intervention log (owner-approved integrity fix, 2026-11-23).

The ultimate goal is autonomy, so every human or Claude-session change that alters what Quantavius sees, decides or is
scored on has to be on record, with who made it and when. Two parts:

 add   python3 interventions.py add REPO WHO KIND "what changed" ["why"]
       Appends one row to ops/interventions.jsonl (append only, in the hash chain).
       WHO  = owner | build-session | quantavius (the AI changing its own playbook or settings) | other
       KIND = prompt | playbook | code | rule | data | model | schedule | other
       Rule (runbook, INTERVENTIONS): any session that edits a scheduled task prompt, the pick playbook, the runbook text a
       task follows, the model of a task, or any script Quantavius's results depend on, adds a row in the same session.
 auto  python3 interventions.py auto REPO
       Nightly report-only step: lists the git commits since the window opened that touch files Quantavius depends on
       (data/nightly/interventions.json), so a change nobody logged by hand still shows up.
 The summary says how many days after the window opened the last intervention came ("autonomous since").
"""
import datetime as dt, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal

REL = os.path.join("ops", "interventions.jsonl")
WATCH = ["ops/pick_playbook.md", "ops/runbook.md", "scripts/judge.py", "scripts/picks.py", "scripts/rank.py", "scripts/aisleeve.py",
         "scripts/seals.py", "scripts/registry.py", "scripts/ml.py", "strategies", "ops/tasks.json"]


def rows(repo):
    p = os.path.join(repo, REL)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def add(repo, who, kind, what, why=""):
    r = {"at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "who": who, "kind": kind, "what": what[:500], "why": why[:500]}
    with open(os.path.join(repo, REL), "a") as f: f.write(json.dumps(r, sort_keys=True) + "\n")
    return r


def auto(repo):
    start = tcal.ALLOC_FREEZE.isoformat()
    try:
        out = subprocess.run(["git", "log", "--since=" + start, "--format=%H|%cI|%an|%s", "--"] + WATCH, cwd=repo,
                             capture_output=True, text=True, timeout=60).stdout.strip().splitlines()
    except Exception as e:
        out = []
    commits = [dict(zip(("sha", "at", "author", "subject"), l.split("|", 3))) for l in out if l.count("|") >= 3]
    logged = rows(repo)
    since = [r for r in logged if r["at_utc"][:10] >= start]
    last = max([r["at_utc"][:10] for r in since] + [c["at"][:10] for c in commits], default=None)
    res = {"window_opens": start, "logged_rows": len(logged), "logged_in_window": len(since),
           "watched_commits_in_window": len(commits), "last_change": last,
           "by_who": {w: sum(1 for r in since if r["who"] == w) for w in sorted({r["who"] for r in since})},
           "recent_commits": commits[:15],
           "note": "report only; every row in the window is part of how the verdict is read (see preregistration, autonomy statement)"}
    os.makedirs(os.path.join(repo, "data", "nightly"), exist_ok=True)
    json.dump(res, open(os.path.join(repo, "data", "nightly", "interventions.json"), "w"), indent=1)
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "add": print(json.dumps(add(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else "")))
    elif a and a[0] == "auto": print(json.dumps(auto(a[1])))
    else: print(__doc__)
