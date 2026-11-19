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

Jobs (in order; revised 2026-11-19 after a diagnostic: IBKR returns at most 1000 bars per call and every result passes
through the model as text, so history is kept to what the strategies need): daily bars step_count 210 (enough for
200-day averages) for watchlist + control + universe.json etfs (index, TLT, GLD, sector ETFs, VIX, VIX3M);
1-hour bars step_count 720 (30 days) for the 7 coins (crypto decision rows). No 5-minute backfill: the stock ML layer
trains on the forward data collected from 2026-11-16 on. Bars go through store.py (merge, no duplicates).
Index-type symbols (VIX, VIX3M) use security_type IND; coins use CRYPTO on exchange ZEROHASH.
Daily jobs carry "include_corporate_actions": true (dividends + splits, saved by corp.py ingest-bars).
Free feed (added 2026-11-19): jobs whose history is already in data/bars (delivered by fetch_free.py on GitHub
Actions) are skipped automatically. A stock whose prices are covered but whose contract id is unknown comes back as a
"contract_only" job: resolve the id, record it with `contract`, then `done`, and fetch no prices.
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
        out.append({"symbol": s, "tf": "1d", "step": "ONE_DAY", "step_count": 210, "include_corporate_actions": not s.startswith("VIX"),
                    "security_type": "IND" if s.startswith("VIX") else "STK", "why": "daily features + breadth + dividends/splits"})
    for c in COINS:
        out.append({"symbol": c, "tf": "1h", "step": "ONE_HOUR", "step_count": 720, "security_type": "CRYPTO",
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
    def covered(j):   # history already delivered by the free feed (fetch_free.py on GitHub Actions)
        f = os.path.join(repo, "data", "bars", j["tf"], j["symbol"] + ".jsonl")
        return j["tf"] in ("1d", "1h") and os.path.exists(f) and sum(1 for _ in open(f)) >= j["step_count"] - 10
    left = [j for j in jobs(repo) if j["symbol"] + "|" + j["tf"] not in st["done"]
            and st["fail"].get(j["symbol"] + "|" + j["tf"], 0) < 3
            and not (covered(j) and (j["security_type"] != "STK" or j["symbol"] in cons))]
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
        else:
            j["contract_id"] = cons.get(j["symbol"])
            if covered(j):   # prices already stored: only the contract id is still needed (for EARNINGS)
                j = {"symbol": j["symbol"], "tf": j["tf"], "contract_only": True, "contract_id": None,
                     "why": "resolve the contract id only (search_contracts) and record it; do NOT fetch prices"}
        out.append(j)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
