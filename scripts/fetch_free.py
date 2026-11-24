"""Free market-data fetcher. Runs on GitHub Actions (internet access, keys in repo secrets), never inside a
scheduled Claude task, so no price data passes through the model as text.

Sources (all free, no extra cost):
  Alpaca Market Data (free plan): stock/ETF bars from the SIP feed (every US exchange, consolidated tape),
      at least 15 minutes old; crypto bars; dividends and splits. Keys: env ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY.
  Cboe: daily VIX and VIX3M history (public CSV files, no key).

  python3 fetch_free.py intraday REPO   -> 5m bars for watchlist + control + SPY/QQQ/IWM since the last stored bar
                                           (regular hours 09:30-15:55 ET only, closed bars only), crypto 15m + 1h
  python3 fetch_free.py nightly REPO    -> daily bars (last 15 days) for every stock and ETF, crypto daily,
                                           dividends + splits (last 60 days), Cboe VIX/VIX3M
  python3 fetch_free.py backfill REPO   -> history: daily 2 years, 5m 90 days, crypto 1h 1 year and 15m 90 days,
                                           corporate actions 3 years, full Cboe VIX/VIX3M
  python3 fetch_free.py tick REPO       -> every 5 minutes in market hours: intraday 5m (crypto every 15 minutes),
                                           then engine.py (sealed real-time signal detections)
  python3 fetch_free.py pit REPO        -> one-off: point-in-time S&P 500 membership + prices incl. departed members (data/pit/)
  python3 fetch_free.py borrow REPO     -> today's stock-loan fees and shares available (also part of nightly)
  python3 fetch_free.py crypto REPO     -> crypto 15m / 1h / 1d only (scheduled every 3 hours, before each crypto-tracks run)
  python3 fetch_free.py etfs REPO       -> one-off history (2 years + archive since 2016) for the ETFs in universe.json
  python3 fetch_free.py wide5m REPO     -> one-off 90 days of 5m bars for the whole universe
  python3 fetch_free.py hist REPO       -> long archive for research (strategy lab, ML): daily bars since 2016 for the
                                           S&P 100 universe + ETFs, 5m bars for 2 years for the 47 intraday symbols,
                                           into data/hist/<tf>/<SYM>.csv.gz (t,o,h,l,c,v; same timestamp rules).
                                           Never read by the nightly library/allocator (their evidence window is 120 days).
Daily bars, dividends and splits cover the whole static S&P 100 snapshot (universe.json "universe") plus the ETFs
since 2026-11-19 (the library's cross-sectional strategies use it).

Merge rule (keeps the live record honest): a bar already in the file keeps its open/high/low/close, because live
decisions were made on it. Only missing bars are added, and a stored volume of 0 (IBKR 5m bars carry none) is
filled in. Exception: a stored crypto price under $1 rounded to the cent (IBKR quotes DOGE that way) is replaced by
the full-precision bar and counted as coarse_fixed. Closes that differ by more than 0.2% from the stored bar are listed in ops/diag/fetch_free.json for the
data-quality check. Timestamps follow store.py: bar START in Unix seconds; daily bars at 12:00 UTC of the trading
date. Every run writes ops/diag/fetch_free.json (what was fetched, counts, errors).
"""
import csv, io, json, os, sys, time, urllib.parse, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York"); UTC = dt.timezone.utc
DATA = "https://data.alpaca.markets"
COINS = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE", "SHIB"]
INTRA_ETFS = ["SPY", "QQQ", "IWM"]
LOG = {"errors": [], "files": {}, "mismatch": [], "mismatch_count": {}}


def now(): return dt.datetime.now(UTC)
def iso(d): return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, params, auth=True, tries=4):
    q = url + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"User-Agent": "quantavius-forward-test/1.0", "Accept": "application/json"}
    if auth:
        h["APCA-API-KEY-ID"] = os.environ["ALPACA_API_KEY_ID"]; h["APCA-API-SECRET-KEY"] = os.environ["ALPACA_API_SECRET_KEY"]
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=h), timeout=60) as r: return r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and k < tries - 1: time.sleep(2 + 5 * k); continue
            raise RuntimeError("HTTP %s %s: %s" % (e.code, url, body))
        except urllib.error.URLError:
            if k < tries - 1: time.sleep(2 + 5 * k); continue
            raise


def paged(url, params, key):
    """Alpaca pagination; returns merged dict symbol -> list (bars) or the raw corporate_actions dict."""
    out = {}; p = dict(params)
    while True:
        j = json.loads(get(url, p)); part = j.get(key) or {}
        for s, rows in part.items(): out.setdefault(s, []).extend(rows)
        tok = j.get("next_page_token")
        if not tok: return out
        p["page_token"] = tok; time.sleep(0.35)


def to_t(ts, tf):
    t = int(dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
    if tf == "1d": return t // 86400 * 86400 + 43200
    return t


def load(path):
    rows = {}
    if os.path.exists(path):
        for line in open(path):
            if line.strip(): b = json.loads(line); rows[b["t"]] = b
    return rows


def merge(repo, tf, sym, bars):
    """bars: [{"t","o","h","l","c","v"}]. Adds missing bars, fills zero volume, logs close mismatches."""
    d = os.path.join(repo, "data", "bars", tf); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, sym + ".jsonl"); rows = load(f); added = filled = fixed = 0
    for b in bars:
        old = rows.get(b["t"])
        if old is None: rows[b["t"]] = b; added += 1; continue
        if not old.get("v") and b.get("v"): old["v"] = b["v"]; filled += 1
        coarse = old["c"] < 1 and round(old["c"], 2) == old["c"] and round(b["c"], 2) != b["c"]
        if coarse:   # IBKR quotes DOGE to the cent, which destroys the bar; replace it with the full-precision bar
            v = old.get("v") or b["v"]; old.update(b); old["v"] = v; fixed += 1; continue
        if old["c"] and abs(b["c"] / old["c"] - 1) > 0.002:
            k = "%s/%s" % (tf, sym); LOG["mismatch_count"][k] = LOG["mismatch_count"].get(k, 0) + 1
            LOG["mismatch"].append({"tf": tf, "sym": sym, "t": b["t"], "stored": old["c"], "alpaca": b["c"]})
    if added or filled or fixed:
        with open(f, "w") as fh:
            for k in sorted(rows): fh.write(json.dumps(rows[k], separators=(",", ":")) + "\n")
    LOG["files"]["%s/%s" % (tf, sym)] = {"added": added, "vol_filled": filled, "coarse_fixed": fixed, "total": len(rows),
                                         "last": iso(dt.datetime.fromtimestamp(max(rows), UTC)) if rows else None}


def last_t(repo, tf, sym):
    f = os.path.join(repo, "data", "bars", tf, sym + ".jsonl"); r = load(f)
    return max(r) if r else None


def rth(t):
    x = dt.datetime.fromtimestamp(t, NY); m = x.hour * 60 + x.minute
    return x.weekday() < 5 and 570 <= m <= 955          # bar starts 09:30 .. 15:55


def conv(rows, tf, closed_before=None, step=0, filt=None):
    out = []
    for r in rows:
        t = to_t(r["t"], tf)
        if filt and not filt(t): continue
        if closed_before is not None and t + step > closed_before: continue
        out.append({"t": t, "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": float(r.get("v") or 0)})
    return out


def stock_bars(repo, syms, tf, start, end):
    tfa = {"1d": "1Day", "5m": "5Min"}[tf]; got = {}
    for i in range(0, len(syms), 30):
        chunk = syms[i:i + 30]
        try:
            got.update(paged(DATA + "/v2/stocks/bars", {"symbols": ",".join(chunk), "timeframe": tfa, "start": iso(start),
                             "end": iso(end), "limit": 10000, "adjustment": "raw", "feed": "sip", "sort": "asc"}, "bars"))
        except Exception as e: LOG["errors"].append("bars %s %s: %s" % (tf, chunk[0], e))
    cut = int(end.timestamp())
    for s, rows in got.items():
        sym = s
        if tf == "5m": merge(repo, tf, sym, conv(rows, tf, closed_before=cut, step=300, filt=rth))
        else:
            today = dt.datetime.now(NY).date()
            done = dt.datetime.now(NY).hour >= 17               # today's daily bar only once the session is final
            merge(repo, tf, sym, [b for b in conv(rows, tf)
                                  if dt.datetime.fromtimestamp(b["t"], UTC).date() < today or done])


def option_bars(repo):
    """5-minute bars of every registered option leg (data/opt_legs.json, scripts/optlegs.py) into
    data/bars/opt5m/OPT_<cid>.jsonl. Alpaca historical option bars: trades from OPRA, at least 15 minutes old on the
    free plan. A leg is marked final once it has been fetched after its expiry day."""
    p = os.path.join(repo, "data", "opt_legs.json")
    if not os.path.exists(p): return
    reg = json.load(open(p)); end = now() - dt.timedelta(minutes=16); todo = {}
    # option picks (AgentPicks asset "option", or "put" from item 57; items 57-58, 2026-11-24): register the contract
    # named in occ= and, for a debit vertical, the one in occ2=
    try:
        import re as _re
        lp = os.path.join(repo, "data", "ledger", "AgentPicks.jsonl")
        for l in (open(lp) if os.path.exists(lp) else []):
            if not l.strip(): continue
            r = json.loads(l)
            if r.get("asset") not in ("put", "option") or not str(r.get("picked_at", ""))[:10]: continue
            for m in _re.finditer(r"\bocc2?=([A-Z]{1,6}(\d{6})[CP]\d{8})\b", str(r.get("checks") or "")):
                k = "OCC_" + m.group(1)
                if k not in reg: reg[k] = {"occ": m.group(1), "expiry": "20" + m.group(2), "from": str(r["picked_at"])[:10]}
    except Exception as e: LOG["errors"].append("put legs: %s" % e)
    for cid, v in reg.items():
        if v.get("final"): continue
        lt = last_t(repo, "opt5m", "OPT_" + cid)
        frm = dt.datetime.fromisoformat(v["from"]).replace(tzinfo=NY, hour=9, minute=30)
        start = max(frm, dt.datetime.fromtimestamp(lt + 300, UTC)) if lt else frm
        todo[v["occ"]] = (cid, start)
    by = {}; res = {"legs": len(reg), "fetched": 0, "bars": 0, "no_bars": [], "errors": []}
    for o, (cid, start) in todo.items(): by.setdefault(start.astimezone(UTC).strftime("%Y-%m-%d"), []).append(o)
    got = {}; failed = set()
    for day, syms in sorted(by.items()):
        for i in range(0, len(syms), 50):
            chunk = syms[i:i + 50]
            try:
                got.update(paged(DATA + "/v1beta1/options/bars", {"symbols": ",".join(chunk), "timeframe": "5Min",
                                 "start": day + "T00:00:00Z", "end": iso(end), "limit": 10000, "sort": "asc"}, "bars"))
            except Exception as e:
                res["errors"].append("%s.. from %s: %s" % (chunk[0], day, e)); LOG["errors"].append("optbars %s: %s" % (chunk[0], e))
                failed.update(chunk)
    cut = int(end.timestamp()); today = dt.datetime.now(NY).strftime("%Y%m%d")
    for o, (cid, start) in todo.items():
        if o in failed: continue                     # request failed: keep the leg open for the next run
        rows = got.get(o, []); b = conv(rows, "opt5m", closed_before=cut, step=300, filt=rth)
        if b: merge(repo, "opt5m", "OPT_" + cid, b); res["bars"] += len(b)
        else: res["no_bars"].append(o)
        res["fetched"] += 1
        if reg[cid]["expiry"] < today: reg[cid]["final"] = True
    with open(p, "w") as f: json.dump(reg, f, indent=0, sort_keys=True); f.write("\n")
    res["at"] = iso(now()); LOG["optbars"] = res
    d = os.path.join(repo, "ops", "diag"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "optbars.json"), "w") as f: json.dump(res, f, indent=1); f.write("\n")


def crypto_bars(repo, tf, start):
    tfa = {"15m": "15Min", "1h": "1Hour", "1d": "1Day"}[tf]; step = {"15m": 900, "1h": 3600, "1d": 86400}[tf]
    try:
        got = paged(DATA + "/v1beta3/crypto/us/bars", {"symbols": ",".join(c + "/USD" for c in COINS), "timeframe": tfa,
                    "start": iso(start), "limit": 10000, "sort": "asc"}, "bars")
    except Exception as e: LOG["errors"].append("crypto %s: %s" % (tf, e)); return
    cut = int(now().timestamp())
    for s, rows in got.items():
        b = conv(rows, tf, closed_before=None if tf == "1d" else cut, step=step)
        if tf == "1d": b = [x for x in b if x["t"] - 43200 + 86400 <= cut]   # UTC day finished
        merge(repo, tf, s.split("/")[0], b)


def corp_actions(repo, syms, start):
    try:
        ca = {}
        for i in range(0, len(syms), 50):
            part = paged(DATA + "/v1/corporate-actions", {"symbols": ",".join(syms[i:i + 50]), "start": start.date().isoformat(),
                         "end": (now() + dt.timedelta(days=30)).date().isoformat(), "limit": 1000,
                         "types": "cash_dividend,forward_split,reverse_split"}, "corporate_actions")
            for k, v in part.items(): ca.setdefault(k, []).extend(v)
    except Exception as e: LOG["errors"].append("corporate actions: %s" % e); return
    per = {}
    for d in ca.get("cash_dividends", []):
        per.setdefault(d["symbol"], {"d": [], "s": []})["d"].append(
            {"ex": d["ex_date"], "value": float(d["rate"]), "announced": d.get("declaration_date"), "type": "CashDividends",
             "src": "alpaca"})
    for k in ("forward_splits", "reverse_splits"):
        for d in ca.get(k, []):
            r = float(d["new_rate"]) / float(d["old_rate"])
            per.setdefault(d["symbol"], {"d": [], "s": []})["s"].append({"date": d["ex_date"], "ratio": r, "src": "alpaca"})
    os.makedirs(os.path.join(repo, "data", "corp"), exist_ok=True); n = 0
    for sym, x in per.items():
        f = os.path.join(repo, "data", "corp", sym + ".json")
        c = json.load(open(f)) if os.path.exists(f) else {"dividends": [], "splits": []}
        dv = {e["ex"]: e for e in c.get("dividends", [])}; sp = {e["date"]: e for e in c.get("splits", [])}
        for e in x["d"]: dv.setdefault(e["ex"], e)
        for e in x["s"]: sp.setdefault(e["date"], e)
        c["dividends"] = sorted(dv.values(), key=lambda e: e["ex"]); c["splits"] = sorted(sp.values(), key=lambda e: e["date"])
        c["fetched"] = dt.datetime.now(NY).date().isoformat()
        json.dump(c, open(f, "w"), indent=1); n += 1
    LOG["corp_symbols"] = n


def cboe(repo, full, to_hist=False):
    for sym in ("VIX", "VIX3M"):
        try:
            raw = get("https://cdn.cboe.com/api/global/us_indices/daily_prices/%s_History.csv" % sym, None, auth=False).decode()
        except Exception as e: LOG["errors"].append("cboe %s: %s" % (sym, e)); continue
        bars = []
        for r in csv.DictReader(io.StringIO(raw)):
            r = {k.strip().upper(): v for k, v in r.items()}
            try:
                d = dt.datetime.strptime(r["DATE"], "%m/%d/%Y").replace(tzinfo=UTC)
                bars.append({"t": int(d.timestamp()) + 43200, "o": float(r["OPEN"]), "h": float(r["HIGH"]),
                             "l": float(r["LOW"]), "c": float(r["CLOSE"]), "v": 0.0})
            except (KeyError, ValueError): continue
        if to_hist:
            write_hist(repo, "1d", sym, [b for b in bars if b["t"] >= 1451606400]); continue   # since 2016-01-01
        cut = int((now() - dt.timedelta(days=760 if full else 20)).timestamp())
        merge(repo, "1d", sym, [b for b in bars if b["t"] >= cut])


def write_hist(repo, tf, sym, bars):
    import gzip
    d = os.path.join(repo, "data", "hist", tf); os.makedirs(d, exist_ok=True)
    with gzip.open(os.path.join(d, sym + ".csv.gz"), "wt") as f:
        f.write("t,o,h,l,c,v\n")
        for b in sorted(bars, key=lambda b: b["t"]): f.write("%d,%s,%s,%s,%s,%s\n" % (b["t"], b["o"], b["h"], b["l"], b["c"], b["v"]))
    LOG["files"]["hist/%s/%s" % (tf, sym)] = {"added": len(bars), "vol_filled": 0, "total": len(bars),
                                              "first": iso(dt.datetime.fromtimestamp(min(b["t"] for b in bars), UTC)) if bars else None}


def hist(repo, syms, tf, start, end):
    tfa = {"1d": "1Day", "5m": "5Min"}[tf]
    for i in range(0, len(syms), 10 if tf == "5m" else 30):
        chunk = syms[i:i + (10 if tf == "5m" else 30)]
        try:
            got = paged(DATA + "/v2/stocks/bars", {"symbols": ",".join(chunk), "timeframe": tfa, "start": iso(start),
                        "end": iso(end), "limit": 10000, "adjustment": "raw", "feed": "sip", "sort": "asc"}, "bars")
        except Exception as e: LOG["errors"].append("hist %s %s: %s" % (tf, chunk[0], e)); continue
        for s, rows in got.items():
            write_hist(repo, tf, s, conv(rows, tf, filt=rth if tf == "5m" else None))


def borrow(repo, syms):
    """Stock-loan fee and shares available to short, from Interactive Brokers' public short-stock file (no account, no
    key; best effort). One small file per day in data/borrow/; library.py charges the real fee on shorts from the first
    day a file exists and keeps the flat 0.5%/year before that or when the file is missing."""
    try:
        import ftplib
        buf = []; f = ftplib.FTP("ftp3.interactivebrokers.com", timeout=15); f.login("shortstock", "")
        f.retrlines("RETR usa.txt", buf.append); f.quit()
        want = set(syms); out = {}; stamp = None
        for line in buf:
            if line.startswith("#BOF"): stamp = line[:60]
            if line.startswith("#"): continue
            c = line.split("|")
            if len(c) >= 8 and c[0] in want:
                try: out[c[0]] = {"fee": float(c[6]), "avail": int(c[7].replace(">", "").replace(",", "") or 0), "cap": c[7].startswith(">")}
                except ValueError: pass
        if len(out) < 20: raise RuntimeError("only %d symbols parsed" % len(out))
        os.makedirs(os.path.join(repo, "data", "borrow"), exist_ok=True)
        day = now().astimezone(ZoneInfo("America/New_York")).date().isoformat()
        json.dump({"day": day, "source": "IBKR public short-stock file usa.txt", "file_stamp": stamp, "rows": out},
                  open(os.path.join(repo, "data", "borrow", day + ".json"), "w"), separators=(",", ":"))
        LOG["borrow_symbols"] = len(out)
    except Exception as e: LOG["errors"].append("borrow file: %s" % str(e)[:120])


def pit(repo, start="2024-01-01", end="2026-11-14"):
    """Point-in-time S&P 500 membership and prices (free build, owner decision 2026-11-21). One-off.
    Membership: the community file "S&P 500 Historical Components & Changes" (github.com/fja05680/sp500, compiled from
    Wikipedia's change lists; one row per change date with every member on that date). Prices: Alpaca daily bars, fully
    adjusted, for every symbol that was a member at any time in the window, INCLUDING the ones that later left; a
    symbol that left is requested "as of" its last member date, so a later reuse of the ticker is not picked up.
    Output: data/pit/sp500_members.csv.gz (the source file, unchanged), data/pit/bars_1d.csv.gz (sym,date,o,h,l,c,v),
    data/pit/source.json (file name, last change date, symbols asked and found). Read only by library.py --pit."""
    import gzip
    def gh(url):
        h = {"User-Agent": "quantavius-forward-test/1.0", "Accept": "application/vnd.github+json"}
        if os.environ.get("GH_TOKEN") and "api.github.com" in url: h["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r: return r.read()
    files = [f for f in json.loads(gh("https://api.github.com/repos/fja05680/sp500/contents/"))
             if f["name"].lower().endswith(".csv") and "historical components" in f["name"].lower()]
    def fdate(f):
        import re
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", f["name"]); return (m.group(3), m.group(1), m.group(2)) if m else ("0", "0", "0")
    upd = [x for x in files if "updated" in x["name"].lower()]       # the maintained file; the undated one stops in 2019
    f = upd[0] if upd else sorted(files, key=fdate)[-1]; raw = gh(f["download_url"])
    out = os.path.join(repo, "data", "pit"); os.makedirs(out, exist_ok=True)
    with gzip.open(os.path.join(out, "sp500_members.csv.gz"), "wb") as fh: fh.write(raw)
    rows = [(r[0], [t.strip() for t in r[1].split(",") if t.strip()]) for r in list(csv.reader(io.StringIO(raw.decode("utf-8"))))[1:] if len(r) >= 2]
    rows.sort(); last_change = rows[-1][0]
    seen = {}; prev = None
    for d, ts in rows:
        if d < start: prev = (d, ts); continue
        if prev: 
            for t in prev[1]: seen.setdefault(t, [start, start])
            prev = None
        for t in ts: seen.setdefault(t, [d, d])[1] = d
    if prev:
        for t in prev[1]: seen.setdefault(t, [start, start])
    current = set(rows[-1][1]); gone = sorted(t for t in seen if t not in current); cur = sorted(current)
    S0 = dt.datetime.fromisoformat(start).replace(tzinfo=UTC); E0 = dt.datetime.fromisoformat(end).replace(tzinfo=UTC)
    base = {"timeframe": "1Day", "start": iso(S0), "end": iso(E0), "limit": 10000, "adjustment": "all", "feed": "sip", "sort": "asc"}
    got = {}
    for i in range(0, len(cur), 25):
        try: got.update(paged(DATA + "/v2/stocks/bars", dict(base, symbols=",".join(cur[i:i + 25])), "bars"))
        except Exception as e: LOG["errors"].append("pit bars %s: %s" % (cur[i], str(e)[:120]))
        time.sleep(0.4)
    for t in gone:
        try:
            g = paged(DATA + "/v2/stocks/bars", dict(base, symbols=t, asof=seen[t][1]), "bars")
            if g: got[t] = next(iter(g.values()))
        except Exception as e: LOG["errors"].append("pit bars %s: %s" % (t, str(e)[:120]))
        time.sleep(0.35)
    n = 0
    with gzip.open(os.path.join(out, "bars_1d.csv.gz"), "wt") as fh:
        fh.write("sym,date,o,h,l,c,v\n")
        for sym in sorted(got):
            for r in got[sym]:
                fh.write("%s,%s,%s,%s,%s,%s,%d\n" % (sym, r["t"][:10], r["o"], r["h"], r["l"], r["c"], int(r.get("v") or 0))); n += 1
    json.dump({"fetched": now().isoformat(timespec="seconds"), "source": "github.com/fja05680/sp500", "file": f["name"], "file_sha": f.get("sha"),
               "last_change_date": last_change, "window": [start, end], "members_ever_in_window": len(seen), "current": len(cur),
               "left_in_window": gone, "symbols_with_bars": len(got), "symbols_without_bars": sorted(t for t in seen if t not in got),
               "bars": n, "prices": "Alpaca SIP daily, adjustment=all"}, open(os.path.join(out, "source.json"), "w"), indent=1)
    LOG["pit"] = {"symbols": len(got), "bars": n, "missing": len(seen) - len(got)}


def main():
    T0 = time.time()
    mode, repo = sys.argv[1], sys.argv[2]
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    stocks = U["watchlist"] + U["control"]; etfs = [e for e in U["etfs"] if not e.startswith("VIX")]
    univ = sorted(set(stocks) | {s for s in U.get("universe", []) if s != "GOOG"})
    intr = (univ if U.get("intraday_wide") else stocks) + INTRA_ETFS      # symbols with 5-minute bars (the foundation's)
    # WIDE DATA (2026-11-23): 5-minute bars for the rest of the universe as well, for research and ML only. Fetched AFTER
    # the core symbols and skipped when the run is already slow, so the engine's 44 stocks are never delayed and a tick
    # stays under one billed minute. Skips are logged (LOG["wide_skipped"]) and shown by `checks.py health`.
    extra = [s for s in univ if s not in intr] if U.get("intraday_wide_data") and not U.get("intraday_wide") else []
    WIDE_BUDGET_S = 20
    end = now() - dt.timedelta(minutes=16)                  # free plan: SIP data must be at least 15 minutes old
    LOG.update({"mode": mode, "started": iso(now())})
    if mode == "tick":
        mode = "intraday"; LOG["tick"] = True
    if mode == "intraday":
        lt = [last_t(repo, "5m", s) for s in intr]
        known = [t for t in lt if t]
        sess = dt.datetime.now(NY).replace(hour=9, minute=30, second=0, microsecond=0)
        start = min(known) + 300 if known and len(known) == len(lt) else int(sess.timestamp())
        start = max(start, int((now() - dt.timedelta(days=5)).timestamp()))
        if start < int(end.timestamp()) - 60:      # never ask for a window that ends before it starts (pre-market)
            stock_bars(repo, intr, "5m", dt.datetime.fromtimestamp(start, UTC), end)
        if extra:
            if time.time() - T0 < WIDE_BUDGET_S:
                lx = [last_t(repo, "5m", s) for s in extra]; kx = [t for t in lx if t]
                # start from the oldest STORED bar of the wide symbols (a symbol with no bars yet must not push the
                # start to the session open, which before 09:46 New York is later than the free plan's newest data
                # and makes Alpaca refuse the whole batch: fixed 2026-11-23 after BK had no bars)
                sx = min(kx) + 300 if kx else int((now() - dt.timedelta(days=5)).timestamp())
                sx = max(sx, int((now() - dt.timedelta(days=5)).timestamp()))
                if sx < int(end.timestamp()) - 60:
                    stock_bars(repo, extra, "5m", dt.datetime.fromtimestamp(sx, UTC), end); LOG["wide_symbols"] = len(extra)
                LOG["wide_missing"] = [s for s, t in zip(extra, lx) if not t]
            else: LOG["wide_skipped"] = round(time.time() - T0, 1)
        if not LOG.get("tick") or now().minute % 15 < 5:
            crypto_bars(repo, "15m", now() - dt.timedelta(hours=12)); crypto_bars(repo, "1h", now() - dt.timedelta(days=2))
    elif mode == "nightly":
        stock_bars(repo, univ + etfs, "1d", now() - dt.timedelta(days=15), end)
        try:                                    # daily bars of the AI's own stock picks (scripts/picks.py, 2026-11-23)
            import ledger
            cut = (now() - dt.timedelta(days=30)).strftime("%Y-%m-%d")
            pk = sorted({r["symbol"] for r in ledger.load(repo, "AgentPicks") if r.get("asset") == "stock"
                         and str(r.get("picked_at"))[:10] >= cut and str(r.get("symbol", "")).isalpha()} - set(univ + etfs))
            if pk: stock_bars(repo, pk, "1d", now() - dt.timedelta(days=15), end)
            LOG["pick_symbols"] = len(pk)
        except Exception as e: LOG["errors"].append("pick bars: %s" % e)
        stock_bars(repo, intr + extra, "5m", now() - dt.timedelta(hours=10), end)   # the session's last bars (wide data too)
        crypto_bars(repo, "1d", now() - dt.timedelta(days=15))
        crypto_bars(repo, "15m", now() - dt.timedelta(hours=12)); crypto_bars(repo, "1h", now() - dt.timedelta(days=2))
        corp_actions(repo, univ + etfs, now() - dt.timedelta(days=60)); cboe(repo, False)
        borrow(repo, univ + etfs); option_bars(repo)
    elif mode == "optbars":       # requested by the deep OTM + weekly options task (ops/fetch_request.json)
        option_bars(repo)
    elif mode == "pit":
        pit(repo)
    elif mode == "borrow":
        borrow(repo, univ + etfs)
    elif mode == "hist":
        hist(repo, univ + etfs, "1d", dt.datetime(2016, 1, 1, tzinfo=UTC), end)
        hist(repo, intr, "5m", now() - dt.timedelta(days=731), end)
        corp_actions(repo, univ + etfs, dt.datetime(2015, 6, 1, tzinfo=UTC)); cboe(repo, True, to_hist=True)
    elif mode == "crypto":        # scheduled around the clock, so the crypto tasks need no IBKR bars
        crypto_bars(repo, "15m", now() - dt.timedelta(hours=12)); crypto_bars(repo, "1h", now() - dt.timedelta(days=2))
        crypto_bars(repo, "1d", now() - dt.timedelta(days=5))
    elif mode == "etfs":          # one-off: history for ETFs added to universe.json
        stock_bars(repo, etfs, "1d", now() - dt.timedelta(days=740), end)
        corp_actions(repo, etfs, dt.datetime(2015, 6, 1, tzinfo=UTC)); hist(repo, etfs, "1d", dt.datetime(2016, 1, 1, tzinfo=UTC), end)
    elif mode == "wide5m":        # one-off: 90 days of stored 5-minute bars + the 2-year archive for the whole universe
        stock_bars(repo, univ + INTRA_ETFS, "5m", now() - dt.timedelta(days=92), end)
        have = {f[:-7] for f in os.listdir(os.path.join(repo, "data", "hist", "5m"))} if os.path.isdir(os.path.join(repo, "data", "hist", "5m")) else set()
        need = [s for s in univ if s not in have]; LOG["wide_hist_symbols"] = len(need)
        if need: hist(repo, need, "5m", now() - dt.timedelta(days=731), end)
    elif mode == "universe":
        stock_bars(repo, univ, "1d", now() - dt.timedelta(days=740), end)
        corp_actions(repo, univ, now() - dt.timedelta(days=1100))
    elif mode == "backfill":
        stock_bars(repo, univ + etfs, "1d", now() - dt.timedelta(days=740), end)
        stock_bars(repo, intr, "5m", now() - dt.timedelta(days=92), end)
        crypto_bars(repo, "1d", now() - dt.timedelta(days=740)); crypto_bars(repo, "1h", now() - dt.timedelta(days=366))
        crypto_bars(repo, "15m", now() - dt.timedelta(days=92))
        corp_actions(repo, univ + etfs, now() - dt.timedelta(days=1100)); cboe(repo, True)
    else: sys.exit("unknown mode " + mode)
    LOG["finished"] = iso(now()); LOG["mismatch"] = LOG["mismatch"][-200:]
    os.makedirs(os.path.join(repo, "ops", "diag"), exist_ok=True)
    json.dump(LOG, open(os.path.join(repo, "ops", "diag", "fetch_free.json"), "w"), indent=1)
    try:      # plumbing health: when each run happened and how long it took (ops/diag/ticks.json)
        import checks; checks.tick_log(repo, "tick" if LOG.get("tick") else mode, time.time() - T0)
    except Exception as e: print("tick log failed:", e)
    print(json.dumps({"mode": mode, "files": len(LOG["files"]), "added": sum(v["added"] for v in LOG["files"].values()),
                      "errors": LOG["errors"][:5], "mismatch": len(LOG["mismatch"])}))


if __name__ == "__main__":
    main()
