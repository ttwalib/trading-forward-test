"""Bar history helper for the GitHub data store (data/bars/<tf>/<SYM>.jsonl, written by store.py).

  plan:   python3 hist.py plan REPO TF NOW SYM[,SYM...] [MAX]      -> {"SYM": step_count to fetch, ...}
  export: python3 hist.py export REPO TF NOW SYM[,SYM...] N        -> {"SYM": raw arrays of the last N closed bars}

plan: how many bars to request from IBKR so that nothing is missed: bars since the last stored bar + 2 (overlap, so a
revised last bar is replaced), at least 3; MAX (default 1000) when the symbol has no history yet.
export: the last N bars that closed before NOW, in the raw IBKR form {"time","open","high","low","close","volume"}
that crypto_tracks.py / orb_adaptive.py / agent_score.py read, so the scripts get full indicator warm-up while each
run only fetches the few new bars.
"""
import json, os, sys, math, datetime as dt
SECS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def load(repo, tf, sym):
    f = os.path.join(repo, "data", "bars", tf, sym.replace("/", "_") + ".jsonl"); rows = {}
    if os.path.exists(f):
        for line in open(f):
            if line.strip():
                b = json.loads(line); rows[int(b["t"])] = b
    return [rows[k] for k in sorted(rows)]


def main():
    cmd, repo, tf, now, syms = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5].split(",")
    step = SECS[tf]; out = {}
    for s in syms:
        B = [b for b in load(repo, tf, s) if tf == "1d" or b["t"] + step <= now]
        if cmd == "plan":
            mx = int(sys.argv[6]) if len(sys.argv) > 6 else 1000
            out[s] = mx if not B else max(3, min(mx, math.ceil((now - B[-1]["t"]) / step) + 2))
        else:
            B = B[-int(sys.argv[6]):]
            out[s] = {"time": [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
                      "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B],
                      "close": [b["c"] for b in B], "volume": [b.get("v", 0) for b in B]}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
