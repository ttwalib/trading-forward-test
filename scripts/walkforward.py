"""Walk-forward test of the adaptive crypto tuning on the stored hourly history.

  python3 walkforward.py HISTORY_DIR STEP [TRAIN_BARS TEST_BARS] > wf.json

HISTORY_DIR holds one file per coin, <COIN>.jsonl, one bar per line {"t": epoch start, "o","h","l","c","v"}
(the GitHub data store's data/bars/1h or data/bars/15m folder). STEP = 3600 or 900.
For each fold: tune on the TRAIN_BARS bars before the fold (crypto_tracks.search, starting from the original rules),
then trade the next TEST_BARS bars with (a) the tuned settings and (b) the original rules, counting only trades entered
inside the test window. Folds step forward by TEST_BARS. The result shows, per strategy, whether daily retuning beats
the fixed rules out of sample, which is the question the adaptive tracks are asking.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crypto_tracks as ct


def load(d, step):
    data = {}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".jsonl"): continue
        rows = {}
        for line in open(os.path.join(d, f)):
            line = line.strip()
            if line:
                r = json.loads(line); rows[int(r["t"]) // step * step] = r
        bars = [rows[k] for k in sorted(rows)]
        data[f[:-6]] = [{"t": int(b["t"]) // step * step, "o": float(b["o"]), "h": float(b["h"]), "l": float(b["l"]),
                         "c": float(b["c"]), "v": float(b.get("v") or 0)} for b in bars]
    return data


def raw(bars):
    iso = [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in bars]
    return {"time": iso, "open": [b["o"] for b in bars], "high": [b["h"] for b in bars], "low": [b["l"] for b in bars],
            "close": [b["c"] for b in bars], "volume": [b["v"] for b in bars]}


def cut(data, t0, t1):
    return {c: [b for b in B if t0 <= b["t"] < t1] for c, B in data.items()}


def summ(rs):
    n = sum(r["trades"] for r in rs)
    if not n: return {"trades": 0, "win_rate": None, "avg_net_pct": None}
    w = sum(r["trades"] * (r["win_rate"] or 0) / 100 for r in rs)
    s = sum(r["trades"] * (r["avg_net_pct"] or 0) for r in rs)
    return {"trades": n, "win_rate": round(100 * w / n, 1), "avg_net_pct": round(s / n, 4)}


def main():
    d, step = sys.argv[1], int(sys.argv[2])
    train = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    test = int(sys.argv[4]) if len(sys.argv) > 4 else (72 if step == 3600 else 96)
    data = load(d, step)
    times = sorted({b["t"] for B in data.values() for b in B})
    if len(times) < train + test:
        print(json.dumps({"error": "need at least %d bars, have %d" % (train + test, len(times))})); return
    out = {"step": step, "train_bars": train, "test_bars": test, "bars": len(times),
           "from": ct.et(times[0]), "to": ct.et(times[-1]), "strategies": {}}
    folds = list(range(train, len(times) - test + 1, test))
    for s in ct.DEFAULTS:
        tuned, fixed, picks = [], [], []
        for i in folds:
            t_tr0, t_te0 = times[i - train], times[i]
            t_te1 = times[i + test - 1] + step
            tr = {c: ct.norm(raw(B), t_te0 + step, step) for c, B in cut(data, t_tr0, t_te0).items()}
            btc_tr = {b["t"]: b["c"] for b in tr.get("BTC", [])}
            new, base, res, nc, nok = ct.search(tr, btc_tr, s, {}, step)
            p = new or {}
            # test window: warm-up bars before it + the test bars; count only trades entered in the window
            te = {c: ct.norm(raw(B), t_te1 + step, step)
                  for c, B in cut(data, t_te0 - ct.WARMUP * step - step, t_te1).items()}
            btc_te = {b["t"]: b["c"] for b in te.get("BTC", [])}
            tuned.append(ct.backtest(te, btc_te, s, {s: p}, step, since=t_te0))
            fixed.append(ct.backtest(te, btc_te, s, {}, step, since=t_te0))
            picks.append({"fold_start": ct.et(t_te0), "settings": p or "original"})
        a, b = summ(tuned), summ(fixed)
        verdict = "not enough trades"
        if a["trades"] >= 10 and b["trades"] >= 10:
            better = a["win_rate"] > b["win_rate"] and a["avg_net_pct"] >= b["avg_net_pct"]
            worse = a["win_rate"] < b["win_rate"] and a["avg_net_pct"] < b["avg_net_pct"]
            verdict = "retuning helped" if better else ("retuning hurt" if worse else "mixed")
        out["strategies"][s] = {"tuned_oos": a, "fixed_oos": b, "verdict": verdict, "folds": len(folds), "picks": picks}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
