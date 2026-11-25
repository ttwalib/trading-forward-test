"""Add IBKR trading fees to the deep-OTM results (1 contract per leg, x100 multiplier).

Usage: python3 fees.py d1 d1_out.json      (output of options_sim.py)
       python3 fees.py spread deep_out.json (output of deep_otm.py)
Fee model (IBKR Pro Fixed, US options), fixed in advance:
- Commission per contract: $0.65 if premium >= $0.10, $0.50 if $0.05-0.0999, $0.25 if under $0.05; minimum $1.00 per order.
- Plus $0.03 per contract per side for regulatory/clearing fees (ORF, OCC, FINRA TAF), approximate.
- D1: one order to open and one to close. An option closed at $0 (worthless) pays no closing fee.
- Spreads: one 2-leg combo order to open, one to close, charged at $0.65/contract (conservative: IBKR charges less on
  legs under $0.10). Held to expiry: no closing fee if it settles at $0, else a closing fee.
- Open positions are marked as if closed now, so the closing fee is included in the mark.
- Fees never change entries, exits, take-profit or stop decisions; they only change the measured result.
"""
import json, sys
REG = 0.03
def rate(p): return 0.65 if p >= 0.10 else 0.50 if p >= 0.05 else 0.25
def order_fee(prices): return round(max(1.00, sum(rate(p) for p in prices)) + REG * len(prices), 2)
kind, path = sys.argv[1], sys.argv[2]
d = json.load(open(path))
if kind == "d1":
    for r in d["trades"]:
        f_in = order_fee([r["option_entry"]])
        f_out = order_fee([r["option_exit"]]) if r["option_exit"] > 0 else 0.0
        cost = r["option_entry"] * 100 + f_in; back = r["option_exit"] * 100 - f_out
        r["fees_usd"] = round(f_in + f_out, 2); r["gross_return_pct"] = r["return_pct"]
        r["return_pct"] = round(100 * (back - cost) / cost, 1)
    rs = [r["return_pct"] for r in d["trades"] if r["status"] == "closed"]
    d["wins"] = sum(x > 0 for x in rs); d["avg_return_pct"] = round(sum(rs) / len(rs), 1) if rs else None
else:
    for r in d["spreads"]:
        if r["status"] not in ("open", "closed"): continue
        f_open = order_fee([1, 1])  # 2 legs at the $0.65 rate
        exitc = r.get("exit_cost", r.get("mark"))
        f_close = 0.0 if (r["status"] == "closed" and r.get("reason", "").startswith("expired") and exitc == 0) else order_fee([1, 1])
        fees = round(f_open + f_close, 2)
        r["fees_usd"] = fees; r["gross_pct"] = r["pct"]
        r["pct"] = round(100 * ((r["credit"] - exitc) * 100 - fees) / (r["max_risk"] * 100), 1)
print(json.dumps(d, indent=1))
