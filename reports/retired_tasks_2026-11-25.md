# Disabled scheduled tasks the owner may delete (setup-debate build list item 6)

DONE 2026-11-25: the owner approved, and all 13 tasks listed below (both tables) were deleted in the build chat, with their run transcripts.

Written on 2026-11-25 by a build session of Quantavius the 1st from list_triggers. Nothing was deleted: deleting is the
owner's choice. Every task below is disabled and does no work; its job now runs on GitHub or was merged elsewhere.

Before deleting, note that deleting a scheduled task also deletes every session it started (their transcripts). The
test's record does not depend on them: the ledgers, prompt copies (ops/prompts/), interventions log and git history hold
everything that counts. Keep a task only if you want to reread one of its old run transcripts.

## Safe to delete now

| Task | Id | Why it is no longer needed |
|---|---|---|
| Stocks + control list (09:12, 16:12 ET) | trig_01Udt8Hay1dh3AyxtaP4ejDN | Runs on GitHub since 2026-11-24 (scripts/daily.py sentiment and stocks) |
| Crypto tracks | trig_015nU8hZEPt63TqiZjdPYPDp | Runs on GitHub since 2026-11-22 (scripts/daily.py crypto) |
| ML nightly | trig_0163kWWp8vAnJjwWjkJvbW9W | Runs on GitHub since 2026-11-22 (scripts/daily.py ml) |
| Deep OTM + weekly options | trig_012o6Jbkhg14NZ4Sq8N4spLW | Retired 2026-11-23; every position was settled, nothing is open |
| Picks review (Fri 23:40 ET) | trig_01WucV8KSj4xydnhqjmC9LmJ | Merged into the weekly report (Fri 21:41) on 2026-11-23 |
| History download | trig_01ECDQ4t7fUGAfo5AcN7EN3y | The backfill finished on 2026-11-20 |
| Dec 8 addendum: repo-review items 4-8 | trig_01LGPUYZuc2z1ZqKXRxMoZTz | Merged into ops/dec8_plan.md on 2026-11-24 (item 56) |
| Dec 8 addendum 2: ML shortlist for the picks | trig_015fjVpfN7VhMiygEDGd2TbA | Merged into ops/dec8_plan.md |
| Dec 8 addendum: lab and ML compute on GitHub | trig_01TbqT3JibXFqDRC6bbWjkow | Merged into ops/dec8_plan.md |
| Dec 8 ML ranker addendum: outside-data features | trig_012McvsY8T9o9QLqViN11cgf | Merged into ops/dec8_plan.md |
| Dec 8 addendum: outside-repo ideas | trig_01V5Wgv8XLWfWjLtcfWgNzkD | Merged into ops/dec8_plan.md |

The five Dec 8 addenda were reminders bound to the owner's build chat on his computer; the Dec 8 lane build reads
ops/dec8_plan.md instead.

## Deletable later (not yet disabled)

| Task | Id | When |
|---|---|---|
| Old watchdog (05:35, 12:35, 19:35 ET) | trig_01RqMJrg5xfsW4xYYgo7RZY4 | After trig_01HubnhXMKjQ5XXJKCNTHd2C disables it (Nov 24 19:55 ET, once the new watchdog's first run succeeded) |
| Adaptive stocks (17:20 ET) | trig_01XqVW4yGp2cwSyEXUobMusn | After the owner approves its retirement (proposed prompt in ops/prompts/proposed/adaptive.md; GitHub runs scripts/daily.py adaptive since 2026-11-25) and it has been disabled |

## Keep

Every enabled task in ops/tasks.json, and the one-off build sessions still scheduled (Nov 25 to Dec 15). One-off
sessions disable themselves after they fire; they can be deleted once their result is in the project notes.
