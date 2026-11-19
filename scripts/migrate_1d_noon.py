"""One-off: move daily-bar timestamps from 00:00 UTC to 12:00 UTC.

Readers turn t into a New York date. 00:00 UTC is 19:00 the previous evening in
New York, so every daily bar was dated one day early. 12:00 UTC keeps the same
UTC date and gives the right New York date. Safe to run twice.
"""
import json, os, sys
repo = sys.argv[1] if len(sys.argv) > 1 else "."
d = os.path.join(repo, "data", "bars", "1d")
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f); rows = {}
    for line in open(p):
        if not line.strip(): continue
        b = json.loads(line); b["t"] = b["t"] // 86400 * 86400 + 43200; rows[b["t"]] = b
    with open(p, "w") as fh:
        for k in sorted(rows): fh.write(json.dumps(rows[k], separators=(",", ":")) + "\n")
    print(f, len(rows))
