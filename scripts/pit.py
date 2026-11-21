"""Point-in-time backtest record for the stock-picking sleeves (free build, owner decision 2026-11-21, before the freeze).

The problem: the past record of L6, L7, L8 and L15 was computed on TODAY's list of large companies. That list was
drawn up with hindsight: it holds the companies that did well enough to be on it now. Their past record is too rosy.

The fix here: replay those four strategies on the list as it stood at the time.
  - Membership: the S&P 500 members on each date (data/pit/sp500_members.csv.gz, a community file built from
    Wikipedia's change lists; see data/pit/source.json).
  - There is no free history of the S&P 100, so each month's list is the 100 members with the highest median daily
    dollar volume over the 60 trading days before that month. It uses nothing from the month itself or later.
  - Prices include the companies that later left the index (Alpaca, fully adjusted). A stock whose prices stop
    (taken over, delisted) is carried flat at its last price so an open position closes at that price.
The run uses library.py unchanged (its ELIGIBLE hook) on a temporary copy of the repo and keeps only the days before
the test started (2026-11-16). allocator.py then uses this record, instead of the hindsight one, as the backtest
history of those four sleeves. Live days are untouched: the live list was fixed before any result.

Limits, to be stated wherever this is reported: the monthly "top 100 by dollar volume" list is a stand-in for the
S&P 100, not the index itself; the membership file is community-maintained; L10 (earnings drift) is NOT covered,
because earnings dates exist only for today's list, so its past record stays hindsight-based.

  python3 pit.py build REPO     -> data/library/daily_pit.json, daily_pit_2x.json, data/pit/report.json (run once)
"""
import csv, gzip, io, json, os, shutil, statistics as st, sys, tempfile, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SLEEVES = ("L6 Bollinger reversion", "L7 Donchian trend", "L8 Momentum top 8", "L15 Market-neutral momentum")
TOP, LOOK = 100, 60


def load(repo):
    P = os.path.join(repo, "data", "pit")
    mem = sorted((r[0], set(t.strip() for t in r[1].split(",") if t.strip()))
                 for r in list(csv.reader(io.StringIO(gzip.open(os.path.join(P, "sp500_members.csv.gz"), "rt").read())))[1:] if len(r) >= 2)
    bars = {}
    with gzip.open(os.path.join(P, "bars_1d.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            bars.setdefault(r["sym"], []).append((r["date"], float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"])))
    return mem, bars


def monthly_lists(mem, bars, cal):
    """{YYYY-MM: [100 symbols]} from data strictly before the month."""
    dv = {s: {d: c * v for d, o, h, l, c, v in rows} for s, rows in bars.items()}
    out = {}
    for m in sorted({d[:7] for d in cal}):
        before = [d for d in cal if d < m + "-01"][-LOOK:]
        if len(before) < 20: continue
        asof = before[-1]; members = next((ts for d, ts in reversed(mem) if d <= asof), set())
        sc = []
        for s in members:
            x = [dv[s][d] for d in before if s in dv and d in dv[s]]
            if len(x) >= 20: sc.append((st.median(x), s))
        out[m] = [s for _, s in sorted(sc, reverse=True)[:TOP]]
    return out


def build(repo, end=None, mode="top100", write=False):
    """mode "top100": monthly 100 most-traded members (the stand-in for the S&P 100).
    mode "sp500_pit": every S&P 500 member on the date. mode "sp500_today": today's S&P 500 list applied to the whole
    past (the hindsight version of the same universe). The last two differ ONLY in hindsight, so their gap measures
    the survivorship flattery directly."""
    import tcal, bisect
    end = end or (tcal.START - dt.timedelta(days=1)).isoformat()
    mem, bars = load(repo)
    cal = sorted({d for d, *_ in bars.get("SPY", [])} or {d for rows in bars.values() for d, *_ in rows})
    cal = [d for d in cal if d <= end]
    lists = monthly_lists(mem, bars, cal)
    if mode == "top100": univ = sorted({s for v in lists.values() for s in v})
    elif mode == "sp500_today": univ = sorted(s for s in mem[-1][1] if s in bars)
    else: univ = sorted(s for s in {t for d, ts in mem if d >= "2023-06-01" for t in ts} | mem[-1][1] if s in bars)
    mdates = [d for d, _ in mem]
    tmp = tempfile.mkdtemp(prefix="pit_")
    try:
        os.makedirs(os.path.join(tmp, "data", "bars", "1d")); shutil.copytree(os.path.join(repo, "scripts"), os.path.join(tmp, "scripts"))
        U = json.load(open(os.path.join(repo, "data", "universe.json")))
        etfs = [e for e in U["etfs"]]
        # ETFs and indices come from the normal store with their corporate actions (the library adjusts them itself)
        os.makedirs(os.path.join(tmp, "data", "corp"))
        for e in etfs:
            for sub, ext in (("bars/1d", ".jsonl"), ("corp", ".json")):
                src = os.path.join(repo, "data", sub, e + ext)
                if os.path.exists(src): shutil.copy(src, os.path.join(tmp, "data", sub, e + ext))
        padded = []
        for s in univ:
            rows = [r for r in bars[s] if r[0] <= end]
            if not rows: continue
            have = {r[0] for r in rows}; last = rows[-1]
            tail = [d for d in cal if d > last[0]]
            if tail:      # prices stopped: carry flat at the last close so open positions close there
                padded.append(s); rows += [(d, last[4], last[4], last[4], last[4], 0.0) for d in tail]
            with open(os.path.join(tmp, "data", "bars", "1d", s + ".jsonl"), "w") as w:
                for d, o, h, l, c, v in rows:
                    t = int(dt.datetime.fromisoformat(d + "T12:00:00+00:00").timestamp())
                    w.write(json.dumps({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}) + "\n")
        json.dump({"watchlist": [], "control": [], "etfs": etfs, "universe": univ, "note": "temporary point-in-time universe"},
                  open(os.path.join(tmp, "data", "universe.json"), "w"))
        import library
        stock = set(univ); member = {m: set(v) for m, v in lists.items()}
        if mode == "top100": library.ELIGIBLE = lambda s, d: s not in stock or s in member.get(d[:7], ())
        elif mode == "sp500_today": library.ELIGIBLE = lambda s, d: True
        else: library.ELIGIBLE = lambda s, d: s not in stock or s in mem[max(0, bisect.bisect_right(mdates, d) - 1)][1]
        res = {}
        for mult, fname in ((1.0, "daily_pit.json"), (2.0, "daily_pit_2x.json")):
            books = library.reprice(tmp, library.build(tmp, end), mult)
            res[fname] = {b.name: {d: round(v, 5) for d, v in sorted(b.daily.items()) if d <= end} for b in books if b.name in SLEEVES}
            res[fname + ":trades"] = {b.name: sum(1 for t in b.trades if t["status"] == "closed") for b in books if b.name in SLEEVES}
        library.ELIGIBLE = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    L = os.path.join(repo, "data", "library")
    if write:
        for fname in ("daily_pit.json", "daily_pit_2x.json"):
            json.dump(res[fname], open(os.path.join(L, fname), "w"), separators=(",", ":"))
    if mode != "top100": return {"mode": mode, "symbols": len(univ), "series": res["daily_pit.json"], "trades": res["daily_pit.json:trades"], "carried_flat": padded}
    hind = json.load(open(os.path.join(L, "daily.json"))); today = set(U.get("universe", [])) | set(U["watchlist"]) | set(U["control"])
    def stat(x):
        if len(x) < 2: return {"days": len(x)}
        m, sd = st.mean(x), st.pstdev(x)
        return {"days": len(x), "total_pct": round(sum(x), 2), "mean_daily_pct": round(m, 4), "sharpe": round(m / sd * 252 ** 0.5, 2) if sd else None}
    cmp_ = {}
    for k in SLEEVES:
        p = res["daily_pit.json"].get(k, {}); h = {d: v for d, v in hind.get(k, {}).items() if d <= end}
        common = sorted(set(p) & set(h))
        cmp_[k] = {"hindsight_list": stat([h[d] for d in common]), "point_in_time_list": stat([p[d] for d in common]),
                   "closed_trades_pit": res["daily_pit.json:trades"].get(k)}
    months = sorted(lists); last = set(lists[months[-1]]) if months else set()
    rep = {"built": dt.date.today().isoformat(), "window": [cal[0], end], "months": len(months), "list_size": TOP,
           "symbols_used": len(univ), "symbols_carried_flat_after_prices_stopped": padded,
           "ever_listed_but_not_in_todays_list": sorted(set(univ) - today),
           "overlap_of_latest_list_with_todays_list": len(last & today), "comparison_before_test": cmp_,
           "limits": __doc__.split("Limits, to be stated wherever this is reported:")[1].split("  python3")[0].strip()}
    # The clean measurement: the same wide universe with and without hindsight.
    A = build(repo, end, "sp500_pit"); B = build(repo, end, "sp500_today"); surv = {}
    for k in SLEEVES:
        a, b = A["series"].get(k, {}), B["series"].get(k, {}); common = sorted(set(a) & set(b))
        pa, pb = stat([a[d] for d in common]), stat([b[d] for d in common])
        surv[k] = {"todays_list_hindsight": pb, "members_at_the_time": pa,
                   "flattery_pct_points_total": round(pb.get("total_pct", 0) - pa.get("total_pct", 0), 2),
                   "flattery_mean_daily_pct": round(pb.get("mean_daily_pct", 0) - pa.get("mean_daily_pct", 0), 4)}
    rep["survivorship_measured_on_sp500"] = {"symbols_pit": A["symbols"], "symbols_today": B["symbols"], "carried_flat": A["carried_flat"], "by_sleeve": surv}
    json.dump(rep, open(os.path.join(repo, "data", "pit", "report.json"), "w"), indent=1)
    return rep


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] != "build": print(__doc__); sys.exit(2)
    print(json.dumps(build(a[1]), indent=1))
