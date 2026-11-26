"""Strategy lab 2026-11-25: one-day cross-sectional reversal, only after high-dispersion days (US daily, long/short).

source: shelf #1 (ops/idea_shelf.md; public notes in github.com/moondevonyt/i-found-an-mit-research-paper-with-a-
sharpe-ratio-of-53-i-tested-their-strategy; ideas only, no code or data taken). The effect itself is the short-term
reversal of Lehmann (1990) / Jegadeesh (1990); the dispersion condition follows the shelf claim.

Rules (no discretion): at the close of day t take every stock that is in that month's point-in-time list (pitu) and has
a bar on t-1, t and t+1. r_i = close-to-close return of day t; D_t = cross-sectional standard deviation of r_i. If the
share of the PREVIOUS 250 days' D values that lie below D_t is >= q (cut point from past days only), buy the tenth of
names with the lowest r_i and short the tenth with the highest, equal weights, half the sleeve on each side. Fill at
the open of t+1, leave at the open of t+1+hold. Cost 0.05% per side on every leg. No stop (a one-to-three-day
market-neutral basket). Tuned on signal days to 2021-12-31 only: q in {0, 0.4, 0.6, 0.8} x hold in {1, 2, 3}.
Differs from L6 (single-name Bollinger reversion, long only) and L13 (pairs): this is a dollar-neutral decile basket
conditioned on the whole cross-section's dispersion.
Limits: prices come from the archive of today's S&P 100 names filtered by the point-in-time list, so a company that
left the index family has no bars here (the lab run also re-tested on data/pit/bars_1d, which holds departed names);
no borrow fee is charged on the short side.
"""
import csv, datetime as dt, gzip, json, math, os, sys

COST = 0.0005
LOOKBACK = 250
DECILE = 0.10
MIN_NAMES = 30
PARAMS = {"q": 0.8, "hold": 3}   # best tuning-data Sharpe of the 12 settings (2017-2021); REJECTED by the gate, kept as a record
TUNE_END = "2021-12-31"


def _scripts(repo):
    p = os.path.join(repo, "scripts")
    if p not in sys.path: sys.path.insert(0, p)


def load_hist(repo, symbols=None):
    """{sym: {date: (o, c)}} from the daily archive joined to the stored bars, total-return adjusted (corp.tr_adjust)."""
    _scripts(repo); import corp
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    syms = symbols or sorted(U["universe"])
    out = {}
    for s in syms:
        rows = {}
        f = os.path.join(repo, "data", "hist", "1d", s.replace("/", "_") + ".csv.gz")
        if os.path.exists(f):
            with gzip.open(f, "rt") as fh:
                for r in csv.DictReader(fh):
                    d = dt.datetime.fromtimestamp(int(r["t"]), dt.timezone.utc).date().isoformat()
                    rows[d] = (float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
        f = os.path.join(repo, "data", "bars", "1d", s + ".jsonl")
        if os.path.exists(f):
            for l in open(f):
                if not l.strip(): continue
                b = json.loads(l)
                d = dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).date().isoformat()
                rows.setdefault(d, (b["o"], b["h"], b["l"], b["c"]))
        adj = corp.tr_adjust(repo, s, sorted((d,) + v for d, v in rows.items()))
        out[s] = {r[0]: (r[1], r[4]) for r in adj if r[1] > 0 and r[4] > 0}
    return out


def load_pit(repo):
    """{sym: {date: (o, c)}} from data/pit/bars_1d.csv.gz (every S&P 500 member since 2016, departed names included)."""
    out = {}
    with gzip.open(os.path.join(repo, "data", "pit", "bars_1d.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            o, c = float(r["o"]), float(r["c"])
            if o > 0 and c > 0: out.setdefault(r["sym"], {})[r["date"]] = (o, c)
    return out


def backtest(px, lists, member, q, hold, cost=COST, cal=None):
    """-> (daily {date: sleeve return %}, baskets [{"day", "net", "n", "long", "short"}]). No look-ahead: the signal
    of day t uses closes to t and dispersion cut points from days before t; fills are opens from t+1 on."""
    cal = cal or sorted({d for v in px.values() for d in v})
    idx = {d: i for i, d in enumerate(cal)}
    hist_d = []; daily = {}; baskets = []
    started = None
    for i in range(1, len(cal) - 1):
        t, tp, tn = cal[i], cal[i - 1], cal[i + 1]
        rs = []
        for s, v in px.items():
            if t in v and tp in v and member(lists, s, t):
                rs.append((v[t][1] / v[tp][1] - 1, s))
        if len(rs) < MIN_NAMES: continue
        m = sum(r for r, _ in rs) / len(rs)
        D = math.sqrt(sum((r - m) ** 2 for r, _ in rs) / (len(rs) - 1))
        past = hist_d[-LOOKBACK:]; hist_d.append(D)
        if len(past) < LOOKBACK: continue
        if started is None: started = i
        daily.setdefault(t, 0.0)
        if sum(1 for x in past if x < D) / len(past) < q: continue
        rs = sorted((r, s) for r, s in rs if tn in px[s])      # a name with no bar tomorrow cannot be filled
        k = max(3, int(round(DECILE * len(rs))))
        legs = [(s, 1) for _, s in rs[:k]] + [(s, -1) for _, s in rs[-k:]]
        e = i + 1; nets = []; per_day = [0.0] * hold
        for s, side in legs:
            v = px[s]; prev = v[cal[e]][0]; entry = prev; last = prev
            for j in range(hold):
                nx = cal[e + j + 1] if e + j + 1 < len(cal) else None
                if nx is not None and nx in v: last = v[nx][0]
                elif e + j < len(cal) and cal[e + j] in v: last = v[cal[e + j]][1]   # no next open (data end or delisting): last close
                per_day[j] += side * (last / prev - 1) / len(legs); prev = last
            nets.append(side * (last / entry - 1) - 2 * cost)
        per_day[0] -= cost; per_day[-1] -= cost
        for j in range(hold):
            if e + j < len(cal):
                d = cal[e + j]; daily[d] = daily.get(d, 0.0) + 100.0 * per_day[j] / hold
        baskets.append({"day": t, "net": sum(nets) / len(nets), "n": len(legs),
                        "long": [s for s, sd in legs if sd > 0], "short": [s for s, sd in legs if sd < 0]})
    return daily, baskets


def daily_series(repo):
    """{date: sleeve return %} with the registered settings, for forward scoring (registry series type lab_daily)."""
    _scripts(repo); import pitu
    px = load_hist(repo); L = pitu.lists(repo)
    cal = sorted(px["AAPL"]) if "AAPL" in px else None
    d, _ = backtest(px, L, pitu.member, PARAMS["q"], PARAMS["hold"], cal=cal)
    return {k: round(v, 5) for k, v in sorted(d.items())}
