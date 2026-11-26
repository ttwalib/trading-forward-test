"""Quantavius's open pick positions right now (2026-11-25, item 66), for the tasks that may write intraday exits.

  python3 positions.py REPO [DAY]     -> JSON list to stdout

Lists every witnessed stock or option pick still inside its holding window on DAY (New York date, default today):
picked_at (the id an exit row names in exits=), asset, symbol, contract (occ for options), hold, entry choice,
stop/tgt, the pick's own reason, and whether an exit or withdrawal was already requested. It reads the ledger and the
witness only; it prices nothing (the task quotes the price itself) and changes nothing.
"""
import json, os, re, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tcal, witness, picks  # noqa: E402


def open_positions(repo, day=None):
    day = day or dt.datetime.now(tcal.NY).date().isoformat()
    cal = [d for d in tcal.trading_days(tcal.START, tcal.END) if d <= day]
    if not cal: return []
    idx = {d: i for i, d in enumerate(cal)}
    PR, W = witness.pick_rows(repo)
    EX = picks.exit_requests(PR, W); WD = picks.withdrawn(PR, W, idx)
    out = []
    for r in PR:
        t = str(r.get("picked_at") or ""); d0 = t[:10]
        if r.get("status") != "picked" or r.get("asset") not in ("stock", "option", "put") or d0 not in idx or t[11:16] >= "09:30": continue
        if not witness.counts(W.get(witness.row_id(r)), d0): continue
        rid = witness.row_id(r)
        if rid in WD: continue
        ck = str(r.get("checks") or ""); mh = re.search(r"\bhold=([1-5])\b", ck); hold = int(mh.group(1)) if mh else 1
        last_i = idx[d0] + hold - 1
        if idx[day] > last_i if day in idx else cal.index(cal[-1]) > last_i: continue
        mo = re.search(r"\bocc=(\S+)", ck)
        out.append({"picked_at": t, "asset": r.get("asset"), "symbol": r.get("symbol"), "occ": mo.group(1).rstrip("|") if mo else None,
                    "hold": hold, "day_of_hold": (idx[day] if day in idx else len(cal) - 1) - idx[d0] + 1,
                    "entry": picks.entry_choice(ck), "stop_tgt": picks._exits(ck), "why": r.get("why"),
                    "exit_requested": EX.get(rid)})
    for r in PR:        # today's day trades (AP4): open until an exit, their stop or target, or the close
        t = str(r.get("picked_at") or "")
        if r.get("asset") == "daytrade" and r.get("status") == "picked" and t[:10] == day:
            ck = str(r.get("checks") or "")
            out.append({"picked_at": t, "asset": "daytrade", "symbol": r.get("symbol"), "occ": None, "hold": 0, "day_of_hold": 0,
                        "entry": "intraday", "stop_tgt": picks._exits(ck), "why": r.get("why"), "exit_requested": EX.get(witness.row_id(r))})
    return out


if __name__ == "__main__":
    print(json.dumps(open_positions(sys.argv[1] if len(sys.argv) > 1 else ".", sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
