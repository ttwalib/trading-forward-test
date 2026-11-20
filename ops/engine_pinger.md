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
- Expiration: 2027-02-20 (just after the test ends)
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
2027-02-12.
