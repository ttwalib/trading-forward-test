"""Crash drill (run once on 2026-11-20, before the change freeze; logged as one trial; no tuning afterwards).

Question: the allocator must always be fully invested. What would the same rules have done in the two worst recent
markets, the 2020 crash (2020-02-19 to 2020-04-30) and the 2022 bear market (2022-01-03 to 2022-10-14)?

Method: a temporary copy of the repo whose daily bars come from the archive data/hist/1d (since 2016), no 5-minute
bars and an empty ledger. library.py and allocator.py run unchanged on it up to 2022-12-30.

Limits, stated with the result:
- Daily sleeves only (L5-L13, L15, L16, and L17 where its ETFs have archive history). The intraday sleeves (L1-L4,
  L14), baseline A, the options tracks and the crypto tracks have no data that far back and are absent.
- The stock list is today's S&P 100, so companies that fell out of the index before today are missing (survivorship
  bias). That flatters every stock-picking sleeve; the true result would be worse.
- Regime labels use the archive's SPY and VIX; costs are today's cost model.
The result is a stress reading of the allocation rules, not evidence that the strategies work.

  python3 2026-11-20-crash_drill.py REPO OUT.json
"""
import csv, gzip, json, os, shutil, subprocess, sys, tempfile, datetime as dt

repo, out = os.path.abspath(sys.argv[1]), sys.argv[2]
END = "2022-12-30"
WINDOWS = {"crash_2020": ("2020-02-19", "2020-04-30"), "bear_2022": ("2022-01-03", "2022-10-14"), "whole_2017_2022": ("2017-01-03", END)}
tmp = tempfile.mkdtemp(prefix="drill_")
os.makedirs(os.path.join(tmp, "data", "bars", "1d")); shutil.copytree(os.path.join(repo, "scripts"), os.path.join(tmp, "scripts"))
shutil.copy(os.path.join(repo, "data", "universe.json"), os.path.join(tmp, "data", "universe.json"))
if os.path.exists(os.path.join(repo, "data", "corp")): shutil.copytree(os.path.join(repo, "data", "corp"), os.path.join(tmp, "data", "corp"))
n = 0
for f in sorted(os.listdir(os.path.join(repo, "data", "hist", "1d"))):
    sym = f[:-7]
    with gzip.open(os.path.join(repo, "data", "hist", "1d", f), "rt") as fh, open(os.path.join(tmp, "data", "bars", "1d", sym + ".jsonl"), "w") as w:
        for r in csv.DictReader(fh):
            if dt.datetime.fromtimestamp(int(r["t"]), dt.timezone.utc).date().isoformat() > END: continue
            w.write(json.dumps({"t": int(r["t"]), "o": float(r["o"]), "h": float(r["h"]), "l": float(r["l"]), "c": float(r["c"]), "v": float(r["v"] or 0)}) + "\n")
    n += 1
sys.path.insert(0, os.path.join(tmp, "scripts"))
run = lambda a: subprocess.run([sys.executable, "-I"] + a, capture_output=True, text=True)
p = run([os.path.join(tmp, "scripts", "library.py"), tmp, END]); assert p.returncode == 0, p.stderr[-600:]
lib = json.loads(p.stdout)
import allocator
allocator.tcal.START = dt.date(2017, 1, 3)     # replay only: the live allocator starts on 2026-11-16
S = allocator.sleeves(tmp); spy = allocator.dclose(tmp, "SPY", total_return=True); vix = allocator.dclose(tmp, "VIX")
rows, W = allocator.simulate(tmp, END, S, spy, vix)
res = {"run_on": "2026-11-20", "symbols_from_archive": n, "sleeves": sorted(S), "limits": __doc__.split("Limits, stated with the result:")[1].split("  python3")[0].strip(), "windows": {}}
for name, (a, b) in WINDOWS.items():
    sel = [r for r in rows if a <= r["date"] <= b]
    res["windows"][name] = {"from": a, "to": b, **{k: allocator.perf([r.get(k, 0.0) for r in sel]) for k in ("ai", "equal", "spy") + allocator.SHADOWS},
                            "avg_forced_fill_weight": round(sum(r.get("fill_w", 0) for r in sel) / max(1, len(sel)), 4),
                            "top_weights_first_day": dict(sorted(next((w["weights"] for w in W if w["date"] >= a), {}).items(), key=lambda kv: -kv[1])[:5])}
json.dump(res, open(out, "w"), indent=1); shutil.rmtree(tmp)
print(json.dumps(res["windows"], indent=1))
