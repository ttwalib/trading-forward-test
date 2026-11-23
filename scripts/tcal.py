"""Test calendar: NYSE trading days, half days, weekly option expiries and test phases for the forward test.

  python3 tcal.py today [YYYY-MM-DD]      -> JSON facts for that New York date (default: today in New York)
  python3 tcal.py days FROM TO            -> list of stock trading days (full days only) in [FROM, TO]
  python3 tcal.py weeks                   -> the weekly-option schedule (entry days -> expiry)

Library: from tcal import info, trading_days, is_trading, is_half, weekly_expiry, PHASES

Test window (extended to six months on 2026-11-21 by the owner, before any data in the verdict window):
2026-11-16 .. 2027-05-14 for stocks/options, crypto through 2027-05-16, settlement-only runs for open option
positions through 2027-05-21. INTERIM report 2027-02-16 (data to 2027-02-12, as first planned); FINAL report 2027-05-18.
Phases: "train" 2026-11-16 .. 2027-01-29 (tuning, learning and ML training allowed);
        "holdout" 2027-02-01 .. 2027-05-14 (FROZEN: no retuning, no challenger promotion, no new learning proposals,
        ML models frozen as of 2027-01-29; every change made during the test is judged on these 73 trading days).
Verdict window: 2026-12-07 .. 2027-05-14 (it was 2026-12-07 .. 2027-02-12 until 2026-11-21; that shorter span is now
the interim reading). There is no further extension: the six-week extension rule of 2026-11-20 is replaced by this. allocator.py and library.py are
frozen from 2026-12-07 (hash recorded in ops/freeze.json); the allocator sets each day's weights from data up to the day
before, so every day from the freeze on is out-of-sample for the AI portfolio verdict. Feb 1-12 stays the holdout for
ML models, champion/challenger tuning and strategy-lab additions.
No new stock or option trades on half days (2026-11-27, 2026-12-24); open positions are still marked and settled.
"""
import json, sys, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
START, END = dt.date(2026, 11, 16), dt.date(2027, 5, 14)
INTERIM_END = dt.date(2027, 2, 12)     # the interim report (2027-02-16) reads the verdict window up to here
CRYPTO_END, SETTLE_END = dt.date(2027, 5, 16), dt.date(2027, 5, 21)
FINAL_REPORT = dt.date(2027, 5, 18)
HOLDOUT_START = dt.date(2027, 2, 1)   # since 2026-11-23 only the start of the SECOND-HALF reading: nothing freezes here
SECOND_HALF = HOLDOUT_START
V2_START = dt.date(2026, 11, 20)   # first full day of the extended setup (ledger, control list, ML, live runs)
ALLOC_FREEZE = dt.date(2026, 12, 7)   # allocator + library code frozen from here; Dec 7 .. END is the verdict window
VERDICT = (ALLOC_FREEZE, END)
HOLIDAYS = {dt.date(2026, 11, 26), dt.date(2026, 12, 25), dt.date(2027, 1, 1), dt.date(2027, 1, 18), dt.date(2027, 2, 15),
            dt.date(2027, 3, 26)}      # Good Friday 2027; the next NYSE holiday, Memorial Day (May 31), is after the test
HALF = {dt.date(2026, 11, 27): "13:00", dt.date(2026, 12, 24): "13:00"}
# AUTONOMY RESTRUCTURE (owner decision 2026-11-23, runbook item 34): the AI keeps learning to the end of the test, so
# there is no frozen holdout any more. Validity comes from scoring every decision only on days after it was made
# ("freeze the referee, not the player"): the scoring code is frozen from the window's start, the AI's strategies,
# picks, playbook and models are not. The whole test is one phase, "train"; reports still show the second half
# (from SECOND_HALF) separately as a robustness reading.
PHASES = {"train": (START, END)}


def D(s): return s if isinstance(s, dt.date) else dt.date.fromisoformat(s)
def is_open(d): d = D(d); return d.weekday() < 5 and d not in HOLIDAYS
def is_half(d): return D(d) in HALF
def is_trading(d): d = D(d); return is_open(d) and d not in HALF          # full trading day (new trades allowed)


def trading_days(a, b):
    a, b = D(a), D(b); out = []
    while a <= b:
        if is_trading(a): out.append(a.isoformat())
        a += dt.timedelta(days=1)
    return out


def week_days(d):
    d = D(d); mon = d - dt.timedelta(days=d.weekday())
    return [mon + dt.timedelta(days=i) for i in range(5)]


def weekly_expiry(d):
    """Last open session (full or half day) of d's week: the weekly option expiry used by W1-W4."""
    opens = [x for x in week_days(d) if is_open(x)]
    return opens[-1] if opens else None


def entry_days(d):
    """Weekly W1-W3 entry days of d's week: the first full trading day on/after Monday and on/after Wednesday."""
    full = [x for x in week_days(d) if is_trading(x)]
    out = []
    for wd in (0, 2):
        c = [x for x in full if x.weekday() >= wd]
        if c and c[0] not in out and c[0] < weekly_expiry(d): out.append(c[0])
    return out


def phase(d):
    d = D(d)
    for k, (a, b) in PHASES.items():
        if a <= d <= b: return k
    return "after" if d > END else "before"


def info(d=None):
    d = D(d) if d else dt.datetime.now(NY).date()
    exp = weekly_expiry(d); ent = entry_days(d)
    last_settle = {"close": HALF.get(exp, "16:00")} if exp else {}
    return {"date": d.isoformat(), "weekday": d.strftime("%a"),
            "stock_test_active": START <= d <= END, "crypto_test_active": START <= d <= CRYPTO_END,
            "settle_only_window": END < d <= SETTLE_END,
            "open_session": is_open(d), "full_trading_day": is_trading(d) and START <= d <= END, "half_day": is_half(d) and START <= d <= END,
            "close_time": HALF.get(d, "16:00") if is_open(d) else None,
            "phase": phase(d), "frozen": False,            # no learning freeze since 2026-11-23 (item 34)
            "allocator_frozen": d >= ALLOC_FREEZE, "verdict_window": ALLOC_FREEZE <= d <= END,
            "interim_end": INTERIM_END.isoformat(), "test_end": END.isoformat(), "final_report": FINAL_REPORT.isoformat(),
            "weekly_expiry": exp.isoformat().replace("-", "") if exp else None, "weekly_expiry_close": last_settle.get("close"),
            "weekly_entry_day": d in ent and START <= d <= END,
            "week_entry_days": [x.isoformat() for x in ent],
            "is_friday_report_day": d.weekday() == 4 and START <= d <= END,
            "week_index": ((d - START).days // 7) + 1 if d >= START else 0}


def main():
    a = sys.argv[1:]
    if a[0] == "today": print(json.dumps(info(a[1] if len(a) > 1 else None)))
    elif len(a[0]) == 10 and a[0][4] == "-": print(json.dumps(info(a[0])))   # "tcal.py YYYY-MM-DD" = "today YYYY-MM-DD"
    elif a[0] == "days": print(json.dumps(trading_days(a[1], a[2])))
    elif a[0] == "weeks":
        d, out = START, []
        while d <= END:
            for e in entry_days(d): out.append({"entry": e.isoformat(), "expiry": weekly_expiry(d).isoformat()})
            d += dt.timedelta(days=7)
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
