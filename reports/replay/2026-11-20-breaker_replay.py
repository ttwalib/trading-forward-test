import sys, json, math, datetime as dt
sys.path.insert(0, '/tmp/repo/scripts')
import allocator as A, tcal
repo = '/tmp/repo'; day = sys.argv[1] if len(sys.argv) > 1 else '2026-11-19'
S_all = A.sleeves(repo)
S = {k: v for k, v in S_all.items() if k.startswith('L')}   # library sleeves: the only ones with history
spy = A.dclose(repo, 'SPY', total_return=True); vix = A.dclose(repo, 'VIX')
tcal.START = dt.date(2025, 6, 2)     # replay: treat history from here as if live (no haircut), 120d warm-up before
out = {}
for mode in ('fixed', 'vol'):
    A.BREAKER_MODE = mode
    rows, W = A.simulate(repo, day, S, spy, vix)
    def perf(xs):
        cum = 1; peak = 1; dd = 0
        for x in xs: cum *= 1 + x / 100; peak = max(peak, cum); dd = max(dd, 1 - cum / peak)
        m = sum(xs) / len(xs); sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
        return {'total_pct': round((cum - 1) * 100, 2), 'sharpe': round(m / sd * math.sqrt(252), 2) if sd else None, 'max_dd_pct': round(dd * 100, 2)}
    bdays = {}
    for w in W:
        for b in w['breakers']: bdays[b] = bdays.get(b, 0) + 1
    out[mode] = {'days': len(rows), 'ai': perf([r['ai'] for r in rows]), 'spy': perf([r['spy'] for r in rows]),
                 'equal': perf([r['equal'] for r in rows]),
                 'avg_invested': round(sum(r['invested'] for r in rows) / len(rows), 3),
                 'breaker_days': dict(sorted(bdays.items())),
                 'avg_weight': {k: round(sum(w['weights'].get(k, 0) for w in W) / len(W), 3) for k in sorted(S)}}
print(json.dumps(out, indent=1))
