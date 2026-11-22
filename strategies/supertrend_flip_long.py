"""Strategy lab 2026-11-21: Supertrend flip, long only, hourly crypto bars (BTC/ETH/SOL).

Idea: Supertrend (Olivier Seban; ATR bands around the bar midpoint). Go long when the Supertrend flips from down to up
on a bar close; leave when it flips back down. Source: public Supertrend crypto backtests, e.g.
https://www.coinquant.ai/blog/supertrend-on-ethereum-6-years-of-backtest-results
Rules: signal on a close, fill at the next open, stop = entry - k x ATR14 (of the signal bar) checked first in each
bar, exit at the next open after a down flip, 0.2% cost per side, one position per coin, no look-ahead.
bars = {"time","open","high","low","close","volume"} arrays (hist.py export). Returns a list of trades.
"""
COST = 0.002
ST_PERIOD = 10
PARAMS = {"m": 2, "k": 4}   # chosen on the first half only (see the .gate.json beside this file)


def _atr(h, l, c, n):
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    out = [None] * len(c); a = None
    for i, x in enumerate(tr):
        if i == n - 1: a = sum(tr[:n]) / n
        elif i >= n: a = (a * (n - 1) + x) / n
        out[i] = a
    return out


def _supertrend(h, l, c, n, m):
    a = _atr(h, l, c, n); up = [None] * len(c); fu = fl = None; d = None
    for i in range(len(c)):
        if a[i] is None: continue
        mid = (h[i] + l[i]) / 2; bu = mid + m * a[i]; bl = mid - m * a[i]
        if fu is None: fu, fl, d = bu, bl, c[i] > mid
        else:
            fu = bu if (bu < fu or c[i - 1] > fu) else fu
            fl = bl if (bl > fl or c[i - 1] < fl) else fl
            if d and c[i] < fl: d = False
            elif (not d) and c[i] > fu: d = True
        up[i] = d
    return up


def strategy(bars, m=None, k=None):
    m = PARAMS["m"] if m is None else m; k = PARAMS["k"] if k is None else k
    t, o, h, l, c = bars["time"], bars["open"], bars["high"], bars["low"], bars["close"]
    up = _supertrend(h, l, c, ST_PERIOD, m); a14 = _atr(h, l, c, 14); trades = []; pos = None
    for i in range(1, len(c)):
        # bar i: act on what was known at the close of bar i-1
        if pos is None:
            if i >= 2 and up[i - 1] is True and up[i - 2] is False and a14[i - 1] is not None:
                pos = {"entry_time": t[i], "entry": o[i], "stop": o[i] - k * a14[i - 1]}
            else: continue
        elif pos.get("exit_next"):
            trades.append(_close(pos, t[i], o[i], "flip")); pos = None; continue
        if pos is not None:
            if l[i] <= pos["stop"]:          # stop first; a gap through the stop fills at the open
                trades.append(_close(pos, t[i], min(o[i], pos["stop"]), "stop")); pos = None
            elif up[i] is False: pos["exit_next"] = True
    return trades


def _close(p, tm, px, why):
    net = px * (1 - COST) / (p["entry"] * (1 + COST)) - 1
    return {"entry_time": p["entry_time"], "entry": p["entry"], "stop": p["stop"], "exit_time": tm, "exit": px,
            "reason": why, "net_pct": round(net * 100, 4)}
