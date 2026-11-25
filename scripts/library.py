"""Strategy library: widely used, documented strategies run on the bars stored in the repo (no AI per trade).

  python3 library.py REPO [DAY]   -> rebuilds data/ledger/Library.jsonl (every trade, backtest + forward) and
                                     data/library/daily.json ({strategy: {date: sleeve return %}}), prints a summary
                                     plus "new_closed" (closed forward trades not yet reported) for the sheet.

Conventions (identical for every strategy, so they are comparable):
- No look-ahead. Daily strategies decide on a close and trade at the NEXT open; exits decided on a close also fill
  at the next open. Intraday strategies use only bars that closed before the entry bar ends.
- Costs per side (revised 2026-11-19): the larger of the floor (0.05% daily stocks/ETFs, 0.03% intraday, 0.01% SPY)
  and a per-symbol estimate: median observed half-spread from midday IBKR snapshots (data/snap) + 0.01% slippage,
  else (stocks only) half of the Corwin-Schultz high/low spread estimate over the prior 20 days (capped at 0.15%). Estimates use
  only data before the trade date. `--cost-mult 2` re-runs everything at double costs into daily_2x.json (stress test;
  a strategy that only works at 1x is fragile).
- Prices: daily bars are total-return adjusted (dividends; splits if still raw) from data/corp (corp.py), so holding
  strategies and SPY buy-and-hold are compared on the same footing.
- Survivorship: the universe is today's S&P 100, so backtest results overstate history; the allocator haircuts
  backtest returns by 50% and caps their weight (see allocator.py).
- Each strategy is a "sleeve" with K equal slots (1/K of the sleeve each). Sleeve return per day = sum over open
  positions of (position return that day) / K, marked to market on closes. Unused slots are cash (0%).
- Trades entered before the test start (2026-11-16) are BACKTEST (phase "before"): they seed the allocator's priors
  but never count in the test statistics.
- Short legs (gap fade, pairs) are simulated only; nothing is ever traded. Pairs short legs pay a borrow fee of
  BORROW_PCT_YR (0.5%/year) on the short notional for every day held (added 2026-11-19).
- Implementable intraday fills (added 2026-11-19, see fills.py): an intraday signal on a bar's close fills at the
  OPEN of the bar FILL_LAG bars after the next one (default 1 = about 5 minutes after the signal bar closed), not at
  the signal close a real engine could not have traded. Exits are scanned from the entry bar. `--fill-lag 0` re-runs
  the old ideal fills into daily_ideal.json for comparison only. L1 trades at scheduled times and is unaffected.
- Universe (widened 2026-11-19, before the freeze): L6, L7, L8 and L10 use the whole static S&P 100 snapshot in
  universe.json ("universe", minus GOOG, a duplicate share class) instead of the 44 watchlist + control stocks, for
  more independent trades. The intraday strategies stay on the 44 stocks that have 5-minute data.

Strategies (name: rule; universe; slots K):
 L1 SPY intraday momentum: sign of SPY's first-30-minute return (prior close to 10:00) held from 15:30 to 16:00
    (Gao, Han, Li, Zhou 2018, "Market intraday momentum"); SPY; K=1.
 L2 VWAP pullback: stock up >= 1% on the day, a bar between 10:30 and 14:30 dips to VWAP and closes back above it ->
    long at that close, stop = min(bar low, VWAP - 0.3%), target 2R, flat 15:55; watchlist + control; K=5.
 L3 Gap and go: gap >= +2% and the first 5-minute bar closes green -> long at 09:35, stop = first bar low, flat 15:55;
    watchlist + control; K=5.
 L4 Gap fade: gap +0.5% to +2% and the first bar closes red -> short at 09:35, stop = first bar high, target = prior
    close (gap fill), flat 15:55; watchlist + control; K=5.
 L5 RSI(2) pullback (Connors): close > SMA200 and RSI(2) < 10 -> buy; exit when close > SMA5 or after 10 days;
    SPY, QQQ, IWM, DIA; K=4.
 L6 Bollinger reversion: close < lower band (20, 2) and close > SMA200 -> buy; exit at close >= SMA20 or after 10 days;
    S&P 100; K=10 (most oversold first).
 L7 Donchian trend (Turtle-style): close > prior 20-day high -> buy; exit on close < prior 10-day low or after 40 days;
    S&P 100 + ETFs; K=10 (strongest breakout first).
 L8 Cross-sectional momentum: each Friday hold the top 8 of the S&P 100 stocks by 126-day return skipping the last 5 days
    (Jegadeesh-Titman style, weekly rebalance); K=8.
 L9 Sector rotation: each Friday hold the top 3 of the 11 sector ETFs by 63-day return when SPY > SMA200, else TLT
    (Faber-style dual momentum); K=3.
 L10 Earnings drift (PEAD): within 3 days of an earnings event (data/events/earnings.jsonl from IBKR earnings
    insights; used only if KNOWN on the decision date; after-close reports count from the next session; legacy
    "earnings SYM" rows in the Events ledger still count),
    a gap >= +3% that closes in the upper half of the day's range -> buy, hold 10 days; S&P 100 (names with earnings
    data); K=5.
 L11 SPY overnight: hold SPY from each close to the next open (documented overnight drift); K=1.
 L12 Turn of month: hold SPY from the close 4 trading days before month end to the close of the 3rd trading day of
    the next month (Lakonishok-Smidt / Ariel effect); K=1.
 L13 Pairs reversion: log price ratio z-score (60 days) beyond +/-2 -> long the cheap leg, short the rich leg; exit at
    z crossing 0 or after 20 days; pairs JPM/BAC, GS/MS, XOM/XLE, PEP/XLP, T/TMUS, GOOGL/META; K=6.
Hedged sleeves (added 2026-11-20, before the freeze): the allocator is always fully invested, so it needs sleeves
that can make money, or lose less, when the market falls. All three are conventional and simulated only.
 L14 Opening-range breakdown (short): the mirror image of baseline A on the 44 stocks: first 15 minutes set the range;
    a 5-minute close below the range low (signal bars ending 09:50-15:30) -> short; stop = range midpoint, target 2R,
    flat at 15:55; first 5 signals of the day; implementable fill; K=5.
 L15 Market-neutral momentum: each Friday long the top 8 and short the bottom 8 of the S&P 100 by the L8 score
    (126-day return skipping the last 5 days), entered at Monday's open; shorts pay the borrow fee; K=16.
 L16 SPY trend short: when SPY closes below its 50-day average and that average is lower than 5 days earlier, be
    short SPY from the next open; cover at the open after the condition ends; borrow fee; K=1.
Multi-asset sleeve (added 2026-11-20, before the freeze): the other sleeves are all US equities, so they tend to fall
together. This one holds assets that follow different cycles.
 L17 Multi-asset trend: each Friday, of TLT, IEF, GLD, DBC, EFA, EEM hold every one whose close is above its 200-day
    average (one fifth of the sleeve each, at most 5, strongest distance above the average first), entered at Monday's
    open; an asset below its average is sold and its share stays in cash inside the sleeve; K=5.
"""
import json, os, sys, math, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal, ledger, corp
NY = ZoneInfo("America/New_York")
START = tcal.START.isoformat()
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
INDEX_ETFS = ["SPY", "QQQ", "IWM", "DIA"]
MULTI = ["TLT", "IEF", "GLD", "DBC", "EFA", "EEM"]
ETFS = set(SECTORS + INDEX_ETFS + ["TLT", "GLD"])
PAIRS = [("JPM", "BAC"), ("GS", "MS"), ("XOM", "XLE"), ("PEP", "XLP"), ("T", "TMUS"), ("GOOGL", "META")]
C_DAY, C_INTRA, C_SPY = 0.05, 0.03, 0.01
BORROW_PCT_YR = 0.5
_BORROW = None


def borrow_fee(repo, sym, day):
    """Yearly stock-loan fee in % for a short in `sym` on `day`: the latest data/borrow file dated on or before `day`
    (Interactive Brokers' public short-stock file, stored nightly from 2026-11-20), floor 0.25; the flat BORROW_PCT_YR
    for earlier days, missing symbols or when no file exists. Point-in-time: a fee is never applied to days before
    its file."""
    global _BORROW
    if _BORROW is None:
        import glob
        _BORROW = sorted((os.path.basename(f)[:10], f) for f in glob.glob(os.path.join(repo, "data", "borrow", "*.json")))
        _BORROW = [(d, None, f) for d, f in _BORROW]
    best = None
    for k, (d, rows, f) in enumerate(_BORROW):
        if d <= day: best = k
    if best is None: return BORROW_PCT_YR
    d, rows, f = _BORROW[best]
    if rows is None:
        try: rows = json.load(open(f)).get("rows", {})
        except Exception: rows = {}
        _BORROW[best] = (d, rows, f)
    r = rows.get(sym)
    return max(0.25, float(r["fee"])) if r and r.get("fee") is not None else BORROW_PCT_YR
FILL_LAG = 1          # implementable fills; 0 = old ideal fills (comparison run only)
SKIPPED = {}          # signals dropped because the expected fill bar was missing, per strategy (review N11, report only)


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def daily(repo, sym):
    """[(date, o, h, l, c)] from data/bars/1d, else built from 5m regular-session bars."""
    rows = {}
    for b in jl(os.path.join(repo, "data", "bars", "1d", sym + ".jsonl")):
        rows[dt.datetime.fromtimestamp(b["t"], NY).date().isoformat()] = (b["o"], b["h"], b["l"], b["c"])
    agg = {}
    for b in jl(os.path.join(repo, "data", "bars", "5m", sym + ".jsonl")):
        t = dt.datetime.fromtimestamp(b["t"], NY)
        if not ("09:30" <= t.strftime("%H:%M") < "16:00"): continue
        d = t.date().isoformat()
        if d not in agg: agg[d] = [b["o"], b["h"], b["l"], b["c"]]
        else:
            a = agg[d]; a[1] = max(a[1], b["h"]); a[2] = min(a[2], b["l"]); a[3] = b["c"]
    for d, a in agg.items(): rows.setdefault(d, tuple(a))
    return corp.tr_adjust(repo, sym, sorted((d,) + tuple(v) for d, v in rows.items()))


def intraday(repo, sym):
    """{date: [(hhmm, o, h, l, c, v)]} regular session 5m bars."""
    out = {}
    for b in jl(os.path.join(repo, "data", "bars", "5m", sym + ".jsonl")):
        t = dt.datetime.fromtimestamp(b["t"], NY); hm = t.strftime("%H:%M")
        if "09:30" <= hm < "16:00": out.setdefault(t.date().isoformat(), []).append((hm, b["o"], b["h"], b["l"], b["c"], b.get("v", 0)))
    for v in out.values(): v.sort()
    return out


def _plus(hhmm, minutes):
    h, m = map(int, hhmm.split(":")); x = h * 60 + m + minutes
    return "%02d:%02d" % (x // 60, x % 60)


def sma(xs, n): return sum(xs[-n:]) / n if len(xs) >= n else None


def rsi(cl, n=2):
    if len(cl) < n + 20: return None
    g = l = 0.0
    for i in range(len(cl) - n - 19, len(cl)):  # Wilder smoothing from a 20-bar warm-up
        ch = cl[i] - cl[i - 1]; up, dn = max(ch, 0), max(-ch, 0)
        g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


class Book:
    """Trades + daily sleeve returns for one strategy."""
    def __init__(self, name, K):
        self.name, self.K, self.trades, self.daily = name, K, [], {}

    def add_day(self, d, r):
        self.daily[d] = self.daily.get(d, 0.0) + r / self.K

    def trade(self, sym, side, ed, et, ep, xd, xt, xp, cost, status="closed"):
        g = (xp / ep - 1) * (1 if side == "long" else -1) * 100
        self.trades.append({"strategy": self.name, "symbol": sym, "side": side, "entry_date": ed, "entry_time": et,
                            "entry": round(ep, 4), "exit_date": xd, "exit_time": xt, "exit": round(xp, 4),
                            "ret_pct": round(g - (2 * cost if status == "closed" else cost), 4), "status": status,
                            "phase": tcal.phase(ed) if ed >= START else "before", "cost_side": cost})


def run_daily(name, K, data, cal, signal, exit_rule, max_hold, cost=C_DAY):
    """Generic next-open engine. data: {sym: {date: (o,h,l,c)}} plus per-symbol close lists by index."""
    bk = Book(name, K); open_pos = {}; pending_entries = []; pending_exits = set()
    idx = {s: {d: i for i, (d, *_rest) in enumerate(rows)} for s, rows in data.items()}
    for di, d in enumerate(cal):
        # 1) exits decided yesterday fill at today's open
        for s in list(pending_exits):
            p = open_pos.pop(s, None); pending_exits.discard(s)
            if not p or d not in idx[s]: continue
            o = data[s][idx[s][d]][1]
            bk.add_day(d, ((o / p["mark"]) - 1) * 100 * p["sgn"] - cost)
            bk.trade(s, p["side"], p["ed"], "open", p["ep"], d, "open", o, cost)
        # 2) entries decided yesterday fill at today's open
        for s, side in pending_entries:
            if s in open_pos or d not in idx[s] or len(open_pos) >= K: continue
            o = data[s][idx[s][d]][1]
            open_pos[s] = {"side": side, "sgn": 1 if side == "long" else -1, "ep": o, "mark": o, "ed": d, "held": 0}
            bk.add_day(d, -cost)
        pending_entries = []
        # 3) mark to close, decide exits for tomorrow
        for s, p in open_pos.items():
            if d not in idx[s]: continue
            i = idx[s][d]; c = data[s][i][4]
            bk.add_day(d, ((c / p["mark"]) - 1) * 100 * p["sgn"]); p["mark"] = c; p["held"] += 1
            if exit_rule(s, i, p) or p["held"] >= max_hold: pending_exits.add(s)
        # 4) signals on today's close for tomorrow's open (strongest first)
        cands = []
        for s in data:
            if s in open_pos or d not in idx[s]: continue
            sc = signal(s, idx[s][d])
            if sc is not None: cands.append((sc, s))
        free = K - (len(open_pos) - len(pending_exits))
        for sc, s in sorted(cands, reverse=True)[:max(0, free)]: pending_entries.append((s, "long"))
        bk.daily.setdefault(d, 0.0)
    for s, p in open_pos.items():
        bk.trade(s, p["side"], p["ed"], "open", p["ep"], cal[-1], "mark", p["mark"], cost, status="open")
    return bk


# Point-in-time hook (added 2026-11-21): None in every normal run, so nothing changes there. scripts/pit.py sets it to
# a function (symbol, date) -> bool for its one-off backtest on the point-in-time universe; a stock that was not in
# that month's list gives no entry signal and no rotation score (open positions still exit by their own rules).
ELIGIBLE = None


def closes(rows, i, n): return [r[4] for r in rows[max(0, i - n + 1):i + 1]]


def build(repo, day=None):
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    stocks = U["watchlist"] + U["control"]
    lib = sorted(set(stocks) | {s for s in U.get("universe", []) if s != "GOOG"})
    D = {s: daily(repo, s) for s in set(lib + SECTORS + INDEX_ETFS + MULTI + [x for p in PAIRS for x in p])}
    D = {s: r for s, r in D.items() if r}
    cal = [r[0] for r in D.get("SPY", [])]
    if day: cal = [d for d in cal if d <= day]
    books = []
    if len(cal) >= 30:
        def sub(syms): return {s: D[s] for s in syms if s in D and len(D[s]) >= 30}

        # L5 RSI(2)
        dd = sub(INDEX_ETFS)
        def sig5(s, i):
            cl = closes(dd[s], i, 230); m = sma(cl, 200); r = rsi(cl)
            return (10 - r) if m and r is not None and cl[-1] > m and r < 10 else None
        books.append(run_daily("L5 RSI(2) pullback", 4, dd, cal, sig5, lambda s, i, p: (lambda cl: cl[-1] > sma(cl, 5))(closes(dd[s], i, 5)), 10))
        # L6 Bollinger
        dd6 = sub(lib)
        def sig6(s, i):
            cl = closes(dd6[s], i, 210)
            if len(cl) < 200 or (ELIGIBLE and not ELIGIBLE(s, dd6[s][i][0])): return None
            m20 = sma(cl, 20); sd = (sum((x - m20) ** 2 for x in cl[-20:]) / 20) ** 0.5
            return (m20 - 2 * sd - cl[-1]) / m20 if cl[-1] < m20 - 2 * sd and cl[-1] > sma(cl, 200) else None
        books.append(run_daily("L6 Bollinger reversion", 10, dd6, cal, sig6, lambda s, i, p: closes(dd6[s], i, 1)[-1] >= sma(closes(dd6[s], i, 20), 20), 10))
        # L7 Donchian
        dd7 = sub(lib + SECTORS + ["QQQ", "IWM", "DIA", "TLT", "GLD"])
        def sig7(s, i):
            rows = dd7[s]
            if i < 21 or (ELIGIBLE and not ELIGIBLE(s, rows[i][0])): return None
            hi = max(r[2] for r in rows[i - 20:i]); c = rows[i][4]
            return c / hi - 1 if c > hi else None
        def ex7(s, i, p):
            rows = dd7[s]
            return i >= 11 and rows[i][4] < min(r[3] for r in rows[i - 10:i])
        books.append(run_daily("L7 Donchian trend", 10, dd7, cal, sig7, ex7, 40))
        # L10 PEAD
        ev = {}   # {SYM: [(event_day, known_at)]}
        for s_, lst in corp.earnings_known_by(repo).items():
            if s_ in lib: ev.setdefault(s_, []).extend(lst)
        for e in ledger.load(repo, "Events"):   # legacy agent-logged rows: known on the day they were logged
            txt = str(e.get("event", "")).upper()
            if "EARNINGS" in txt:
                for s_ in lib:
                    if s_ in txt.replace(",", " ").split(): ev.setdefault(s_, []).append((str(e.get("date"))[:10], str(e.get("date"))[:10]))
        dd10 = sub([s for s in lib if s in ev])
        def sig10(s, i):
            rows = dd10[s]
            if i < 1: return None
            d = rows[i][0]
            if not any(k <= d and 0 <= (dt.date.fromisoformat(d) - dt.date.fromisoformat(x)).days <= 3 for x, k in ev[s]): return None
            o, h, l, c = rows[i][1:5]; gap = o / rows[i - 1][4] - 1
            return gap if gap >= 0.03 and h > l and (c - l) / (h - l) >= 0.5 else None
        if dd10: books.append(run_daily("L10 Earnings drift", 5, dd10, cal, sig10, lambda s, i, p: False, 10))

        # L8 / L9 weekly rotations
        def rotation(name, K, univ, score, fallback=None, allow_empty=False):
            bk = Book(name, K); hold = {}; nxt = None
            idx = {s: {r[0]: j for j, r in enumerate(D[s])} for s in univ + ([fallback] if fallback else []) if s in D}
            for k, d in enumerate(cal):
                if nxt is not None:  # rebalance at today's open
                    for s in list(hold):
                        if s not in nxt and d in idx.get(s, {}):
                            o = D[s][idx[s][d]][1]; p = hold.pop(s)
                            bk.add_day(d, (o / p["mark"] - 1) * 100 - C_DAY); bk.trade(s, "long", p["ed"], "open", p["ep"], d, "open", o, C_DAY)
                    for s in nxt:
                        if s not in hold and d in idx.get(s, {}):
                            o = D[s][idx[s][d]][1]; hold[s] = {"ep": o, "mark": o, "ed": d}; bk.add_day(d, -C_DAY)
                    nxt = None
                for s, p in hold.items():
                    if d in idx.get(s, {}):
                        c = D[s][idx[s][d]][4]; bk.add_day(d, (c / p["mark"] - 1) * 100); p["mark"] = c
                bk.daily.setdefault(d, 0.0)
                last_of_week = k + 1 == len(cal) or dt.date.fromisoformat(cal[k + 1]).isocalendar()[1] != dt.date.fromisoformat(d).isocalendar()[1]
                if last_of_week and k + 1 < len(cal):
                    sc = []
                    for s in univ:
                        if s in idx and d in idx[s]:
                            v = score(s, idx[s][d])
                            if v is not None: sc.append((v, s))
                    pick = [s for _, s in sorted(sc, reverse=True)[:K]]
                    if fallback:
                        sp = closes(D["SPY"], k, 200)
                        if len(sp) >= 200 and sp[-1] < sma(sp, 200): pick = [fallback]
                    if pick or allow_empty: nxt = set(pick)
            for s, p in hold.items(): bk.trade(s, "long", p["ed"], "open", p["ep"], cal[-1], "mark", p["mark"], C_DAY, "open")
            return bk
        def mom(s, i):
            rows = D[s]
            if ELIGIBLE and not ELIGIBLE(s, rows[i][0]): return None
            return rows[i - 5][4] / rows[i - 131][4] - 1 if i >= 131 else None
        books.append(rotation("L8 Momentum top 8", 8, [s for s in lib if s in D], mom))
        def sec(s, i):
            rows = D[s]
            return rows[i][4] / rows[i - 63][4] - 1 if i >= 63 else None
        books.append(rotation("L9 Sector rotation", 3, [s for s in SECTORS if s in D], sec, "TLT"))

        # L17 multi-asset trend: hold each asset only while it is above its 200-day average
        def trend17(s, i):
            cl = closes(D[s], i, 200)
            return cl[-1] / sma(cl, 200) - 1 if len(cl) >= 200 and cl[-1] > sma(cl, 200) else None
        if sum(1 for s in MULTI if s in D and len(D[s]) >= 200) >= 4:
            books.append(rotation("L17 Multi-asset trend", 5, [s for s in MULTI if s in D], trend17, None, True))

        # L15 market-neutral momentum: long the top K, short the bottom K, rebalanced weekly
        def ls_rotation(name, K, univ, score):
            bk = Book(name, 2 * K); hold = {}; nxt = None
            idx = {s: {r[0]: j for j, r in enumerate(D[s])} for s in univ if s in D}
            for k, d in enumerate(cal):
                if nxt is not None:
                    for s in list(hold):
                        if nxt.get(s) != hold[s]["sg"] and d in idx[s]:
                            o = D[s][idx[s][d]][1]; p = hold.pop(s)
                            bk.add_day(d, (o / p["mark"] - 1) * 100 * p["sg"] - C_DAY)
                            bk.trade(s, "long" if p["sg"] > 0 else "short", p["ed"], "open", p["ep"], d, "open", o, C_DAY)
                    for s, sg in nxt.items():
                        if s not in hold and d in idx[s]:
                            o = D[s][idx[s][d]][1]; hold[s] = {"ep": o, "mark": o, "ed": d, "sg": sg}; bk.add_day(d, -C_DAY)
                    nxt = None
                for s, p in hold.items():
                    if d in idx[s]:
                        c = D[s][idx[s][d]][4]
                        bk.add_day(d, (c / p["mark"] - 1) * 100 * p["sg"] - (borrow_fee(repo, s, d) / 252 if p["sg"] < 0 else 0.0)); p["mark"] = c
                bk.daily.setdefault(d, 0.0)
                last_of_week = k + 1 == len(cal) or dt.date.fromisoformat(cal[k + 1]).isocalendar()[1] != dt.date.fromisoformat(d).isocalendar()[1]
                if last_of_week and k + 1 < len(cal):
                    sc = []
                    for s in univ:
                        if s in idx and d in idx[s]:
                            v = score(s, idx[s][d])
                            if v is not None: sc.append((v, s))
                    sc.sort()
                    if len(sc) >= 4 * K:
                        nxt = {s: 1 for _, s in sc[-K:]}; nxt.update({s: -1 for _, s in sc[:K]})
            for s, p in hold.items():
                bk.trade(s, "long" if p["sg"] > 0 else "short", p["ed"], "open", p["ep"], cal[-1], "mark", p["mark"], C_DAY, "open")
            return bk
        books.append(ls_rotation("L15 Market-neutral momentum", 8, [s for s in lib if s in D], mom))

        # L11 overnight, L12 turn of month (SPY)
        spy = D["SPY"]; sidx = {r[0]: i for i, r in enumerate(spy)}
        b11 = Book("L11 SPY overnight", 1); b12 = Book("L12 Turn of month", 1)
        for k, d in enumerate(cal):
            i = sidx[d]
            b11.daily.setdefault(d, 0.0); b12.daily.setdefault(d, 0.0)
            if i >= 1:
                r = (spy[i][1] / spy[i - 1][4] - 1) * 100 - 2 * C_SPY
                b11.add_day(d, r); b11.trade("SPY", "long", spy[i - 1][0], "close", spy[i - 1][4], d, "open", spy[i][1], C_SPY)
        months = {}
        for k, d in enumerate(cal): months.setdefault(d[:7], []).append(k)
        ks = sorted(months)
        for m_i, m in enumerate(ks[:-1]):
            days_m, days_n = months[m], months[ks[m_i + 1]]
            if len(days_m) < 5 or len(days_n) < 3: continue
            a, b = days_m[-5], days_n[2]   # close 4 trading days before month end -> close of 3rd trading day
            for k in range(a + 1, b + 1):
                i, j = sidx[cal[k]], sidx[cal[k - 1]]
                b12.add_day(cal[k], (spy[i][4] / spy[j][4] - 1) * 100)
            b12.add_day(cal[a], -C_DAY); b12.add_day(cal[b], -C_DAY)
            b12.trade("SPY", "long", cal[a], "close", spy[sidx[cal[a]]][4], cal[b], "close", spy[sidx[cal[b]]][4], C_DAY)
        books += [b11, b12]

        # L16 SPY trend short: short while SPY is below a falling 50-day average
        b16 = Book("L16 SPY trend short", 1); p16 = None; go = False
        for k, d in enumerate(cal):
            i = sidx[d]; b16.daily.setdefault(d, 0.0)
            if go and p16 is None:
                p16 = {"ep": spy[i][1], "mark": spy[i][1], "ed": d}; b16.add_day(d, -C_SPY)
            elif not go and p16 is not None:
                o = spy[i][1]; b16.add_day(d, -(o / p16["mark"] - 1) * 100 - C_SPY)
                b16.trade("SPY", "short", p16["ed"], "open", p16["ep"], d, "open", o, C_SPY); p16 = None
            if p16 is not None:
                c = spy[i][4]; b16.add_day(d, -(c / p16["mark"] - 1) * 100 - borrow_fee(repo, "SPY", d) / 252); p16["mark"] = c
            cl = closes(spy, i, 55)
            go = len(cl) >= 55 and cl[-1] < sma(cl, 50) and sma(cl, 50) < sma(cl[:-5], 50)
        if p16 is not None: b16.trade("SPY", "short", p16["ed"], "open", p16["ep"], cal[-1], "mark", p16["mark"], C_SPY, "open")
        books.append(b16)

        # L13 pairs
        b13 = Book("L13 Pairs reversion", 6); pos = {}
        pidx = {s: {r[0]: i for i, r in enumerate(D[s])} for p in PAIRS for s in p if s in D}
        for d in cal:
            b13.daily.setdefault(d, 0.0)
            for a, b in PAIRS:
                if a not in pidx or b not in pidx or d not in pidx[a] or d not in pidx[b]: continue
                ia, ib = pidx[a][d], pidx[b][d]
                if ia < 61 or ib < 61: continue
                ra = [math.log(D[a][ia - k][4] / D[b][ib - k][4]) for k in range(60, -1, -1)]
                m = sum(ra[:-1]) / 60; sd = (sum((x - m) ** 2 for x in ra[:-1]) / 59) ** 0.5
                z = (ra[-1] - m) / sd if sd else 0
                key = a + "/" + b; p = pos.get(key)
                # Decide on the close, trade at the NEXT open (rule at the top of this file; pre-freeze review
                # 2026-11-25: entries and exits used to fill at the same close that produced the signal).
                oa, ob_ = D[a][ia][1], D[b][ib][1]
                if p and p.get("exit"):          # exit decided on the previous close: fill at today's open
                    r = ((oa / p["ma"] - 1) * p["sa"] + (ob_ / p["mb"] - 1) * -p["sa"]) * 50
                    b13.add_day(d, r - C_DAY); p["cum"] += r
                    b13.trades.append({"strategy": b13.name, "symbol": key, "side": "long " + (b if p["sa"] < 0 else a),
                                       "entry_date": p["ed"], "entry_time": "open", "entry": round(p["z0"], 3),
                                       "exit_date": d, "exit_time": "open", "exit": round(p["zx"], 3),
                                       "ret_pct": round(p["cum"] - 2 * C_DAY, 4), "status": "closed",
                                       "phase": tcal.phase(p["ed"]) if p["ed"] >= START else "before"})
                    del pos[key]; p = None
                elif p and p.get("pending"):     # entry decided on the previous close: fill at today's open
                    p.update(ma=oa, mb=ob_, ed=d, pending=False); b13.add_day(d, -C_DAY)
                if p:
                    ca, cb = D[a][ia][4], D[b][ib][4]
                    r = ((ca / p["ma"] - 1) * p["sa"] + (cb / p["mb"] - 1) * -p["sa"]) * 50 - 0.5 * borrow_fee(repo, b if p["sa"] > 0 else a, d) / 252
                    b13.add_day(d, r); p["ma"], p["mb"] = ca, cb; p["held"] += 1; p["cum"] += r
                    if (p["z0"] > 0 and z <= 0) or (p["z0"] < 0 and z >= 0) or p["held"] >= 20:
                        p["exit"] = True; p["zx"] = z
                elif abs(z) > 2 and len(pos) < 6:
                    # rich leg = a when z > 0: short a, long b (sa = -1); filled at the next open
                    pos[key] = {"sa": -1 if z > 0 else 1, "pending": True, "z0": z, "held": 0, "cum": 0.0}
        books.append(b13)

    istocks = lib if U.get("intraday_wide") else stocks      # baseline A lists never change; this is the library only
    istocks = [s for s in istocks if os.path.exists(os.path.join(repo, "data", "bars", "5m", s + ".jsonl"))]
    books += intraday_books({s: intraday(repo, s) for s in istocks + ["SPY"]}, istocks, day)
    return books


def intraday_books(I, stocks, day=None):
    """L1-L4 and L14 from {symbol: {date: [(hhmm, o, h, l, c, v)]}}. Also called by engine.py on today's bars."""
    books = []
    b1 = Book("L1 SPY intraday momentum", 1)
    spyd = I.get("SPY", {}); sd_ = sorted(spyd)
    for k in range(1, len(sd_)):
        d, prev = sd_[k], sd_[k - 1]
        if day and d > day: continue
        bars = {b[0]: b for b in spyd[d]}
        if not tcal.is_trading(d) or "09:55" not in bars or "15:25" not in bars or "15:55" not in bars: continue
        pc = spyd[prev][-1][4]; r1 = bars["09:55"][4] / pc - 1
        if r1 == 0: continue
        side = "long" if r1 > 0 else "short"; ep, xp = bars["15:25"][4], bars["15:55"][4]
        b1.add_day(d, (xp / ep - 1) * 100 * (1 if side == "long" else -1) - 2 * C_SPY)
        b1.trade("SPY", side, d, "15:30", ep, d, "16:00", xp, C_SPY)
    for d in sd_: b1.daily.setdefault(d, 0.0)
    books.append(b1)

    b2, b3, b4 = Book("L2 VWAP pullback", 5), Book("L3 Gap and go", 5), Book("L4 Gap fade", 5)
    b14 = Book("L14 ORB breakdown short", 5)
    days_all = sorted({d for s in stocks for d in I.get(s, {})})
    for d in days_all:
        if day and d > day: continue
        for bk in (b2, b3, b4, b14): bk.daily.setdefault(d, 0.0)
        if not tcal.is_trading(d): continue
        sig2, sig34, sig14 = [], [], []
        for s in stocks:
            days = I.get(s, {})
            if d not in days: continue
            prevs = [x for x in days if x < d]
            if not prevs: continue
            pc = days[prevs[-1]][-1][4]; bars = days[d]
            if not bars or bars[0][0] != "09:30": continue
            o0, h0, l0, c0 = bars[0][1:5]; gap = o0 / pc - 1
            if gap >= 0.02 and c0 > o0: sig34.append(("L3", s, gap, bars, pc))
            elif 0.005 <= gap < 0.02 and c0 < o0: sig34.append(("L4", s, gap, bars, pc))
            if len(bars) > 3 and [x[0] for x in bars[:3]] == ["09:30", "09:35", "09:40"]:
                hi = max(x[2] for x in bars[:3]); lo = min(x[3] for x in bars[:3])
                for j in range(3, len(bars)):
                    if _plus(bars[j][0], 5) > "15:30": break
                    if bars[j][4] < lo: sig14.append((bars[j][0], s, j, (hi + lo) / 2, bars)); break
            pv = vv = 0.0
            for j, (hm, o, h, l, c, v) in enumerate(bars):
                tp = (h + l + c) / 3; pv += tp * max(v, 1); vv += max(v, 1); vw = pv / vv
                if hm < "10:30" or hm > "14:30" or j == 0: continue
                if c / pc - 1 >= 0.01 and bars[j - 1][4] > vw and l <= vw < c:
                    sig2.append((hm, s, j, min(l, vw * 0.997), bars)); break
        for hm, s, j, stop, bars in sorted(sig2)[:5]:
            k = j + 1 + FILL_LAG if FILL_LAG else j + 1
            if FILL_LAG and (k >= len(bars) or bars[k][0] != _plus(bars[j][0], 5 * (1 + FILL_LAG))):
                SKIPPED['L2'] = SKIPPED.get('L2', 0) + 1; continue
            ep = bars[k][1] if FILL_LAG else bars[j][4]; hm = bars[k][0] if FILL_LAG else hm; r = ep - stop
            if r <= 0: continue
            tgt = ep + 2 * r; xp, xt = None, None
            for hm2, o, h, l, c, v in bars[k:]:
                if l <= stop: xp, xt = (o if o < stop else stop), hm2; break
                if h >= tgt: xp, xt = (o if o > tgt else tgt), hm2; break
                if hm2 >= "15:55": xp, xt = c, "16:00"; break
            if xp is None: xp, xt = bars[-1][4], "last"
            b2.add_day(d, (xp / ep - 1) * 100 - 2 * C_INTRA); b2.trade(s, "long", d, hm, ep, d, xt, xp, C_INTRA)
        for hm, s, j, stop, bars in sorted(sig14)[:5]:
            k = j + 1 + FILL_LAG if FILL_LAG else j + 1
            if FILL_LAG and (k >= len(bars) or bars[k][0] != _plus(bars[j][0], 5 * (1 + FILL_LAG))):
                SKIPPED['L14'] = SKIPPED.get('L14', 0) + 1; continue
            ep = bars[k][1] if FILL_LAG else bars[j][4]; et = bars[k][0] if FILL_LAG else _plus(hm, 5); r = stop - ep
            if r <= 0 or r / ep * 100 < 0.05: continue
            tgt = ep - 2 * r; xp, xt = None, None
            for hm2, o, h, l, c, v in bars[k:]:
                if h >= stop: xp, xt = (o if o > stop else stop), hm2; break
                if l <= tgt: xp, xt = (o if o < tgt else tgt), hm2; break
                if hm2 >= "15:55": xp, xt = c, "16:00"; break
            if xp is None: xp, xt = bars[-1][4], "last"
            b14.add_day(d, -(xp / ep - 1) * 100 - 2 * C_INTRA); b14.trade(s, "short", d, et, ep, d, xt, xp, C_INTRA)
        for kind, s, gap, bars, pc in sorted(sig34, key=lambda x: -abs(x[2])):
            bk = b3 if kind == "L3" else b4
            if sum(1 for t in bk.trades if t["entry_date"] == d) >= 5: continue
            k = 1 + FILL_LAG if FILL_LAG else 1
            if FILL_LAG and (k >= len(bars) or bars[k][0] != _plus("09:30", 5 * (1 + FILL_LAG))):
                SKIPPED[kind] = SKIPPED.get(kind, 0) + 1; continue
            ep = bars[k][1] if FILL_LAG else bars[0][4]; et = bars[k][0] if FILL_LAG else "09:35"
            stop = bars[0][3] if kind == "L3" else bars[0][2]; xp = xt = None
            if (kind == "L3" and ep <= stop) or (kind == "L4" and ep >= stop): continue   # already past the stop: no trade
            for hm2, o, h, l, c, v in bars[k:]:
                if kind == "L3":
                    if l <= stop: xp, xt = (o if o < stop else stop), hm2; break
                else:
                    if h >= stop: xp, xt = (o if o > stop else stop), hm2; break
                    if l <= pc: xp, xt = (o if o < pc else pc), hm2; break
                if hm2 >= "15:55": xp, xt = c, "16:00"; break
            if xp is None: xp, xt = bars[-1][4], "last"
            side = "long" if kind == "L3" else "short"; sg = 1 if side == "long" else -1
            bk.add_day(d, (xp / ep - 1) * 100 * sg - 2 * C_INTRA); bk.trade(s, side, d, et, ep, d, xt, xp, C_INTRA)
    books += [b2, b3, b4, b14]
    return books


SLIP, CS_CAP = 0.01, 0.15
_DC = {}


def cs_half_spread(repo, sym, day):
    """Half of the Corwin-Schultz (2012) spread estimate (in %), mean over the 20 day-pairs before `day`, halved
    again for its known upward bias on liquid large caps; capped at CS_CAP."""
    if sym not in _DC: _DC[sym] = daily(repo, sym)
    rows = [r for r in _DC[sym] if r[0] < day][-21:]
    if len(rows) < 10: return None
    k = 3 - 2 * math.sqrt(2); est = []
    for a, b in zip(rows, rows[1:]):
        h1, l1, h2, l2 = a[2], a[3], b[2], b[3]
        if min(h1, l1, h2, l2) <= 0 or h1 < l1 or h2 < l2: continue
        beta = math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2
        gamma = math.log(max(h1, h2) / min(l1, l2)) ** 2
        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / k - math.sqrt(gamma / k)
        S = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
        est.append(max(S, 0.0))
    if not est: return None
    return min(CS_CAP, 0.5 * 50 * sum(est) / len(est))


def side_cost(repo, sym, day, floor):
    obs = corp.half_spread(repo, sym, day)
    if obs is not None: est = obs + SLIP
    elif sym in ETFS or "/" in sym: est = None        # liquid ETFs: Corwin-Schultz overstates badly; floor until observed
    else: est = cs_half_spread(repo, sym, day)
    return max(floor, est if est is not None else floor)


def reprice(repo, books, mult=1.0):
    """Apply per-symbol costs (and the stress multiplier) on top of the floor costs the engines charged."""
    cache = {}
    for b in books:
        for t in b.trades:
            c0 = t.get("cost_side", C_DAY); key = (t["symbol"], t["entry_date"], c0)
            if key not in cache: cache[key] = side_cost(repo, t["symbol"], t["entry_date"], c0) * mult
            c1 = cache[key]; dlt = c1 - c0
            if dlt <= 0: continue
            legs = 2 if t["status"] == "closed" else 1
            t["ret_pct"] = round(t["ret_pct"] - legs * dlt, 4); t["cost_side"] = round(c1, 4)
            b.daily[t["entry_date"]] = b.daily.get(t["entry_date"], 0.0) - dlt / b.K
            if t["status"] == "closed": b.daily[t["exit_date"]] = b.daily.get(t["exit_date"], 0.0) - dlt / b.K
    return books


def write_stress(repo, books, fname="daily_2x.json"):
    os.makedirs(os.path.join(repo, "data", "library"), exist_ok=True)
    json.dump({b.name: {d: round(v, 5) for d, v in sorted(b.daily.items())} for b in books},
              open(os.path.join(repo, "data", "library", fname), "w"), separators=(",", ":"))
    if fname != "daily_2x.json": return {"written": fname}
    out = {}
    for b in books:
        fw = [t["ret_pct"] for t in b.trades if t["phase"] != "before" and t["status"] == "closed"]
        bt = [t["ret_pct"] for t in b.trades if t["phase"] == "before" and t["status"] == "closed"]
        out[b.name] = {"backtest_avg_pct_2x": round(sum(bt) / len(bt), 3) if bt else None, "forward_avg_pct_2x": round(sum(fw) / len(fw), 3) if fw else None}
    return {"stress_2x": out}


def write(repo, books):
    os.makedirs(os.path.join(repo, "data", "library"), exist_ok=True)
    trades = [t for b in books for t in b.trades]
    old = {(t["strategy"], t["symbol"], t["entry_date"], t.get("side")): t for t in ledger.load(repo, "Library")}
    new_closed = [t for t in trades if t["status"] == "closed" and t["phase"] != "before"
                  and old.get((t["strategy"], t["symbol"], t["entry_date"], t.get("side")), {}).get("status") != "closed"]
    p = ledger.path(repo, "Library"); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        for t in sorted(trades, key=lambda t: (t["entry_date"], t["strategy"], t["symbol"])):
            f.write(json.dumps(t, separators=(",", ":")) + "\n")
    json.dump({b.name: {d: round(v, 5) for d, v in sorted(b.daily.items())} for b in books},
              open(os.path.join(repo, "data", "library", "daily.json"), "w"), separators=(",", ":"))
    summ = {}
    for b in books:
        fw = [t for t in b.trades if t["phase"] != "before" and t["status"] == "closed"]
        bt = [t for t in b.trades if t["phase"] == "before" and t["status"] == "closed"]
        summ[b.name] = {"backtest_trades": len(bt), "backtest_avg_pct": round(sum(t["ret_pct"] for t in bt) / len(bt), 3) if bt else None,
                        "forward_trades": len(fw), "forward_avg_pct": round(sum(t["ret_pct"] for t in fw) / len(fw), 3) if fw else None,
                        "open": sum(1 for t in b.trades if t["status"] == "open"), "days": len(b.daily)}
    cols = ["strategy", "symbol", "side", "entry_date", "entry_time", "entry", "exit_date", "exit_time", "exit", "ret_pct", "status", "phase"]
    return {"summary": summ, "new_closed": len(new_closed), "new_closed_rows": [[t[c] for c in cols] for t in new_closed],
            "skipped_no_fill_bar": dict(sorted(SKIPPED.items()))}


if __name__ == "__main__":
    a = sys.argv[1:]; mult = 1.0
    if "--cost-mult" in a: i = a.index("--cost-mult"); mult = float(a[i + 1]); del a[i:i + 2]
    if "--fill-lag" in a: i = a.index("--fill-lag"); FILL_LAG = int(a[i + 1]); del a[i:i + 2]
    if "--wide" in a:     # report-only wide run (2026-11-23): the intraday books on every symbol with stored 5m bars
        a.remove("--wide"); repo = a[0]; day = a[1] if len(a) > 1 else None
        U = json.load(open(os.path.join(repo, "data", "universe.json")))
        ws = [s for s in sorted(set(U["watchlist"] + U["control"]) | {x for x in U.get("universe", []) if x != "GOOG"})
              if os.path.exists(os.path.join(repo, "data", "bars", "5m", s + ".jsonl"))]
        # POINT-IN-TIME (2026-11-23): a stock counts on a day only if it was on that month's point-in-time list
        # (scripts/pitu.py: top 100 S&P 500 members by prior dollar volume). The hindsight version (today's list on
        # every day) is written beside it only to show how much the hindsight flattered the result.
        import pitu
        PL = pitu.lists(repo); I = {s: intraday(repo, s) for s in ws + ["SPY"]}
        Ip = {s: ({d: v for d, v in I[s].items() if pitu.member(PL, s, d)} if s != "SPY" else I[s]) for s in I}
        kept = sum(len(Ip[s]) for s in ws); total = sum(len(I[s]) for s in ws)
        out = {}
        for fname, src in (("intraday_wide.json", Ip), ("intraday_wide_hindsight.json", I)):
            books = [b for b in intraday_books(src, ws, day) if not b.name.startswith("L1 ")]
            for b in books: b.name = b.name + " (wide, report only)"
            books = reprice(repo, books, 1.0); write_stress(repo, books, fname)
            out[fname] = {b.name.split(" (")[0]: round(sum(b.daily.values()), 2) for b in books}
        print(json.dumps({"symbols": len(ws), "symbol_days_kept_point_in_time": kept, "symbol_days_total": total,
                          "sum_of_daily_returns_pct": out})); sys.exit(0)
    repo = a[0]; day = a[1] if len(a) > 1 else None
    books = reprice(repo, build(repo, day), mult)
    if FILL_LAG == 0: print(json.dumps(write_stress(repo, books, "daily_ideal.json"), indent=1))
    else: print(json.dumps(write(repo, books) if mult == 1.0 else write_stress(repo, books), indent=1))
