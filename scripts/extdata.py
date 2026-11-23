"""Free outside context data, fetched on GitHub (added 2026-11-23, owner request; report-only inputs).

Scheduled AI sessions have no network, so GitHub fetches these and commits them; tasks read the files.
Each source is independent: a failure is recorded in ops/diag/extdata.json and never stops the others.
Files: data/ext/<source>/<New York fetch day>.json. Nothing here is a rule: the files are context for the
morning research, the evidence pack (judge.py market_context) and, from the Dec 8 lane build, ML features.

  edgar   SEC EDGAR (no key): the current 8-K feed with item codes per ticker, and Form 4 (insider) filing
          counts per ticker over the last 5 index days. Contact in the User-Agent is the bot address, never a person's.
  fred    St. Louis Fed daily market series through the keyless CSV download (yields, curve, credit spread,
          financial conditions). These series are not revised, so a daily snapshot is point-in-time.
  finra   FINRA consolidated daily short-sale volume (off-exchange trades only) for the universe and the market.
  cboe    Cboe daily put/call ratios.
  crypto  Perpetual funding rates for the universe coins (Binance, else OKX) and total stablecoin supply (DefiLlama).

    python3 extdata.py REPO [source ...]      (no source = all)
"""
import csv, datetime as dt, io, json, os, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UA_SEC = "Quantavius-forward-test forward-test-bot@users.noreply.github.com"
UA = "Mozilla/5.0 (compatible; forward-test-bot; research)"
FRED = ["DGS2", "DGS10", "T10Y2Y", "T10Y3M", "BAMLH0A0HYM2", "DFF", "NFCI"]
COINS = ["BTC", "ETH", "SOL", "DOGE", "SHIB", "AVAX", "LINK"]
ITEMS = {"1.01": "material agreement", "1.03": "bankruptcy", "2.01": "acquisition or disposal done",
         "2.02": "results of operations (earnings)", "2.05": "restructuring costs", "2.06": "impairment",
         "3.01": "delisting notice", "4.02": "earlier statements not reliable", "5.02": "officer or director change",
         "7.01": "Regulation FD disclosure", "8.01": "other events"}


def get(url, ua=UA, timeout=40, tries=2):
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
        except Exception as e:
            err = e; time.sleep(2)
    raise err


def bdays(n, end=None):
    d = end or dt.datetime.now(NY).date(); out = []
    while len(out) < n:
        if d.weekday() < 5: out.append(d)
        d -= dt.timedelta(days=1)
    return out


def edgar(repo, U):
    tk = json.loads(get("https://www.sec.gov/files/company_tickers.json", UA_SEC))
    cik2t = {}
    for v in tk.values(): cik2t.setdefault(int(v["cik_str"]), v["ticker"].upper())
    ns = {"a": "http://www.w3.org/2005/Atom"}; eight = {}; n8 = 0; notes = []
    for start in (0, 100, 200, 300):
        try:
            x = get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include"
                    f"&start={start}&count=100&output=atom", UA_SEC)
            ents = ET.fromstring(x).findall("a:entry", ns)
        except Exception as e:
            notes.append(f"8-K feed page {start}: {type(e).__name__}"); break
        for e in ents:
            title = e.findtext("a:title", "", ns); m = re.search(r"\((\d{10})\)", title)
            if not m or not title.startswith("8-K"): continue
            t = cik2t.get(int(m.group(1)))
            if not t: continue
            summ = e.findtext("a:summary", "", ns) or ""
            link = e.find("a:link", ns)
            row = {"filed": (e.findtext("a:updated", "", ns) or "")[:19], "form": title.split(" - ")[0],
                   "items": sorted(set(re.findall(r"Item (\d\.\d\d)", summ))),
                   "url": link.get("href") if link is not None else None}
            if row not in eight.setdefault(t, []): eight[t].append(row); n8 += 1
        if len(ents) < 100: break
        time.sleep(0.3)
    f4 = {}; days_used = []
    for d in bdays(8):
        if len(days_used) >= 5: break
        q = (d.month - 1) // 3 + 1
        try: txt = get(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/form.{d:%Y%m%d}.idx", UA_SEC).decode("latin-1")
        except Exception: continue                       # today's index appears late in the evening; holidays have none
        days_used.append(d.isoformat())
        for line in txt.splitlines():
            if not line.startswith("4 "): continue
            p = re.split(r"\s{2,}", line.strip())
            if len(p) < 5 or not p[-3].isdigit(): continue
            t = cik2t.get(int(p[-3]))
            if t: f4[t] = f4.get(t, 0) + 1
        time.sleep(0.3)
    # Form 4 lines list the issuer and each reporting insider; a ticker-mapped CIK is the issuer, so this counts filings.
    return {"eight_k": eight, "form4_filings_5d": dict(sorted(f4.items(), key=lambda kv: -kv[1])[:600]),
            "form4_index_days": days_used, "item_legend": ITEMS, "notes": notes}, n8 + len(f4)


def fred(repo, U):
    out = {}; notes = []
    for s in FRED:
        try:
            rows = list(csv.reader(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}").decode())))
            obs = [(r[0], float(r[1])) for r in rows[1:] if len(r) > 1 and r[1] not in ("", ".")]
            out[s] = [{"date": d, "value": v} for d, v in obs[-60:]]
        except Exception as e:
            notes.append(f"{s}: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(0.5)
    if not out: raise RuntimeError("; ".join(notes))
    return {"series": out, "notes": notes,
            "legend": {"DGS2": "2-year Treasury yield %", "DGS10": "10-year Treasury yield %", "T10Y2Y": "10y minus 2y",
                       "T10Y3M": "10y minus 3m", "BAMLH0A0HYM2": "high-yield credit spread %", "DFF": "fed funds rate %",
                       "NFCI": "Chicago Fed financial conditions (weekly; above 0 = tight)"}}, sum(len(v) for v in out.values())


def finra(repo, U):
    syms = set(U["watchlist"] + U["control"] + U.get("universe", []) + [e for e in U["etfs"] if not e.startswith("VIX")])
    days = {}
    for d in bdays(6):
        if len(days) >= 3: break
        try: txt = get(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d:%Y%m%d}.txt").decode("latin-1")
        except Exception: continue
        S = T = 0; rows = {}
        for r in csv.reader(io.StringIO(txt), delimiter="|"):
            if len(r) < 5 or not r[0].isdigit(): continue
            try: sv, tv = float(r[2]), float(r[4])
            except ValueError: continue
            S += sv; T += tv
            if r[1] in syms and tv > 0: rows[r[1]] = {"short": int(sv), "total": int(tv), "short_pct": round(100 * sv / tv, 1)}
        if T > 0: days[d.isoformat()] = {"market_short_pct": round(100 * S / T, 2), "symbols": rows}
    if not days: raise RuntimeError("no daily file found for the last 6 weekdays")
    return {"days": days, "note": "off-exchange (TRF/ADF) trades only; short volume is not short interest"}, sum(len(v["symbols"]) for v in days.values())


def cboe(repo, U):
    days = {}; notes = []
    for d in bdays(5):
        if len(days) >= 3: break
        row = None
        try:
            js = json.loads(get(f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{d}_daily_options"))
            row = {str(x.get("name", "")).strip().lower(): x.get("value") for x in js.get("ratios", [])}
        except Exception as e:
            notes.append(f"{d} json: {type(e).__name__}")
        if not row:
            try:
                h = get(f"https://www.cboe.com/us/options/market_statistics/daily/?dt={d}").decode("utf-8", "ignore")
                row = {m[0].strip().lower(): m[1] for m in re.findall(r"([A-Z0-9 +/()]+PUT/CALL RATIO)\s*</t[dh]>\s*<t[dh][^>]*>\s*([\d.]+)", h)}
            except Exception as e:
                notes.append(f"{d} html: {type(e).__name__}")
        if row:
            pick = {}
            for k, name in (("total put/call ratio", "total"), ("index put/call ratio", "index"), ("equity put/call ratio", "equity"),
                            ("exchange traded products put/call ratio", "etp"), ("cboe volatility index (vix) put/call ratio", "vix")):
                try: pick[name] = float(row[k])
                except Exception: pass
            if pick: days[d.isoformat()] = pick
    if not days: raise RuntimeError("; ".join(notes) or "no ratios parsed")
    return {"days": days, "notes": notes, "note": "Cboe exchanges only; above about 1.0 total = more puts than calls"}, len(days)


def crypto(repo, U):
    fund = {}; src = None; notes = []
    try:
        js = json.loads(get("https://fapi.binance.com/fapi/v1/premiumIndex"))
        m = {x["symbol"]: x for x in js}
        for c in COINS:
            x = m.get(("1000SHIB" if c == "SHIB" else c) + "USDT")
            if x: fund[c] = {"funding_rate_pct": round(float(x["lastFundingRate"]) * 100, 5), "mark": float(x["markPrice"])}
        src = "binance"
    except Exception as e:
        notes.append(f"binance: {type(e).__name__}: {str(e)[:60]}")
    if not fund:
        for c in COINS:
            try:
                js = json.loads(get(f"https://www.okx.com/api/v5/public/funding-rate?instId={c}-USDT-SWAP"))
                fund[c] = {"funding_rate_pct": round(float(js["data"][0]["fundingRate"]) * 100, 5)}
            except Exception as e:
                notes.append(f"okx {c}: {type(e).__name__}")
            time.sleep(0.2)
        src = "okx" if fund else None
    stable = None
    try:
        js = json.loads(get("https://stablecoins.llama.fi/stablecoincharts/all"))
        last = [{"date": dt.datetime.fromtimestamp(int(x["date"]), dt.timezone.utc).date().isoformat(),
                 "usd_bn": round(float(x["totalCirculatingUSD"]["peggedUSD"]) / 1e9, 2)} for x in js[-31:]]
        stable = {"last": last[-1], "change_7d_pct": round(100 * (last[-1]["usd_bn"] / last[-8]["usd_bn"] - 1), 2),
                  "change_30d_pct": round(100 * (last[-1]["usd_bn"] / last[0]["usd_bn"] - 1), 2)}
    except Exception as e:
        notes.append(f"defillama: {type(e).__name__}: {str(e)[:60]}")
    if not fund and not stable: raise RuntimeError("; ".join(notes))
    return {"funding": fund, "funding_source": src, "stablecoins": stable, "notes": notes,
            "note": "funding is the latest 8-hour perpetual rate in %; positive = longs pay shorts (crowded longs)"}, len(fund) + (1 if stable else 0)


SOURCES = {"edgar": edgar, "fred": fred, "finra": finra, "cboe": cboe, "crypto": crypto}


def main():
    repo = os.path.abspath(sys.argv[1]); want = sys.argv[2:] or list(SOURCES)
    U = json.load(open(os.path.join(repo, "data", "universe.json")))
    now = dt.datetime.now(dt.timezone.utc); day = now.astimezone(NY).date().isoformat()
    sf = os.path.join(repo, "ops", "diag", "extdata.json")
    try: status = json.load(open(sf))
    except Exception: status = {}
    for s in want:
        at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            data, n = SOURCES[s](repo, U)
            d = os.path.join(repo, "data", "ext", s); os.makedirs(d, exist_ok=True)
            data = {"source": s, "day": day, "fetched_at_utc": at, "fetched_at_ny": now.astimezone(NY).strftime("%Y-%m-%d %H:%M"), **data}
            json.dump(data, open(os.path.join(d, day + ".json"), "w"), separators=(",", ":"))
            status[s] = {"ok": True, "at": at, "day": day, "rows": n, "notes": data.get("notes") or []}
        except Exception as e:
            status[s] = {"ok": False, "at": at, "day": day, "error": f"{type(e).__name__}: {str(e)[:200]}",
                         "last_ok": (status.get(s) or {}).get("at") if (status.get(s) or {}).get("ok") else (status.get(s) or {}).get("last_ok")}
    os.makedirs(os.path.dirname(sf), exist_ok=True); json.dump(status, open(sf, "w"), indent=1)
    print(json.dumps({k: (v.get("rows") if v.get("ok") else v.get("error")) for k, v in status.items()}))


if __name__ == "__main__":
    main()
