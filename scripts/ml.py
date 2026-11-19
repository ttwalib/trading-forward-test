"""Machine-learning layer: meta-labelling (take / skip) and instrument choice, validated without look-ahead.

  python3 ml.py train REPO DAY        walk-forward evaluation of every config, PBO, calibration, champion selection,
                                      fit + save models (refuses to refit during the frozen holdout: uses saved models)
  python3 ml.py predict REPO CANDS.json NOW_ISO   predictions for live candidates (decisions.py live output);
                                      prints MLShadow rows (logged BEFORE outcomes are known)
  python3 ml.py predict-crypto REPO NOW   shadow predictions for newly opened crypto track trades (MLShadow rows)
  python3 ml.py score REPO            fill realized results into unscored MLShadow ledger rows; prints updated rows
  python3 ml.py drift REPO DAY        PSI of each feature: training distribution vs the last 10 trading days
  python3 ml.py report REPO DAY       one JSON summary (what the ML nightly task posts)

Families
- stock: rows of data/decisions/stock.jsonl. Targets: take = y_stock > 0; expected result per instrument
  (stock, atm, d1, w4) from per-instrument regressors trained on rows where that instrument has a label.
  Choice = instrument with the highest predicted result; "none" (skip) when the take probability < threshold or
  the best predicted result <= 0. Until 40 rows carry option labels the chooser is stock-only (take / skip).
- crypto: rows of data/decisions/crypto.jsonl, one model across all tracks with the strategy as one-hot; take = R > 0.

Validation (Lopez de Prado): purged, embargoed walk-forward by trading day. Test blocks of 5 days; training uses only
days that end at least 1 trading day (embargo) before the test block; at least 15 training days. Metrics on the
out-of-sample predictions only: AUC, Brier, calibration table, mean result of taken trades vs always-take, share taken.
Configs: {logistic, gradient boosting (depth 2), random forest (depth 3)} x take thresholds {0.45, 0.50, 0.55}
(9 configs, all counted as trials). PBO by CSCV on the matrix of per-day OOS results (S = 8 blocks).
Champion = best OOS mean-taken config, accepted only if n_oos >= 60, its OOS mean beats always-take with a paired
day-bootstrap P >= 0.9, and either PBO < 0.5 or the median config also beats always-take (PBO alone is high when
every config is similarly good); otherwise the champion is "always take" (no ML filter). Live predictions always log
the best config's own decision (shadow), so it keeps being scored as a challenger. The training set is train-phase (and pre-test backfill) rows;
holdout rows are never used for fitting.
"""
import json, os, sys, math, pickle, random, itertools, datetime as dt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions, ledger, tcal
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.inspection import permutation_importance

SEED = 20261119; TEST_BLOCK = 5; EMBARGO = 1; MIN_TRAIN_DAYS = 15; MIN_OPT_ROWS = 40
THRESH = [0.45, 0.50, 0.55]


def clf(kind):
    if kind == "logistic":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), LogisticRegression(C=0.5, max_iter=2000))
    if kind == "gbm":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                             HistGradientBoostingClassifier(max_depth=2, learning_rate=0.05, max_iter=150, l2_regularization=1.0,
                                                            min_samples_leaf=15, random_state=SEED))
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                         RandomForestClassifier(n_estimators=300, max_depth=3, min_samples_leaf=10, random_state=SEED, n_jobs=-1))


def reg(kind="ridge"):
    if kind == "gbm":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                             HistGradientBoostingRegressor(max_depth=2, learning_rate=0.05, max_iter=150, min_samples_leaf=15, random_state=SEED))
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=10.0))


def matrix(rows, feats, keys=None):
    X = np.array([[np.nan if r["x"].get(f) is None else float(r["x"][f]) for f in feats] for r in rows], dtype=float)
    if keys:
        K = np.array([[1.0 if r.get("key") == k else 0.0 for k in keys] for r in rows]); X = np.hstack([X, K])
    return X


def family(repo, fam):
    rows = decisions.load(repo, fam)
    if fam == "stock":
        feats = decisions.STOCK_FEATURES; keys = None; ycol = "y_stock"
    else:
        feats = decisions.CRYPTO_FEATURES; keys = sorted({r["key"] for r in rows}); ycol = "y"
    rows = [r for r in rows if r["y"].get(ycol) is not None]
    return rows, feats, keys, ycol


def folds(days):
    days = sorted(days); out = []
    i = MIN_TRAIN_DAYS + EMBARGO
    while i < len(days):
        test = days[i:i + TEST_BLOCK]; train = days[:i - EMBARGO]
        out.append((set(train), set(test))); i += TEST_BLOCK
    return out


def walk_forward(rows, feats, keys, ycol):
    """OOS take-probabilities per config. Returns {kind: np.array of OOS prob (nan where not tested)}, mask."""
    fit_rows = [r for r in rows if r["phase"] in ("before", "train")]
    days = sorted({r["date"] for r in fit_rows}); X = matrix(fit_rows, feats, keys)
    y = np.array([r["y"][ycol] for r in fit_rows]); t = (y > 0).astype(int); D = np.array([r["date"] for r in fit_rows])
    P = {k: np.full(len(fit_rows), np.nan) for k in ("logistic", "gbm", "forest")}
    for tr, te in folds(days):
        a = np.array([d in tr for d in D]); b = np.array([d in te for d in D])
        if len(set(t[a])) < 2: continue
        for k in P:
            m = clf(k).fit(X[a], t[a]); P[k][b] = m.predict_proba(X[b])[:, 1]
    return fit_rows, X, y, t, D, P


def cscv_pbo(M, S=8):
    """M: (days x configs) OOS results. Probability of backtest overfitting via combinatorially symmetric CV."""
    T, N = M.shape
    if T < S or N < 2: return None
    blocks = np.array_split(np.arange(T), S); logits = []
    for c in itertools.combinations(range(S), S // 2):
        is_ = np.concatenate([blocks[i] for i in c]); oos = np.concatenate([blocks[i] for i in range(S) if i not in c])
        best = int(np.argmax(M[is_].mean(0))); perf = M[oos].mean(0)
        rank = (perf < perf[best]).sum() + 0.5 * ((perf == perf[best]).sum() - 1)
        w = (rank + 1) / (N + 1); logits.append(math.log(w / (1 - w)))
    return float(np.mean(np.array(logits) <= 0))


def calib(p, t, bins=5):
    out = []
    edges = np.linspace(0, 1, bins + 1)
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= 1)
        if m.sum(): out.append({"bin": "%.1f-%.1f" % (edges[i], edges[i + 1]), "n": int(m.sum()),
                                "pred": round(float(p[m].mean()), 3), "hit": round(float(t[m].mean()), 3)})
    return out


def evaluate(fam, rows, feats, keys, ycol):
    fit_rows, X, y, t, D, P = walk_forward(rows, feats, keys, ycol)
    tested = ~np.isnan(P["logistic"]); res = {"family": fam, "rows": len(rows), "fit_rows": len(fit_rows),
                                               "oos_rows": int(tested.sum()), "oos_days": len(set(D[tested]))}
    if tested.sum() < 20:
        res["status"] = "not enough out-of-sample rows yet (%d < 20)" % tested.sum(); return res, None, X, t, y, fit_rows
    yt, tt, Dt = y[tested], t[tested], D[tested]
    res["always_take_mean"] = round(float(yt.mean()), 4); cfgs = {}; days = sorted(set(Dt))
    M = []
    for k, p in P.items():
        pk = p[tested]
        for th in THRESH:
            take = pk >= th; name = "%s@%.2f" % (k, th)
            cfgs[name] = {"model": k, "threshold": th, "n_taken": int(take.sum()), "share_taken": round(float(take.mean()), 3),
                          "mean_taken": round(float(yt[take].mean()), 4) if take.any() else None,
                          "auc": round(float(roc_auc_score(tt, pk)), 3) if len(set(tt)) > 1 else None,
                          "brier": round(float(brier_score_loss(tt, pk)), 4)}
            M.append([float(np.sum(yt[(Dt == d) & take])) for d in days])
    M = np.array(M).T; res["pbo"] = cscv_pbo(M) if len(days) >= 8 else None
    res["configs"] = cfgs
    ok = {n: c for n, c in cfgs.items() if c["mean_taken"] is not None and c["n_taken"] >= 20}
    best = max(ok, key=lambda n: ok[n]["mean_taken"]) if ok else None
    if best:
        # paired day-level bootstrap: P(best config's daily result > always-take's daily result)
        j = list(cfgs).index(best); base = np.array([float(np.sum(yt[Dt == d])) for d in days]); diff = M[:, j] - base
        rng = np.random.default_rng(SEED); bs = diff[rng.integers(0, len(diff), (5000, len(diff)))].mean(1)
        res["p_beats_always_take"] = round(float((bs > 0).mean()), 3)
        med = float(np.median([c["mean_taken"] for c in ok.values()]))
        res["median_config_mean_taken"] = round(med, 4)
    accept = (best is not None and res["oos_rows"] >= 60 and ok[best]["mean_taken"] > res["always_take_mean"]
              and res["p_beats_always_take"] >= 0.9
              and ((res["pbo"] is not None and res["pbo"] < 0.5) or res["median_config_mean_taken"] > res["always_take_mean"]))
    res["best_config"] = best; res["champion"] = best if accept else "always_take"
    res["why"] = ("accepted: OOS mean %.3f vs always-take %.3f, P(beats) %.2f, PBO %s, median config %.3f"
                  % (ok[best]["mean_taken"], res["always_take_mean"], res["p_beats_always_take"], res["pbo"], res["median_config_mean_taken"])
                  if accept else "kept always-take: needs n_oos >= 60, an OOS mean above always-take with P(beats) >= 0.9, "
                  "and PBO < 0.5 or the median config also above always-take")
    if best: res["calibration"] = calib(P[cfgs[best]["model"]][tested], tt)
    return res, (cfgs[best]["model"], cfgs[best]["threshold"]) if best else None, X, t, y, fit_rows


def train(repo, day):
    os.makedirs(os.path.join(repo, "models"), exist_ok=True); out = {"date": day}
    frozen = tcal.info(day)["frozen"] if hasattr(tcal, "info") else False
    for fam in ("stock", "crypto"):
        rows, feats, keys, ycol = family(repo, fam)
        res, best, X, t, y, fit_rows = evaluate(fam, rows, feats, keys, ycol)
        path = os.path.join(repo, "models", fam + ".pkl")
        if frozen and os.path.exists(path):
            res["fit"] = "frozen holdout: kept the model saved on or before %s" % tcal.PHASES["train"][1]; out[fam] = res; continue
        if best is None or len(set(t)) < 2:
            out[fam] = res; continue
        kind, th = best; m = clf(kind).fit(X, t)
        try:
            pi = permutation_importance(m, X, t, n_repeats=10, random_state=SEED, scoring="roc_auc")
            names = feats + (["key=" + k for k in keys] if keys else [])
            res["importance"] = sorted([{"feature": n, "auc_drop": round(float(v), 4)} for n, v in zip(names, pi.importances_mean)],
                                       key=lambda d: -d["auc_drop"])[:12]
        except Exception as ex: res["importance"] = "n/a: %s" % ex
        bundle = {"family": fam, "kind": kind, "threshold": th, "champion": res["champion"], "feats": feats, "keys": keys,
                  "clf": m, "trained_on": day, "n": len(fit_rows), "train_X": X, "regs": {}}
        if fam == "stock":
            for ins in decisions.INSTR:
                lab = [(i, r["y"].get("y_" + ins)) for i, r in enumerate(fit_rows) if r["y"].get("y_" + ins) is not None]
                if len(lab) >= (30 if ins == "stock" else MIN_OPT_ROWS):
                    idx = [i for i, _ in lab]; bundle["regs"][ins] = reg().fit(X[idx], np.array([v for _, v in lab]))
            res["instrument_models"] = sorted(bundle["regs"])
        pickle.dump(bundle, open(path, "wb")); res["fit"] = "saved models/%s.pkl (%d rows)" % (fam, len(fit_rows))
        out[fam] = res
    json.dump(out, open(os.path.join(repo, "models", "report_%s.json" % day), "w"), indent=1, default=str)
    return out


def predict(repo, cands, now):
    path = os.path.join(repo, "models", "stock.pkl"); rows = []
    b = pickle.load(open(path, "rb")) if os.path.exists(path) else None
    for c in cands:
        if b is None:
            p, preds, choice, take = None, {}, "stock", True; model = "always_take (no model yet)"
        else:
            X = matrix([c], b["feats"], b["keys"]); p = float(b["clf"].predict_proba(X)[0, 1])
            preds = {k: round(float(m.predict(X)[0]), 4) for k, m in b["regs"].items()}
            best = max(preds, key=preds.get) if preds else "stock"
            # always the model's own decision (shadow), so it is scored as a challenger even while the champion is always-take
            take = p >= b["threshold"] and (not preds or preds[best] > 0); choice = best if take else "none"
            model = "%s@%.2f" % (b["kind"], b["threshold"])
        rows.append({"predicted_at": now, "model": model.split(" ")[0], "family": "stock", "date": c["date"], "symbol": c["symbol"],
                     "candidate_id": c["id"], "choice": choice, "take": take, "pred_best": round(p, 4) if p is not None else None,
                     "pred_json": json.dumps(preds), "realized": None, "realized_choice": None, "scored_at": None,
                     "phase": tcal.phase(c["date"])})
    return rows


def predict_crypto(repo, now):
    """Shadow predictions for crypto track trades that are OPEN and have no prediction yet (logged at the first run
    after entry, before the outcome; features use only bars closed before the entry)."""
    path = os.path.join(repo, "models", "crypto.pkl"); b = pickle.load(open(path, "rb")) if os.path.exists(path) else None
    seen = {s.get("candidate_id") for s in ledger.load(repo, "MLShadow")}; rows = []
    for c in decisions.crypto_rows(repo, status="open"):
        if c["id"] in seen: continue
        if b is None: p, take, model = None, True, "always_take"
        else:
            X = matrix([c], b["feats"], b["keys"]); p = float(b["clf"].predict_proba(X)[0, 1])
            take = p >= b["threshold"]; model = "%s@%.2f" % (b["kind"], b["threshold"])
        rows.append({"predicted_at": now, "model": model, "family": "crypto", "date": c["date"], "symbol": c["symbol"],
                     "candidate_id": c["id"], "choice": c["key"] if take else "none", "take": take,
                     "pred_best": round(p, 4) if p is not None else None, "pred_json": "{}", "realized": None,
                     "realized_choice": None, "scored_at": None, "phase": tcal.phase(c["date"])})
    return rows


def score(repo):
    lab = {r["id"]: r for r in decisions.load(repo, "stock")}; out = []
    clab = {r["id"]: r for r in decisions.load(repo, "crypto")}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    for s in ledger.load(repo, "MLShadow"):
        if s.get("realized") not in (None, ""): continue
        if s.get("family") == "crypto":
            d = clab.get(s.get("candidate_id"))
            if d and d["y"].get("y") is not None:
                s = dict(s); take = str(s.get("take")).lower() == "true"
                s.update(realized=d["y"]["y"] if take else 0.0, realized_choice=s.get("choice"), scored_at=now); out.append(s)
            continue
        d = lab.get(s.get("candidate_id"))
        if not d: continue
        ch = s.get("choice") or "stock"
        if ch == "none": v, rc = 0.0, "none"
        else:
            v = d["y"].get("y_" + ch); rc = ch
            if v is None and d["y"].get("y_stock") is not None: v, rc = d["y"]["y_stock"], "stock (chosen instrument not simulated)"
        if v is None: continue
        s = dict(s); s.update(realized=v, realized_choice=rc, scored_at=now); out.append(s)
    return out


def psi(a, b, bins=10):
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 20 or len(b) < 10: return None
    q = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    if len(q) < 3: return None
    q[0], q[-1] = -np.inf, np.inf
    pa = np.histogram(a, q)[0] / len(a) + 1e-4; pb = np.histogram(b, q)[0] / len(b) + 1e-4
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def drift(repo, day):
    out = {}
    for fam in ("stock", "crypto"):
        path = os.path.join(repo, "models", fam + ".pkl")
        if not os.path.exists(path): out[fam] = "no model yet"; continue
        b = pickle.load(open(path, "rb")); rows = decisions.load(repo, fam)
        recent_days = [d for d in tcal.trading_days("2026-01-01", day)][-10:]
        rec = [r for r in rows if r["date"] in recent_days]
        if not rec: out[fam] = "no recent rows"; continue
        R = matrix(rec, b["feats"]); res = {}
        for j, f in enumerate(b["feats"]):
            v = psi(b["train_X"][:, j], R[:, j])
            if v is not None: res[f] = round(v, 3)
        out[fam] = {"psi": res, "flagged": sorted(f for f, v in res.items() if v > 0.25),
                    "note": "PSI > 0.25 = the live inputs no longer look like the training data; > 0.1 = watch"}
    return out


def report(repo, day):
    f = os.path.join(repo, "models", "report_%s.json" % day)
    tr = json.load(open(f)) if os.path.exists(f) else train(repo, day)
    sh = ledger.load(repo, "MLShadow"); sc = [s for s in sh if s.get("realized") not in (None, "")]
    def m(xs): return round(sum(xs) / len(xs), 4) if xs else None
    taken = [ledger.num(s["realized"]) for s in sc if str(s.get("take")).lower() == "true"]
    allr = []
    lab = {r["id"]: r for r in decisions.load(repo, "stock")}
    for s in sc:
        d = lab.get(s.get("candidate_id"))
        if d and d["y"].get("y_stock") is not None: allr.append(d["y"]["y_stock"])
    return {"date": day, "train": tr, "drift": drift(repo, day),
            "shadow": {"predictions": len(sh), "scored": len(sc), "taken": len(taken), "mean_taken": m(taken),
                       "always_take_mean_same_candidates": m(allr)}}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "train": print(json.dumps(train(a[1], a[2]), indent=1, default=str))
    elif a[0] == "predict": print(json.dumps(predict(a[1], json.load(open(a[2])), a[3]), indent=1))
    elif a[0] == "predict-crypto": print(json.dumps(predict_crypto(a[1], a[2]), indent=1))
    elif a[0] == "score": print(json.dumps(score(a[1]), indent=1))
    elif a[0] == "drift": print(json.dumps(drift(a[1], a[2]), indent=1))
    elif a[0] == "report": print(json.dumps(report(a[1], a[2]), indent=1, default=str))
