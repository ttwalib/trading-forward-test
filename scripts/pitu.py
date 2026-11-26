"""Point-in-time universe for research (2026-11-23, owner: "proceed").

Today's S&P 100 is a list drawn up with hindsight: it holds the companies that grew enough to be on it now, so any
backtest on it looks better than it would have at the time. This module gives, for any date, the stocks that WOULD
have been chosen then: the 100 S&P 500 members (as of that date) with the highest median daily dollar volume over the
60 trading days before that month (the same rule as scripts/pit.py, which uses nothing from the month itself).

Use it in the lab for ANY idea on a stock universe (daily or 5-minute bars), and in the report-only wide intraday run:
a stock counts on a date only if it is in that month's list.

Limits (state them where results are reported): the list is a stand-in for the S&P 100, not the index; the membership
file is community-maintained; 5-minute bars exist only for today's names, so a departed company that was on the list
at the time has no intraday bars and simply drops out (some bias remains for intraday ideas); before the first month
of point-in-time data every stock is excluded rather than assumed.

  python3 pitu.py month REPO YYYY-MM     -> the list for that month
  python3 pitu.py coverage REPO          -> months covered and list sizes
  Python: pitu.lists(repo) -> {YYYY-MM: set}; pitu.member(lists, sym, "YYYY-MM-DD") -> bool
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pit

CACHE = os.path.join("data", "pit", "monthly_top100.json")


def lists(repo, rebuild=False):
    f = os.path.join(repo, CACHE)
    if os.path.exists(f) and not rebuild:
        return {m: set(v) for m, v in json.load(open(f)).items()}
    mem, bars = pit.load(repo)
    try:                     # warm-up bars 2014-07..2015-12 (scripts/warmup.py, build_todo item 13): look-back only
        import warmup; warmup.merge_into(bars, repo)
    except ImportError: pass
    cal = sorted({d for rows in bars.values() for d, *_ in rows})
    L = pit.monthly_lists(mem, bars, cal)
    json.dump({m: sorted(v) for m, v in L.items()}, open(f, "w"), separators=(",", ":"))
    return {m: set(v) for m, v in L.items()}


def member(L, sym, day):
    """True only if sym was on the list for day's month. Months after the last point-in-time month use the last list
    (the forward test's own period: the live lists were fixed before any result)."""
    m = day[:7]
    if m in L: return sym in L[m]
    last = max(L) if L else None
    return bool(last and m > last and sym in L[last])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "month": print(json.dumps(sorted(lists(a[1]).get(a[2], set()))))
    elif a and a[0] == "coverage":
        L = lists(a[1], rebuild=True); print(json.dumps({"months": len(L), "first": min(L), "last": max(L),
                                                         "sizes": sorted({len(v) for v in L.values()})}))
    else: print(__doc__)
