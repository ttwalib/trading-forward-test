"""labrun self-test (2026-11-25): a moving-average filter on SPY, used only to prove the GitHub sweep job; removed after the test, never a lab trial."""
import decisions, datetime as dt
def configs(repo, sym="SPY"):
    b = decisions.hist_bars(repo, "1d", sym); c = [x["c"] for x in b]; out = {}
    for n in (20, 50, 100):
        s = {}
        for i in range(n + 1, len(c)):
            d = dt.datetime.utcfromtimestamp(b[i]["t"]).date().isoformat()
            s[d] = (c[i] / c[i-1] - 1) * 100 if c[i-1] > sum(c[i-1-n:i-1]) / n else 0.0
        out["ma%d" % n] = s
    return out
def trades(repo, setting, sym="SPY"):
    return [0.1, -0.2, 0.3]
