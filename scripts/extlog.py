"""Keep what the morning research fetches from rate-limited tools (added 2026-11-23, owner request).

The free Alpha Vantage plan (25 calls a day) and the IBKR theme tool cannot backfill history, so every reading the
morning research takes is saved here, dated when it was taken. Over the test this builds a point-in-time dataset the
Dec 8 ML stock ranker may use as candidate features (challengers only, each logged as a trial).

  python3 extlog.py transcript REPO RAW.json SYM QUARTER   Alpha Vantage EARNINGS_CALL_TRANSCRIPT result
  python3 extlog.py putcall    REPO RAW.json SYM           Alpha Vantage HISTORICAL_PUT_CALL_RATIO result
  python3 extlog.py insider    REPO RAW.json SYM           Alpha Vantage INSIDER_TRANSACTIONS result
  python3 extlog.py peers      REPO RAW.json               {SYM: IBKR get_company_themes result, ...} (weekly peer map)

Rows go to data/ext/av/<kind>.jsonl (one compact row per reading, with taken_at_utc); peers go to
data/ext/peers/<New York day>.json and data/ext/peers/latest.json. Raw text is not stored (summaries only).
"""
import datetime as dt, json, os, statistics, sys
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def transcript(d, sym, q):
    rows = d.get("transcript") or []
    def avg(pred):
        v = [f(r.get("sentiment")) for r in rows if pred(r) and f(r.get("sentiment")) is not None and r.get("speaker") != "Operator"]
        return round(statistics.mean(v), 3) if v else None
    mgmt = lambda r: str(r.get("title", "")).lower() not in ("analyst", "operator")
    return {"symbol": sym, "quarter": q, "n_parts": len(rows), "sentiment_all": avg(lambda r: True),
            "sentiment_management": avg(mgmt), "sentiment_analysts": avg(lambda r: str(r.get("title", "")).lower() == "analyst"),
            "n_analyst_questions": sum(1 for r in rows if str(r.get("title", "")).lower() == "analyst")}


def putcall(d, sym):
    by = d.get("put_call_ratio_by_expiration") or []
    near = [f(x.get("value")) for x in by[:3] if f(x.get("value")) is not None]
    return {"symbol": sym, "as_of": d.get("date"), "full_chain": f(d.get("put_call_ratio_full_chain")),
            "nearest_3_expiries_mean": round(statistics.mean(near), 3) if near else None, "n_expiries": len(by)}


def insider(d, sym):
    rows = d.get("data") or []
    buys = sum(f(r.get("shares")) or 0 for r in rows if r.get("acquisition_or_disposal") == "A" and r.get("security_type") == "Common Stock")
    sells = sum(f(r.get("shares")) or 0 for r in rows if r.get("acquisition_or_disposal") == "S")
    dates = sorted(r.get("transaction_date") for r in rows if r.get("transaction_date"))
    return {"symbol": sym, "n_rows": len(rows), "open_market_or_grant_shares_acquired": buys, "shares_sold": sells,
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None}


def peers(d):
    out = {}
    for sym, r in d.items():
        th = []
        for t in (r or {}).get("linked_themes", []):
            th.append({"theme": t.get("name"), "peers": [c.get("symbol") for c in t.get("linked_companies", []) if c.get("symbol") and c.get("symbol") != sym]})
        out[sym] = th
    return out


def main():
    kind, repo, raw = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
    d = json.load(open(raw)); now = dt.datetime.now(dt.timezone.utc)
    taken = now.strftime("%Y-%m-%dT%H:%M:%SZ"); day = now.astimezone(NY).date().isoformat()
    if kind == "peers":
        p = os.path.join(repo, "data", "ext", "peers"); os.makedirs(p, exist_ok=True)
        o = {"taken_at_utc": taken, "day": day, "symbols": peers(d)}
        for name in (day + ".json", "latest.json"): json.dump(o, open(os.path.join(p, name), "w"), separators=(",", ":"))
        print(json.dumps({"peers_symbols": len(o["symbols"])})); return
    sym = sys.argv[4].upper()
    row = {"transcript": lambda: transcript(d, sym, sys.argv[5]), "putcall": lambda: putcall(d, sym), "insider": lambda: insider(d, sym)}[kind]()
    row = {"taken_at_utc": taken, "day": day, **row}
    p = os.path.join(repo, "data", "ext", "av"); os.makedirs(p, exist_ok=True)
    with open(os.path.join(p, kind + ".jsonl"), "a") as fh: fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    print(json.dumps(row))


if __name__ == "__main__":
    main()
