import urllib.request, json
uas = {"bot": "Quantavius-forward-test forward-test-bot@users.noreply.github.com",
       "plain": "Quantavius Forward Test (research, non-commercial) admin@quantavius-forward-test.example",
       "moz": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
urls = {"tickers": "https://www.sec.gov/files/company_tickers.json", "tickertxt": "https://www.sec.gov/include/ticker.txt",
        "subm": "https://data.sec.gov/submissions/CIK0000320193.json",
        "atom": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=10&output=atom",
        "idx": "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261120.idx"}
out = {}
for un, ua in uas.items():
    for k, u in urls.items():
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}), timeout=30) as r:
                out[f"{un}/{k}"] = f"{r.status} {len(r.read())}"
        except Exception as e:
            out[f"{un}/{k}"] = f"{type(e).__name__} {getattr(e,'code','')}"
json.dump(out, open("ops/diag/sec_probe.json", "w"), indent=1)
