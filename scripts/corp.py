"""Corporate actions, earnings dates, macro calendar and midday snapshots: the reference data that keeps the
strategies and the ML free of split/dividend artefacts and look-ahead.

  python3 corp.py ingest-bars REPO BARS.json      -> pulls "corp_actions" out of saved get_price_history responses
                                                    ({"SYM": response, ...}, fetched with include_corporate_actions)
                                                    into data/corp/SYM.json (dividends + splits, de-duplicated)
  python3 corp.py ingest-earnings REPO FILE.json  -> merges search_earnings_insights results (one response or a list of
                                                    responses) into data/events/earnings.jsonl
  python3 corp.py ingest-snap REPO FILE.json      -> merges midday get_price_snapshot results
                                                    {"SYM": {snapshot fields...}, ...} into data/snap/SYM.jsonl
  python3 corp.py status REPO                     -> coverage summary

Library use: from corp import tr_adjust, earnings, macro_features, snap_features, half_spread
- tr_adjust(sym, rows): total-return, split-consistent daily rows. Dividends: every price before an ex-date is
  multiplied by (1 - dividend / previous close) (the standard total-return back-adjustment). Splits: applied only if
  the stored bars still show the raw jump (IBKR history is normally split-adjusted already; the check decides).
- earnings(repo, decision_date): {SYM: [event dates]} for events KNOWN on or before decision_date. known_at = the
  first preview's created_at when it precedes the report; otherwise reporting date minus 14 days, marked "assumed"
  (companies normally confirm dates two or more weeks ahead). After-close reports count from the next trading day.
- macro_features(day): FOMC / CPI / jobs report / monthly opex flags and day counts; None where the month's date is
  not confirmed in data/macro.json.
"""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tcal
NY = ZoneInfo("America/New_York")


def jl(path): return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def wjl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows: f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")


def ymd(s): s = str(s); return "%s-%s-%s" % (s[:4], s[4:6], s[6:8]) if len(s) == 8 and s.isdigit() else s[:10]


# ---------- corporate actions ----------
def corp(repo, sym):
    f = os.path.join(repo, "data", "corp", sym + ".json")
    return json.load(open(f)) if os.path.exists(f) else {"dividends": [], "splits": [], "fetched": None}


def ingest_bars(repo, path):
    data = json.load(open(path)); out = {}
    for sym, r in data.items():
        if not isinstance(r, dict) or "corp_actions" not in r and "close" not in r: continue
        c = corp(repo, sym); divs = {d["ex"]: d for d in c["dividends"]}; spl = {s["date"]: s for s in c["splits"]}
        for a in r.get("corp_actions") or []:
            t = str(a.get("type", "")).lower()
            if "dividend" in t:
                try: v = float(a.get("value"))
                except (TypeError, ValueError): continue
                divs[ymd(a["date"])] = {"ex": ymd(a["date"]), "value": v, "announced": ymd(a.get("announce_date", "")), "type": a.get("type")}
            elif "split" in t:
                v = a.get("value") or a.get("ratio")
                try:
                    if isinstance(v, str) and ":" in v: n, d_ = v.split(":"); ratio = float(n) / float(d_)
                    elif isinstance(v, str) and "/" in v: n, d_ = v.split("/"); ratio = float(n) / float(d_)
                    else: ratio = float(v)
                except (TypeError, ValueError, ZeroDivisionError): continue
                spl[ymd(a["date"])] = {"date": ymd(a["date"]), "ratio": ratio, "raw": a}
        c["dividends"] = sorted(divs.values(), key=lambda x: x["ex"]); c["splits"] = sorted(spl.values(), key=lambda x: x["date"])
        c["fetched"] = dt.datetime.now(NY).date().isoformat()
        os.makedirs(os.path.join(repo, "data", "corp"), exist_ok=True)
        json.dump(c, open(os.path.join(repo, "data", "corp", sym + ".json"), "w"), indent=1)
        out[sym] = {"dividends": len(c["dividends"]), "splits": len(c["splits"])}
    return out


def tr_adjust(repo, sym, rows):
    """rows: sorted [(date, o, h, l, c)] -> same shape, total-return adjusted. Unknown corp data -> rows unchanged."""
    c = corp(repo, sym)
    if not rows or (not c["dividends"] and not c["splits"]): return rows
    idx = {r[0]: i for i, r in enumerate(rows)}; fac = [1.0] * len(rows)
    for s in c["splits"]:
        i = next((k for k, r in enumerate(rows) if r[0] >= s["date"]), None)
        if i is None or i == 0 or not s["ratio"]: continue
        jump = rows[i - 1][4] / rows[i][1] if rows[i][1] else 1
        if abs(jump / s["ratio"] - 1) < 0.15:            # raw jump still in the data: back-adjust
            for k in range(i): fac[k] /= s["ratio"]
    for d in c["dividends"]:
        i = next((k for k, r in enumerate(rows) if r[0] >= d["ex"]), None)
        if i is None or i == 0: continue
        pc = rows[i - 1][4] * fac[i - 1]
        if pc <= 0 or d["value"] >= pc * 0.5: continue
        f = 1 - d["value"] / pc
        for k in range(i): fac[k] *= f
    return [(r[0],) + tuple(x * fac[k] for x in r[1:5]) for k, r in enumerate(rows)]


# ---------- earnings ----------
def ingest_earnings(repo, path):
    data = json.load(open(path)); resp = data if isinstance(data, list) else [data]
    f = os.path.join(repo, "data", "events", "earnings.jsonl"); have = {(r["symbol"], r["reporting_ts"]): r for r in jl(f)}
    previews = {}
    for r in resp:
        for it in (r.get("insights") if isinstance(r, dict) else None) or ([r] if isinstance(r, dict) and "reporting_date" in r else []):
            if it.get("type") == "preview": previews.setdefault((it["ticker"], it["reporting_date"]), []).append(it["created_at"])
    n_new = 0
    for r in resp:
        for it in (r.get("insights") if isinstance(r, dict) else None) or ([r] if isinstance(r, dict) and "reporting_date" in r else []):
            sym, ts = it.get("ticker"), it.get("reporting_date")
            if not sym or not ts: continue
            rt = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(NY)
            pv = [p for p in previews.get((sym, ts), []) if p < ts]
            if pv: known, how = dt.datetime.fromisoformat(min(pv).replace("Z", "+00:00")).astimezone(NY).date().isoformat(), "preview"
            else: known, how = (rt.date() - dt.timedelta(days=14)).isoformat(), "assumed"
            hm = rt.strftime("%H:%M"); session = "bmo" if hm < "09:30" else ("amc" if hm >= "16:00" else "intraday")
            k = (sym, ts); old = have.get(k)
            row = {"symbol": sym, "reporting_ts": ts, "date": rt.date().isoformat(), "session": session,
                   "known_at": min(known, old["known_at"]) if old else known, "known_how": how if not old or known <= old["known_at"] else old["known_how"],
                   "contract_id": it.get("contract_id"), "source": "IBKR earnings insights"}
            if not old: n_new += 1
            have[k] = row
    wjl(f, sorted(have.values(), key=lambda r: (r["date"], r["symbol"])))
    return {"events": len(have), "new": n_new}


def event_day(row):
    """First regular session that can react: same day for bmo/intraday, next open session for amc."""
    d = dt.date.fromisoformat(row["date"])
    if row.get("session") == "amc":
        d += dt.timedelta(days=1)
        while not tcal.is_open(d): d += dt.timedelta(days=1)
    return d.isoformat()


def earnings(repo, decision_date=None):
    out = {}
    for r in jl(os.path.join(repo, "data", "events", "earnings.jsonl")):
        if decision_date and r["known_at"] > decision_date: continue
        out.setdefault(r["symbol"], set()).add(event_day(r))
    return out


def earnings_known_by(repo):
    """{SYM: [(event_day, known_at)]}: lets a backtest check, for each decision date, what was known then."""
    out = {}
    for r in jl(os.path.join(repo, "data", "events", "earnings.jsonl")):
        out.setdefault(r["symbol"], []).append((event_day(r), r["known_at"]))
    return out


# ---------- macro ----------
_M = None
def _macro():
    global _M
    if _M is None:
        f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "macro.json")
        _M = json.load(open(f)) if os.path.exists(f) else {}
    return _M


def opex(d):
    first = d.replace(day=1); fri = first + dt.timedelta(days=(4 - first.weekday()) % 7)
    x = fri + dt.timedelta(days=14)
    while not tcal.is_open(x): x -= dt.timedelta(days=1)
    return x


def macro_features(day):
    M = _macro(); d = dt.date.fromisoformat(day); f = {}
    def known(kind):
        lst = M.get(kind, []); unk = M.get("unknown", {}).get(kind, [])
        if day[:7] in unk or not lst or day < min(lst) or day[:7] > max(lst)[:7]: return None
        return lst
    for kind, key in (("fomc_decision", "fomc"), ("cpi", "cpi"), ("nfp", "nfp")):
        lst = known(kind)
        if lst is None: f[key + "_day"] = None; f["days_to_" + key] = None; continue
        f[key + "_day"] = 1 if day in lst else 0
        nxt = [x for x in lst if x >= day]
        f["days_to_" + key] = len(tcal.trading_days(day, nxt[0])) - 1 if nxt else None
    ox = opex(d)
    if ox < d: ox = opex((d.replace(day=1) + dt.timedelta(days=32)).replace(day=1))
    f["opex_day"] = 1 if ox == d else 0
    f["days_to_opex"] = len(tcal.trading_days(day, ox.isoformat())) - 1
    flags = [f[k] for k in ("fomc_day", "cpi_day", "nfp_day")]
    f["macro_day"] = None if None in flags else int(any(flags))
    return f


# ---------- midday snapshots (spreads, implied vol) ----------
def ingest_snap(repo, path, when=None):
    data = json.load(open(path)); now = when or dt.datetime.now(NY).strftime("%Y-%m-%d %H:%M"); out = {}
    for sym, s in data.items():
        ba = s.get("bid-ask") or s.get("bid_ask") or {}; bid, ask = ba.get("bid"), ba.get("ask")
        row = {"ts": now, "date": now[:10]}
        if bid and ask and ask > bid > 0: row["half_spread_pct"] = round(50 * (ask - bid) / ((ask + bid) / 2), 5)
        iv = s.get("implied-vol-underlying") or {}
        if iv.get("is_valid", True) and iv.get("annual_iv") is not None: row["iv"] = round(iv["annual_iv"], 5)
        hv = s.get("historical-vol") or {}
        if hv.get("annual_pct") is not None: row["hv30"] = round(hv["annual_pct"], 5)
        p = s.get("implied-volatility-percentile") or {}
        for k in ("high_13w", "high_26w", "high_52w"):
            if p.get(k) is not None: row["ivp_" + k.split("_")[1]] = round(p[k], 4)
        f = os.path.join(repo, "data", "snap", sym + ".jsonl")
        rows = {r["ts"]: r for r in jl(f)}; rows[now] = row; wjl(f, sorted(rows.values(), key=lambda r: r["ts"]))
        out[sym] = row
    return out


_SNAP = {}
def _snaps(repo, sym):
    if (repo, sym) not in _SNAP: _SNAP[(repo, sym)] = jl(os.path.join(repo, "data", "snap", sym + ".jsonl"))
    return _SNAP[(repo, sym)]


def half_spread(repo, sym, day, n=20):
    """Median observed half-spread (%) from the last n snapshots taken before `day`, else None."""
    xs = sorted(r["half_spread_pct"] for r in _snaps(repo, sym) if r["date"] < day and "half_spread_pct" in r)[-n:]
    return xs[len(xs) // 2] if xs else None


def snap_features(repo, sym, day):
    """Latest snapshot strictly before `day`: implied vol, IV/realised ratio, 52w IV percentile."""
    rs = [r for r in _snaps(repo, sym) if r["date"] < day]
    if not rs: return {"iv": None, "iv_hv": None, "ivp_52w": None}
    r = {}
    for x in rs[-6:]:                      # latest non-empty value of each field (snapshots come in two passes)
        r.update({k: v for k, v in x.items() if v is not None})
    return {"iv": r.get("iv"), "iv_hv": round(r["iv"] / r["hv30"], 4) if r.get("iv") and r.get("hv30") else None, "ivp_52w": r.get("ivp_52w")}


def status(repo):
    U = json.load(open(os.path.join(repo, "data", "universe.json"))); syms = U["watchlist"] + U["control"] + U.get("etfs", [])
    cd = os.path.join(repo, "data", "corp")
    ev = jl(os.path.join(repo, "data", "events", "earnings.jsonl"))
    return {"corp_files": sum(1 for s in syms if os.path.exists(os.path.join(cd, s + ".json"))), "symbols": len(syms),
            "earnings_events": len(ev), "earnings_symbols": len({r["symbol"] for r in ev}),
            "snap_symbols": sum(1 for s in syms if os.path.exists(os.path.join(repo, "data", "snap", s + ".jsonl")))}


if __name__ == "__main__":
    a = sys.argv[1:]
    fn = {"ingest-bars": lambda: ingest_bars(a[1], a[2]), "ingest-earnings": lambda: ingest_earnings(a[1], a[2]),
          "ingest-snap": lambda: ingest_snap(a[1], a[2], a[3] if len(a) > 3 else None), "status": lambda: status(a[1]),
          "macro": lambda: macro_features(a[1])}[a[0]]
    print(json.dumps(fn(), indent=1))
