"""Tests for the defects fixed after the pre-freeze code review of Quantavius the 1st (2026-11-25,
reports/audit/2026-11-25-code-review.md). Offline, synthetic data in temporary folders; no network.

Run: python3 tests/test_prefreeze_2026_11_25.py [REPO_COPY]
With REPO_COPY (a copy on which scripts/nightly.py has run), the L13 test also checks the real library output.
Testing only, not financial advice.
"""
import sys, os, json, tempfile, datetime as dt, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import allocator, seals, aisleeve, rank, picks, tcal, witness
NY = tcal.NY


def mk(root, *dirs):
    for d in dirs: os.makedirs(os.path.join(root, d), exist_ok=True)


def test_seal_caps():
    """A sealed book keeps own-sleeve shares up to 50% when it is scored (judge.py checks seals against 50%)."""
    seal = {"AP2 Agent picks (AI sizing and holding)": 0.40, "L8 Momentum": 0.25, "L16 SPY trend short": 0.20,
            "AS AI strategies (lab, approved)": 0.15}
    w = allocator.fill_to_one([seal], allocator.seal_cap)
    assert all(abs(w[k] - v) < 1e-9 for k, v in seal.items()), w
    w = allocator.fill_to_one([{"AP Agent picks (open to close)": 0.5, "X": 0.25, "Y": 0.25}], allocator.seal_cap)
    assert abs(sum(w.values()) - 1) < 1e-9 and abs(w["AP Agent picks (open to close)"] - 0.5) < 1e-9, w
    # foundation sleeves stay at 25%, and the formula's own fill is unchanged
    w = allocator.fill_to_one([{"L8 Momentum": 0.6, "X": 0.2, "Y": 0.2}], allocator.seal_cap)
    assert abs(w["L8 Momentum"] - 0.25) < 1e-9, w
    w = allocator.fill_to_one([{"AP Agent picks (open to close)": 0.5, "X": 0.5}])
    assert abs(w["AP Agent picks (open to close)"] - 0.25) < 1e-9, w
    # seals.score (contests, daily challenger) uses the same caps
    A2 = "AP2 Agent picks (AI sizing and holding)"
    S = {A2: {"2026-12-07": 1.0}, "X": {"2026-12-07": 0.0}, "Y": {"2026-12-07": 0.0}, "Z": {"2026-12-07": 0.0}}
    sw = {A2: 0.45, "X": 0.25, "Y": 0.25, "Z": 0.05}
    out = seals.score(S, {"2026-12-07": sw}, "week", ["2026-12-07"])
    want = 0.45 - sum(v * allocator.rebal_cost(k) for k, v in sw.items())
    assert abs(out["2026-12-07"] - want) < 1e-4, (out, want)


def test_g1_needs_60_sealed_days():
    """Missed days count as IC 0 but not towards the 60 sealed days."""
    R = [{"ic": 0.3, "missed": False} for _ in range(30)] + [{"ic": 0.0, "missed": True} for _ in range(69)]
    s = rank.summary(R)
    assert s["sealed_days"] == 30 and s["days"] == 99 and s["g1_primary"].startswith("too few sealed days"), s
    R = [{"ic": 0.3 + 0.01 * (i % 3), "missed": False} for i in range(60)] + [{"ic": 0.0, "missed": True}]
    assert rank.summary(R)["g1_primary"] == "PASS"


def test_as_mix_from_the_scored_row():
    """as_mixes takes as_mix from the row judge_seals scores, not from the first row in the file."""
    M = tempfile.mkdtemp(); mk(M, "data/allocator", "data/witness/obj/seal")
    old = witness.ENFORCE_FROM; witness.ENFORCE_FROM = "2000-01-01"
    try:
        r1 = {"effective": "2027-03-01", "sealed_at": "2027-02-28T13:00:00-05:00", "weights": {"X": 1.0}, "as_mix": {"lane:a": 1.0}}
        r2 = {"effective": "2027-03-01", "sealed_at": "2027-02-28T14:00:00-05:00", "weights": {"Y": 1.0}, "as_mix": {"lane:b": 1.0}}
        for i, r in enumerate((r1, r2)):
            json.dump({"kind": "seal", "id": "judge.jsonl|%s|%s" % (r["effective"], r["sealed_at"]), "sha": witness.sha(r),
                       "seen_at_ny": "2027-02-28 1%d:01:00" % (3 + i), "seen_at_utc": "x", "grandfathered": False},
                      open(os.path.join(M, "data/witness/obj/seal/%d.json" % i), "w"))
        r1e = dict(r1, as_mix={"lane:c": 1.0})   # row 1 edited after it was witnessed: no longer valid
        open(os.path.join(M, "data/allocator/judge.jsonl"), "w").write(json.dumps(r1e) + "\n" + json.dumps(r2) + "\n")
        assert allocator.judge_seals(M) == {"2027-03-01": {"Y": 1.0}}
        assert aisleeve.as_mixes(M) == [("2027-03-01", {"lane:b": 1.0})], aisleeve.as_mixes(M)
        # a row that cannot be checked is reported, not silently dropped
        open(os.path.join(M, "data/allocator/judge.jsonl"), "a").write('{"effective": "2027-03-08"}\n')
        allocator.judge_seals(M); assert len(allocator.JUDGE_SEAL_ERRORS) == 1, allocator.JUDGE_SEAL_ERRORS
    finally:
        witness.ENFORCE_FROM = old


def _ap3_repo():
    R = tempfile.mkdtemp(); mk(R, "data/ledger", "data/bars/opt5m", "data/witness/obj/pick")
    occ = "XYZ261218C00100000"; occ2 = "XYZ261224C00100000"
    rows = [{"picked_at": "2026-12-14 09:00", "asset": "option", "symbol": "XYZ", "status": "picked", "checks": "occ=%s | w=0.5 | hold=3" % occ},
            {"picked_at": "2026-12-21 09:00", "asset": "option", "symbol": "XYZ", "status": "picked", "checks": "occ=%s | w=0.5 | hold=5" % occ2}]
    open(os.path.join(R, "data/ledger/AgentPicks.jsonl"), "w").write("".join(json.dumps(r) + "\n" for r in rows))

    def bars(o, days, px):
        with open(os.path.join(R, "data/bars/opt5m/OPT_OCC_%s.jsonl" % o), "w") as f:
            for d, p in zip(days, px):
                t = dt.datetime.fromisoformat(d + "T09:30").replace(tzinfo=NY).timestamp()
                f.write(json.dumps({"t": t, "o": p, "h": p, "l": p, "c": p}) + "\n")
    bars(occ, ["2026-12-14", "2026-12-15", "2026-12-16"], [1.0, 1.0, 1.0])
    bars(occ2, ["2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24"], [1.0, 1.0, 1.0, 3.0])
    os.environ.pop("WITNESS_AT", None); witness.run(R, now=dt.datetime(2026, 12, 1, 12, tzinfo=dt.timezone.utc))
    for r in rows:
        w = {"kind": "pick", "id": witness.row_id(r), "sha": "x", "seen_at_ny": r["picked_at"][:10] + " 08:00:00",
             "seen_at_utc": r["picked_at"][:10] + " 13:00:00", "grandfathered": False, "altered": False, "row": witness._pick_copy(r)}
        open(os.path.join(R, "data/witness/obj/pick/%s.json" % r["picked_at"][:10]), "w").write(json.dumps(w))
    return R, occ, occ2


def _run(R, day):
    cal = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]; ci = {d: i for i, d in enumerate(cal)}
    return picks.puts(R, cal, ci, day, witness.load(R))


def test_ap3_open_positions_stay_open():
    """A position whose hold runs past tonight is neither closed nor charged exit costs tonight, and tonight's
    figure is the one the next night computes for the same day."""
    R, occ, occ2 = _ap3_repo()
    s14, c14, _, _ = _run(R, "2026-12-14")
    assert not [x for x in c14 if x["occ"] == occ], c14
    s16, c16, _, _ = _run(R, "2026-12-16")
    assert abs(s14["2026-12-14"] - s16["2026-12-14"]) < 1e-9, (s14, s16)
    assert [x["exit_day"] for x in c16 if x["occ"] == occ] == ["2026-12-16"], c16


def test_ap3_half_day_expiry():
    """An option expiring on the 2026-12-24 half day is priced on that day's last trade."""
    R, occ, occ2 = _ap3_repo()
    s, c, _, _ = _run(R, "2026-12-31")
    x = [x for x in c if x["occ"] == occ2]
    assert len(x) == 1 and x[0]["exit"] == 3.0 and x[0]["exit_day"] == "2026-12-24", x
    assert s["2026-12-28"] > 150, s["2026-12-28"]


def test_l13_next_open(repo=None):
    """L13 trades are entered and exited at an open after the signal close (source check; plus the real library
    output when a nightly-run copy is given)."""
    src = open(os.path.join(HERE, "..", "scripts", "library.py")).read()
    blk = src[src.index("# L13 pairs"):src.index("books.append(b13)")]
    assert '"entry_time": "open"' in blk and '"exit_time": "open"' in blk and '"pending": True' in blk
    if repo:
        L = json.load(open(os.path.join(repo, "data", "library", "daily.json")))
        tr = [t for t in (L.get("trades") or []) if str(t.get("strategy", "")).startswith("L13")]
        assert all(t.get("entry_time") == "open" for t in tr), tr[:3]
        print("  L13 trades in the copy:", len(tr))


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else None
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(repo) if name == "test_l13_next_open" else fn(); print("ok", name)
    print("all passed")
