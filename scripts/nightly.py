"""Nightly maths on GitHub's servers (added 2026-11-20, before the change freeze).

Before this, the orchestrator (an AI task) ran the library, the allocator and the statistics itself every night. An AI
task can time out, skip a step or run them in the wrong order. This script runs them in one fixed order on GitHub,
with no AI in the loop; the orchestrator only requests the run, reads the results and writes them to the sheet.

  python3 nightly.py REPO [DAY]

Order (each step's printed result is saved under data/nightly/):
  1. library.py REPO DAY                 -> data/nightly/library.json      (new_closed_rows for the "Library trades" tab)
  2. library.py REPO DAY --cost-mult 2   -> data/nightly/library_2x.json   (cost stress)
  3. library.py REPO DAY --fill-lag 0    -> data/nightly/library_ideal.json (ideal fills, comparison only)
  4. allocator.py REPO DAY               -> data/nightly/allocator.json    (sheet_rows for the "Allocation" tab)
  5. stats.py REPO DAY                   -> data/nightly/stats.json        (sheet_rows for the "Stats" tab)
  6. checks.py engine-report / slip-report / health -> data/nightly/checks.json
  7. dashboard.py REPO                   -> data/dashboard.json
data/nightly/stamp.json records the day, the start and end time, each step's seconds and exit code, and the commit the
run was computed from. The orchestrator must see stamp.day == DAY and ok == true before it uses the results; otherwise
it runs the same steps itself (runbook ORCHESTRATOR 4b fallback).

The request: push ops/fetch_request.json {"mode": "compute", "day": "YYYY-MM-DD"}. The request is made after the
ledger mirror check (runbook 4-pre), because the allocator and the statistics read the repo ledger.
Nothing here places, previews or changes an order: it only reads stored bars and the ledger.
"""
import json, os, subprocess, sys, time, datetime as dt
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))


def step(name, args, out, timeout=900):
    t = time.time()
    try:
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True, timeout=timeout)
        code, txt, err = p.returncode, p.stdout, p.stderr[-400:]
    except Exception as e:
        code, txt, err = 99, "", str(e)[:400]
    ok = code == 0
    if ok and out:
        try: json.loads(txt)
        except Exception: ok = False; err = "output is not JSON: " + txt[:200]
    if ok and out:
        with open(out, "w") as f: f.write(txt)
    return {"step": name, "ok": ok, "seconds": round(time.time() - t, 1), "exit": code, "error": None if ok else err}


def main():
    repo = os.path.abspath(sys.argv[1])
    day = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else dt.datetime.now(NY).date().isoformat()
    N = os.path.join(repo, "data", "nightly"); os.makedirs(N, exist_ok=True)
    S = lambda f: os.path.join(HERE, f)
    stamp = {"day": day, "started": dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    try: stamp["commit"] = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception: stamp["commit"] = None
    plan = [("library", [S("library.py"), repo, day], "library.json"),
            ("library_2x", [S("library.py"), repo, day, "--cost-mult", "2"], "library_2x.json"),
            ("library_ideal", [S("library.py"), repo, day, "--fill-lag", "0"], "library_ideal.json"),
            ("allocator", [S("allocator.py"), repo, day], "allocator.json"),
            ("stats", [S("stats.py"), repo, day], "stats.json")]
    for name, args, out in plan:
        r = step(name, args, os.path.join(N, out)); stamp["steps"].append(r)
        if not r["ok"] and name in ("library", "allocator"): break       # later steps would read stale inputs
    if all(s["ok"] for s in stamp["steps"]):
        ck = {}
        for name, args in (("engine_report", ["engine-report", repo]), ("slip_report", ["slip-report", repo]), ("health", ["health", repo])):
            tmp = os.path.join(N, "_tmp.json"); r = step(name, [S("checks.py")] + args, tmp, 300); stamp["steps"].append(r)
            if r["ok"]: ck[name] = json.load(open(tmp)); os.remove(tmp)
        json.dump(ck, open(os.path.join(N, "checks.json"), "w"), indent=1)
        stamp["steps"].append(step("dashboard", [S("dashboard.py"), repo], None, 300))
    need = {"library", "library_2x", "library_ideal", "allocator", "stats"}
    stamp["ok"] = need <= {s["step"] for s in stamp["steps"] if s["ok"]}
    stamp["finished"] = dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S")
    json.dump(stamp, open(os.path.join(N, "stamp.json"), "w"), indent=1)
    print(json.dumps(stamp, indent=1))
    sys.exit(0 if stamp["ok"] else 1)


if __name__ == "__main__":
    main()
