"""Tamper-evident record of the append-only evidence files (added 2026-11-23, runbook item 31; the hash-chain idea comes
from Vibe-Trading's governance ledger, re-expressed here, no code copied).

  python3 chain.py update REPO      verify every earlier entry, then chain the lines added since the last run
  python3 chain.py verify REPO      verify only (exit code 1 if anything changed)

Some files must only ever grow: the AI-judgment seals, the lifetime trial log, the lane's champion history and the
5-minute engine's sealed detections (with their ML scores). Each line of these files gets an entry in ops/chain.jsonl:
the file, the line number, the SHA-256 of the line, and a hash that folds in the previous entry's hash. Editing or
deleting any chained line, or editing the chain itself, breaks every hash after it, so the nightly check sees it.
Result: data/nightly/chain.json ({"ok", "entries", "added", "broken": [...], "head"}); a broken chain raises the health
alert "CHAIN BROKEN" (scripts/checks.py) and is reported first in the digest.

What this proves and what it does not: it shows that a sealed line was not changed after the night it was first
chained, and the head hash printed in each GitHub Actions log (kept by GitHub outside the repo) dates the chain.
It cannot stop someone with write access from rewriting the files and the chain together on the same night; the
git history and the Actions logs are the check against that.
"""
import glob, hashlib, json, os, sys

SOURCES = ["data/allocator/judge.jsonl", "data/trials.jsonl", "data/lane/champions.jsonl",
           "data/decisions/engine/*.jsonl", "data/decisions/engine_ml/*.jsonl", "data/picks/playbook_log.jsonl",
           "data/picks/rank/*.json", "data/allocator/contest_*.jsonl", "data/allocator/judge_daily.jsonl",
           "data/witness/picks.jsonl", "ops/interventions.jsonl", "data/ai/lane_admissions.jsonl",
           "data/witness/obj/*/*.json"]      # one file per witness sighting (2026-11-24, review N1/N7)
GENESIS = "0" * 64
H = lambda s: hashlib.sha256(s.encode()).hexdigest()


def files(repo):
    out = []
    for pat in SOURCES: out += sorted(os.path.relpath(p, repo) for p in glob.glob(os.path.join(repo, pat)))
    return out


def lines(repo, rel):
    with open(os.path.join(repo, rel), encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f if l.strip()]


def load(repo):
    p = os.path.join(repo, "ops", "chain.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def verify(repo, chain):
    broken, prev, cache = [], GENESIS, {}
    for i, e in enumerate(chain):
        want = H("%s|%s|%d|%s" % (prev, e["path"], e["line"], e["sha"]))
        if e.get("prev") != prev or e.get("hash") != want:
            broken.append({"entry": i, "path": e.get("path"), "line": e.get("line"), "why": "chain entry edited"}); prev = e.get("hash", prev); continue
        if e["path"] not in cache:
            cache[e["path"]] = lines(repo, e["path"]) if os.path.exists(os.path.join(repo, e["path"])) else None
        L = cache[e["path"]]
        if L is None: broken.append({"entry": i, "path": e["path"], "line": e["line"], "why": "file deleted"})
        elif e["line"] >= len(L): broken.append({"entry": i, "path": e["path"], "line": e["line"], "why": "line deleted"})
        elif H(L[e["line"]]) != e["sha"]: broken.append({"entry": i, "path": e["path"], "line": e["line"], "why": "line edited"})
        prev = e["hash"]
    return broken, prev


def update(repo, write=True):
    chain = load(repo); broken, head = verify(repo, chain); added = 0
    if write:
        seen = {}
        for e in chain: seen[e["path"]] = max(seen.get(e["path"], -1), e["line"])
        new = []
        for rel in files(repo):
            for n, l in enumerate(lines(repo, rel)):
                if n <= seen.get(rel, -1): continue
                sha = H(l); h = H("%s|%s|%d|%s" % (head, rel, n, sha))
                new.append({"seq": len(chain) + len(new) + 1, "path": rel, "line": n, "sha": sha, "prev": head, "hash": h}); head = h
        if new:
            with open(os.path.join(repo, "ops", "chain.jsonl"), "a") as f:
                for e in new: f.write(json.dumps(e, separators=(",", ":")) + "\n")
        added = len(new)
    res = {"ok": not broken, "entries": len(chain) + added, "added": added, "broken": broken[:50], "head": head,
           "sources": SOURCES}
    if write:
        os.makedirs(os.path.join(repo, "data", "nightly"), exist_ok=True)
        json.dump(res, open(os.path.join(repo, "data", "nightly", "chain.json"), "w"), indent=1)
    return res


def main():
    cmd, repo = sys.argv[1], sys.argv[2]
    r = update(repo, write=(cmd == "update"))
    print(json.dumps(r, indent=1)); print("CHAIN HEAD %s" % r["head"])
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
