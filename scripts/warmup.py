"""Warm-up daily bars 2014-07-01 to 2015-12-31 (build_todo item 13; owner decisions 2026-11-26).

Purpose: LOOK-BACK ONLY. The tuning window stays 2016-2021 and 2022 onwards stays held out. These bars let a strategy
with a long look-back (for example 250 days) signal from January 2016, and let the point-in-time lists (scripts/pitu.py)
start before 2016-03. A signal or a result dated before 2016-01-04 is never scored.

Sources (owner: combine them; raw prices are committed because this is a personal project):
  Tiingo end-of-day (env TIINGO_API_KEY): the bulk, split- and dividend-adjusted prices in one call. Free limits:
      50 requests an hour, 1,000 a day, 500 unique symbols a calendar month. This script stays under 45 / 950 / 490.
  Alpha Vantage (env ALPHAVANTAGE_API_KEY): every symbol Tiingo has nothing for, and a cross-check of 30 symbols.
      TIME_SERIES_DAILY (full) gives raw prices; SPLITS gives the split dates, and the split adjustment is done here.
      Dividends are NOT adjusted for these rows ("adj": "split"). Stays under 24 calls a UTC day.
  Cboe: VIX and VIX3M (public files, no key).
One source per symbol for its whole span: the sources are never mixed or averaged inside a series.

Symbols: every S&P 500 member at any time from 2014-07-01 to 2016-02-29 (data/pit/sp500_members.csv.gz), under the
member file's ticker (the key the point-in-time bars use), plus every archive symbol in data/hist/1d that already has a
bar on 2016-01-04 (the S&P 100 + ETFs). A ticker the providers no longer know is retried under a known later name
(ALIASES), and the row keeps the member ticker.

Joining: Tiingo and Alpaca are both fully adjusted as of their fetch date, so they should meet at the same level. Each
warm-up series is still scaled so that its close on the first common day from 2016-01-04 equals the stored Alpaca close
(data/pit/bars_1d.csv.gz, else data/hist/1d). The factor is reported (about 1 for Tiingo; for Alpha Vantage rows it is
the dividend factor). The returns on the common days 2016-01-05 to 2016-02-29 are compared with Alpaca's: a symbol
passes if they agree within 0.1% on at least 99% of the days. Names that left before 2016 have no common days and are
marked "no_overlap".

  python3 warmup.py run REPO       -> one rate-limited step (the warmup workflow runs it every hour until complete)
  python3 warmup.py status REPO    -> progress
  python3 warmup.py build REPO     -> data/pit/warmup/bars_1d.csv.gz + data/pit/warmup/check.json (run by `run` at the end)
  Python: warmup.bars(repo) -> {sym: {date: (o, h, l, c, v)}}; warmup.merge_into(bars) adds the rows to pit.load()'s
          bars before any stored date (pitu.lists uses it when it rebuilds the cache).
Read-only market data: nothing here touches orders or accounts.
"""
import csv, gzip, hashlib, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request, datetime as dt

START, END, FETCH_END, SEAM = "2014-07-01", "2015-12-31", "2016-02-29", "2016-01-04"
W = os.path.join("data", "pit", "warmup")
TI_HOUR, TI_DAY, TI_MONTH, AV_DAY = 45, 950, 490, 24
N_XCHECK, N_XCHECK_DEPARTED = 30, 5
# Later names of tickers in the member file, tried only after the member ticker itself returns nothing.
ALIASES = {"FB": "META", "ANTM": "ELV", "PCLN": "BKNG", "BBT": "TFC", "HRS": "LHX", "COG": "CTRA", "UTX": "RTX",
           "SYMC": "GEN", "HCN": "WELL", "KORS": "CPRI", "CBS": "PARA", "ABC": "COR", "DISCA": "WBD", "ADS": "BFH"}
UA = {"User-Agent": "quantavius-forward-test/1.0"}


def P(repo, *a): return os.path.join(repo, W, *a)
def jload(f, d):
    try: return json.load(open(f))
    except (OSError, ValueError): return d
def jsave(f, o):
    os.makedirs(os.path.dirname(f), exist_ok=True); json.dump(o, open(f + ".tmp", "w"), indent=1, sort_keys=True); os.replace(f + ".tmp", f)
def utcnow(): return dt.datetime.now(dt.timezone.utc)


# ---------- symbols ----------
def members_in_window(repo):
    rows = list(csv.reader(io.StringIO(gzip.open(os.path.join(repo, "data", "pit", "sp500_members.csv.gz"), "rt").read())))[1:]
    rows = sorted((r[0], [t.strip() for t in r[1].split(",") if t.strip()]) for r in rows if len(r) >= 2)
    need, last = set(), None
    for d, ts in rows:
        if d < START: last = ts; continue
        if d > FETCH_END: break
        need |= set(ts)
    if last: need |= set(last)
    return need


def hist_close(repo, sym):
    """{date: close} of the stored archive for sym (data/hist/1d), or {}."""
    f = os.path.join(repo, "data", "hist", "1d", sym.replace("/", "_") + ".csv.gz")
    if not os.path.exists(f): return {}
    out = {}
    with gzip.open(f, "rt") as fh:
        for r in csv.DictReader(fh):
            out[dt.datetime.fromtimestamp(int(r["t"]), dt.timezone.utc).date().isoformat()] = float(r["c"])
    return out


def archive_symbols(repo):
    d = os.path.join(repo, "data", "hist", "1d"); out = set()
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        s = f[:-7] if f.endswith(".csv.gz") else None
        if s and s not in ("VIX", "VIX3M") and SEAM in hist_close(repo, s): out.add(s)
    return out


def universe(repo):
    return sorted(members_in_window(repo) | archive_symbols(repo))


# ---------- providers ----------
class RateLimited(Exception): pass
class Refused(Exception): pass


def http(url, headers=None, tries=3):
    h = dict(UA); h.update(headers or {})
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r: return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:400]
            if e.code == 429: raise RateLimited(body.decode("utf-8", "replace"))
            if e.code in (500, 502, 503, 504) and k < tries - 1: time.sleep(3 + 5 * k); continue
            return e.code, body
        except urllib.error.URLError:
            if k < tries - 1: time.sleep(3 + 5 * k); continue
            raise


def tiingo(ticker):
    """-> list of rows (date, o, h, l, c, v) adjusted, plus split dates; [] when Tiingo has no rows; None when unknown."""
    q = urllib.parse.urlencode({"startDate": START, "endDate": FETCH_END, "format": "json", "resampleFreq": "daily"})
    code, body = http("https://api.tiingo.com/tiingo/daily/%s/prices?%s" % (urllib.parse.quote(ticker.replace(".", "-")), q),
                      {"Authorization": "Token " + os.environ["TIINGO_API_KEY"], "Content-Type": "application/json"})
    if code == 404: return None, []
    if code != 200: raise Refused("tiingo HTTP %s: %s" % (code, body[:200]))
    j = json.loads(body)
    if isinstance(j, dict): raise Refused("tiingo: %s" % str(j)[:200])
    rows, splits = [], []
    for r in j:
        d = r["date"][:10]
        rows.append((d, r["adjOpen"], r["adjHigh"], r["adjLow"], r["adjClose"], r["adjVolume"]))
        if float(r.get("splitFactor") or 1) != 1: splits.append(d)
    return rows, splits


def av(function, ticker, **kw):
    q = dict(function=function, symbol=ticker.replace(".", "-"), apikey=os.environ["ALPHAVANTAGE_API_KEY"], **kw)
    code, body = http("https://www.alphavantage.co/query?" + urllib.parse.urlencode(q))
    if code != 200: raise Refused("alphavantage HTTP %s" % code)
    txt = body.decode("utf-8", "replace")
    if txt.lstrip().startswith("{"):
        j = json.loads(txt)
        msg = j.get("Note") or j.get("Information")
        if msg and "premium" in msg.lower(): raise Refused("alphavantage premium only: " + msg[:280])
        if msg and ("frequency" in msg.lower() or "rate limit" in msg.lower() or "per day" in msg.lower()): raise RateLimited(msg[:300])
        if msg: raise Refused("alphavantage: " + msg[:280])
        return j
    return txt


def alphavantage(ticker):
    """-> (rows split-adjusted to the latest split, split dates in range, raw rows); rows [] when no data in range."""
    txt = av("TIME_SERIES_DAILY", ticker, outputsize="full", datatype="csv")
    if isinstance(txt, dict):
        if "Error Message" in txt: return None, [], []
        raise Refused("alphavantage: %s" % str(txt)[:200])
    raw = []
    for r in csv.DictReader(io.StringIO(txt)):
        d = r.get("timestamp") or r.get("date")
        if d and START <= d <= FETCH_END:
            raw.append((d, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])))
    raw.sort()
    if not raw: return [], [], []
    sp = av("SPLITS", ticker)
    sp = [(x["effective_date"], float(x["split_factor"])) for x in (sp.get("data") or [])] if isinstance(sp, dict) else []
    rows = []
    for d, o, h, l, c, v in raw:
        f = 1.0
        for e, k in sp:
            if e > d and k > 0: f *= k          # a later split: earlier prices divide by its factor
        rows.append((d, o / f, h / f, l / f, c / f, v * f))
    return rows, sorted(e for e, _ in sp if START <= e <= FETCH_END), raw


def cboe(sym):
    code, body = http("https://cdn.cboe.com/api/global/us_indices/daily_prices/%s_History.csv" % sym)
    if code != 200: raise Refused("cboe HTTP %s" % code)
    rows = []
    for r in csv.DictReader(io.StringIO(body.decode())):
        r = {k.strip().upper(): v for k, v in r.items()}
        try: d = dt.datetime.strptime(r["DATE"], "%m/%d/%Y").date().isoformat()
        except (KeyError, ValueError): continue
        if START <= d <= FETCH_END: rows.append((d, float(r["OPEN"]), float(r["HIGH"]), float(r["LOW"]), float(r["CLOSE"]), 0.0))
    return rows


# ---------- storage ----------
def write_raw(repo, source, sym, rows, splits=None, extra=None):
    f = P(repo, "raw", source, sym.replace("/", "_") + ".csv.gz"); os.makedirs(os.path.dirname(f), exist_ok=True)
    with gzip.open(f, "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "o", "h", "l", "c", "v"])
        for r in rows: w.writerow([r[0]] + ["%.6g" % x for x in r[1:]])
    if splits is not None or extra:
        jsave(f[:-7] + ".meta.json", dict(splits=splits or [], **(extra or {})))


def read_raw(repo, source, sym):
    f = P(repo, "raw", source, sym.replace("/", "_") + ".csv.gz")
    if not os.path.exists(f): return []
    with gzip.open(f, "rt") as fh:
        return [(r["date"], float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"])) for r in csv.DictReader(fh)]


def read_meta(repo, source, sym): return jload(P(repo, "raw", source, sym.replace("/", "_") + ".meta.json"), {})


# ---------- state ----------
def state(repo):
    s = jload(P(repo, "state.json"), {})
    s.setdefault("symbols", {}); s.setdefault("tiingo", {}); s.setdefault("av", {}); s.setdefault("xcheck", {})
    for sym in universe(repo): s["symbols"].setdefault(sym, {"status": "pending", "tried": []})
    s.setdefault("cboe", {"VIX": "pending", "VIX3M": "pending"})
    return s


def _bucket(b, key, val):
    if b.get(key) != val: b[key] = val; b["n_" + key] = 0


def ti_room(s, sym):
    t = s["tiingo"]; n = utcnow()
    _bucket(t, "hour", n.strftime("%Y-%m-%dT%H")); _bucket(t, "day", n.strftime("%Y-%m-%d"))
    m = t.setdefault("months", {}).setdefault(n.strftime("%Y-%m"), [])
    if t["n_hour"] >= TI_HOUR or t["n_day"] >= TI_DAY: return False
    return sym in m or len(m) < TI_MONTH


def ti_used(s, sym):
    t = s["tiingo"]; t["n_hour"] += 1; t["n_day"] += 1
    m = t["months"][utcnow().strftime("%Y-%m")]
    if sym not in m: m.append(sym)


def av_room(s, calls=2):
    a = s["av"]; _bucket(a, "day", utcnow().strftime("%Y-%m-%d"))
    return not a.get("refused") and a["n_day"] + calls <= AV_DAY


def xcheck_list(s, repo):
    """30 symbols for the two-source cross-check: 25 survivors and 5 departed names (left before 2016-03), both covered
    by Tiingo, chosen by a fixed hash so the choice does not depend on any result."""
    if s.get("xcheck_list"): return s["xcheck_list"]
    pit = pit_symbols(repo); mem = members_in_window(repo)
    ok = [x for x, v in s["symbols"].items() if v.get("status") == "ok" and v.get("source") == "tiingo"]
    h = lambda x: hashlib.sha256(x.encode()).hexdigest()
    dep = sorted((x for x in ok if x not in pit and x in mem), key=h)[:N_XCHECK_DEPARTED]
    sur = sorted((x for x in ok if x in pit), key=h)[:N_XCHECK - len(dep)]
    s["xcheck_list"] = sorted(dep + sur)
    return s["xcheck_list"]


def run(repo):
    for k in ("TIINGO_API_KEY", "ALPHAVANTAGE_API_KEY"):
        if not os.environ.get(k): print(json.dumps({"error": "%s is not set (GitHub Actions secret)" % k})); return 2
    s = state(repo); log = {"at": utcnow().isoformat(timespec="seconds"), "tiingo": 0, "av": 0, "notes": []}
    if s.get("complete"): print(json.dumps({"complete": True})); return 0
    for v in ("VIX", "VIX3M"):
        if s["cboe"].get(v) == "pending":
            try: rows = cboe(v); write_raw(repo, "cboe", v, rows); s["cboe"][v] = "ok %d rows" % len(rows)
            except Exception as e: s["cboe"][v] = "pending"; log["notes"].append("cboe %s: %s" % (v, e))
    try:
        # 1) Tiingo for every pending symbol: the member ticker first, then its later name.
        for sym, v in sorted(s["symbols"].items()):
            if v["status"] != "pending": continue
            tickers = [sym] + ([ALIASES[sym]] if sym in ALIASES else [])
            todo = [t for t in tickers if "tiingo:" + t not in v["tried"]]
            if not todo: v["status"] = "need_av"; continue
            for t in todo:
                if not ti_room(s, sym): raise RateLimited("tiingo budget for this hour, day or month")
                rows, splits = tiingo(t); ti_used(s, sym); log["tiingo"] += 1; v["tried"].append("tiingo:" + t)
                if rows and any(r[0] <= END for r in rows):
                    write_raw(repo, "tiingo", sym, rows, splits, {"ticker": t})
                    v.update(status="ok", source="tiingo", ticker=t, rows=len(rows)); break
            else: v["status"] = "need_av"
        # 2) Alpha Vantage for what Tiingo did not have.
        for sym, v in sorted(s["symbols"].items()):
            if v["status"] != "need_av": continue
            tickers = [sym] + ([ALIASES[sym]] if sym in ALIASES else [])
            todo = [t for t in tickers if "av:" + t not in v["tried"]]
            for t in todo:
                if not av_room(s): raise RateLimited("alphavantage budget for today")
                rows, splits, _ = alphavantage(t); s["av"]["n_day"] += 2 if rows else 1; log["av"] += 1; v["tried"].append("av:" + t)
                if rows and any(r[0] <= END for r in rows):
                    write_raw(repo, "alphavantage", sym, rows, splits, {"ticker": t, "adj": "split"})
                    v.update(status="ok", source="alphavantage", ticker=t, rows=len(rows)); break
            else: v["status"] = "missing"
        # 3) Cross-check: Alpha Vantage for 30 symbols Tiingo covered.
        for sym in xcheck_list(s, repo):
            if s["xcheck"].get(sym): continue
            if not av_room(s): raise RateLimited("alphavantage budget for today")
            t = s["symbols"][sym].get("ticker", sym)
            rows, splits, _ = alphavantage(t); s["av"]["n_day"] += 2 if rows else 1; log["av"] += 1
            if rows: write_raw(repo, "xcheck_av", sym, rows, splits, {"ticker": t, "adj": "split"})
            s["xcheck"][sym] = "ok" if rows else "no_rows"
    except RateLimited as e:
        log["notes"].append("stopped for this run: %s" % e)
    except Refused as e:
        log["notes"].append("refused: %s" % e)
        if "alphavantage" in str(e).lower() or "premium" in str(e).lower(): s["av"]["refused"] = str(e)[:300]
    if s["av"].get("refused"):      # no Alpha Vantage: what Tiingo lacks stays missing, and the cross-check is skipped
        for v in s["symbols"].values():
            if v["status"] == "need_av": v.update(status="missing", why="alphavantage refused")
    done = all(v["status"] in ("ok", "missing") for v in s["symbols"].values()) and all(x.startswith("ok") for x in s["cboe"].values())
    xc_done = s["av"].get("refused") or (s.get("xcheck_list") and all(s["xcheck"].get(x) for x in s["xcheck_list"]))
    if done and xc_done:
        res = build(repo, s); s["complete"] = True; log["built"] = res["summary"]
        rebuild_lists(repo); log["notes"].append("pit lists rebuilt with the warm-up bars")
    s.setdefault("runs", []).append(log); s["runs"] = s["runs"][-200:]
    jsave(P(repo, "state.json"), s)
    print(json.dumps(dict(log, progress=progress(s)), indent=1))
    return 0


def progress(s):
    c = {}
    for v in s["symbols"].values(): c[v["status"]] = c.get(v["status"], 0) + 1
    return {"symbols": len(s["symbols"]), "by_status": c, "xcheck": "%d/%d" % (sum(1 for x in s.get("xcheck_list") or [] if s["xcheck"].get(x)), len(s.get("xcheck_list") or [])),
            "av_refused": s["av"].get("refused"), "complete": bool(s.get("complete"))}


# ---------- build and checks ----------
def pit_symbols(repo):
    out = set()
    with gzip.open(os.path.join(repo, "data", "pit", "bars_1d.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh): out.add(r["sym"])
    return out


def alpaca_closes(repo, syms):
    """{sym: {date: close}} for 2016-01-04..2016-02-29 from the point-in-time bars, else the archive."""
    out = {}
    with gzip.open(os.path.join(repo, "data", "pit", "bars_1d.csv.gz"), "rt") as fh:
        for r in csv.DictReader(fh):
            if r["sym"] in syms and SEAM <= r["date"] <= FETCH_END: out.setdefault(r["sym"], {})[r["date"]] = float(r["c"])
    for s in syms:
        if s not in out:
            h = {d: c for d, c in hist_close(repo, s).items() if SEAM <= d <= FETCH_END}
            if h: out[s] = h
    return out


def rets(closes, days):
    return {b: closes[b] / closes[a] - 1 for a, b in zip(days, days[1:]) if closes.get(a) and closes.get(b)}


def agree(r1, r2, tol=0.001):
    common = sorted(set(r1) & set(r2))
    if not common: return None, 0
    return sum(1 for d in common if abs(r1[d] - r2[d]) <= tol) / len(common), len(common)


def build(repo, s=None):
    s = s or state(repo)
    ok = {x: v for x, v in s["symbols"].items() if v["status"] == "ok"}
    alp = alpaca_closes(repo, set(ok))
    out_rows, per = [], {}
    for sym, v in sorted(ok.items()):
        rows = read_raw(repo, v["source"], sym); meta = read_meta(repo, v["source"], sym)
        wc = {r[0]: r[4] for r in rows}; a = alp.get(sym, {})
        common = sorted(set(wc) & set(a))
        k, info = 1.0, {"source": v["source"], "ticker": v.get("ticker", sym), "adj": meta.get("adj", "split+dividend"),
                        "rows_warmup": sum(1 for r in rows if r[0] <= END), "splits_in_range": meta.get("splits", [])}
        if common:
            k = a[common[0]] / wc[common[0]]
            share, n = agree(rets(wc, common), rets(a, common))
            info.update(seam_day=common[0], scale=round(k, 6), overlap_days=n, overlap_agree=None if share is None else round(share, 4),
                        overlap_pass=bool(share is not None and share >= 0.99),
                        scale_suspicious=bool(v["source"] == "tiingo" and abs(k - 1) > 0.05))
        else:
            info.update(seam_day=None, scale=1.0, overlap="no_overlap (left before 2016 or no stored 2016 bars)")
        per[sym] = info
        for d, o, h, l, c, vol in rows:
            if d <= END: out_rows.append((sym, d, o * k, h * k, l * k, c * k, vol, v["source"]))
    for vx in ("VIX", "VIX3M"):
        rows = read_raw(repo, "cboe", vx)
        per[vx] = {"source": "cboe", "rows_warmup": sum(1 for r in rows if r[0] <= END)}
        out_rows += [(vx, d, o, h, l, c, vol, "cboe") for d, o, h, l, c, vol in rows if d <= END]
    f = P(repo, "bars_1d.csv.gz")
    with gzip.open(f, "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["sym", "date", "o", "h", "l", "c", "v", "source"])
        for r in sorted(out_rows): w.writerow([r[0], r[1]] + ["%.6g" % x for x in r[2:7]] + [r[7]])
    # two-source cross-check
    xc = {}
    for sym in s.get("xcheck_list") or []:
        avr = read_raw(repo, "xcheck_av", sym); ti = read_raw(repo, "tiingo", sym)
        if not avr or not ti: xc[sym] = {"result": s["xcheck"].get(sym) or "not run"}; continue
        days = sorted(set(r[0] for r in avr) & set(r[0] for r in ti))
        tsp = set(read_meta(repo, "tiingo", sym).get("splits", [])); asp = set(read_meta(repo, "xcheck_av", sym).get("splits", []))
        # dividends are not adjusted in the Alpha Vantage rows, so ex-dividend days may differ slightly: tolerance 0.1%
        share, n = agree(rets({r[0]: r[4] for r in ti}, days), rets({r[0]: r[4] for r in avr}, days))
        xc[sym] = {"days": n, "agree_0.1pct": None if share is None else round(share, 4), "pass": bool(share is not None and share >= 0.99),
                   "splits_tiingo": sorted(tsp), "splits_av": sorted(asp), "splits_match": tsp == asp}
    ov = [v for v in per.values() if "overlap_pass" in v]
    summary = {"symbols_ok": len(ok), "missing": sorted(x for x, v in s["symbols"].items() if v["status"] == "missing"),
               "by_source": {src: sum(1 for v in ok.values() if v["source"] == src) for src in ("tiingo", "alphavantage")},
               "rows": len(out_rows), "overlap_checked": len(ov), "overlap_pass": sum(1 for v in ov if v["overlap_pass"]),
               "overlap_fail": sorted(x for x, v in per.items() if v.get("overlap_pass") is False),
               "scale_suspicious": sorted(x for x, v in per.items() if v.get("scale_suspicious")),
               "xcheck_pass": sum(1 for v in xc.values() if v.get("pass")), "xcheck_run": sum(1 for v in xc.values() if "pass" in v),
               "xcheck_split_mismatch": sorted(x for x, v in xc.items() if v.get("splits_match") is False),
               "av_refused": s["av"].get("refused")}
    jsave(P(repo, "check.json"), {"built": utcnow().isoformat(timespec="seconds"), "window": [START, END],
                                  "rule": "look-back only; never score a signal before 2016-01-04", "summary": summary,
                                  "symbols": per, "xcheck": xc})
    return {"summary": summary}


def rebuild_lists(repo):
    sys.path.insert(0, os.path.join(repo, "scripts"))
    import pitu
    pitu.lists(repo, rebuild=True)


# ---------- readers ----------
def bars(repo):
    """{sym: {date: (o, h, l, c, v)}} of the warm-up file ({} when it is not built yet). Look-back only."""
    f = P(repo, "bars_1d.csv.gz"); out = {}
    if not os.path.exists(f): return out
    with gzip.open(f, "rt") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["sym"], {})[r["date"]] = (float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"]))
    return out


def merge_into(pit_bars, repo):
    """Add warm-up rows to pit.load()'s bars {sym: [(date, o, h, l, c, v)]}, only before each symbol's first stored date."""
    W_ = bars(repo); n = 0
    for sym, rows in W_.items():
        L = pit_bars.setdefault(sym, [])
        first = min((r[0] for r in L), default="9999")
        add = [(d,) + v for d, v in sorted(rows.items()) if d < first]
        if add: L[:0] = add; n += len(add)
    return n


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "run": sys.exit(run(a[1]))
    elif len(a) == 2 and a[0] == "status": print(json.dumps(progress(state(a[1])), indent=1))
    elif len(a) == 2 and a[0] == "build": print(json.dumps(build(a[1])["summary"], indent=1))
    else: print(__doc__)
