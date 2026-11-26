"""The quant desk (owner decision 2026-11-26, item 70): numbers Quantavius can ask for about any stock before it
picks, sizes, sets a stop or opens a day trade. Read only; it prices nothing in the test and changes no file except a
cache under /tmp. Everything is computed from bars dated BEFORE the day asked about (default: today, New York).

  python3 quant.py brief REPO SYM [--day YYYY-MM-DD] [--gap PCT] [--bars FILE]
      technical pack + the stock's own gap history + the cross-sectional gap base rate (when --gap is given) + intraday
      profile (when the 5-minute archive has the stock) + the move the stored option chain implies.
      --gap PCT   today's pre-market gap in percent (from the task's own quote), e.g. --gap 4.2 or --gap -3
      --bars FILE daily bars for a stock that is in none of the stores: an IBKR get_price_history result saved as JSON
                  (arrays time, open, high, low, close, volume) or {SYM: that result}
  python3 quant.py gaprate REPO LO HI [--day D]
      base rate over the whole point-in-time S&P 500 history (2016 on, companies that later left included): every
      stock-day whose open gapped between LO and HI percent from the previous close.
  python3 quant.py live REPO SYM --bars FILE
      the state of TODAY's session from 5-minute bars the task just fetched (an IBKR get_price_history result, FIVE_MINS,
      ONE_DAY, regular hours, saved as JSON or {SYM: result}): move from the open, session VWAP and distance from it,
      opening range (first 30 minutes) and whether price is outside it, place in the day's range, the last hour's
      drift, volume against the stock's own average by this time of day (when the archive has it), and stop and target
      distances that fit this stock's ordinary rest-of-day swings. For the intraday desk's day trades.
  python3 quant.py many REPO SYM1,SYM2,... [--day D]
      the technical pack of several stocks, one compact line each (for a shortlist or the 44 ranked stocks).

WHAT THE NUMBERS MEAN. "oc" is the move from the open to the close in percent; "rel" is that move minus the same day's
average over all members (the closest history has to "beats the control list"); win = share above zero. "mae"/"mfe" are
the worst and best points of the day from the open (low and high), so a stop tighter than the median mae is hit on
more than half of ordinary days. Base rates are history, not a forecast: quote n with every rate, and treat anything
with n under 30 as an anecdote. Costs are not included. The histories are daily bars adjusted for splits and dividends.

DATA, in this order: data/bars/1d (the test's own universe and picks), data/hist/1d (2016 archive), data/pit (S&P 500
members since 2016), then --bars. Intraday: data/hist/5m plus data/bars/5m. Options: the newest data/optarch/snap file
dated before the day.
"""
import csv, gzip, json, math, os, pickle, sys, glob, statistics as st, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from zoneinfo import ZoneInfo  # noqa: E402
NY = ZoneInfo("America/New_York")
r2 = lambda x, n=2: None if x is None else round(x, n)


def _day(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()


def daily(repo, sym, bars_file=None):
    """[(date, o, h, l, c, v)] ascending, from the first store that has the stock."""
    out = {}
    f = os.path.join(repo, "data", "hist", "1d", sym + ".csv.gz")
    if os.path.exists(f):
        for r in csv.DictReader(gzip.open(f, "rt")): out[_day(int(r["t"]))] = (float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r.get("v") or 0))
    f = os.path.join(repo, "data", "bars", "1d", sym + ".jsonl")
    if os.path.exists(f):
        for l in open(f):
            if l.strip():
                b = json.loads(l); out[_day(b["t"])] = (b["o"], b["h"], b["l"], b["c"], b.get("v") or 0)
    src = "stored bars" if out else None
    if len(out) < 60:
        P = pit_all(repo).get(sym)
        if P:
            for d, o, h, l, c, v in P: out.setdefault(d, (o, h, l, c, v))
            src = "point-in-time S&P 500 file"
    if len(out) < 60 and bars_file:
        j = json.load(open(bars_file)); j = j.get(sym, j)
        for i, t in enumerate(j["time"]):
            d = t[:10] if isinstance(t, str) else _day(t if t < 1e11 else t / 1000)
            out[d] = (j["open"][i], j["high"][i], j["low"][i], j["close"][i], (j.get("volume") or [0] * len(j["time"]))[i])
        src = "bars file"
    return [(d,) + out[d] for d in sorted(out)], src


def pit_all(repo, _c={}):
    """{sym: [(date, o, h, l, c, v)]} for every S&P 500 member since 2016 (cached in /tmp by file size and time)."""
    if "b" in _c: return _c["b"]
    P = os.path.join(repo, "data", "pit"); f = os.path.join(P, "bars_1d.csv.gz")
    if not os.path.exists(f): _c["b"] = {}; return {}
    sig = "%d-%d-%d" % (os.path.getsize(f), int(os.path.getmtime(f)), len(glob.glob(os.path.join(P, "fwd", "*.csv.gz"))))
    cache = "/tmp/quant_pit_%s.pkl" % sig
    if os.path.exists(cache):
        try: _c["b"] = pickle.load(open(cache, "rb")); return _c["b"]
        except Exception: pass
    import pit
    _c["b"] = pit.load(repo)[1]
    try: pickle.dump(_c["b"], open(cache, "wb"))
    except Exception: pass
    return _c["b"]


def rsi(c, n=14):
    if len(c) <= n: return None
    g = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]; l = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for i in range(n, len(g)): ag, al = (ag * (n - 1) + g[i]) / n, (al * (n - 1) + l[i]) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def q(xs, p):
    xs = sorted(xs)
    if not xs: return None
    k = (len(xs) - 1) * p; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def pack(B):
    """Technical pack from daily bars B (all dated before the day asked about)."""
    if len(B) < 30: return {"error": "fewer than 30 daily bars"}
    d, o, h, l, c, v = zip(*B); n = len(c); last = c[-1]
    ret = lambda k: (last / c[-1 - k] - 1) * 100 if n > k else None
    tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    atr = sum(tr[-14:]) / 14
    lr = [math.log(c[i] / c[i - 1]) for i in range(max(1, n - 21), n)]
    ma = lambda k: sum(c[-k:]) / k if n >= k else None
    dist = lambda m: (last / m - 1) * 100 if m else None
    w = min(n, 252); oc = [(c[i] / o[i] - 1) * 100 for i in range(n - w, n) if o[i]]
    mae = [(l[i] / o[i] - 1) * 100 for i in range(n - w, n) if o[i]]; mfe = [(h[i] / o[i] - 1) * 100 for i in range(n - w, n) if o[i]]
    hi52 = max(h[-w:]); lo52 = min(l[-w:]); av = sum(v[-22:-1]) / max(1, len(v[-22:-1]))
    up = sum(1 for i in range(n - 10, n) if c[i] > c[i - 1])
    return {"last_day": d[-1], "close": r2(last), "bars": n,
            "ret_pct": {"1d": r2(ret(1)), "5d": r2(ret(5)), "21d": r2(ret(21)), "63d": r2(ret(63)), "126d": r2(ret(126))},
            "trend": {"vs_ma20_pct": r2(dist(ma(20))), "vs_ma50_pct": r2(dist(ma(50))), "vs_ma200_pct": r2(dist(ma(200))),
                      "ma50_above_ma200": (ma(50) > ma(200)) if ma(200) else None, "up_days_of_last_10": up},
            "rsi14": r2(rsi(list(c[-120:])), 1), "atr14_pct": r2(atr / last * 100), "realised_vol_21d_annual_pct": r2(st.pstdev(lr) * math.sqrt(252) * 100, 1),
            "levels": {"high_20d": r2(max(h[-20:])), "low_20d": r2(min(l[-20:])), "high_52w": r2(hi52), "low_52w": r2(lo52),
                       "below_52w_high_pct": r2((last / hi52 - 1) * 100), "prev_high": r2(h[-1]), "prev_low": r2(l[-1])},
            "volume": {"last_vs_21d_avg": r2(v[-1] / av) if av else None, "avg_21d_shares": int(av), "avg_21d_dollars_m": r2(av * last / 1e6, 1)},
            "ordinary_day_last_252": {"note": "from the open: oc = to the close, mae = to the low, mfe = to the high (percent)",
                                      "oc_abs_median": r2(q([abs(x) for x in oc], .5)), "oc_win_rate": r2(sum(1 for x in oc if x > 0) / len(oc)),
                                      "mae_median": r2(q(mae, .5)), "mae_worst_quarter": r2(q(mae, .25)), "mae_worst_tenth": r2(q(mae, .10)),
                                      "mfe_median": r2(q(mfe, .5)), "mfe_best_quarter": r2(q(mfe, .75)), "mfe_best_tenth": r2(q(mfe, .90))},
            "stop_target_guide_pct": {"note": "a stop at -X is hit on about this share of ordinary days; a target at +X likewise",
                                      "stop_hit_on_25pct_of_days": r2(q(mae, .25)), "stop_hit_on_10pct_of_days": r2(q(mae, .10)),
                                      "target_reached_on_25pct_of_days": r2(q(mfe, .75)), "target_reached_on_10pct_of_days": r2(q(mfe, .90))}}


def summ(rows):
    """rows: [(oc, rel, mae, mfe, next5)] -> summary."""
    if not rows: return {"n": 0}
    oc = [x[0] for x in rows]; rel = [x[1] for x in rows if x[1] is not None]; n5 = [x[4] for x in rows if x[4] is not None]
    out = {"n": len(rows), "oc_mean": r2(st.mean(oc), 3), "oc_median": r2(q(oc, .5), 3), "oc_win_rate": r2(sum(1 for x in oc if x > 0) / len(oc), 3),
           "mae_median": r2(q([x[2] for x in rows], .5)), "mfe_median": r2(q([x[3] for x in rows], .5))}
    if rel: out.update(rel_mean=r2(st.mean(rel), 3), rel_win_rate=r2(sum(1 for x in rel if x > 0) / len(rel), 3))
    if n5: out.update(next5d_from_close_mean=r2(st.mean(n5), 3))
    if len(oc) >= 30: out["oc_t"] = r2(st.mean(oc) / (st.pstdev(oc) / math.sqrt(len(oc))), 2) if st.pstdev(oc) > 0 else None
    return out


def gap_rows(B, lo, hi, before, mkt=None):
    out = []
    for i in range(1, len(B)):
        d, o, h, l, c, v = B[i]
        if d >= before or not B[i - 1][4] or not o: continue
        g = (o / B[i - 1][4] - 1) * 100
        if lo <= g <= hi:
            oc = (c / o - 1) * 100
            out.append((oc, oc - mkt[d] if mkt and d in mkt else None, (l / o - 1) * 100, (h / o - 1) * 100,
                        (B[i + 5][4] / c - 1) * 100 if i + 5 < len(B) and B[i + 5][0] < before else None))
    return out


def market_oc(repo, _c={}):
    """{date: equal-weight average open-to-close move of all stocks in the point-in-time file} (cached)."""
    if "m" in _c: return _c["m"]
    acc = {}
    for sym, L in pit_all(repo).items():
        for d, o, h, l, c, v in L:
            if o: a = acc.setdefault(d, [0.0, 0]); a[0] += (c / o - 1) * 100; a[1] += 1
    _c["m"] = {d: a[0] / a[1] for d, a in acc.items() if a[1] >= 50}
    return _c["m"]


def gaprate(repo, lo, hi, before):
    mkt = market_oc(repo); rows = []; by_year = {}
    for sym, L in pit_all(repo).items():
        for i in range(1, len(L)):
            d, o, h, l, c, v = L[i]
            if d >= before or not L[i - 1][4] or not o: continue
            g = (o / L[i - 1][4] - 1) * 100
            if lo <= g <= hi and abs(g) < 60:
                oc = (c / o - 1) * 100
                x = (oc, oc - mkt[d] if d in mkt else None, (l / o - 1) * 100, (h / o - 1) * 100,
                     (L[i + 5][4] / c - 1) * 100 if i + 5 < len(L) and L[i + 5][0] < before else None)
                rows.append(x); by_year.setdefault(d[:4], []).append(x)
    out = {"gap_band_pct": [lo, hi], "universe": "S&P 500 members since 2016, companies that later left included", "all": summ(rows),
           "by_year_rel_mean": {y: r2(st.mean([x[1] for x in v if x[1] is not None]), 3) for y, v in sorted(by_year.items()) if len(v) >= 20},
           "read": "rel_* is against the same day's average stock: the fair comparison for beating the control list"}
    return out


def intraday(repo, sym, before):
    """Profile from the 5-minute archive: how the day's move is spread, and what the first half hour said about the rest."""
    rows = {}
    f = os.path.join(repo, "data", "hist", "5m", sym + ".csv.gz")
    if os.path.exists(f):
        for r in csv.DictReader(gzip.open(f, "rt")):
            t = dt.datetime.fromtimestamp(int(r["t"]), NY); hm = t.strftime("%H:%M")
            if "09:30" <= hm < "16:00": rows.setdefault(t.date().isoformat(), {})[hm] = (float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
    f = os.path.join(repo, "data", "bars", "5m", sym + ".jsonl")
    if os.path.exists(f):
        for l in open(f):
            if l.strip():
                b = json.loads(l); t = dt.datetime.fromtimestamp(b["t"], NY); hm = t.strftime("%H:%M")
                if "09:30" <= hm < "16:00": rows.setdefault(t.date().isoformat(), {})[hm] = (b["o"], b["h"], b["l"], b["c"])
    days = [d for d in sorted(rows) if d < before and "09:30" in rows[d] and "10:00" in rows[d] and len(rows[d]) >= 70]
    if len(days) < 40: return {"status": "no 5-minute history for this stock (%d days)" % len(days)}
    first, rest, up_cont, dn_cont, lows, highs, lunch, last_hr = [], [], [], [], [], [], [], []
    for d in days:
        R = rows[d]; ks = sorted(R); o = R["09:30"][0]; p10 = R["10:00"][0]; c = R[ks[-1]][3]
        f30 = (p10 / o - 1) * 100; re = (c / p10 - 1) * 100; first.append(f30); rest.append(re)
        (up_cont if f30 > 0 else dn_cont).append(re)
        lo_t = min(ks, key=lambda k: R[k][2]); hi_t = max(ks, key=lambda k: R[k][1]); lows.append(lo_t); highs.append(hi_t)
        if "12:00" in R and "14:00" in R: lunch.append(abs(R["14:00"][0] / R["12:00"][0] - 1) * 100)
        if "15:00" in R: last_hr.append(abs(c / R["15:00"][0] - 1) * 100)
    share = lambda L, a, b: r2(sum(1 for x in L if a <= x < b) / len(L))
    return {"days": len(days), "from": days[0],
            "first_30min_abs_median_pct": r2(q([abs(x) for x in first], .5)), "rest_of_day_abs_median_pct": r2(q([abs(x) for x in rest], .5)),
            "after_up_first_30min": {"n": len(up_cont), "rest_mean_pct": r2(st.mean(up_cont), 3) if up_cont else None,
                                     "rest_up_share": r2(sum(1 for x in up_cont if x > 0) / len(up_cont)) if up_cont else None},
            "after_down_first_30min": {"n": len(dn_cont), "rest_mean_pct": r2(st.mean(dn_cont), 3) if dn_cont else None,
                                       "rest_up_share": r2(sum(1 for x in dn_cont if x > 0) / len(dn_cont)) if dn_cont else None},
            "day_low_set": {"by_10:00": share(lows, "09:30", "10:00"), "10:00-12:00": share(lows, "10:00", "12:00"), "12:00-15:00": share(lows, "12:00", "15:00"), "last_hour": share(lows, "15:00", "16:00")},
            "day_high_set": {"by_10:00": share(highs, "09:30", "10:00"), "10:00-12:00": share(highs, "10:00", "12:00"), "12:00-15:00": share(highs, "12:00", "15:00"), "last_hour": share(highs, "15:00", "16:00")},
            "midday_12_to_14_abs_median_pct": r2(q(lunch, .5)) if lunch else None, "last_hour_abs_median_pct": r2(q(last_hr, .5)) if last_hr else None}


def implied(repo, sym, before):
    """The move the stored option chain implies: the at-the-money straddle of the nearest expiry at least 2 days out."""
    fs = sorted(f for f in glob.glob(os.path.join(repo, "data", "optarch", "snap", sym, "*.json.gz")) if os.path.basename(f)[:10] < before)
    if not fs: return {"status": "no stored option chain"}
    d = json.loads(gzip.decompress(open(fs[-1], "rb").read())); spot = d.get("spot"); day = d["day"]
    by = {}
    for occ, v in d["c"].items():
        root = occ[:-15]; exp = "20%s-%s-%s" % (occ[-15:-13], occ[-13:-11], occ[-11:-9]); right = occ[-9]; k = int(occ[-8:]) / 1000
        if root != sym or not v[0] or not v[1] or v[1] <= v[0]: continue
        by.setdefault(exp, {}).setdefault(k, {})[right] = ((v[0] + v[1]) / 2, v[3], (v[1] - v[0]) / 2 / ((v[0] + v[1]) / 2) * 100)
    out = []
    for exp in sorted(by):
        days = (dt.date.fromisoformat(exp) - dt.date.fromisoformat(day)).days
        if days < 2 or not spot: continue
        ks = [k for k, x in by[exp].items() if "C" in x and "P" in x]
        if not ks: continue
        k = min(ks, key=lambda x: abs(x - spot)); c, p = by[exp][k]["C"], by[exp][k]["P"]
        mv = (c[0] + p[0]) / spot * 100
        out.append({"expiry": exp, "calendar_days": days, "atm_strike": k, "straddle_pct_of_spot": r2(mv),
                    "implied_move_1_day_pct": r2(mv / math.sqrt(max(1, days * 252 / 365))), "atm_iv": r2(((c[1] or 0) + (p[1] or 0)) / 2, 3),
                    "atm_half_spread_pct": r2(max(c[2], p[2]), 1)})
        if len(out) == 2: break
    return {"chain_day": day, "spot": spot, "feed": d.get("feed"), "expiries": out} if out else {"status": "no two-sided at-the-money quotes"}


def brief(repo, sym, day, gap=None, bars_file=None):
    B, src = daily(repo, sym, bars_file); B = [b for b in B if b[0] < day]
    out = {"symbol": sym, "as_of_before": day, "daily_source": src}
    if len(B) < 30:
        out["error"] = "no daily history in the stores: save an IBKR get_price_history result (ONE_DAY bars, one year) and pass --bars FILE"; return out
    out["technical"] = pack(B)
    own = {"up_2_to_4": summ(gap_rows(B, 2, 4, day)), "up_over_4": summ(gap_rows(B, 4, 60, day)),
           "down_2_to_4": summ(gap_rows(B, -4, -2, day)), "down_over_4": summ(gap_rows(B, -60, -4, day))}
    out["own_gap_history"] = {"note": "this stock's own gap days (open vs previous close), all history in the store", **own}
    if gap is not None:
        g = float(gap); lo, hi = (g * 0.6, g * 1.6) if g > 0 else (g * 1.6, g * 0.6)
        if abs(g) >= 1:
            out["gap_today"] = {"gap_pct": g, "own": summ(gap_rows(B, lo, hi, day)), "base_rate": gaprate(repo, r2(lo, 1), r2(hi, 1), day)}
        else: out["gap_today"] = {"gap_pct": g, "note": "under 1%: an ordinary open, see technical.ordinary_day_last_252"}
    out["intraday_profile"] = intraday(repo, sym, day)
    out["options_implied"] = implied(repo, sym, day)
    return out


def live(repo, sym, bars_file):
    j = json.load(open(bars_file)); j = j.get(sym, j); R = []
    for i, t in enumerate(j["time"]):
        ts = dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if isinstance(t, str) else dt.datetime.fromtimestamp(t if t < 1e11 else t / 1000, dt.timezone.utc)
        ny = ts.astimezone(NY); hm = ny.strftime("%H:%M")
        if "09:30" <= hm < "16:00": R.append((ny.date().isoformat(), hm, j["open"][i], j["high"][i], j["low"][i], j["close"][i], (j.get("volume") or [0] * len(j["time"]))[i]))
    if not R: return {"error": "no regular-session bars in the file"}
    day = max(r[0] for r in R); R = sorted(r for r in R if r[0] == day)
    o = R[0][2]; last = R[-1][5]; hi = max(r[3] for r in R); lo = min(r[4] for r in R); vol = sum(r[6] for r in R)
    vwap = sum((r[3] + r[4] + r[5]) / 3 * r[6] for r in R) / vol if vol else None
    orb = [r for r in R if r[1] < "10:00"]; orh = max(r[3] for r in orb) if orb else None; orl = min(r[4] for r in orb) if orb else None
    hour = [r for r in R[-12:]]
    out = {"symbol": sym, "day": day, "last_bar": R[-1][1], "bars": len(R), "last": r2(last), "from_open_pct": r2((last / o - 1) * 100),
           "day_high": r2(hi), "day_low": r2(lo), "place_in_range": r2((last - lo) / (hi - lo)) if hi > lo else None,
           "vwap": r2(vwap), "vs_vwap_pct": r2((last / vwap - 1) * 100) if vwap else None,
           "opening_range": {"high": r2(orh), "low": r2(orl), "state": None if not orb else ("above" if last > orh else "below" if last < orl else "inside")},
           "last_hour_pct": r2((last / hour[0][2] - 1) * 100), "higher_lows_last_6_bars": all(R[i][4] >= R[i - 1][4] for i in range(max(1, len(R) - 5), len(R)))}
    # the stock's own history from the archive: volume by this time of day and the rest-of-day swing from this time
    hist = {}
    f = os.path.join(repo, "data", "hist", "5m", sym + ".csv.gz")
    if os.path.exists(f):
        for r in csv.DictReader(gzip.open(f, "rt")):
            t = dt.datetime.fromtimestamp(int(r["t"]), NY); hm = t.strftime("%H:%M")
            if "09:30" <= hm < "16:00" and t.date().isoformat() < day: hist.setdefault(t.date().isoformat(), []).append((hm, float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r.get("v") or 0)))
    days = sorted(hist)[-60:]; cut = R[-1][1]
    if len(days) >= 20:
        vs = [sum(x[5] for x in hist[d] if x[0] <= cut) for d in days]; av = st.mean(vs) if vs else 0
        mae, mfe = [], []
        for d in days:
            rest = [x for x in hist[d] if x[0] > cut]
            if rest and rest[0][1]: mae.append((min(x[3] for x in rest) / rest[0][1] - 1) * 100); mfe.append((max(x[2] for x in rest) / rest[0][1] - 1) * 100)
        out["volume_vs_own_average_by_now"] = r2(vol / av) if av else None
        if mae: out["rest_of_day_guide_pct"] = {"note": "from this time to the close on the last 60 days: a stop at -X is hit on about this share of days",
                                                 "stop_hit_on_50pct": r2(q(mae, .5)), "stop_hit_on_25pct": r2(q(mae, .25)), "stop_hit_on_10pct": r2(q(mae, .10)),
                                                 "target_reached_on_50pct": r2(q(mfe, .5)), "target_reached_on_25pct": r2(q(mfe, .75)), "target_reached_on_10pct": r2(q(mfe, .90))}
    else: out["history"] = "no 5-minute archive for this stock: size the stop from quant.py brief (technical.atr14_pct)"
    return out


def main(a):
    def opt(name, default=None):
        if name in a:
            i = a.index(name); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    day = opt("--day", dt.datetime.now(NY).date().isoformat()); gap = opt("--gap"); bf = opt("--bars")
    cmd, repo = a[0], a[1]
    if cmd == "brief": r = brief(repo, a[2].upper(), day, gap, bf)
    elif cmd == "live": r = live(repo, a[2].upper(), bf)
    elif cmd == "gaprate": r = gaprate(repo, float(a[2]), float(a[3]), day)
    elif cmd == "many":
        r = {}
        for s in a[2].upper().split(","):
            B = [b for b in daily(repo, s)[0] if b[0] < day]; p = pack(B)
            r[s] = p if "error" in p else {"close": p["close"], "ret": p["ret_pct"], "rsi14": p["rsi14"], "atr14_pct": p["atr14_pct"],
                                             "vs_ma20": p["trend"]["vs_ma20_pct"], "vs_ma50": p["trend"]["vs_ma50_pct"], "vs_ma200": p["trend"]["vs_ma200_pct"],
                                             "below_52w_high": p["levels"]["below_52w_high_pct"], "rel_volume": p["volume"]["last_vs_21d_avg"]}
        print(json.dumps(r, separators=(",", ":"))); return
    else: sys.exit("unknown command")
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
