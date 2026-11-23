"""ApeWisdom snapshot fetched on GitHub (added 2026-11-23, tools audit).

Why: scheduled AI sessions have no WebFetch and no shell network, so the 08:05 morning research and the 09:12 stocks
task could no longer read ApeWisdom (2026-11-23: "fetch blocked"). GitHub has the network: this script saves the first
three pages of https://apewisdom.io/api/v1.0/filter/all-stocks/page/N once per New York day, before the open.
Output data/sentiment/ape/DAY.json = {"day", "fetched_at_utc", "fetched_at_ny", "pages": [{"results": [...]}, ...],
"errors": [...]}. Tasks split "pages" into one file per page and run scripts/sentiment.py on them, as before.
Reddit itself is never contacted. A day that already has a complete file is not fetched again.

    python3 ape.py REPO [--force]
"""
import datetime as dt, json, os, sys, time, urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/{}"


def main():
    repo = os.path.abspath(sys.argv[1]); force = "--force" in sys.argv
    now = dt.datetime.now(dt.timezone.utc); day = now.astimezone(NY).date().isoformat()
    d = os.path.join(repo, "data", "sentiment", "ape"); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, day + ".json")
    if os.path.exists(f) and not force:
        try:
            if not json.load(open(f)).get("errors"): print(json.dumps({"day": day, "skipped": "already fetched"})); return
        except Exception: pass
    pages, errors = [], []
    for n in (1, 2, 3):
        for attempt in (1, 2):
            try:
                req = urllib.request.Request(URL.format(n), headers={"User-Agent": "forward-test-bot (research; github.com)"})
                with urllib.request.urlopen(req, timeout=30) as r: js = json.loads(r.read())
                pages.append({"results": js.get("results", [])}); break
            except Exception as e:
                if attempt == 2: errors.append(f"page {n}: {type(e).__name__}: {str(e)[:120]}")
                else: time.sleep(3)
    out = {"day": day, "fetched_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "fetched_at_ny": now.astimezone(NY).strftime("%Y-%m-%d %H:%M"), "pages": pages, "errors": errors}
    json.dump(out, open(f, "w"))
    print(json.dumps({"day": day, "pages": len(pages), "rows": sum(len(p["results"]) for p in pages), "errors": errors}))


if __name__ == "__main__":
    main()
