"""Lab sweeps on GitHub (Dec 8 plan stage 1.3, built 2026-11-25). Runs by .github/workflows/labrun.yml when a request
file is pushed, so a heavy parameter sweep and its CPCV run on GitHub instead of inside the lab's AI session.

  python3 labrun.py REPO            run every request in strategies/requests/ that has no result yet
  python3 labrun.py REPO ID         run (or re-run) one request

REQUEST strategies/requests/<id>.json (written by the lab task; id = letters, digits, "-" and "_"):
  {"id": "...", "module": "strategies/candidates/<id>.py", "args": {...}, "cpcv": [10, 2, 5]}
The module must define configs(repo, **args) -> {"<setting name>": {"YYYY-MM-DD": daily return %, ...}, ...}: the
daily returns of EVERY setting in its grid over the whole history (same cost and fill rules as the runbook's lab
sections). Optional trades(repo, setting, **args) -> per-trade results for the gate's oos_results.

RESULT strategies/results/<id>.json: the request, its sha, run time, the configs, the CPCV output (scripts/cpcv.py with
the requested groups, test groups and embargo), and per-setting trade lists when the module has trades(). The lab task
still runs review.py gate itself on these results and writes the StrategyLab row; every setting counts as a trial.

Safety: the workflow runs with no secrets and no market-data keys; only files under strategies/ may be imported; the
module is run in a child process with a time limit; nothing here touches the frozen scripts or any score.
"""
import hashlib, importlib.util, json, os, re, subprocess, sys, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
LIMIT_S = 3000


def _child(repo, req, out):
    """Runs inside a child process: imports the module and writes its configs (and trades) to out."""
    path = os.path.realpath(os.path.join(repo, req["module"]))
    if not path.startswith(os.path.realpath(os.path.join(repo, "strategies")) + os.sep) or not path.endswith(".py"):
        raise SystemExit("module must be a .py file under strategies/")
    sys.path.insert(0, os.path.join(repo, "scripts"))
    spec = importlib.util.spec_from_file_location("lab_candidate", path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    args = req.get("args") or {}
    cfg = m.configs(repo, **args)
    res = {"configs": {str(k): {str(d): float(v) for d, v in s.items()} for k, s in cfg.items()}}
    if hasattr(m, "trades"):
        res["trades"] = {k: [float(x) for x in (m.trades(repo, k, **args) or [])] for k in res["configs"]}
    json.dump(res, open(out, "w"))


def run_one(repo, rid):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", rid): return {"id": rid, "error": "bad id"}
    rp = os.path.join(repo, "strategies", "requests", rid + ".json")
    raw = open(rp, "rb").read(); req = json.loads(raw)
    t0 = time.time(); tmp = "/tmp/labrun_%s.json" % rid
    p = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--child", repo, rp, tmp],
                       capture_output=True, text=True, timeout=LIMIT_S)
    out = {"id": rid, "request": req, "request_sha": hashlib.sha256(raw).hexdigest(),
           "ran_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": round(time.time() - t0, 1)}
    if p.returncode != 0 or not os.path.exists(tmp):
        out["error"] = (p.stderr or p.stdout)[-1500:]
    else:
        r = json.load(open(tmp)); out.update(r)
        import cpcv
        n, k, e = (req.get("cpcv") or [10, 2, 5])[:3]
        try: out["cpcv"] = cpcv.cpcv(r["configs"], int(n), int(k), int(e))
        except Exception as ex: out["cpcv"] = {"error": str(ex)[:300]}
        out["n_configs"] = len(r["configs"])
    od = os.path.join(repo, "strategies", "results"); os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, rid + ".json"), "w"), indent=1)
    return {"id": rid, "ok": "error" not in out, "n_configs": out.get("n_configs"), "seconds": out["seconds"],
            "cpcv_pass": (out.get("cpcv") or {}).get("pass")}


def main(a):
    if a and a[0] == "--child":
        _child(a[1], json.load(open(a[2])), a[3]); return
    repo = a[0] if a else "."
    rq = os.path.join(repo, "strategies", "requests")
    ids = [a[1]] if len(a) > 1 else sorted(f[:-5] for f in os.listdir(rq) if f.endswith(".json")
                                         and not os.path.exists(os.path.join(repo, "strategies", "results", f))) if os.path.isdir(rq) else []
    print(json.dumps([run_one(repo, i) for i in ids], indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
