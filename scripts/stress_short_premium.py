#!/usr/bin/env python3
"""Stress test of the short-premium option sleeves W1, W2, D2 and D3 (added 2026-11-21, after the external review).

The crash drill of 2026-11-20 covered the daily library sleeves only. Option prices before 2024 are not in the store,
so this test needs no option prices: it replays each structure's fixed entry rules on SPY's daily history since 2016
and settles every position at expiry at intrinsic value, with a fixed credit taken from what the live test has paid so
far in a calm market. That is deliberately harsh in two ways: the stop-loss and take-profit rules are ignored (every
position is held to expiry), and in a real sell-off the credits would be larger than assumed.

  python3 stress_short_premium.py REPO > out.json

Results are in % of each position's max risk and in % of sleeve capital (allocator.py gives every ledger trade
1/5 of a percent of its sleeve per unit risked, so one full max loss costs the sleeve 0.20%).
Run once; logged as one trial. Nothing here feeds the allocator.
"""
import csv, gzip, json, os, sys, datetime as dt

RISK_PER_TRADE = 0.2     # % of sleeve capital per unit risked (allocator.sleeves: result / 5)
# short and long distance from S, and credit as a share of the spread width (live entries 2026-11-16..20)
RULES = {"W1": {"legs": [("P", 0.02, 0.03)], "credit": 0.13, "weekly": True},
         "W2": {"legs": [("P", 0.025, 0.035), ("C", 0.025, 0.035)], "credit": 0.075, "weekly": True},   # per side
         "D2": {"legs": [("P", 0.03, 0.05)], "credit": 0.03, "weekly": False},
         "D3": {"legs": [("C", 0.03, 0.05)], "credit": 0.015, "weekly": False}}


def load(repo):
    f = os.path.join(repo, "data", "hist", "1d", "SPY.csv.gz"); out = []
    for r in csv.DictReader(gzip.open(f, "rt")):
        out.append((dt.datetime.fromtimestamp(int(r["t"]), dt.timezone.utc).date(), float(r["o"]), float(r["c"])))
    return out


def position(rule, s, st):
    """Result in % of max risk, held to expiry. Width is the same on both sides of a condor; max risk = width - credit."""
    legs = rule["legs"]; loss = 0.0; credit = 0.0; width = None
    for right, a, b in legs:
        w = (b - a) * s; width = w; credit += rule["credit"] * w
        ks = s * (1 - a) if right == "P" else s * (1 + a)
        hit = (ks - st) if right == "P" else (st - ks)
        loss += min(max(hit, 0.0), w)
    return 100.0 * (credit - loss) / (width - credit)


def run(repo):
    B = load(repo); idx = {d: i for i, (d, _, _) in enumerate(B)}; out = {}
    weeks = {}
    for i, (d, o, c) in enumerate(B): weeks.setdefault(d.isocalendar()[:2], []).append(i)
    all_by_week = {}
    for name, rule in RULES.items():
        trades = []
        if rule["weekly"]:
            for wk, ii in weeks.items():
                last = ii[-1]
                mon = ii[0]; wed = next((i for i in ii if B[i][0].weekday() >= 2), None)
                for e in {mon, wed} - {None}:
                    if e >= last: continue                     # needs at least one day to expiry
                    trades.append((B[e][0], position(rule, B[e][1], B[last][2])))
        else:
            for i in range(len(B) - 2): trades.append((B[i][0], position(rule, B[i][1], B[i + 2][2])))
        res = [r for _, r in trades]; n = len(res)
        byw = {}
        for d, r in trades: byw.setdefault(d.isocalendar()[:2], []).append(r)
        wk_sum = {k: sum(v) for k, v in byw.items()}
        for k, v in wk_sum.items(): all_by_week[k] = all_by_week.get(k, 0.0) + v
        ks = sorted(wk_sum); roll4 = [sum(wk_sum[k] for k in ks[i:i + 4]) for i in range(len(ks) - 3)]
        worst_wk = min(wk_sum, key=wk_sum.get)
        def window(a, b): return round(sum(r for d, r in trades if a <= d.isoformat() <= b) * RISK_PER_TRADE / 100, 2)
        wins = [r for r in res if r > 0]
        out[name] = {"trades": n, "win_rate_pct": round(100 * len(wins) / n, 1), "avg_pct_of_risk": round(sum(res) / n, 2),
                     "avg_win_pct_of_risk": round(sum(wins) / len(wins), 2) if wins else None,
                     "full_max_loss_trades": sum(1 for r in res if r <= -99.9),
                     "worst_trade_pct_of_risk": round(min(res), 1),
                     "worst_week": {"iso_week": "%d-W%02d" % worst_wk, "sum_pct_of_risk": round(wk_sum[worst_wk], 1),
                                    "pct_of_sleeve": round(wk_sum[worst_wk] * RISK_PER_TRADE / 100, 2)},
                     "worst_4_weeks_pct_of_sleeve": round(min(roll4) * RISK_PER_TRADE / 100, 2),
                     "total_pct_of_sleeve": round(sum(res) * RISK_PER_TRADE / 100, 2),
                     "crash_2020_02_19_to_04_30_pct_of_sleeve": window("2020-02-19", "2020-04-30"),
                     "bear_2022_01_03_to_10_14_pct_of_sleeve": window("2022-01-03", "2022-10-14")}
    ks = sorted(all_by_week); w = min(all_by_week, key=all_by_week.get)
    roll4 = [sum(all_by_week[k] for k in ks[i:i + 4]) for i in range(len(ks) - 3)]
    comb = {"worst_week": "%d-W%02d" % w,
            "worst_week_sum_pct_of_sleeve_if_all_four_equal": round(all_by_week[w] * RISK_PER_TRADE / 100 / 4, 2),
            "worst_4_weeks_pct_if_all_four_equal": round(min(roll4) * RISK_PER_TRADE / 100 / 4, 2)}
    return {"what": "short-premium option sleeves held to expiry on SPY daily history, fixed calm-market credits, stops ignored",
            "from": B[0][0].isoformat(), "to": B[-1][0].isoformat(), "risk_per_trade_pct_of_sleeve": RISK_PER_TRADE,
            "assumed_credit_share_of_width": {k: v["credit"] for k, v in RULES.items()}, "sleeves": out, "combined": comb}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1]), indent=1))
