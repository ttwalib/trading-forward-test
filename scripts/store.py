"""GitHub data store: merge freshly fetched IBKR bars into the repo's history files.

  python3 store.py REPO_DIR TF BARS.json [NOW]

BARS.json: {"SYM": raw IBKR get_price_history arrays {"time","open","high","low","close","volume"?}, ...}.
TF: folder name under data/bars/ (e.g. "1h", "15m", "5m", "1d"). Each symbol's history is data/bars/TF/SYM.jsonl,
one bar per line {"t": epoch start (UTC), "o","h","l","c","v"}, sorted, one line per bar start. Bars still forming at
NOW (bar start + bar length > NOW) are not stored. Re-fetched bars overwrite the stored ones (IBKR can revise the last
bar). Prints {SYM: {"added", "replaced", "total", "first", "last"}}.
"""
import json, os, sys, time, datetime as dt
SECS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def parse_t(s):
    return int(dt.datetime.strptime(s.replace("Z", "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())


def main():
    repo, tf, path = sys.argv[1], sys.argv[2], sys.argv[3]
    now = int(sys.argv[4]) if len(sys.argv) > 4 else int(time.time())
    step = SECS[tf]; data = json.load(open(path)); out = {}
    folder = os.path.join(repo, "data", "bars", tf); os.makedirs(folder, exist_ok=True)
    for sym, r in data.items():
        n = len(r.get("close", []))
        for k in ("time", "open", "high", "low", "close"):
            assert len(r[k]) == n, "%s: %s length %d != %d" % (sym, k, len(r[k]), n)
        f = os.path.join(folder, sym.replace("/", "_") + ".jsonl"); rows = {}
        if os.path.exists(f):
            for line in open(f):
                if line.strip():
                    b = json.loads(line); rows[int(b["t"])] = b
        added = replaced = 0; vol = r.get("volume") or [0] * n
        for i in range(n):
            if r["close"][i] is None: continue
            t = parse_t(r["time"][i]) // step * step
            if tf == "1d": t += 43200  # daily bars sit at 12:00 UTC so the New York date is the trading date
            if tf != "1d" and t + step > now: continue
            b = {"t": t, "o": float(r["open"][i]), "h": float(r["high"][i]), "l": float(r["low"][i]),
                 "c": float(r["close"][i]), "v": float(vol[i] or 0)}
            if t in rows:
                if rows[t] != b: replaced += 1
            else: added += 1
            rows[t] = b
        keys = sorted(rows)
        with open(f, "w") as fh:
            for k in keys: fh.write(json.dumps(rows[k], separators=(",", ":")) + "\n")
        out[sym] = {"added": added, "replaced": replaced, "total": len(keys),
                    "first": dt.datetime.fromtimestamp(keys[0], dt.timezone.utc).isoformat() if keys else None,
                    "last": dt.datetime.fromtimestamp(keys[-1], dt.timezone.utc).isoformat() if keys else None}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
