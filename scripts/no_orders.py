#!/usr/bin/env python3
"""No-orders check (added 2026-11-21): fails if any script or workflow in the repo contains an order-related call.

The forward test is a simulation. Nothing in this repository may place, preview, modify or cancel an order. The data
feed talks only to data.alpaca.markets (market data); the trading hosts and every order call are forbidden strings.
Run: python3 scripts/no_orders.py REPO   (exit code 1 and a list of hits if anything is found). The no-orders workflow
runs it on every push that touches scripts or workflows. Scheduled-task prompts are not in the repo; each of them
carries the same rule in words and names the read-only tools it may use.
"""
import os, re, sys

FORBIDDEN = [r"/v2/orders", r"/v1/orders", r"paper-api\.alpaca", r"(?<!data\.)(?<!broker-)\bapi\.alpaca\.markets", r"broker-api\.alpaca",
             r"submit_order", r"place_order", r"placeOrder", r"create_order", r"cancel_order", r"replace_order",
             r"close_position", r"close_all_positions", r"create_order_instruction", r"delete_order_instruction",
             r"TradingClient", r"/iserver/account/.*/orders?", r"/v2/positions", r"/v2/account\b"]
SKIP = {os.path.join("scripts", "no_orders.py")}


def scan(repo):
    hits = []
    for base in ("scripts", ".github", "strategies"):
        for dp, _, fs in os.walk(os.path.join(repo, base)):
            for f in fs:
                p = os.path.join(dp, f); rel = os.path.relpath(p, repo)
                if rel in SKIP or not f.endswith((".py", ".yml", ".yaml", ".sh", ".js")): continue
                try: txt = open(p, encoding="utf-8", errors="replace").read()
                except OSError: continue
                for i, line in enumerate(txt.splitlines(), 1):
                    for pat in FORBIDDEN:
                        if re.search(pat, line): hits.append("%s:%d: %s" % (rel, i, pat))
    return hits


if __name__ == "__main__":
    h = scan(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("no order-related calls found" if not h else "ORDER-RELATED CALLS FOUND:\n" + "\n".join(h))
    sys.exit(1 if h else 0)
