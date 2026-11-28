"""Strategy lab 2026-11-27 (IMPROVE A BASELINE): L5 RSI(2) pullback with ONE change, a market-breadth entry filter.

source: own. The original is library L5 (Connors RSI(2): an index ETF closes above its 200-day average with
RSI(2) < 10 -> buy the next open; leave at the open after a close above the 5-day average, or after 10 days; SPY, QQQ,
IWM, DIA, K = 4, 0.05% a side). The change comes from this week's learning: the ML report's strongest feature is
nh_nl, the baseline did best after breadth had recovered, and L5's largest live and replay losses (March and November
2026) were dips bought while most stocks were already below their averages and the 10-day time exit took the loss.

The one change: an entry signal counts only if BREADTH >= `min_breadth` on the signal day, where BREADTH = the percent
of that month's point-in-time list (scripts/pitu.py) whose close is above its own `window`-day average, using closes up
to the signal day only. Everything else (signal, exits, K, cost, next-open fills) is library.run_daily unchanged.
Tuned on days to 2021-12-31 only: window in {20, 50} x min_breadth in {30, 40, 50} = 6 settings; measured on 2022 onwards.

Economic reason: an RSI(2) dip pays the buyer for taking stock from sellers who want out now; that payment is earned
when the dip is a pause in a broad advance, and is not when breadth says the selling is already general (the start of
a leg down). The other side is short-horizon de-risking flow (vol-target and stop selling).
Limits: breadth is measured on the archive's names (today's S&P 100 family filtered by the point-in-time list), so
departed companies are missing from the gauge; the traded instruments are index ETFs, so no stock-selection hindsight
enters the returns. No stop (as the original).

Result 2026-11-27: gate REVISE, not approved. Held-out (2022 onwards) 140 trades, +0.40% a trade, but the mean daily
sleeve return (0.0115%) is BELOW the unmodified L5 over the same days (0.0131%): the 38 entries the filter skipped
earned +0.23% on average, so weak breadth did not mark the losing dips. Do not retest this filter on L5.
"""
import csv, datetime as dt, gzip, json, os, sys

ETFS = ["SPY", "QQQ", "IWM", "DIA"]
PARAMS = {"window": 20, "min_breadth": 30}   # best tuning-data Sharpe of the 6 settings (2016-10..2021); gate REVISE, NOT approved, kept as a record
TUNE_END = "2021-12-31"
MIN_NAMES = 30


def _scripts(repo):
    p = os.path.join(repo, "scripts")
    if p not in sys.path: sys.path.insert(0, p)


def load(repo, syms):
    """{sym: [(date, o, h, l, c)]}: the daily archive joined to the stored bars, total-return adjusted like the library."""
    _scripts(repo); import corp
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
        adj = [r for r in adj if r[1] > 0 and r[4] > 0]
        if adj: out[s] = adj
    return out


def breadth(stocks, lists, member, window):
    """{date: percent of that day's point-in-time members above their own `window`-day average}; closes to that day only."""
    up = {}; n = {}
    for s, rows in stocks.items():
        run = 0.0
        for i, r in enumerate(rows):
            run += r[4]
            if i >= window: run -= rows[i - window][4]
            if i < window - 1 or not member(lists, s, r[0]): continue
            n[r[0]] = n.get(r[0], 0) + 1
            if r[4] > run / window: up[r[0]] = up.get(r[0], 0) + 1
    return {d: 100.0 * up.get(d, 0) / k for d, k in n.items() if k >= MIN_NAMES}


def book(etfs, br, min_breadth, cost=0.05):
    """library.run_daily with L5's own signal and exit; min_breadth None = the unmodified original."""
    import library as L
    cal = [r[0] for r in etfs["SPY"]]
    def sig(s, i):
        cl = L.closes(etfs[s], i, 230); m = L.sma(cl, 200); r = L.rsi(cl)
        if not (m and r is not None and cl[-1] > m and r < 10): return None
        if min_breadth is not None:
            b = br.get(etfs[s][i][0])
            if b is None or b < min_breadth: return None
        return 10 - r
    return L.run_daily("L5 breadth filter", 4, etfs, cal, sig,
                       lambda s, i, p: (lambda cl: cl[-1] > L.sma(cl, 5))(L.closes(etfs[s], i, 5)), 10, cost=cost)


def universe(repo):
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    return sorted(s for s in U["universe"] if s not in ETFS)


def daily_series(repo):
    """{date: sleeve return %} with the registered settings, for forward scoring (registry series type lab_daily)."""
    _scripts(repo); import pitu
    etfs = load(repo, ETFS); stocks = load(repo, universe(repo))
    br = breadth(stocks, pitu.lists(repo), pitu.member, PARAMS["window"])
    return {k: round(v, 5) for k, v in sorted(book(etfs, br, PARAMS["min_breadth"]).daily.items())}
