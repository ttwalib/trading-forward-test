"""Server-side witness for everything Quantavius seals before an outcome (picks 2026-11-23; seals and rankings
2026-11-24 after the external review, points N1, N3 and N7).

A pick row, a weekly or daily seal and a ranking each carry a time that the task writes itself, so on their own they
prove nothing about when they were made. This script runs on GitHub's servers (on every push that touches them, every
tick and the nightly maths) and records the FIRST time each object was seen in the repository, by GitHub's clock.

WHAT IS WITNESSED (kind: object id; the content hash is the sha256 of the canonical JSON of the object):
  pick   AgentPicks ledger rows                      id = picked_at|asset|symbol   (a copy of the row is kept)
  seal   rows of data/allocator/judge.jsonl, contest_*.jsonl, judge_daily.jsonl
                                                     id = <file>|<effective>|<sealed_at>
  draft  data/allocator/drafts/*.json                id = drafts/<file name>
  rank   data/picks/rank/<DAY>.json                  id = rank|<date>|<sealed_at>
WHERE: one small file per sighting, data/witness/obj/<kind>/<id hash>-<seen time>.json (in the hash chain). Two runs
that witness at the same moment write different files, so a git merge can never drop or overwrite a sighting; the
earliest sighting of an (id, content hash) pair is the one that counts. The pick sightings of 2026-11-23..24 stay in
data/witness/picks.jsonl (read only from 2026-11-24).
CLOCK: on a push the time is GitHub's own push time (WITNESS_AT = github.event.repository.pushed_at), else the runner's
clock. A changed object (same id, different content) is a new sighting at the later time and is listed as altered.

RULE (from ENFORCE_FROM): a pick counts only if first seen before 09:30 New York on its pick day, with its sizing and
confidence from the first-seen copy; a weekly, contest or daily seal only if its exact content was first seen before
09:30 on its effective day; a ranking only if first seen before 09:30 on its day. Objects that existed when the
witness first saw their kind are "grandfathered" (warm-up days before the window).

Usage: python3 witness.py REPO            (witness and write new sightings)
       python3 witness.py REPO --report   (print what is witnessed, late, altered or missing; writes nothing)
"""
import datetime as dt, glob, hashlib, json, os, sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger

NY = ZoneInfo("America/New_York")
ENFORCE_FROM = "2026-11-30"          # first shakedown day; earlier days are accepted on their own stamp
REL = os.path.join("data", "witness", "picks.jsonl")      # legacy pick sightings (read only)
OBJ = os.path.join("data", "witness", "obj")
SEAL_FILES = ("judge.jsonl", "judge_daily.jsonl")          # plus contest_*.jsonl


def row_id(r):
    return "%s|%s|%s" % (r.get("picked_at"), r.get("asset"), r.get("symbol"))


def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _pick_copy(r):
    return {k: r.get(k) for k in ("picked_at", "asset", "symbol", "contract_id", "status", "checks")}


def objects(repo):
    """Every witnessable object now in the repository: [(kind, id, content hash, extra fields)]."""
    out = []
    for r in ledger.load(repo, "AgentPicks"):
        if r.get("picked_at"): out.append(("pick", row_id(r), sha(_pick_copy(r)), {"row": _pick_copy(r)}))
    A = os.path.join(repo, "data", "allocator")
    files = [os.path.join(A, f) for f in SEAL_FILES] + sorted(glob.glob(os.path.join(A, "contest_*.jsonl")))
    for f in files:
        if not os.path.exists(f): continue
        for l in open(f):
            if not l.strip(): continue
            try: r = json.loads(l)
            except ValueError: continue
            out.append(("seal", "%s|%s|%s" % (os.path.basename(f), r.get("effective"), r.get("sealed_at")), sha(r), {}))
    for f in sorted(glob.glob(os.path.join(A, "drafts", "*.json"))):
        try: out.append(("draft", "drafts/" + os.path.basename(f), sha(json.load(open(f))), {}))
        except ValueError: continue
    for f in sorted(glob.glob(os.path.join(repo, "data", "picks", "rank", "*.json"))):
        try: R = json.load(open(f))
        except ValueError: continue
        out.append(("rank", "rank|%s|%s" % (R.get("date"), R.get("sealed_at")), sha(R), {}))
    return out


def sightings(repo):
    """{(kind, id): [sighting, ...]} sorted earliest first; legacy pick lines included (content hash unknown)."""
    S = {}
    p = os.path.join(repo, REL)
    if os.path.exists(p):
        for l in open(p):
            if l.strip():
                w = json.loads(l); w = dict(w, kind="pick", sha=None, legacy=True); S.setdefault(("pick", w["id"]), []).append(w)
    for f in glob.glob(os.path.join(repo, OBJ, "*", "*.json")):
        try: w = json.load(open(f))
        except ValueError: continue
        S.setdefault((w["kind"], w["id"]), []).append(w)
    for v in S.values(): v.sort(key=lambda w: w["seen_at_utc"])
    return S


def _clock():
    e = os.environ.get("WITNESS_AT")       # GitHub's push time (epoch seconds) on a push-triggered run
    now = dt.datetime.now(dt.timezone.utc)
    if e:
        try: t = dt.datetime.fromtimestamp(int(float(e)), dt.timezone.utc)          # push events give epoch seconds
        except ValueError:
            try: t = dt.datetime.fromisoformat(e.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
            except ValueError: t = None
        if t is not None and t <= now and (now - t).total_seconds() < 6 * 3600: return t, "push"
    return now, os.environ.get("WITNESS_SOURCE", "run")


def run(repo, now=None):
    now, src = (now, "test") if now else _clock()
    S = sightings(repo); kinds_seen = {k for k, _ in S}
    new = []
    for kind, oid, h, extra in objects(repo):
        prev = S.get((kind, oid), [])
        if any(w.get("sha") == h for w in prev): continue
        w = {"kind": kind, "id": oid, "sha": h, "seen_at_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
             "seen_at_ny": now.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S"), "source": src,
             "grandfathered": kind not in kinds_seen and now.astimezone(NY).date().isoformat() < ENFORCE_FROM,
             "altered": any(w.get("sha") for w in prev)}
        w.update(extra); new.append(w); S.setdefault((kind, oid), []).append(w)
    for w in new:
        d = os.path.join(repo, OBJ, w["kind"]); os.makedirs(d, exist_ok=True)
        fn = "%s-%s.json" % (hashlib.sha256(w["id"].encode()).hexdigest()[:16], now.strftime("%Y%m%dT%H%M%SZ") + "-" + w["sha"][:8])
        with open(os.path.join(d, fn), "w") as f: f.write(json.dumps(w, sort_keys=True) + "\n")
    return {"new": len(new), "by_kind": {k: sum(1 for w in new if w["kind"] == k) for k in ("pick", "seal", "draft", "rank")},
            "clock": src, "seen_at_ny": now.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S")}


def _before(w, day, hhmm="09:30"):
    return w["seen_at_ny"][:10] < day or (w["seen_at_ny"][:10] == day and w["seen_at_ny"][11:16] < hhmm)


def on_time(S, kind, oid, h, day):
    """True if this exact object (content hash h; None = any content, legacy picks) was first seen before 09:30 New
    York on day, or is grandfathered, or day is before ENFORCE_FROM."""
    if day < ENFORCE_FROM: return True
    for w in S.get((kind, oid), []):
        if h is not None and w.get("sha") not in (h, None): continue
        if w.get("grandfathered"): return True
        return _before(w, day)
    return False


# ---------- picks (used by picks.py) ----------
def load(repo):
    """{pick id: first sighting} (legacy name kept for picks.py)."""
    return {oid: v[0] for (k, oid), v in sightings(repo).items() if k == "pick"}


def counts(w, pick_day):
    """True if this witnessed pick (its first sighting) may count for pick_day under the rule."""
    if pick_day < ENFORCE_FROM: return True
    if not w: return False
    if w.get("grandfathered"): return True
    return _before(w, pick_day)


def first_copy(w, live):
    """The pick as first seen: the sighting's row copy when there is one, else the live row (legacy sightings kept
    only the checks cell, which is applied over the live row)."""
    if w and w.get("row"): return dict(w["row"])
    r = dict(live or {})
    if w and w.get("checks") is not None and not w.get("grandfathered"): r["checks"] = w["checks"]
    return r


def pick_rows(repo):
    """AgentPicks rows to score (review point N3): every witnessed pick in its first-seen form, even if the live
    ledger row was later edited or deleted, plus live rows never witnessed (they count only before ENFORCE_FROM)."""
    W = load(repo); live = {row_id(r): r for r in ledger.load(repo, "AgentPicks")}
    out = []
    for i in sorted(set(W) | set(live)):
        r = first_copy(W.get(i), live.get(i)) if i in W else dict(live[i])
        if not r.get("symbol"):          # legacy sighting of a deleted row: rebuild what the id holds
            pa, asset, sym = i.split("|", 2); r.update(picked_at=pa, asset=asset, symbol=sym, status="picked")
        out.append(r)
    return out, W


def integrity(repo):
    """Witnessed objects that were later altered or deleted, and objects that are late (report for the nightly)."""
    S = sightings(repo); now = {(k, i): h for k, i, h, _ in objects(repo)}
    rep = {"altered": [], "missing": [], "late": []}
    for (k, i), v in S.items():
        if (k, i) not in now: rep["missing"].append({"kind": k, "id": i})
        elif any(w.get("altered") for w in v) or (v[0].get("sha") and now[(k, i)] != v[0]["sha"]): rep["altered"].append({"kind": k, "id": i})
    for (k, i), h in now.items():
        day = i.split("|")[0][:10] if k == "pick" else (i.split("|")[1][:10] if k in ("seal", "rank") else None)
        if day and not on_time(S, k, i, None if k == "pick" else h, day): rep["late"].append({"kind": k, "id": i})
    rep["counts"] = {k: len(v) for k, v in rep.items()}
    return rep


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    if "--report" in sys.argv: print(json.dumps(integrity(repo), indent=1))
    else:
        r = run(repo); r["integrity"] = integrity(repo)["counts"]; print(json.dumps(r))
