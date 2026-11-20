"""Decision dataset for machine learning: one row per decision the bot faced, features known AT decision time only,
plus counterfactual labels (what each possible instrument would have returned).

  python3 decisions.py build REPO            rebuild data/decisions/stock.jsonl and crypto.jsonl from stored bars + ledger
  python3 decisions.py live REPO DAY NOW     candidates so far today (ORB breakouts up to NOW, HH:MM) with features,
                                             for ml.py predict (prints JSON)

STOCK decisions = every baseline-A opening-range breakout (identical rules to orb_daily.py, imported from it) on the
watchlist AND the fixed control list, on every stored 5-minute day. Decision time = the breakout bar's close.
Features (no look-ahead: only bars that closed by the decision time, daily data up to the PRIOR close):
  gap_pct, or_width_pct, or_width_atr, or_vol_rel (opening-range volume / mean of prior stored days), breakout_min
  (minutes after 09:45), risk_pct, ret1d, ret5d, vs_sma20 (prior close vs 20-day mean), spy_gap, spy_run (SPY % from
  09:30 to decision), spy_vs20, vix, vix_chg, breadth20, breadth50, nh_nl, crypto_score (prior day regime, in-house),
  weekday, is_control, event_day (high-importance event that day, Events ledger), sent_chg (ApeWisdom mention change,
  Sentiment ledger, prior row), iv_atm (ATM call IV at entry when a Live/Options row has it).
Labels (result per unit risked; null when that instrument was not simulated that day):
  y_stock = stock R net of costs (baseline A), y_atm = ATM call % / 100 (Options), y_d1 = deep OTM D1 % / 100,
  y_w4 = weekly W4 follow % of max risk / 100 (Weekly), y_none = 0.
  best = instrument with the highest label among those available (none if all < 0).
  Since 2026-11-19 y_stock uses the IMPLEMENTABLE entry (fills.py: engine detection price, else the price 5 minutes
  after the signal bar); y_stock_ideal keeps the old signal-close label for comparison.
Archive (2026-11-19): `build-hist REPO` builds rows from data/hist (2 years of 5-minute bars) for days before the
first stored bar into data/decisions/hist/stock.jsonl.gz; load() adds them, so ML trains on about 2 years.
CRYPTO decisions = every closed CryptoTracks trade (all tracks and strategies), features from 1h bars before entry:
  ret1h, ret6h, ret24h, rv24 (% stdev of 1h returns), vs_ema20, atr_pct, btc_ret24, crypto_breadth20, crypto_score,
  hour, weekday, strategy one-hot key ("track strategy"); label y = R.
"""
import json, os, sys, math, hashlib, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, tcal, regime2, corp, checks, fills
NY = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))

# Import the exact baseline rules from orb_daily.py (its module-level CLI code is cut off before exec).
_src = open(os.path.join(HERE, "orb_daily.py")).read()
_src = _src[:_src.index("data = json.load(open(sys.argv[1]))")]
ORB = {}; exec(compile(_src, "orb_daily.py", "exec"), ORB)


USE_HIST = False   # build-hist: prepend the long archive in data/hist (fetch_free.py hist)


def hist_bars(repo, tf, sym):
    """Archive bars from data/hist/<tf>/<SYM>.csv.gz (t,o,h,l,c,v), or []."""
    import gzip, csv
    f = os.path.join(repo, "data", "hist", tf, sym.replace("/", "_") + ".csv.gz")
    if not os.path.exists(f): return []
    with gzip.open(f, "rt") as fh:
        return [{"t": int(r["t"]), "o": float(r["o"]), "h": float(r["h"]), "l": float(r["l"]), "c": float(r["c"]),
                 "v": float(r.get("v") or 0)} for r in csv.DictReader(fh)]


def bars(repo, tf, sym):
    """Stored bars; plus the real-time overlay (env QV_OVERLAY_DIR, used only by engine.py) and, with USE_HIST, the
    archive for times before the first stored bar. Stored bars always win."""
    f = os.path.join(repo, "data", "bars", tf, sym.replace("/", "_") + ".jsonl"); out = []
    if os.path.exists(f):
        for line in open(f):
            if line.strip(): out.append(json.loads(line))
    have = {b["t"] for b in out}
    ov = os.environ.get("QV_OVERLAY_DIR")
    if ov and os.path.exists(os.path.join(ov, tf, sym.replace("/", "_") + ".jsonl")):
        for line in open(os.path.join(ov, tf, sym.replace("/", "_") + ".jsonl")):
            if line.strip():
                b = json.loads(line)
                if b["t"] not in have: out.append(b); have.add(b["t"])
    if USE_HIST:
        first = min(have) if have else 1 << 62
        out += [b for b in hist_bars(repo, tf, sym) if b["t"] < first]
    out.sort(key=lambda b: b["t"]); return out


def raw(B):
    return {"time": [dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for b in B],
            "open": [b["o"] for b in B], "high": [b["h"] for b in B], "low": [b["l"] for b in B], "close": [b["c"] for b in B]}


def nyday(t): return dt.datetime.fromtimestamp(t, NY).date().isoformat()


def nyhm(t): return dt.datetime.fromtimestamp(t, NY).strftime("%H:%M")


def daily_closes(repo, sym, B5):
    """{day: close}: stored daily bars if any, else the last 5m close of each stored day."""
    d = {nyday(b["t"]): b["c"] for b in bars(repo, "1d", sym)}
    by = {}
    for b in B5:
        if "09:30" <= nyhm(b["t"]) < "16:00": by[nyday(b["t"])] = b["c"]
    for k, v in by.items(): d.setdefault(k, v)
    return {k: v for k, v in d.items() if v}


def prior(dc, day, n=1):
    ks = sorted(k for k in dc if k < day)
    return [dc[k] for k in ks[-n:]] if len(ks) >= n else None


class Ctx:
    """Shared, cached market context per day."""
    def __init__(self, repo):
        self.repo = repo; self.reg = {}; self.spy5 = bars(repo, "5m", "SPY"); self.spyd = daily_closes(repo, "SPY", self.spy5)
        self.vix = {nyday(b["t"]): b["c"] for b in bars(repo, "1d", "VIX")}
        self.earn = corp.earnings_known_by(repo)
        try: self.excluded = checks.excluded(repo)
        except Exception: self.excluded = set()
        self.events = {}
        for r in ledger.load(repo, "Events"):
            if str(r.get("importance", "")).lower() in ("high", "3", "red"): self.events[str(r.get("date"))[:10]] = 1
        self.sent = {}
        for r in ledger.load(repo, "Sentiment"):
            self.sent.setdefault(r.get("symbol"), []).append((str(r.get("date"))[:10], ledger.num(r.get("change_pct"))))
        for v in self.sent.values(): v.sort()
        self.iv = {}  # ATM implied vol at decision time, from live runs (Live tab, instrument atm_call, note "iv=0.43")
        for r in ledger.load(repo, "Live"):
            n = str(r.get("note") or "")
            if r.get("instrument") == "atm_call" and "iv=" in n:
                self.iv[(str(r.get("decided_at"))[:10], r.get("symbol"))] = ledger.num(n.split("iv=")[1].split()[0].rstrip(";,"))
        self.labels = {}
        for r in ledger.load(repo, "Options"):
            if r.get("status") == "closed": self.labels.setdefault((r["date"], r["symbol"]), {})["y_atm"] = ledger.num(r.get("return_pct")) / 100 if ledger.num(r.get("return_pct")) is not None else None
        for r in ledger.load(repo, "DeepD1"):
            if r.get("status") == "closed": self.labels.setdefault((r["date"], r["symbol"]), {})["y_d1"] = ledger.num(r.get("return_pct")) / 100 if ledger.num(r.get("return_pct")) is not None else None
        for r in ledger.load(repo, "Weekly"):
            if r.get("status") == "closed" and str(r.get("strategy", "")).startswith("W4"):
                pos = str(r.get("position") or "")
                for tok in pos.replace(",", " ").split():
                    if tok.isupper() and tok.isalpha(): self.labels.setdefault((r["day"], tok), {})["y_w4"] = ledger.num(r.get("pct")) / 100 if ledger.num(r.get("pct")) is not None else None

    def regime(self, day):
        p = tcal.trading_days("2026-01-01", day)
        pd = [d for d in p if d < day]
        key = pd[-1] if pd else day
        if key not in self.reg:
            try: self.reg[key] = regime2.compute(self.repo, key)
            except Exception: self.reg[key] = {}
        return self.reg[key]


_IDX = {}


def by_day(B):
    """{NY date: [bars]} plus opening-range volume per day, cached per bar list (dataset builds call this per row)."""
    k = (id(B), len(B), B[-1]["t"] if B else 0)
    if k not in _IDX:
        days, orv = {}, {}
        for b in B:
            d = nyday(b["t"]); days.setdefault(d, []).append(b)
            if nyhm(b["t"]) in ("09:30", "09:35", "09:40"): orv[d] = orv.get(d, 0) + b.get("v", 0)
        if len(_IDX) > 200: _IDX.clear()
        _IDX[k] = (days, orv, sorted(days))
    return _IDX[k]


def stock_features(ctx, sym, B5, day, trade, is_control, dc=None):
    dc = dc if dc is not None else daily_closes(ctx.repo, sym, B5)
    days5, orv5, dkeys5 = by_day(B5)
    today = days5.get(day, [])
    et = trade["entry_time"]
    upto = [b for b in today if nyhm(b["t"] + 300) <= et]
    o930 = next((b["o"] for b in today if nyhm(b["t"]) == "09:30"), None)
    pc = prior(dc, day)
    f = {}
    f["gap_pct"] = 100 * (o930 / pc[0] - 1) if o930 and pc else None
    e, stop, hi, lo = trade["entry"], trade["stop"], trade["or_high"], trade["or_low"]
    f["or_width_pct"] = 100 * (hi - lo) / e
    p15 = prior(dc, day, 15)
    if p15 and len(p15) >= 15:
        tr = [abs(p15[i] - p15[i - 1]) for i in range(1, 15)]; atr = sum(tr) / len(tr)
        f["or_width_atr"] = (hi - lo) / atr if atr else None
    else: f["or_width_atr"] = None
    orv = sum(b.get("v", 0) for b in today if nyhm(b["t"]) in ("09:30", "09:35", "09:40"))
    pv = [orv5[d] for d in dkeys5 if d < day and orv5.get(d, 0) > 0][-20:]
    f["or_vol_rel"] = orv / (sum(pv) / len(pv)) if pv and orv else None
    h, m = map(int, et.split(":")); f["breakout_min"] = (h * 60 + m) - (9 * 60 + 45)
    f["risk_pct"] = 100 * (e - stop) / e
    p6 = prior(dc, day, 6); p20 = prior(dc, day, 20)
    f["ret1d"] = 100 * (p6[-1] / p6[-2] - 1) if p6 else None
    f["ret5d"] = 100 * (p6[-1] / p6[0] - 1) if p6 else None
    f["vs_sma20"] = 100 * (p20[-1] / (sum(p20) / 20) - 1) if p20 else None
    st = by_day(ctx.spy5)[0].get(day, [])
    so = next((b["o"] for b in st if nyhm(b["t"]) == "09:30"), None)
    sl = [b for b in st if nyhm(b["t"] + 300) <= et]
    spc = prior(ctx.spyd, day); s20 = prior(ctx.spyd, day, 20)
    f["spy_gap"] = 100 * (so / spc[0] - 1) if so and spc else None
    f["spy_run"] = 100 * (sl[-1]["c"] / so - 1) if so and sl else None
    f["spy_vs20"] = 100 * (s20[-1] / (sum(s20) / 20) - 1) if s20 else None
    vk = sorted(k for k in ctx.vix if k < day)
    f["vix"] = ctx.vix[vk[-1]] if vk else None
    f["vix_chg"] = ctx.vix[vk[-1]] - ctx.vix[vk[-2]] if len(vk) >= 2 else None
    R = ctx.regime(day)
    for k in ("breadth20", "breadth50", "nh_nl", "crypto_score"): f[k] = R.get(k)
    f["weekday"] = dt.date.fromisoformat(day).weekday()
    f["is_control"] = 1 if is_control else 0
    f["event_day"] = ctx.events.get(day, 0)
    s = [v for d, v in ctx.sent.get(sym, []) if d < day]
    f["sent_chg"] = s[-1] if s else None
    f["iv_atm"] = trade.get("iv_atm") if trade.get("iv_atm") is not None else ctx.iv.get((day, sym))
    m = corp.macro_features(day)
    for k in ("fomc_day", "days_to_fomc", "cpi_day", "nfp_day", "opex_day", "days_to_opex", "macro_day"): f[k] = m.get(k)
    sn = corp.snap_features(ctx.repo, sym, day)
    f["iv_snap"], f["iv_hv"], f["ivp_52w"] = sn["iv"], sn["iv_hv"], sn["ivp_52w"]
    ev = [d_ for d_, known in ctx.earn.get(sym, []) if known <= day and d_ <= day]   # last known earnings reaction day
    f["earn_days"] = len(tcal.trading_days(max(ev), day)) - 1 if ev and (dt.date.fromisoformat(day) - dt.date.fromisoformat(max(ev))).days <= 30 else None
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in f.items()}


STOCK_FEATURES = ["gap_pct", "or_width_pct", "or_width_atr", "or_vol_rel", "breakout_min", "risk_pct", "ret1d", "ret5d",
                  "vs_sma20", "spy_gap", "spy_run", "spy_vs20", "vix", "vix_chg", "breadth20", "breadth50", "nh_nl",
                  "crypto_score", "weekday", "is_control", "event_day", "sent_chg", "iv_atm",
                  # added 2026-11-19: scheduled macro releases (data/macro.json) and the midday IBKR snapshot taken
                  # before the decision day (implied vol, IV / 30-day realised vol, 52-week IV percentile)
                  "fomc_day", "days_to_fomc", "cpi_day", "nfp_day", "opex_day", "days_to_opex", "macro_day",
                  "iv_snap", "iv_hv", "ivp_52w", "earn_days"]
INSTR = ["stock", "atm", "d1", "w4"]


def cid(*a): return hashlib.sha1("|".join(map(str, a)).encode()).hexdigest()[:12]


def candidates(repo, day=None, now="16:00", ctx=None):
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); ctx = ctx or Ctx(repo); rows = []
    for sym in U["watchlist"] + U["control"]:
        B5 = bars(repo, "5m", sym)
        if not B5: continue
        days5 = by_day(B5)[0]
        days = sorted(days5) if day is None else [day]
        dc = daily_closes(repo, sym, B5)
        for d in days:
            if not tcal.is_trading(d) and day is None: continue
            if (sym, d) in ctx.excluded or ("SPY", d) in ctx.excluded: continue   # sources disagree on this bar
            today = days5.get(d, [])
            if not today: continue
            try: t, why = ORB["sim"](sym, ORB["bars_of"](raw(today)), d, now)
            except Exception: continue
            if not t: continue
            row = {"id": cid("stock", d, sym), "date": d, "symbol": sym, "decided_at": "%s %s" % (d, t["entry_time"]),
                   "phase": tcal.phase(d), "list": "control" if sym in U["control"] else "watchlist",
                   "trade": t, "x": stock_features(ctx, sym, B5, d, t, sym in U["control"], dc)}
            lab = {"y_none": 0.0, "y_stock": t["r_net"] if t["outcome"] != "open" else None}
            if lab["y_stock"] is not None:   # implementable fill (fills.py): label = what a real engine could have got
                lab["y_stock_ideal"] = lab["y_stock"]
                real, src = fills.implementable_entry(repo, sym, d, t["entry_time"])
                rk = t["entry"] - t["stop"]
                if real and rk > 0:
                    lab["y_stock"] = round(lab["y_stock"] + max(-1.5, min(1.5, -(real - t["entry"]) / rk)), 4); lab["fill"] = src
            lab.update(ctx.labels.get((d, sym), {}))
            for k in ("y_atm", "y_d1", "y_w4"): lab.setdefault(k, None)
            avail = {k[2:]: v for k, v in lab.items() if k in ("y_none", "y_stock", "y_atm", "y_d1", "y_w4") and v is not None}
            lab["best"] = max(avail, key=avail.get) if avail else None
            row["y"] = lab; rows.append(row)
    return rows


def crypto_rows(repo, status="closed"):
    out = []; cache = {}
    R = {}
    for r in ledger.load(repo, "CryptoTracks"):
        if r.get("status") != status or ledger.void_data(r): continue   # void (data) trades: see ledger.void_data
        sym = str(r.get("symbol")); t0 = str(r.get("entry_time"))
        try: te = int(dt.datetime.fromisoformat(t0[:16]).replace(tzinfo=NY).timestamp())
        except ValueError: continue
        if sym not in cache: cache[sym] = bars(repo, "1h", sym.split("/")[0].split(".")[0])
        if "BTC" not in cache: cache["BTC"] = bars(repo, "1h", "BTC")
        B = [b for b in cache[sym] if b["t"] + 3600 <= te]; Bb = [b for b in cache["BTC"] if b["t"] + 3600 <= te]
        if len(B) < 25: continue
        c = [b["c"] for b in B]; rets = [c[i] / c[i - 1] - 1 for i in range(len(c) - 24, len(c))]
        k = 2 / 21; e = c[-60] if len(c) >= 60 else c[0]
        for x in c[-59:]: e = x * k + e * (1 - k)
        tr = [max(B[i]["h"], B[i - 1]["c"]) - min(B[i]["l"], B[i - 1]["c"]) for i in range(len(B) - 14, len(B))]
        day = dt.datetime.fromtimestamp(te, NY).date().isoformat()
        if day not in R:
            try: R[day] = regime2.compute(repo, (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat())
            except Exception: R[day] = {}
        m = sum(rets) / 24
        x = {"ret1h": 100 * (c[-1] / c[-2] - 1), "ret6h": 100 * (c[-1] / c[-7] - 1), "ret24h": 100 * (c[-1] / c[-25] - 1),
             "rv24": 100 * math.sqrt(sum((a - m) ** 2 for a in rets) / 23), "vs_ema20": 100 * (c[-1] / e - 1),
             "atr_pct": 100 * sum(tr) / 14 / c[-1],
             "btc_ret24": 100 * (Bb[-1]["c"] / Bb[-25]["c"] - 1) if len(Bb) >= 25 else None,
             "crypto_breadth20": R[day].get("crypto_breadth20"), "crypto_score": R[day].get("crypto_score"),
             "hour": dt.datetime.fromtimestamp(te, NY).hour, "weekday": dt.datetime.fromtimestamp(te, NY).weekday()}
        out.append({"id": cid("crypto", r.get("track"), r.get("strategy"), sym, t0), "date": day, "symbol": sym,
                    "decided_at": t0[:16], "phase": tcal.phase(day),
                    "key": "%s %s" % (r.get("track"), r.get("strategy")),
                    "x": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in x.items()}, "y": {"y": ledger.num(r.get("r"))}})
    return out


CRYPTO_FEATURES = ["ret1h", "ret6h", "ret24h", "rv24", "vs_ema20", "atr_pct", "btc_ret24", "crypto_breadth20",
                   "crypto_score", "hour", "weekday"]


def build(repo):
    d = os.path.join(repo, "data", "decisions"); os.makedirs(d, exist_ok=True); res = {}
    for name, rows in (("stock", candidates(repo)), ("crypto", crypto_rows(repo))):
        rows.sort(key=lambda r: (r["decided_at"], r["symbol"]))
        with open(os.path.join(d, name + ".jsonl"), "w") as f:
            for r in rows: f.write(json.dumps(r, separators=(",", ":")) + "\n")
        res[name] = {"rows": len(rows), "days": len({r["date"] for r in rows}),
                     "labelled": {k: sum(1 for r in rows if r["y"].get(k) is not None) for k in rows[0]["y"]} if rows else {}}
    return res


def build_hist(repo):
    """Candidates from the long archive only (days before the first stored 5m SPY bar), written once to
    data/decisions/hist/<name>.jsonl.gz. ML training adds them to the stored rows (load)."""
    import gzip
    global USE_HIST
    first = bars(repo, "5m", "SPY"); cut = nyday(first[0]["t"]) if first else "9999"
    USE_HIST = True
    try: rows = [r for r in candidates(repo) if r["date"] < cut]
    finally: USE_HIST = False
    d = os.path.join(repo, "data", "decisions", "hist"); os.makedirs(d, exist_ok=True)
    rows.sort(key=lambda r: (r["decided_at"], r["symbol"]))
    with gzip.open(os.path.join(d, "stock.jsonl.gz"), "wt") as f:
        for r in rows: f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return {"rows": len(rows), "days": len({r["date"] for r in rows}), "before": cut,
            "first": rows[0]["date"] if rows else None}


def load(repo, name):
    """Stored decision rows plus, for the stock family, the archive rows (data/decisions/hist, older days only)."""
    import gzip
    f = os.path.join(repo, "data", "decisions", name + ".jsonl")
    rows = [json.loads(l) for l in open(f) if l.strip()] if os.path.exists(f) else []
    h = os.path.join(repo, "data", "decisions", "hist", name + ".jsonl.gz")
    if os.path.exists(h):
        ids = {r["id"] for r in rows}; first = min((r["date"] for r in rows), default="9999")
        with gzip.open(h, "rt") as fh:
            old = [json.loads(l) for l in fh if l.strip()]
        rows = [r for r in old if r["id"] not in ids and r["date"] < first] + rows
    return rows


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "build": print(json.dumps(build(a[1]), indent=1))
    elif a[0] == "build-hist": print(json.dumps(build_hist(a[1]), indent=1))
    elif a[0] == "live":
        rows = candidates(a[1], a[2], a[3])
        print(json.dumps([r for r in rows], indent=1))
