# 5-minute engine trigger (external pinger) – set-up for the owner

Why: GitHub runs `*/5` schedules late or not at all when it is busy. On 2026-11-19 the market-data workflow ran
only 9 scheduled times (about hourly, at :43-:53 UTC), so the signal engine sealed every breakout 29-44 minutes late.
`fills.py` ignores detections more than 20 minutes late and uses the price 5 minutes after the signal instead, so the
verdict numbers are not hurt. But the engine (the timestamped, no-AI proof of when each signal was seen) almost never
produced a usable detection. A free external cron service that calls GitHub's `workflow_dispatch` API every 5 minutes
fixes the timing. The existing GitHub schedules stay on as a backup. The workflow already accepts
`workflow_dispatch` with `mode: tick`, so **no workflow change is needed**.

Read-only market data only: the pinger can start this workflow and nothing else. It cannot trade, and it cannot read
or change any other repo.

## 1. Create a fine-grained token (GitHub, about 2 minutes)

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.

- Name: `quantavius-engine-pinger`
- Expiration: 2027-06-15 (after the six-month test ends on 2027-05-21; see RENEWAL below if the token is older)
- Repository access: **Only select repositories** → `ttwalib/trading-forward-test`
- Permissions → Repository permissions → **Actions: Read and write** (everything else: No access)

Copy the token. Store it only in the cron service. Never paste it into the chat, the sheet or the repo.

## 2. Create the cron job (cron-job.org, free)

Create a job:

- URL: `https://api.github.com/repos/ttwalib/trading-forward-test/actions/workflows/data.yml/dispatches`
- Method: **POST**
- Headers:
  - `Authorization: Bearer <your token>`
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`
  - `Content-Type: application/json`
- Body: `{"ref":"main","inputs":{"mode":"tick"}}`
- Schedule (time zone **America/New_York**): every 5 minutes, Monday-Friday, 09:30-15:55. If the site only takes
  cron syntax: `*/5 9-15 * * 1-5` (the 09:00-09:25 calls are harmless: the engine idles before 09:45).
- Expected response: **HTTP 204** (no content). A 404 means a wrong URL, or a token without access to this repo.
  A 403 means the token lacks Actions write.

Holidays and half days need nothing: `engine.py` and `fetch_free.py` check the NYSE calendar themselves and idle.

## 3. Check it worked (next trading day)

- GitHub → Actions → market-data: runs with event `workflow_dispatch` about every 5 minutes.
- `data/decisions/engine/DAY.jsonl`: `delay_min` mostly 5-10 instead of 30-45.
- The orchestrator digest reports the engine median delay. Over 20 minutes it is flagged CHECK.

## Cost note

Each tick takes about 20-25 s, which GitHub bills as 1 minute: about 78 runs × 21 trading days ≈ 1,640 minutes a
month, plus the nightly run. That is free if the repo is public. If it is private, it uses most of the 2,000 free
minutes a month. To save minutes, schedule the pinger only 09:45-15:35 (the engine's active window): about 71 runs a
day.

## Turning it off

Delete the cron job and revoke the token (GitHub → Settings → Developer settings → Fine-grained tokens) after
2027-05-21.

## RENEWAL (added 2026-11-21: the test now runs to 2027-05-21, the first token expires on 2027-03-31)

Do this on a weekend, when no ticks are due. About 3 minutes.

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → `quantavius-engine-pinger`
   → **Regenerate token**. Expiration: custom date **2027-06-15**. Leave repository access and permissions as they are.
2. Copy the new token. The old one stops working at once.
3. cron-job.org → the job → Headers → replace the value of `Authorization` with `Bearer <new token>` → Save.
4. Press "Test run" on cron-job.org: the response must be **HTTP 204**.
5. Tell Quantavius the new expiry date, so `TOKEN_EXPIRY` in `scripts/checks.py` can be updated (the health line
   warns 21 days before that date).

Never paste the token into the chat, the sheet or the repo. If the pinger ever stops, the test does not: GitHub's own
backup tick still runs about once an hour, `fills.py` falls back to the price 5 minutes after the signal, and the
health line raises an alert. A second person who can do steps 1 to 4 (a backup owner) is worth naming.
