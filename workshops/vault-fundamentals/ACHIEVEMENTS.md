# vault-fundamentals: achievements catalog (DRAFT for review)

Nothing here is built. Same format and rules as `workshops/git-fundamentals/ACHIEVEMENTS.md`. Points are the defaults
(milestone 10, funny 5, challenge 100, capstone 300, all settable in `.env`); `core` counts toward the certificate (80%
of the `core` set). Triggers: `shell:` (shell hook), `bao:` (an OpenBao audit-log event for the student's entity or
namespace, read by the audit event adapter), `forgejo:` (webhook), `verify:` (end-state verbs: `secret_exists`,
`policy_attached`, `resource_state`).

**Every lab is mandatory** (labs 0-13), so every lab milestone is `core`. Challenges, the capstone and funny unlocks
never count toward completion. Secret *values* are never logged or scored: only paths, counts and states.

## Lab 0: sign in and meet your token

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v0-ui | Front Door | "Signed in with Forgejo. No password to forget." | 10 | yes | bao: OIDC login for the student |
| v0-token | Token Holder | "The terminal was already signed in." | 10 | yes | shell: `bao token lookup` (exit 0) |
| v0-first | First Secret | "Your very first secret." | 10 | yes | verify: `secret_exists` at the lab 0 path |

## Lab 1: leak it

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v1-leak | Oops, Committed | "A secret in git. It happens to everyone." | 10 | yes | shell: `git commit` with the lab's fake key staged |
| v1-scan | Scanner Darkly | "A scanner found it." | 10 | yes | shell: `gitleaks` (exit non-zero, then 0 later) |
| v1-hook | Pre-Commit Bouncer | "A hook now stops the next leak." | 10 | yes | verify: `.git/hooks/pre-commit` present and blocks the fake key |

## Lab 2: `pass` on your own machine

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v2-key | A Key of Your Own | "Your own GPG key." | 10 | yes | shell: `gpg --gen-key` or `--list-keys` shows a student key |
| v2-store | Password Store | "An encrypted store." | 10 | yes | shell: `pass init` (exit 0) |
| v2-share | Shared, Then Unshared | "Shared it and took it back." | 10 | yes | shell: `pass` re-encrypt after a recipient change |

## Lab 3: the shared vault

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v3-putget | Put and Get | "Secrets in, secrets out." | 10 | yes | bao: KV write then read by the student |
| v3-versions | Version Hoarder | "Versions kept so you can undo." | 10 | yes | bao: read of an older version |
| v3-destroy | Deleted, Undeleted, Destroyed | "The three levels of gone." | 10 | yes | bao: delete, undelete and destroy events |
| v3-door | Knocked on a Neighbour's Door | "Denied. Good." | 10 | yes | bao: permission denied on another student's path (also the 0-point funny) |

## Lab 4: you are the admin

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v4-ns | Own Namespace | "Your own corner of the vault." | 10 | yes | bao: first request inside the student's namespace |
| v4-engine | Engine Enabled | "A secrets engine of your own." | 10 | yes | verify: KV engine mounted in the namespace |
| v4-policy | Least Privilege | "A policy that gives only what is needed." | 10 | yes | verify: `policy_attached` for the app token |
| v4-revoke | Revoked It | "One command, no more token." | 10 | yes | bao: token revoke by the student |

## Lab 5: the app reads a secret

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v5-env | Not in the Code | "Moved it out of the source." | 10 | yes | shell: app run reading from `.env` |
| v5-vault | The App Asks the Vault | "No file, no leak." | 10 | yes | bao: KV read by the app's token |
| v5-nolog | Loose Lips | "Logging the secret? No." | 10 | yes | verify: app log does not contain the secret value |
| v5-expired | Token Expiry | "Tokens run out. That is the point." | 10 | yes | bao: request with an expired token |

## Lab 6: OpenBao Agent

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v6-approle | AppRole Assigned | "An identity for the app." | 10 | yes | verify: AppRole exists in the namespace |
| v6-agent | The Agent Works | "It logs in and keeps the token alive." | 10 | yes | bao: AppRole login from the Agent |
| v6-rotate | Rotated Live | "No restart. No downtime." | 10 | yes | bao: secret rewritten; verify: app file content changed |

## Lab 7: encrypted config in the repo

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v7-key | Key in the Vault | "A key that never leaves the vault." | 10 | yes | bao: transit key created |
| v7-encrypt | Encrypted Config | "A file only the key can read." | 10 | yes | shell: `sops -e` (exit 0) |
| v7-rotate | Key Rotation | "A new key version, old data still works." | 10 | yes | bao: transit rotate; shell: `sops updatekeys` |

## Lab 8: Forgejo Actions secrets

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v8-secret | Repository Secret | "A secret in the repository." | 10 | yes | forgejo: secret created on the fork |
| v8-masked | Masking Is Not Protection | "The log hid it. The job still knew it." | 10 | yes | forgejo: workflow run using the secret |
| v8-rotate | Cleaned Up After | "Rotated what leaked." | 10 | yes | forgejo: secret updated after the run |

## Lab 9: CI logs in to OpenBao

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v9-approle | The Stored Login | "The usual way: a login secret in CI." | 10 | yes | bao: AppRole login from a CI job |
| v9-jwt | The Job's Own Identity | "No stored secret at all." | 10 | yes | bao: JWT login from a CI job |
| v9-branch | Other Branches Refused | "Only main gets in." | 10 | yes | bao: denied login from a non-main branch |
| v9-retire | Retired the Stored Secret | "Nothing left to steal." | 10 | yes | forgejo: repository secret deleted |

## Lab 10: deploy with a delivered secret ID

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v10-strict | Strict Role | "The app's role is locked down." | 10 | yes | verify: `policy_attached` with a narrow role |
| v10-wrap | Wrapped Delivery | "A secret ID only the app can open." | 10 | yes | bao: response-wrapped secret ID created and unwrapped once |
| v10-deploy | Delivered and Deployed | "Pipeline delivers, app logs in." | 10 | yes | bao: app login with the delivered ID |
| v10-branch | A Branch Gets Nothing | "A feature branch cannot deploy." | 10 | yes | bao: denied delivery from a non-main branch |

## Lab 11: workload identity

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v11-role | A Role for Your Slot | "The platform vouches for the app." | 10 | yes | verify: role bound to the student's slot |
| v11-deploy | Deployed With Identity | "No secret ID at all." | 10 | yes | bao: workload login from the app |
| v11-nobread | The Pipeline Cannot Read | "Deployed, but never saw the secret." | 10 | yes | verify: pipeline identity has no read on the app path |
| v11-rotate | Rotated, No Deploy | "New value, same code." | 10 | yes | bao: secret rewritten; verify: app serves the new value |

## Lab 12: dynamic database credentials

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v12-role | A Role, Not a Password | "What a login may do." | 10 | yes | verify: DB role defined in the namespace |
| v12-lease | Lease Holder | "A login made just for you." | 10 | yes | bao: dynamic credential issued |
| v12-renew | Renewed | "Extended the lease." | 10 | yes | bao: lease renew |
| v12-revoke | Revoked | "Login gone, instantly." | 10 | yes | bao: lease revoke; verify: DB login fails |

## Lab 13: incident drill

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| v13-leak | Playing the Attacker | "You found the leaked token." | 10 | yes | bao: request made with the leaked token |
| v13-audit | Read the Audit Log | "What did it do? Now you know." | 10 | yes | shell: `jq`/`grep` over the audit log |
| v13-revoke | Revoke the Tree | "Killed the token and its children." | 10 | yes | bao: revoke with tree scope |
| v13-rotate | Rotated What It Read | "New secrets, old ones worthless." | 10 | yes | bao: writes to the paths the token read |
| v13-recover | The App Recovers | "No manual restart." | 10 | yes | verify: app serving with the new secret |

## Funny unlocks (5 points, any time)

| ID | Title | Joke | Pts | Trigger |
|---|---|---|---|---|
| f-echo | Echo Chamber | "You `echo`ed a secret. To your shell history." | 5 | shell: `echo` or `export` with a `hvs.`-style string |
| f-history | Hist-Oh-Ry | "It is in your shell history now." | 5 | shell: `history` after a token was typed |
| f-root | Root of the Problem | "You used the root token. Everyone has, once." | 5 | bao: any request with a root-policy token |
| f-typopath | Wrong Path, Right Attitude | "No value at that path. Check the mount." | 5 | bao: 404 on a KV path |
| f-seal | Sealed and Loving It | "The vault is sealed. This is fine." | 5 | bao: `sealed` response (facilitator action) |
| f-paste | Paste Bin Energy | "A secret in the chat. It happens." | 5 | shell: a fake secret string appears in a shared channel (only in lab 13) |

## Challenges (100 points, no steps given)

### C1: The Shared Secret (after Lab 4 or 5)
- **Goal:** "Give a teammate's app read access to one of your secrets without giving it access to anything else in your namespace."
- **Seed:** a per-student teammate identity `buddy-{user}` with no policy.
- **Verify:** `policy_attached` for `buddy-{user}`, allows read of exactly one path, denied elsewhere.
- **Hint 1:** "A policy, then attach it." **Hint 2:** "The path in the policy is the whole permission."

### C2: The Right Lease (after Lab 12)
- **Goal:** "The app needs DB credentials valid 2 minutes and never longer than 10 minutes in total. Make it so."
- **Verify:** DB role has `default_ttl=2m`, `max_ttl=10m`, and the app got a credential from it.
- **Hint 1:** "TTL and max TTL are separate settings." **Hint 2:** "On the role, not on the mount."

## Capstone (300 points): Zero Standing Secrets
- **Goal:** "Deploy a new app slot with no secret stored anywhere in git, CI or on disk: identity from the platform,
  its own least-privilege policy, one static secret and one dynamic credential, and prove a rotation with no deploy."
- **Seed:** a fresh slot and a starter repo per student.
- **Verify:** workload login only (no AppRole, no CI secret), policy narrow, dynamic credential issued, secret rotated
  with no deploy event, no secret in git history (scanner passes).
- **Hints:** (1) "Labs 9, 11 and 12 combined." (2) "Rotation is a write, not a deploy."
- **Badge tier:** capstone (stars).

## Rough totals

Core ~510 (51 milestones) · funny up to 30 · challenges 200 · capstone 300 · plus bonuses. Near 1040, the biggest
catalog; worth halving the per-lab milestone count if that feels lopsided next to the other workshops.
