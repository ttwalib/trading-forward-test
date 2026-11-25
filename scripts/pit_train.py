#!/usr/bin/env python3
"""Honest training history for the machine-learning stock models (challenger lane, stage 1; built 2026-11-22).

Problem it solves: the 10-year daily archive holds today's large companies only, so a model trained on it learns that
"stocks that ended up in the index did well", which is hindsight. This builds the training set from the S&P 500 as it
stood ON EACH DAY (data/pit/sp500_members.csv.gz), with the prices of companies that later left the index
(data/pit/bars_1d.csv.gz, Alpaca, fully adjusted). A company whose prices stop (taken over, delisted) is carried flat at
its last price, so a label that runs past its last day uses that price, as a holder would have received.

One row per (day, member with a price that day and at least LOOKBACK days of history):
  features, computed from that day's close and earlier only:
    r1, r5, r21, r63, r126          past returns over 1, 5, 21, 63, 126 trading days
    mom_126_21                      return from 126 to 21 days ago (momentum without the last month)
    vol21, vol63                    annualised volatility of daily log returns
    hi126, lo126                    distance from the 126-day high and low
    dvol21                          log of the median daily dollar volume over 21 days
    vratio                          mean volume over 5 days / over 21 days
    rsi14                           14-day RSI (Wilder)
    mkt_r21, breadth50              market context: median r21 of that day's members, share above their 50-day mean
  label (the next 5 trading days, never used as a feature):
    fwd5                            close t+5 / close t - 1
    xs5                             fwd5 minus the median fwd5 of that day's members (relative, for ranking)
    left5                           1 if the company's prices stop within those 5 days
The file carries no transaction costs; the ranker adds them when it turns predictions into trades.

Check built in: for a few random days the features are rebuilt from price files cut off at that day; any difference
means a feature looked ahead, and the build fails.

  python3 pit_train.py build REPO   -> data/pit/train_1d.csv.gz, data/pit/train_report.json
Limits: about 2.9 years (2024-01 to 2026-11), one market regime family; the membership file is community-maintained;
prices from one source. Testing only, not financial advice.
"""
import csv, gzip, io, json, math, os, random, statistics as st, sys

LOOKBACK, H = 126, 5
FEATS = ["r1", "r5", "r21", "r63", "r126", "mom_126_21", "vol21", "vol63", "hi126", "lo126", "dvol21", "vratio", "rsi14"]


def load(repo):
    P = os.path.join(repo, "data", "pit")
    rows = list(csv.reader(io.StringIO(gzip.open(os.path.join(P, "sp500_members.csv.gz"), "rt").read())))[1:]
    mem = sorted((r[0], frozenset(t.strip() for t in r[1].split(",") if t.strip())) for r in rows if len(r) >= 2)
    bars = {}
    with gzip.open(os.path.join(P, "bars_1d.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            bars.setdefault(r["sym"], {})[r["date"]] = (float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"]))
    import glob                  # forward bars from the nightly refresh (data/pit/fwd/, 2026-11-25); stored dates win
    for f in sorted(glob.glob(os.path.join(P, "fwd", "*.csv.gz"))):
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh): bars.setdefault(r["sym"], {}).setdefault(r["date"], (float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"])))
    return mem, bars


def members_on(mem, d):
    lo, hi = 0, len(mem) - 1; out = None
    while lo <= hi:
        m = (lo + hi) // 2
        if mem[m][0] <= d: out = mem[m][1]; lo = m + 1
        else: hi = m - 1
    return out or frozenset()


def feats(H_, L_, C, V, i):
    """Features for index i from arrays up to and including i (nothing later is read)."""
    c = C[i]
    def ret(k): return c / C[i - k] - 1
    lr = [math.log(C[j] / C[j - 1]) for j in range(i - 62, i + 1)]
    def vol(xs): return st.pstdev(xs) * math.sqrt(252)
    up = dn = 0.0
    g = [C[j] - C[j - 1] for j in range(i - 13, i + 1)]
    up = sum(x for x in g if x > 0) / 14; dn = -sum(x for x in g if x < 0) / 14
    dv = sorted(C[j] * V[j] for j in range(i - 20, i + 1))
    v5 = sum(V[i - 4:i + 1]) / 5; v21 = sum(V[i - 20:i + 1]) / 21
    return {"r1": ret(1), "r5": ret(5), "r21": ret(21), "r63": ret(63), "r126": ret(126),
            "mom_126_21": C[i - 21] / C[i - 126] - 1, "vol21": vol(lr[-21:]), "vol63": vol(lr),
            "hi126": c / max(H_[i - 125:i + 1]) - 1, "lo126": c / min(L_[i - 125:i + 1]) - 1,
            "dvol21": math.log(max(dv[10], 1.0)), "vratio": v5 / v21 if v21 > 0 else 1.0,
            "rsi14": 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)}


def arrays(b, cal):
    """Aligned arrays from the first to the last day the stock has a price; gaps and days after the last price are
    carried flat (the last close), which is how a holder of a delisted or acquired stock would be paid."""
    ds = sorted(b); first, last = ds[0], ds[-1]
    idx = [d for d in cal if d >= first]; Hh, Ll, Cc, Vv, has = [], [], [], [], []
    for d in idx:
        if d in b: h, l, c, v = b[d]; has.append(True)
        else: c = Cc[-1]; h = l = c; v = 0.0; has.append(False)
        Hh.append(h); Ll.append(l); Cc.append(c); Vv.append(v)
    return idx, Hh, Ll, Cc, Vv, has, last


def build(repo, write=True):
    mem, bars = load(repo)
    cnt = {}
    for b in bars.values():
        for d in b: cnt[d] = cnt.get(d, 0) + 1
    cal = sorted(d for d, n in cnt.items() if n >= 300)
    pos = {d: k for k, d in enumerate(cal)}
    A = {s: arrays(b, cal) for s, b in bars.items() if len(b) > LOOKBACK + H}
    rows = []
    for s, (idx, Hh, Ll, Cc, Vv, has, last) in A.items():
        for i in range(LOOKBACK, len(idx) - H):
            d = idx[i]
            if not has[i] or d > last or s not in members_on(mem, d): continue
            f = feats(Hh, Ll, Cc, Vv, i)
            j = i + H; left = 1 if idx[j] > last else 0
            rows.append([d, s] + [f[k] for k in FEATS] + [Cc[j] / Cc[i] - 1, left])
    by = {}
    for r in rows: by.setdefault(r[0], []).append(r)
    out = []
    ma50 = {}
    for s, (idx, Hh, Ll, Cc, Vv, has, last) in A.items():
        for i in range(49, len(idx)):
            ma50[(idx[i], s)] = Cc[i] > sum(Cc[i - 49:i + 1]) / 50
    for d in sorted(by):
        rs = by[d]; med = st.median(r[-2] for r in rs); mr21 = st.median(r[2 + FEATS.index("r21")] for r in rs)
        br = sum(1 for r in rs if ma50.get((d, r[1]))) / len(rs)
        for r in rs: out.append(r[:2 + len(FEATS)] + [mr21, br, r[-2], r[-2] - med, r[-1]])
    head = ["date", "sym"] + FEATS + ["mkt_r21", "breadth50", "fwd5", "xs5", "left5"]
    # look-ahead check: rebuild a few rows from price files cut off at their day
    rng = random.Random(20261122); bad = []; checked = 0
    for r in rng.sample(out, min(200, len(out))):
        d, s = r[0], r[1]; cut = {k: v for k, v in bars[s].items() if k <= d}
        idx, Hh, Ll, Cc, Vv, has, last = arrays(cut, [x for x in cal if x <= d]); i = idx.index(d)
        f = feats(Hh, Ll, Cc, Vv, i); checked += 1
        if any(abs(f[k] - r[2 + n]) > 1e-9 for n, k in enumerate(FEATS)): bad.append("%s %s" % (d, s))
    if bad: raise SystemExit("LOOK-AHEAD: features changed when later prices were removed: %s" % bad[:5])
    today = mem[-1][1]
    syms = {r[1] for r in out}
    rep = {"built": "2026-11-22", "rows": len(out), "days": len(by), "from": min(by), "to": max(by),
           "label_through": cal[-1], "members_per_day_median": st.median(len(v) for v in by.values()),
           "symbols": len(syms), "symbols_not_in_latest_list": len(syms - today),
           "rows_from_companies_not_in_latest_list_pct": round(100 * sum(1 for r in out if r[1] not in today) / len(out), 2),
           "rows_whose_label_runs_past_the_last_price": sum(1 for r in out if r[-1]),
           "lookahead_check": {"rows_checked": checked, "differences": 0},
           "fwd5_mean_pct": round(100 * st.mean(r[-3] for r in out), 4), "xs5_sd_pct": round(100 * st.pstdev(r[-2] for r in out), 4),
           "features": FEATS + ["mkt_r21", "breadth50"], "label": "xs5 (5-day return minus that day's member median)",
           "limits": ["about 2.9 years, 2024-01 to 2026-11: one stretch of market history",
                      "membership from a community-maintained file (github.com/fja05680/sp500)",
                      "one price source (Alpaca, adjusted); no costs in the labels"]}
    if write:
        P = os.path.join(repo, "data", "pit")
        with gzip.open(os.path.join(P, "train_1d.csv.gz"), "wt", newline="") as f:
            w = csv.writer(f); w.writerow(head)
            for r in out: w.writerow(r[:2] + [round(x, 6) if isinstance(x, float) else x for x in r[2:]])
        json.dump(rep, open(os.path.join(P, "train_report.json"), "w"), indent=1)
    return rep


if __name__ == "__main__":
    if sys.argv[1] == "build": print(json.dumps(build(sys.argv[2]), indent=1))
