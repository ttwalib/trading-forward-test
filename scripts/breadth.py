"""Market breadth from Quantavius the 1st's own daily bars (added 2026-11-23, tools audit).

Why: breadth (how many stocks take part in a move) is a standard regime input that the evidence pack and the morning
research did not have. The trading-research-addons skill "market-breadth-analyzer" reads a third-party CSV that the
scheduled tasks cannot reach and whose history could be revised; this script computes the same kind of measures from
the stored bars instead, so it is point-in-time and needs no network.

For each of the last 60 trading days of SPY, over that month's point-in-time top-100 list (scripts/pitu.py):
  pct_above_50d / pct_above_200d : share of members whose close is above its 50 / 200-day simple average
  net_new_highs_20d              : (members at a 20-day closing high - members at a 20-day closing low) / members
  advancers_pct                  : share of members that closed up on the day
A short "read" line says where the latest values sit against their own 60-day range. Report only: no rule uses it.

    python3 breadth.py REPO [DAY]   -> JSON on stdout (nightly writes data/nightly/breadth.json)
"""
import datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import decisions, pitu  # noqa: E402


def closes(repo, sym):
    out = {}
    for b in decisions.hist_bars(repo, "1d", sym) + decisions.bars(repo, "1d", sym):
        out[dt.datetime.fromtimestamp(b["t"], dt.timezone.utc).date().isoformat()] = b["c"]
    return out


def main():
    repo = os.path.abspath(sys.argv[1]); day = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "9999-12-31"
    L = pitu.lists(repo)
    spy = closes(repo, "SPY"); cal = sorted(d for d in spy if d <= day)
    days = cal[-60:]
    syms = sorted({s for m in L.values() for s in m})
    C = {s: closes(repo, s) for s in syms}
    rows = []
    for d in days:
        i = cal.index(d); a50 = a200 = hi = lo = up = n = 0
        for s in syms:
            if not pitu.member(L, s, d) or d not in C[s]: continue
            ser = [C[s][x] for x in cal[max(0, i - 199): i + 1] if x in C[s]]
            if len(ser) < 50: continue
            n += 1; c = ser[-1]
            a50 += c > sum(ser[-50:]) / 50
            a200 += len(ser) >= 200 and c > sum(ser[-200:]) / 200
            w = ser[-20:]; hi += c >= max(w); lo += c <= min(w)
            up += len(ser) > 1 and c > ser[-2]
        if n: rows.append({"date": d, "members": n, "pct_above_50d": round(100 * a50 / n, 1),
                           "pct_above_200d": round(100 * a200 / n, 1), "net_new_highs_20d": round(100 * (hi - lo) / n, 1),
                           "advancers_pct": round(100 * up / n, 1)})
    out = {"day": day if day != "9999-12-31" else (days[-1] if days else None), "universe": "pit top 100", "rows": rows}
    if rows:
        last = rows[-1]; rng = lambda k: (min(r[k] for r in rows), max(r[k] for r in rows))
        out["latest"] = last
        out["read"] = "; ".join(f"{k} {last[k]} (60-day range {rng(k)[0]} to {rng(k)[1]})"
                                for k in ("pct_above_50d", "pct_above_200d", "net_new_highs_20d"))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
