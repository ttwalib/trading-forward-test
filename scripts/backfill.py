"""Historical backfill planner (the scheduled "Backfill" task calls IBKR; this script decides WHAT to fetch next,
so each run stays small and the job resumes where it stopped).

  python3 backfill.py next REPO [BATCH]     -> JSON list of the next fetch jobs (default 6), each
        {"symbol", "tf", "step", "period", "security_type", "contract_id" or null, "why"}
        contract_id null = resolve it first with search_contracts (exact symbol, US primary listing, STK) and record it
        with `backfill.py contract REPO SYM ID`.
  python3 backfill.py contract REPO SYM ID  -> store a resolved contract id in data/contracts.json
  python3 backfill.py done REPO SYM TF      -> mark a job done (after store.py merged the bars)
  python3 backfill.py fail REPO SYM TF WHY  -> mark a job failed (retried at most 2 times)
  python3 backfill.py status REPO           -> progress summary; "complete": true when nothing is left

Jobs (in order): daily bars ONE_YEAR for watchlist + control + universe.json etfs (index, TLT, GLD, sector ETFs, VIX, VIX3M) (breadth, ATR, SMA features);
5-minute bars THREE_MONTHS for watchlist + control + SPY (historical ORB decisions and labels for ML pre-training);
1-hour bars THREE_MONTHS for the 7 coins (crypto decision rows). Bars go through store.py (merge, no duplicates).
Index-type symbols (VIX, VIX3M) use security_type IND; coins use CRYPTO on exchange ZEROHASH.
Daily jobs carry "include_corporate_actions": true (dividends + splits, saved by corp.py ingest-bars).
Last job (added 2026-11-19): "EARNINGS|events": search_earnings_insights for every resolved stock contract id (the job
lists them), start one year back, paginated (size 50, offset += 50 until a short page); save the responses as a JSON
list and run corp.py ingest-earnings. It waits until every stock's contract id is resolved.
"""
import json, os, sys
COINS = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE", "SHIB"]


def P(repo, f): return os.path.join(repo, "data", f)


def jl(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def jobs(repo):
    U = json.load(open(P(repo, "universe.json"))); stocks = U["watchlist"] + U["control"]; out = []
    for s in stocks + U.get("etfs", ["SPY", "QQQ", "IWM", "VIX", "VIX3M"]):
        out.append({"symbol": s, "tf": "1d", "step": "ONE_DAY", "period": "ONE_YEAR", "include_corporate_actions": not s.startswith("VIX"),
                    "security_type": "IND" if s.startswith("VIX") else "STK", "why": "daily features + breadth + dividends/splits"})
    for s in stocks + ["SPY"]:
        out.append({"symbol": s, "tf": "5m", "step": "FIVE_MINS", "period": "THREE_MONTHS", "security_type": "STK",
                    "why": "historical ORB decisions"})
    for c in COINS:
        out.append({"symbol": c, "tf": "1h", "step": "ONE_HOUR", "period": "THREE_MONTHS", "security_type": "CRYPTO",
                    "exchange": "ZEROHASH", "why": "crypto decision rows"})
    out.append({"symbol": "EARNINGS", "tf": "events", "why": "earnings dates with known-at times (IBKR earnings insights)",
                "stocks": stocks, "start": "one year before today, UTC midnight", "size": 50})
    return out


def main():
    a = sys.argv[1:]; repo = a[1]
    st = jl(P(repo, "backfill_state.json"), {"done": [], "fail": {}}); cons = jl(P(repo, "contracts.json"), {})
    save = lambda: (json.dump(st, open(P(repo, "backfill_state.json"), "w"), indent=1),
                    json.dump(cons, open(P(repo, "contracts.json"), "w"), indent=1, sort_keys=True))
    if a[0] == "contract":
        cons[a[2]] = int(a[3]); save(); print(json.dumps({a[2]: cons[a[2]]})); return
    if a[0] == "done":
        k = a[2] + "|" + a[3]
        if k not in st["done"]: st["done"].append(k)
        save(); print(json.dumps({"done": k})); return
    if a[0] == "fail":
        k = a[2] + "|" + a[3]; st["fail"][k] = st["fail"].get(k, 0) + 1; st.setdefault("why", {})[k] = " ".join(a[4:])
        save(); print(json.dumps({"fail": k, "count": st["fail"][k]})); return
    left = [j for j in jobs(repo) if j["symbol"] + "|" + j["tf"] not in st["done"]
            and st["fail"].get(j["symbol"] + "|" + j["tf"], 0) < 3]
    if a[0] == "status":
        allj = jobs(repo)
        print(json.dumps({"jobs": len(allj), "done": len(st["done"]), "left": len(left),
                          "given_up": [k for k, n in st["fail"].items() if n >= 3], "complete": not left}, indent=1)); return
    n = int(a[2]) if len(a) > 2 else 6
    out = []
    for j in left[:n]:
        j = dict(j)
        if j["symbol"] == "EARNINGS":
            miss = [s for s in j["stocks"] if s not in cons]
            if miss: continue   # resolve stock contracts first (their daily/5m jobs do that)
            j["contract_ids"] = [cons[s] for s in j.pop("stocks")]
        else: j["contract_id"] = cons.get(j["symbol"])
        out.append(j)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
