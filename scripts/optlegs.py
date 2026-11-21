#!/usr/bin/env python3
"""Registry of option legs whose 5-minute bars the free feed stores (added 2026-11-21).

The deep OTM + weekly options task picks strikes with IBKR (small results), registers every leg here, and asks GitHub
to fetch the bars (fetch_free.py mode "optbars": Alpaca historical option bars, trades from OPRA, at least 15 minutes
old). The bars land in data/bars/opt5m/OPT_<cid>.jsonl, so no price ever passes through the AI's hands.

  optlegs.py add REPO CID UND YYYYMMDD C|P STRIKE FROM_DAY   register one leg (idempotent); prints its OCC symbol
  optlegs.py add-json REPO FILE     FILE = [{"cid","und","expiry","right","strike","from"}, ...]
  optlegs.py list REPO              legs still being fetched
  optlegs.py bars REPO NOW CID[,CID...]   stored bars as {"<cid>": {"time","open","high","low","close","volume"}}
                                          (the shape deep_otm.py, weekly_opts.py, greeks.py and options_sim.py read)
"""
import json, os, sys, datetime as dt

UTC = dt.timezone.utc


def occ(und, expiry, right, strike):
    e = str(expiry).replace("-", ""); k = int(round(float(strike) * 1000))
    assert len(e) == 8 and right in ("C", "P") and k > 0
    return "%s%s%s%08d" % (und.upper().replace(".", ""), e[2:], right, k)


def path(repo): return os.path.join(repo, "data", "opt_legs.json")


def load(repo):
    p = path(repo)
    return json.load(open(p)) if os.path.exists(p) else {}


def save(repo, reg):
    with open(path(repo), "w") as f: json.dump(reg, f, indent=0, sort_keys=True); f.write("\n")


def add(reg, cid, und, expiry, right, strike, frm):
    cid = str(int(float(cid))); e = str(expiry).replace("-", "")
    dt.date.fromisoformat(frm)
    o = occ(und, e, right, strike)
    old = reg.get(cid)
    if old and old["occ"] != o: raise SystemExit("cid %s already registered as %s, not %s" % (cid, old["occ"], o))
    if old: old["from"] = min(old["from"], frm); old.pop("final", None) if frm < old["from"] else None
    else: reg[cid] = {"occ": o, "expiry": e, "from": frm}
    return o


def bars(repo, now, cids):
    out = {}
    for c in cids:
        f = os.path.join(repo, "data", "bars", "opt5m", "OPT_%s.jsonl" % c); B = []
        if os.path.exists(f):
            B = sorted((json.loads(l) for l in open(f) if l.strip()), key=lambda b: b["t"])
        B = [b for b in B if b["t"] + 300 <= now]
        out[str(c)] = {"time": [dt.datetime.fromtimestamp(b["t"], UTC).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
                       "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B],
                       "close": [b["c"] for b in B], "volume": [b.get("v", 0) for b in B]}
    return out


if __name__ == "__main__":
    cmd, repo = sys.argv[1], sys.argv[2]
    if cmd == "add":
        reg = load(repo); print(add(reg, *sys.argv[3:9])); save(repo, reg)
    elif cmd == "add-json":
        reg = load(repo)
        for r in json.load(open(sys.argv[3])): print(r["cid"], add(reg, r["cid"], r["und"], r["expiry"], r["right"], r["strike"], r["from"]))
        save(repo, reg)
    elif cmd == "list":
        print(json.dumps({c: v for c, v in load(repo).items() if not v.get("final")}))
    elif cmd == "bars":
        print(json.dumps(bars(repo, int(sys.argv[3]), sys.argv[4].split(",")), separators=(",", ":")))
    else: sys.exit("unknown command")
