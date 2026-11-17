import json, sys
# Morning Reddit snapshot (taken before 9:30 ET). Input: ApeWisdom all-stocks pages saved as JSON files.
# Pre-registered rules: "rising" = at least 10 mentions in 24h AND at least 1.5x the previous 24h.
# Trending pool = top 5 by 24h mentions that are not on the watchlist and not an index/leveraged ETF.
WATCH = "AAPL TSLA NVDA AMD MSFT AMZN META GOOGL NFLX AVGO PLTR COIN MU INTC UBER JPM BAC XOM SOFI HOOD MARA MSTR".split()
ETFS = set("SPY QQQ IWM DIA TQQQ SQQQ SPXL SPXS UVXY VXX SOXL SOXS ARKK GLD SLV TLT TSLL NVDL VOO VTI XLF XLE SMH".split())
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0
rows = {}
for path in sys.argv[1:]:
    d = json.load(open(path))
    for it in d.get("results", []):
        t = str(it.get("ticker", "")).upper().strip()
        if not t or t in rows: continue
        m, m0 = num(it.get("mentions")), num(it.get("mentions_24h_ago"))
        rows[t] = {"mentions": int(m), "mentions_24h_ago": int(m0), "rank": int(num(it.get("rank"))),
                   "upvotes": int(num(it.get("upvotes"))), "name": it.get("name", ""),
                   "change_pct": round(100 * (m - m0) / m0, 1) if m0 else None,
                   "rising": m >= 10 and m >= 1.5 * max(m0, 1)}
trending = [t for t, r in sorted(rows.items(), key=lambda kv: -kv[1]["mentions"])
            if t not in WATCH and t not in ETFS and t.isalpha() and len(t) <= 5][:5]
out = {"symbols": {t: rows.get(t, {"mentions": 0, "mentions_24h_ago": 0, "rank": None, "upvotes": 0, "change_pct": None, "rising": False})
                   for t in WATCH + trending}, "trending": trending, "tickers_seen": len(rows)}
print(json.dumps(out, indent=1))
