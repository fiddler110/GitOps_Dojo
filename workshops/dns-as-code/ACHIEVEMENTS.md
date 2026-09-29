# dns-as-code: achievements catalog (DRAFT for review)

Nothing here is built. Same format and rules as `workshops/git-fundamentals/ACHIEVEMENTS.md` (read its "How to read
it" first). Points are the defaults (milestone 10, funny 5, challenge 100, capstone 300, all settable in `.env`);
`core` counts toward the certificate (80% of the `core` set). Triggers: `shell:` (shell hook), `forgejo:` (webhook), `dns:` (dns-gate / PowerDNS audit lines), `verify:` (end state).

**Every lab is mandatory**, so every lab milestone is `core`. Challenges, the capstone and funny unlocks are bonuses and
never count toward completion. The shared cheating and "bumped into your neighbour" unlocks live with the module.

## Lab 1: your own zone

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d1-preview | Look Before You Leap | "Previewed before pushing. Adults do that." | 10 | yes | shell: `dnscontrol preview` (exit 0) |
| d1-push | Live on the Wire | "Your zone exists. Somewhere a resolver blinked." | 10 | yes | shell: `dnscontrol push` (exit 0); dns: zone created |
| d1-add | Record Collector | "More records than a 90s teenager." | 10 | yes | verify: `resource_state` zone has 3+ records |
| d1-change | Changed My Mind | "TTLs are a suggestion, apparently." | 10 | yes | verify: a record differs from its first pushed value |
| d1-remove | Gone, Not Forgotten | "Removed a record by deleting one line." | 10 | yes | dns: record deleted after a push |
| d1-dot | The Trailing Dot | "One character. Whole different hostname." | 10 | yes | shell: `dnscontrol preview` output shows the doubled zone name |

## Lab 2: drift and undoing

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d2-drift | Who Touched My Zone? | "Someone changed it behind your back. Classic." | 10 | yes | shell: `dnscontrol preview` shows a change you did not make |
| d2-fix | Back to Declared | "Config is the truth. The zone obeys." | 10 | yes | shell: `dnscontrol push` after drift, exit 0 |
| d2-revert | Time Machine | "Undid a pushed change the polite way." | 10 | yes | shell: `git revert` (exit 0) then `dnscontrol push` |

## Lab 3: the change process on a shared zone

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d3-clone | Shared Custody | "Cloned the class's production zone. Nobody panic." | 10 | yes | forgejo: clone of `dns-team/dns-as-code` |
| d3-blocked | Computer Says No | "You tried the shortcut. It said no." | 10 | yes | forgejo: direct push to `main` rejected (also a funny unlock, no double score) |
| d3-pr | Please Look at This | "A pull request, as nature intended." | 10 | yes | forgejo: PR opened on `dns-team/dns-as-code` |
| d3-review | Second Pair of Eyes | "You reviewed someone else's change." | 10 | yes | forgejo: review submitted on a PR by another student |
| d3-applied | CI Did the Thing | "Merged, and the robot applied it." | 10 | yes | forgejo: PR merged; verify: record present in the zone |

## Lab 4: `dnsctl.py`

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d4-wizard | Wizardry | "Added a record with a wizard. Very Gandalf." | 10 | yes | shell: `dnsctl.py add` (exit 0) |
| d4-submit | Submitted | "Preview, then a PR, in one command." | 10 | yes | forgejo: PR opened by `dnsctl.py submit` branch pattern |
| d4-status | Status Report | "Checked on your PR from the terminal." | 10 | yes | shell: `dnsctl.py status` (exit 0) |
| d4-validated | Trust, Then Verify | "The record is live and you checked." | 10 | yes | shell: `dnsctl.py validate` (exit 0) |

## Lab 5: history and rollback

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d5-history | DNS Archaeologist | "Read the zone's past like a diary." | 10 | yes | shell: `dnsctl.py history` (exit 0) |
| d5-rollback | Rewind | "Rolled back through a pull request." | 10 | yes | forgejo: PR opened from a `rollback-*` branch |
| d5-gone | Actually Gone | "Confirmed it is really gone." | 10 | yes | dns: rolled-back record no longer resolves (verify) |

## Lab 6: conflicts in `dnsconfig.js`

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| d6-conflict | Same Line, Different Idea | "Two edits, one line." | 10 | yes | shell: `git merge` or `git pull --rebase` exits non-zero with a conflict in `dnsconfig.js` |
| d6-resolved | Diplomat | "Both records kept. Peace in our time." | 10 | yes | shell: commit completes a merge; verify: no `<<<<<<<` in `dnsconfig.js` |
| d6-preview | Preview First, Always | "Previewed the merge result before pushing." | 10 | yes | shell: `dnscontrol preview` after a merge commit |

## Funny unlocks (5 points, any time)

| ID | Title | Joke | Pts | Trigger |
|---|---|---|---|---|
| f-dot2 | Dot. Com. Dot. | "Trailing dot on the wrong record." | 5 | shell: `dnscontrol` errors with a name ending in the zone twice |
| f-ttl | Time To Live, Laugh, Love | "TTL of 1. Very confident." | 5 | shell: file diff sets a TTL below 60 |
| f-nxdomain | It's Always DNS | "NXDOMAIN. Of course it was." | 5 | dns: your lookup for your own name returns NXDOMAIN |
| f-rejected | Denied at the Gate | "You tried to change `dojo.test` without CI." | 5 | dns: API refusal for a non-CI write (funny, but see cheating tiers) |
| f-fivepr | PR Machine | "Five pull requests. Do you sleep?" | 5 | forgejo: 5th PR opened |

## Challenges (100 points, no steps given)

### C1: The Typo (after Lab 1 or 2)
- **Goal:** "The zone contains a record whose hostname is wrong. Find it and fix it without touching any other record."
- **Seed:** a per-student zone file with one doubled-zone hostname (`www.{user}.dojo.test.dojo.test`) among ~6 records.
- **Verify:** `resource_state`: the record now resolves, and the other records are unchanged.
- **Hint 1:** "Run the tool that shows you what it would change." **Hint 2:** "Look at the end of each hostname."

### C2: The Cutover (after Lab 5 or 6)
- **Goal:** "`app.{user}.dojo.test` must point at the new server `10.20.0.{n}` and `www` must become an alias of `app`, in
  one pull request that someone else approves."
- **Verify:** PR merged; `app` A record equals `10.20.0.{n}`; `www` is a CNAME to `app`; one approval by another user.
- **Hint 1:** "One PR, two records." **Hint 2:** "An alias is a CNAME; the target ends with a dot."

## Capstone (300 points): The Bad Push
- **Goal:** "A record merged to `dojo.test` an hour ago is sending traffic to the wrong address, and the same commit
  also added a record you want to keep. Get `dojo.test` to the right state through the process, keeping the good
  record, dropping the bad one, with a review."
- **Seed:** a merged commit in the shared repo that adds one good and one bad record (one seed per student prefix).
- **Verify:** bad record absent, good record present in the live zone, the PR approved by another student, no direct push.
- **Hints:** (1) "History shows you which commit." (2) "You can roll back part of a commit by editing, not only by `revert`."
- **Badge tier:** capstone (stars).

## Rough totals

Core ~190 · funny up to 25 · challenges 200 · capstone 300 · plus bonuses. About 715.
