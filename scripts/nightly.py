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
  6b. montecarlo.py report               -> data/nightly/montecarlo.json   (risk of a 10% fall; report only)
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
            ("interventions", [S("interventions.py"), "auto", repo], "interventions_step.json"),   # who changed what (2026-11-23)
            ("witness", [S("witness.py"), repo], "witness.json"),      # server-side first-seen time of each pick (2026-11-23)
            ("picks", [S("picks.py"), repo, day], "picks.json"),        # the AI's own picks, scored directly (2026-11-23)
            ("aisleeve", [S("aisleeve.py"), repo, day], "aisleeve.json"),   # the AI's approved strategies as one sleeve
            ("rank", [S("rank.py"), "score", repo, day], "rank.json"),       # G1 primary: the daily ranking IC
            ("allocator", [S("allocator.py"), repo, day], "allocator.json"),
            ("stats", [S("stats.py"), repo, day], "stats.json")]
    for name, args, out in plan:
        r = step(name, args, os.path.join(N, out)); stamp["steps"].append(r)
        if not r["ok"] and name in ("library", "allocator"): break       # later steps would read stale inputs
    if all(s["ok"] for s in stamp["steps"] if s["step"] != "rank"):      # an optional step (rank) never stops the rest
        ck = {}
        for name, args in (("engine_report", ["engine-report", repo]), ("slip_report", ["slip-report", repo]), ("cost_check", ["cost-check", repo]), ("health", ["health", repo]),
                           ("replay_day", ["replay-days", repo, "5"])):      # random past day re-run against the ledger (2026-11-21)
            tmp = os.path.join(N, "_tmp.json"); r = step(name, [S("checks.py")] + args, tmp, 300); stamp["steps"].append(r)
            if r["ok"]: ck[name] = json.load(open(tmp)); os.remove(tmp)
        json.dump(ck, open(os.path.join(N, "checks.json"), "w"), indent=1)
        # Monte Carlo risk report (report only, never part of the verdict; added 2026-11-21)
        stamp["steps"].append(step("montecarlo", [S("montecarlo.py"), "report", repo], os.path.join(N, "montecarlo.json"), 300))
        # report-only additions of 2026-11-23 (runbook item 31): break-even cost per sleeve, risk breakdown,
        # tamper-evident chain over the append-only evidence files
        stamp["steps"].append(step("costgrid", [S("costgrid.py"), repo], os.path.join(N, "costgrid.json"), 300))
        stamp["steps"].append(step("riskx", [S("riskx.py"), repo], os.path.join(N, "riskx.json"), 300))
        # report-only market breadth over the point-in-time top 100 (tools audit 2026-11-23); shown in the pack
        stamp["steps"].append(step("breadth", [S("breadth.py"), repo, day], os.path.join(N, "breadth.json"), 300))
        stamp["steps"].append(step("chain", [S("chain.py"), "update", repo], None, 120))
        try: stamp["chain_head"] = json.load(open(os.path.join(N, "chain.json")))["head"]
        except Exception: stamp["chain_head"] = None
        stamp["steps"].append(step("dashboard", [S("dashboard.py"), repo], None, 300))
        # challenger lane (2026-11-22): register lab approvals, then score every entry on its forward days only
        # report-only (2026-11-23): L2-L4 and L14 on the whole universe from the wide 5-minute data; never read by the
        # allocator, never part of the verdict; for the lab, the ML and the Dec 8 lane (data/library/intraday_wide.json)
        stamp["steps"].append(step("library_wide", [S("library.py"), repo, day, "--wide"], None, 900))
        stamp["steps"].append(step("seals", [S("seals.py"), repo, day], os.path.join(N, "seals.json"), 300))   # contest + daily challenger
        stamp["steps"].append(step("calib", [S("calib.py"), repo], os.path.join(N, "calib.json"), 300))
        stamp["steps"].append(step("lane_auto", [S("registry.py"), "auto", repo], None, 120))
        stamp["steps"].append(step("lane", [S("registry.py"), "score", repo], None, 600))
        # the current specification, regenerated from the configuration every night (2026-11-21)
        stamp["steps"].append(step("spec", [S("spec.py"), repo, os.path.join(repo, "ops", "SPEC.md")], None, 120))
    # CRITICAL steps (the verdict's path): the stamp is ok only if all of these ran. Since 2026-11-23 (external review 3.6)
    # this includes the steps whose output the allocator reads (witness, picks, aisleeve) and the chain check. Every
    # other step is OPTIONAL: its failure is listed in "optional_failed" and never fails the night.
    need = {"library", "library_2x", "library_ideal", "witness", "picks", "aisleeve", "allocator", "stats", "chain"}
    stamp["optional_failed"] = sorted(s["step"] for s in stamp["steps"] if not s["ok"] and s["step"] not in need)
    stamp["ok"] = need <= {s["step"] for s in stamp["steps"] if s["ok"]}
    stamp["finished"] = dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S")
    json.dump(stamp, open(os.path.join(N, "stamp.json"), "w"), indent=1)
    print(json.dumps(stamp, indent=1))
    sys.exit(0 if stamp["ok"] else 1)


if __name__ == "__main__":
    main()
