"""Implementable fills (added 2026-11-19, before the 2026-12-07 freeze; frozen with allocator.py and library.py).

The intraday strategies decide on the close of a 5-minute bar. A real trading engine sees that bar only after it has
closed, then needs time to act. Simulating the fill AT the signal bar's close ("ideal fill") is therefore a mild
look-ahead that flatters every intraday strategy. Every intraday result used for the verdict now uses an
IMPLEMENTABLE fill instead:

  1. If the 5-minute engine on GitHub Actions (engine.py) sealed a detection for that signal, the fill is the price it
     recorded at detection time (real-time IEX last trade), so the real detection delay is charged. A detection more
     than 20 minutes late (engine outage, GitHub not starting the job) falls back to rule 2.
  2. Otherwise the fill is the open of the 5-minute bar that starts LAG_MIN minutes after the signal bar closed
     (the price about LAG_MIN minutes later: the engine runs every 5 minutes and GitHub may start it late).

Exits are unchanged (stop and target orders rest at the broker; time exits are market-on-close).
Ledger trades (baseline A, variants, control list, adaptive, agent stock picks) are scored in R; the delay cost in R
is (implementable entry - ideal entry) / (ideal entry - stop) for a long. Rows without a stop use the baseline A
trade of the same symbol and day, else the median baseline A risk (entry - stop) / entry.
The ledger itself is never rewritten: the adjustment is applied where results are scored (allocator.py). The ideal
version is still reported beside it, so the size of the delay cost is visible.
"""
import json, os, datetime as dt
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
LAG_MIN = 5
_B5, _ENG = {}, {}


def _bars5(repo, sym):
    if sym not in _B5:
        out = {}
        f = os.path.join(repo, "data", "bars", "5m", sym + ".jsonl")
        if os.path.exists(f):
            for line in open(f):
                if line.strip():
                    b = json.loads(line); t = dt.datetime.fromtimestamp(b["t"], NY)
                    out[(t.date().isoformat(), t.strftime("%H:%M"))] = b
        h = os.path.join(repo, "data", "hist", "5m", sym + ".csv.gz")   # archive (older days), stored bars win
        if os.path.exists(h):
            import gzip, csv
            with gzip.open(h, "rt") as fh:
                for r in csv.DictReader(fh):
                    t = dt.datetime.fromtimestamp(int(r["t"]), NY); k = (t.date().isoformat(), t.strftime("%H:%M"))
                    if k not in out: out[k] = {"t": int(r["t"]), "o": float(r["o"]), "h": float(r["h"]), "l": float(r["l"]), "c": float(r["c"])}
        _B5[sym] = out
    return _B5[sym]


def _engine(repo, day):
    if day not in _ENG:
        rows = {}
        f = os.path.join(repo, "data", "decisions", "engine", day + ".jsonl")
        if os.path.exists(f):
            for line in open(f):
                if line.strip():
                    r = json.loads(line)
                    if r.get("fill_price") and (r.get("delay_min") or 99) <= 20: rows.setdefault((r["symbol"], r.get("signal_end")), r)
        _ENG[day] = rows
    return _ENG[day]


def plus(hhmm, minutes):
    h, m = map(int, hhmm.split(":")); x = h * 60 + m + minutes
    return "%02d:%02d" % (x // 60, x % 60)


def ideal_entry(repo, sym, day, signal_end):
    """Close of the signal bar (the bar that ends at signal_end)."""
    b = _bars5(repo, sym).get((day, plus(signal_end, -5)))
    return b["c"] if b else None


def implementable_entry(repo, sym, day, signal_end, lag=LAG_MIN):
    """(price, source) or (None, None). source: 'engine' or 'lag'."""
    e = _engine(repo, day).get((sym, signal_end))
    if e: return float(e["fill_price"]), "engine"
    b = _bars5(repo, sym).get((day, plus(signal_end, lag)))
    return (b["o"], "lag") if b else (None, None)


def hhmm_of(x):
    s = str(x or "")
    return s[-5:] if len(s) >= 5 and s[-3] == ":" and s[-5:-3].isdigit() else None


def delay_r(repo, trades):
    """{index: delta R} for R-unit stock trades with an HH:MM entry time. Negative = worse than the ideal fill."""
    risk = {}; allr = []
    for t in trades:
        if t.get("strategy") == "A baseline (watchlist)" and t.get("stop_px") and t.get("entry_px"):
            rp = (t["entry_px"] - t["stop_px"]) / t["entry_px"]
            if rp > 0: risk[(t["day"], t["symbol"])] = rp; allr.append(rp)
    med = sorted(allr)[len(allr) // 2] if allr else 0.005
    out = {}
    for i, t in enumerate(trades):
        if t.get("unit") != "R" or t.get("asset") != "stock" or not t.get("symbol"): continue
        se = hhmm_of(t.get("entry"))
        if not se or not ("09:30" < se <= "16:00"): continue
        ideal = t.get("entry_px") or ideal_entry(repo, t["symbol"], t["day"], se)
        real, src = implementable_entry(repo, t["symbol"], t["day"], se)
        if not ideal or not real: continue
        rp = (ideal - t["stop_px"]) / ideal if t.get("stop_px") and t["stop_px"] < ideal else risk.get((t["day"], t["symbol"]), med)
        if rp <= 0: continue
        d = -(real / ideal - 1) / rp                      # long-only ORB family
        out[i] = max(-1.5, min(1.5, d))                   # a fill beyond the stop/target is capped
    return out
