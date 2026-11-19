"""Combinatorial purged cross-validation (CPCV, Lopez de Prado 2018) for the strategy lab (added 2026-11-19).

  python3 cpcv.py FILE.json [N_GROUPS] [K_TEST] [EMBARGO_DAYS]   (defaults 10, 2, 5)

FILE = {"configs": {"<setting name>": {"YYYY-MM-DD": daily return %, ...}, ...}}: the daily returns of EVERY
parameter setting that was tried, over the whole history (use data/hist: daily bars since 2016, 5-minute bars for
2 years). Days are split into N contiguous groups; every combination of K groups is a test set, the other groups
(minus EMBARGO_DAYS on each side of every test group, so overlapping trades cannot leak) are the training set. In each
split the setting with the best training Sharpe is chosen and its test-group returns are kept. The test pieces are
assembled into K/N x C(N, K) full backtest paths (9 for 10/2), so the result is a DISTRIBUTION of out-of-sample
Sharpe ratios across market regimes instead of one lucky or unlucky train/test split.

Output: path Sharpes (annualised), median, share of paths above 0, PBO (share of splits where the chosen setting
ranks in the bottom half of all settings on the test set) and pass. Pass (pre-registered 2026-11-19): median path
Sharpe > 0, at least 70% of paths above 0, PBO <= 0.5. review.py gate requires this when "cpcv" is given.
"""
import itertools, json, math, sys


def sharpe(xs):
    n = len(xs)
    if n < 2: return 0.0
    m = sum(xs) / n; v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(v) * math.sqrt(252) if v > 0 else 0.0


def cpcv(configs, N=10, K=2, embargo=5):
    days = sorted({d for c in configs.values() for d in c})
    if len(days) < N * 20: return {"error": "need at least %d days, have %d" % (N * 20, len(days))}
    names = sorted(configs); R = {n: [configs[n].get(d, 0.0) for d in days] for n in names}
    size = len(days) / N; G = [list(range(int(round(g * size)), int(round((g + 1) * size)))) for g in range(N)]
    splits = list(itertools.combinations(range(N), K)); test_pieces = {}; pbo_hits = 0
    for sp in splits:
        test = set(i for g in sp for i in G[g]); ban = set()
        for g in sp:
            lo, hi = G[g][0], G[g][-1]; ban |= set(range(max(0, lo - embargo), min(len(days), hi + embargo + 1)))
        train = [i for i in range(len(days)) if i not in ban]
        best = max(names, key=lambda n: sharpe([R[n][i] for i in train]))
        for g in sp: test_pieces.setdefault(g, []).append([R[best][i] for i in G[g]])
        ts = sorted(names, key=lambda n: sharpe([R[n][i] for i in sorted(test)]))
        if len(names) > 1 and ts.index(best) < len(names) / 2: pbo_hits += 1
    n_paths = len(test_pieces[0])
    paths = [sharpe([x for g in range(N) for x in test_pieces[g][j]]) for j in range(n_paths)]
    srt = sorted(paths); med = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
    pos = sum(1 for p in paths if p > 0) / len(paths); pbo = pbo_hits / len(splits) if len(names) > 1 else None
    ok = med > 0 and pos >= 0.7 and (pbo is None or pbo <= 0.5)
    return {"days": len(days), "first": days[0], "last": days[-1], "configs": len(names), "groups": N, "k_test": K,
            "embargo_days": embargo, "paths": [round(p, 3) for p in paths], "median_sharpe": round(med, 3),
            "share_positive": round(pos, 3), "pbo": round(pbo, 3) if pbo is not None else None, "pass": ok}


if __name__ == "__main__":
    a = sys.argv[1:]
    cfg = json.load(open(a[0]))["configs"]
    print(json.dumps(cpcv(cfg, int(a[1]) if len(a) > 1 else 10, int(a[2]) if len(a) > 2 else 2,
                          int(a[3]) if len(a) > 3 else 5), indent=1))
