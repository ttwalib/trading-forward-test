import json, sys, random
# Week-end uncertainty: bootstrap the average result per trade for each strategy.
# Input JSON: {"name": [r1, r2, ...], ...}  (R per trade for stock variants; % of premium for options).
# Output per strategy: trades, average, 90% range of the average, chance the true average is above 0, verdict.
data = json.load(open(sys.argv[1])); B = 10000; rng = random.Random(20261120)
out = {}
for name, xs in data.items():
    xs = [float(x) for x in xs]; n = len(xs)
    if n == 0: out[name] = {"trades": 0, "verdict": "no trades"}; continue
    avg = sum(xs) / n
    if n < 10:
        out[name] = {"trades": n, "avg": round(avg, 2), "verdict": "too few trades to judge (under 10)"}; continue
    means = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(B))
    lo, hi = means[int(0.05 * B)], means[int(0.95 * B) - 1]
    p_pos = sum(m > 0 for m in means) / B
    verdict = ("edge likely positive" if lo > 0 else "edge likely negative" if hi < 0
               else "can't tell from noise")
    out[name] = {"trades": n, "avg": round(avg, 2), "range90": [round(lo, 2), round(hi, 2)],
                 "chance_above_zero": round(p_pos, 2), "verdict": verdict}
print(json.dumps(out, indent=1))
