"""Repo ledger: a machine-readable mirror of the sheet logs, the single source for stats.py, decisions.py and ml.py.

  python3 ledger.py add REPO TAB ROWS.json     upsert rows (a list of lists in sheet column order, or a list of dicts)
  python3 ledger.py count REPO                 rows per tab
  python3 ledger.py trades REPO [> out.json]   unified closed-trade table used by stats.py

Every task that writes trade or log rows to the sheet ALSO passes the same rows to `ledger.py add` before its git
commit, so the repo always holds the full history (data/ledger/<TAB>.jsonl, one JSON object per line).
Rows are upserted by the tab's key, so re-running a task never duplicates rows. Values are stored as written
(leading ' of text cells removed; {"date": ...} / {"number": ...} sheet objects flattened).
"""
import json, os, sys, hashlib

SPECS = {
    "Trades": (["date", "symbol", "outcome", "r_net", "entry_time", "entry", "stop", "target", "exit_time", "exit",
                "or_low", "or_high", "r_gross"], ["date", "symbol"]),
    "VariantTrades": (["date", "variant", "symbol", "outcome", "r_net", "entry_time"], ["date", "variant", "symbol"]),
    "Options": (["date", "symbol", "contract", "status", "entry_time", "option_entry", "exit_time", "option_exit",
                 "return_pct", "stock_outcome", "stock_r_net", "contract_id", "exchange"], ["date", "symbol"]),
    "DeepD1": (["date", "symbol", "contract", "status", "entry_time", "option_entry", "exit_time", "option_exit",
                "return_pct", "stock_outcome", "stock_r_net", "contract_id", "exchange", "gross_return_pct", "fees_usd"],
               ["date", "symbol"]),
    "DeepSpreads": (["day", "side", "expiry", "short_strike", "long_strike", "short_id", "long_id", "status", "credit",
                     "max_risk", "exit_cost", "exit_time", "reason", "pct", "gross_pct", "fees_usd", "iv_entry_pct",
                     "delta", "theta_day", "vega_1pct", "gamma"], ["day", "side"]),
    "Weekly": (["day", "strategy", "expiry", "position", "status", "entry_value", "max_risk", "pnl_per_share",
                "exit_time", "reason", "pct", "gross_pct", "fees_usd", "iv_entry_pct", "delta", "theta_day", "vega_1pct",
                "gamma"], ["day", "strategy", "position"]),
    "CryptoTracks": (["track", "strategy", "symbol", "status", "entry_time", "entry", "stop", "exit_time", "exit",
                      "reason", "r", "pct", "gross_pct", "settings"], ["track", "strategy", "symbol", "entry_time"]),
    "AdaptiveStocks": (["date", "symbol", "outcome", "r_net", "entry_time", "params"], ["date", "symbol"]),
    "AgentTrades": (["date", "segment", "rules", "symbol", "outcome", "entry_time", "entry", "exit_time", "exit",
                     "r_net", "return_pct", "note"], ["date", "segment", "rules", "symbol", "entry_time"]),
    "AgentPicks": (["picked_at", "asset", "symbol", "contract_id", "why", "checks", "sentiment", "sources", "status"],
                   ["picked_at", "symbol"]),
    "Sentiment": (["date", "symbol", "pool", "mentions", "mentions_24h_ago", "change_pct", "rank", "upvotes", "rising",
                   "contract_id"], ["date", "symbol"]),
    "Regime": (["date", "vix", "vix_band", "spy", "spy_vs20", "spy_slope", "spy_trend", "btc", "btc_vs20", "btc_trend",
                "label", "breadth20", "breadth50", "nh_nl", "qqq_vs20", "iwm_vs20", "crypto_breadth20", "btc_rv30",
                "crypto_score", "vix_term"], ["date"]),
    "Events": (["date", "time_et", "event", "importance", "consensus", "actual", "source"], ["date", "event"]),
    "Live": (["decided_at", "kind", "symbol", "signal_time", "stock_last", "instrument", "contract", "bid", "ask", "mid",
              "spread_pct", "ml_choice", "ml_score", "note"], ["decided_at", "kind", "symbol", "instrument"]),
    "MLShadow": (["predicted_at", "model", "family", "date", "symbol", "candidate_id", "choice", "take", "pred_best",
                  "pred_json", "realized", "realized_choice", "scored_at", "phase"], ["model", "candidate_id"]),
    "Stats": (["date", "strategy", "unit", "phase", "n", "mean", "ci_lo", "ci_hi", "p_gt0", "q_bh", "psr", "dsr",
               "alpha", "alpha_t", "beta", "kelly_share", "breaker", "verdict"], ["date", "strategy", "phase"]),
}
ALIASES = {"Variant trades": "VariantTrades", "Deep OTM D1": "DeepD1", "Deep OTM spreads": "DeepSpreads",
           "Weekly options": "Weekly", "Crypto tracks": "CryptoTracks", "Adaptive stocks": "AdaptiveStocks",
           "Agent trades": "AgentTrades", "Agent picks": "AgentPicks", "Live decisions": "Live", "ML shadow": "MLShadow"}


def flat(v):
    if isinstance(v, dict):
        for k in ("date", "number", "value", "shown"):
            if k in v: return flat(v[k])
        return None
    if isinstance(v, str) and v.startswith("'"): return v[1:]
    return v


def path(repo, tab): return os.path.join(repo, "data", "ledger", tab + ".jsonl")


def load(repo, tab):
    tab = ALIASES.get(tab, tab); f = path(repo, tab); out = []
    if os.path.exists(f):
        for line in open(f):
            if line.strip(): out.append(json.loads(line))
    return out


def key_of(tab, r):
    cols, key = SPECS[tab]
    k = "|".join(str(r.get(c, "")) for c in key)
    return hashlib.sha1(k.encode()).hexdigest()[:16]


def add(repo, tab, rows):
    tab = ALIASES.get(tab, tab); cols, _ = SPECS[tab]
    cur = {key_of(tab, r): r for r in load(repo, tab)}; n_new = n_upd = 0
    for row in rows:
        if isinstance(row, dict): r = {k: flat(v) for k, v in row.items()}
        else:
            row = list(row) + [None] * (len(cols) - len(row))
            r = {c: flat(v) for c, v in zip(cols, row)}
        if all(r.get(c) in (None, "") for c in cols): continue
        k = key_of(tab, r)
        if k in cur:
            merged = dict(cur[k]); merged.update({a: b for a, b in r.items() if b not in (None, "")})
            if merged != cur[k]: n_upd += 1
            cur[k] = merged
        else: cur[k] = r; n_new += 1
    os.makedirs(os.path.dirname(path(repo, tab)), exist_ok=True)
    with open(path(repo, tab), "w") as f:
        for r in cur.values(): f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return {"tab": tab, "new": n_new, "updated": n_upd, "total": len(cur)}


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def trades(repo):
    """Closed trades of every strategy in one table. result = return per unit risked (R, or % / 100)."""
    T = []
    def put(strategy, unit, day, res, symbol=None, entry=None, exit_=None, asset="stock", extra=None):
        v = num(res)
        if v is None or not day: return
        T.append({"strategy": strategy, "unit": unit, "day": str(day)[:10], "result": v if unit == "R" else v / 100,
                  "raw": v, "symbol": symbol, "entry": entry, "exit": exit_, "asset": asset, **(extra or {})})
    for r in load(repo, "Trades"):
        if r.get("outcome") and r["outcome"] != "open":
            put("A baseline (watchlist)", "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"), r.get("exit_time"))
    for r in load(repo, "VariantTrades"):
        v = str(r.get("variant") or "").split(" ")[0]
        if r.get("outcome") and r["outcome"] != "open":
            name = "A control list" if v == "AC" else v + " variant (watchlist)"
            put(name, "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"))
    for r in load(repo, "AdaptiveStocks"):
        if r.get("outcome") and r["outcome"] != "open":
            put("Adaptive ORB (watchlist)", "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"))
    for r in load(repo, "Options"):
        if r.get("status") == "closed": put("O ATM calls (watchlist)", "% premium", r["date"], r.get("return_pct"), r["symbol"], r.get("entry_time"), r.get("exit_time"), "option")
    for r in load(repo, "DeepD1"):
        if r.get("status") == "closed": put("D1 lottery calls", "% premium", r["date"], r.get("return_pct"), r["symbol"], r.get("entry_time"), r.get("exit_time"), "option")
    for r in load(repo, "DeepSpreads"):
        if r.get("status") == "closed":
            put("D2 SPY put spreads" if r.get("side") == "put" else "D3 SPY call spreads", "% max risk", r["day"], r.get("pct"),
                "SPY", None, r.get("exit_time"), "option", {"iv": num(r.get("iv_entry_pct"))})
    for r in load(repo, "Weekly"):
        if r.get("status") == "closed":
            put(str(r.get("strategy")), "% max risk", r["day"], r.get("pct"), None, None, r.get("exit_time"), "option",
                {"iv": num(r.get("iv_entry_pct")), "theta": num(r.get("theta_day")), "vega": num(r.get("vega_1pct"))})
    for r in load(repo, "CryptoTracks"):
        if r.get("status") == "closed":
            put("%s %s" % (r.get("track"), r.get("strategy")), "R", str(r.get("entry_time"))[:10], r.get("r"), r.get("symbol"),
                r.get("entry_time"), r.get("exit_time"), "crypto")
    for r in load(repo, "AgentTrades"):
        seg, rules = r.get("segment"), str(r.get("rules") or "")
        if seg == "stock" and rules.startswith("baseline A") and r.get("outcome") not in (None, "", "open"):
            put("Agent picks: stocks, baseline A", "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"), r.get("exit_time"))
        elif seg == "stock" and rules.startswith("adaptive") and r.get("outcome") not in (None, "", "open"):
            put("Agent picks: stocks, adaptive", "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"), r.get("exit_time"))
        elif seg == "option" and rules in ("ATM call", "smart call") and not str(r.get("note") or "").endswith(" open") \
                and not str(r.get("outcome") or "").startswith("skipped"):
            put("Agent picks: " + ("ATM calls" if rules == "ATM call" else "smart calls (delta 0.6, 7-21d, no earnings)"),
                "% premium", r["date"], r.get("return_pct"), r["symbol"], r.get("entry_time"), r.get("exit_time"), "option")
        elif seg == "crypto":
            put("Agent picks: crypto 1h", "R", r["date"], r.get("r_net"), r["symbol"], r.get("entry_time"), r.get("exit_time"), "crypto")
    for r in load(repo, "MLShadow"):
        if r.get("realized") not in (None, "") and str(r.get("take")).lower() in ("true", "1", "yes"):
            put("ML meta: " + str(r.get("model")), "R-equivalent", r["date"], num(r["realized"]) * 100 if num(r["realized"]) is not None else None,
                r.get("symbol"), None, None, "ml", {"choice": r.get("realized_choice") or r.get("choice")})
    return T


def main():
    a = sys.argv[1:]
    if a[0] == "add":
        rows = json.load(open(a[3]))
        if isinstance(rows, dict) and "rows" in rows: rows = rows["rows"]
        print(json.dumps(add(a[1], a[2], rows)))
    elif a[0] == "count":
        print(json.dumps({t: len(load(a[1], t)) for t in SPECS}))
    elif a[0] == "trades":
        print(json.dumps(trades(a[1]), separators=(",", ":")))


if __name__ == "__main__":
    main()
