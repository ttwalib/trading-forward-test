"""Monte Carlo risk report (added 2026-11-21, before the change freeze; report only, never part of the verdict).

Question it answers, in plain words: if the AI portfolio keeps behaving the way it has, how likely is a painful run?
For the AI portfolio and every benchmark it resamples the daily returns in blocks of 5 trading days (a block bootstrap
keeps short streaks and calm/stormy stretches together) into 10,000 possible futures, and reports:
  - over 47 trading days (the length of the verdict window) and 63 trading days (about three months):
    the median return, the 5% and 95% outcomes, the chance of ending below zero, and the chance of a fall of 10% or
    more from a high at some point;
  - over up to 252 trading days: the chance of falling 10% before gaining 10% ("pain first"), the chance of the
    reverse, and the chance of neither.
All series are resampled with the SAME block draws, so the comparison between the AI and a benchmark is like for like.
The seed is fixed (20261121), so every run on the same data gives the same numbers.

Two bases:
  replay - the allocator's rules replayed on the strategy library's past data (2025-06-02 to 2026-11-13, before the
           test). Built once with `montecarlo.py build-replay REPO` into reports/replay/2026-11-21-mc_series.json.
           Past data flatters (survivorship, strategies chosen with hindsight), so this basis is a rough guide.
  live   - the AI portfolio's own forward days (data/allocator/portfolio.jsonl). Reported only once there are at least
           20 live days; until then the live block says so.
A resample cannot invent events that are not in its history: a crash worse than the worst stretch in the data is
outside what this report can show.

  python3 montecarlo.py build-replay REPO      -> reports/replay/2026-11-21-mc_series.json (run once)
  python3 montecarlo.py report REPO            -> JSON to stdout (nightly.py saves it as data/nightly/montecarlo.json)
"""
import json, os, random, sys, datetime as dt

SERIES = ("ai", "equal", "spy", "sh_rp", "sh_mv", "sh_win")
LABELS = {"ai": "AI allocator", "equal": "Equal weight", "spy": "SPY", "sh_rp": "Risk parity", "sh_mv": "Minimum variance",
          "sh_win": "Recent winners"}
PATHS, BLOCK, SEED, MIN_LIVE = 10000, 5, 20261121, 20
HORIZONS, LONG, BAND = (47, 63), 252, 10.0
REPLAY = os.path.join("reports", "replay", "2026-11-21-mc_series.json")


def build_replay(repo):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tcal, allocator
    tcal.START = dt.date(2025, 6, 2)          # replay only: every day from here counts as a forward day of the rules
    end = "2026-11-13"
    S = allocator.sleeves(repo); spy = allocator.dclose(repo, "SPY", total_return=True); vix = allocator.dclose(repo, "VIX")
    rows, _ = allocator.simulate(repo, end, S, spy, vix)
    rows = [{"date": r["date"], **{k: round(float(r.get(k) or 0.0), 5) for k in SERIES}} for r in rows if r["date"] <= end]
    out = {"built": dt.date.today().isoformat(), "from": rows[0]["date"] if rows else None, "to": end, "days": len(rows),
           "note": "allocator rules replayed on the library's past data; daily returns in percent", "rows": rows}
    p = os.path.join(repo, REPLAY); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w"), separators=(",", ":"))
    return {k: v for k, v in out.items() if k != "rows"}


def simulate(rows):
    """rows: list of {series: daily % return}. Returns per-series statistics from shared block draws."""
    n = len(rows); rng = random.Random(SEED)
    R = {k: [float(r.get(k) or 0.0) / 100.0 for r in rows] for k in SERIES}
    acc = {k: {"end": {h: [] for h in HORIZONS}, "dd": {h: 0 for h in HORIZONS}, "pain": 0, "gain": 0} for k in SERIES}
    for _ in range(PATHS):
        idx = []
        while len(idx) < LONG:
            s = rng.randrange(n); idx.extend((s + j) % n for j in range(BLOCK))
        idx = idx[:LONG]
        for k in SERIES:
            x = R[k]; v = peak = 1.0; mdd = 0.0; hit = None; a = acc[k]
            for i, j in enumerate(idx, 1):
                v *= 1.0 + x[j]
                if v > peak: peak = v
                dd = 1.0 - v / peak
                if dd > mdd: mdd = dd
                if hit is None:
                    if v <= 1 - BAND / 100: hit = "pain"
                    elif v >= 1 + BAND / 100: hit = "gain"
                if i in a["end"]:
                    a["end"][i].append(v - 1.0)
                    if mdd >= BAND / 100: a["dd"][i] += 1
                if i >= max(HORIZONS) and hit is not None: break
            if hit: a[hit] += 1
    pct = lambda xs, q: round(sorted(xs)[min(len(xs) - 1, int(q * len(xs)))] * 100, 2)
    out = {}
    for k in SERIES:
        a = acc[k]; o = {"label": LABELS[k]}
        for h in HORIZONS:
            e = a["end"][h]
            o["d%d" % h] = {"median_pct": pct(e, 0.5), "p5_pct": pct(e, 0.05), "p95_pct": pct(e, 0.95),
                            "chance_loss": round(sum(1 for v in e if v < 0) / len(e), 3),
                            "chance_dd10": round(a["dd"][h] / PATHS, 3)}
        o["pain_first"] = round(a["pain"] / PATHS, 3); o["gain_first"] = round(a["gain"] / PATHS, 3)
        o["neither"] = round(1 - o["pain_first"] - o["gain_first"], 3)
        out[k] = o
    return out


def report(repo):
    rep = {"method": "block bootstrap, %d paths, blocks of %d days, seed %d; shared draws across series" % (PATHS, BLOCK, SEED),
           "band_pct": BAND, "horizons_days": list(HORIZONS), "long_horizon_days": LONG,
           "never_in_verdict": True}
    p = os.path.join(repo, REPLAY)
    if os.path.exists(p):
        D = json.load(open(p))
        rep["replay"] = {"from": D["from"], "to": D["to"], "days": D["days"], "series": simulate(D["rows"]),
                         "caveat": "past data replayed with the allocator's rules; survivorship and hindsight flatter it"}
    else:
        rep["replay"] = {"missing": "run montecarlo.py build-replay first"}
    live = []
    f = os.path.join(repo, "data", "allocator", "portfolio.jsonl")
    if os.path.exists(f):
        live = [json.loads(l) for l in open(f) if l.strip()]
    if len(live) >= MIN_LIVE:
        rep["live"] = {"from": live[0]["date"], "to": live[-1]["date"], "days": len(live), "series": simulate(live)}
    else:
        rep["live"] = {"days": len(live), "waiting": "reported from %d live days" % MIN_LIVE}
    return rep


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("build-replay", "report"):
        print(__doc__); sys.exit(2)
    print(json.dumps(build_replay(a[1]) if a[0] == "build-replay" else report(a[1]), indent=1))
