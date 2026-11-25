"""Record and check the change freeze by hand (review N2, 2026-11-24).

  python3 freeze.py record REPO     writes ops/freeze.json: the sha256 of every file in allocator.FROZEN_FILES, the
                                    commit it was taken at and the pinned packages of the nightly maths. Run ONCE, by
                                    hand, after the Dec 4 audit has been triaged (Dec 6), then commit and tag it
                                    (git tag -a freeze-<date>). Refuses if ops/freeze.json already exists.
  python3 freeze.py check REPO      compares the files with ops/freeze.json; prints what differs (exit 1 if any).

The nightly allocator still writes ops/freeze.json itself on the first night on or after the freeze date if nobody
recorded it (marked "recorded_by": "nightly fallback"), so the guard is never left without a record.
"""
import datetime as dt, hashlib, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allocator

HERE = os.path.dirname(os.path.abspath(__file__))


def hashes():
    return {f: hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
            for f in allocator.FROZEN_FILES if os.path.exists(os.path.join(HERE, f))}


def pins(repo):
    """Exact package pins installed by the nightly maths and the ML jobs (from the workflow file)."""
    p = os.path.join(repo, ".github", "workflows", "data.yml")
    return sorted(set(re.findall(r"\b([a-zA-Z][\w-]*==[\w.]+)", open(p).read()))) if os.path.exists(p) else []


def record(repo):
    f = os.path.join(repo, "ops", "freeze.json")
    if os.path.exists(f): return {"recorded": False, "why": "ops/freeze.json already exists; it is never rewritten"}
    try: commit = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception: commit = None
    missing = [x for x in allocator.FROZEN_FILES if not os.path.exists(os.path.join(HERE, x))]
    rec = {"recorded_on": dt.date.today().isoformat(), "recorded_by": "hand (scripts/freeze.py record)", "commit": commit,
           "sha256": hashes(), "pins": pins(repo), "missing": missing}
    json.dump(rec, open(f, "w"), indent=1)
    return {"recorded": True, "files": len(rec["sha256"]), "missing": missing, "pins": rec["pins"], "commit": commit}


def check(repo):
    f = os.path.join(repo, "ops", "freeze.json")
    if not os.path.exists(f): return {"recorded": False}
    rec = json.load(open(f))["sha256"]; cur = hashes()
    bad = sorted(x for x in rec if cur.get(x) != rec[x])
    unrecorded = sorted(x for x in cur if x not in rec)
    return {"recorded": True, "differ": bad, "frozen_but_not_in_record": unrecorded, "ok": not bad}


if __name__ == "__main__":
    a = sys.argv[1:]
    r = record(a[1]) if a[0] == "record" else check(a[1])
    print(json.dumps(r, indent=1))
    if a[0] == "check" and r.get("recorded") and not r.get("ok"): sys.exit(1)
