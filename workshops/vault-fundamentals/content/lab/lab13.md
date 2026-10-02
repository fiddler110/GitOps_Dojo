# Lab 13 — Incident drill: a token leaked

**Goal:** practise the leak you'll one day get a message about. A vault token was pasted where it shouldn't be, and someone used it. Find out **what it did** from the audit log, **cut it off** (and anything it made), **rotate** what it saw, and check that the app recovers **by itself**.

**In this lab you will:**

1. Set the scene: a job with a long-lived token that can make more tokens.
2. Play the attacker: use the leaked token, and leave a spare behind.
3. Switch sides: look the token up by its accessor, without using it.
4. Read the audit log to find everything it did, including the spare.
5. Revoke the whole tree, rotate what it read, and check the app recovers.
6. Write the four-line incident review.

You play both parts in one terminal, so the commands share shell variables (`$LEAKED`, `$ACC`...). Keep the same terminal for the whole lab.

---

## 1. Before the incident

A "nightly report" job got a token of its own, the way many teams still do it: a person made it, it lives a day, and it can make tokens for the job's workers.

First make sure the three secrets are there (a catch-up, as in earlier labs):

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
bao kv get team/app >/dev/null 2>&1 || until echo '{"db_password": "app-db-pass", "api_key": "app-api-key"}' | bao kv put team/app -; do sleep 2; done
bao kv get team/ci >/dev/null 2>&1 || printf '%s' "deploy-$USER-$RANDOM" | bao kv put team/ci deploy_token=-
bao kv get team/admin >/dev/null 2>&1 || printf '%s' 'do-not-share' | bao kv put team/admin root_password=-
```

The job's policy. In VS Code, create **`nightly-report.hcl`** at the top of your lab folder (right-click an empty part of the Explorer → **New File...**):

```hcl
path "team/data/app" { capabilities = ["read"] }
path "team/data/ci"  { capabilities = ["read"] }
# "The report starts workers, and each one needs a token."
path "auth/token/create" { capabilities = ["update"] }
```

Read it as the attacker will: two secrets it can read, and the right to **make new tokens**. That last line is the mistake this drill turns on. Save it, upload it, and make the job's token: an orphan (Lab 4), for a whole day:

```bash
bao policy write nightly-report ~/lab/nightly-report.hcl
LEAKED="$(bao token create -orphan -policy=nightly-report -ttl=24h -display-name=nightly-report -field=token)"
```

## 2. The leak (you play the attacker)

Someone pasted `$LEAKED` into a team chat to "help debug the job". Someone else copied it. With it, they read the two secrets, try a third, and make themselves a spare token, since the policy allows it. Each line prints what the attacker got:

```bash
BAO_TOKEN=$LEAKED bao kv get -field=api_key team/app >/dev/null && echo "attacker: read team/app"
BAO_TOKEN=$LEAKED bao kv get -field=deploy_token team/ci >/dev/null && echo "attacker: read team/ci"
BAO_TOKEN=$LEAKED bao kv get team/admin >/dev/null 2>&1 || echo "attacker: team/admin refused"
SPARE="$(BAO_TOKEN=$LEAKED bao token create -policy=nightly-report -ttl=24h -display-name=backup -field=token)"
BAO_TOKEN=$SPARE bao kv get -field=api_key team/app >/dev/null && echo "attacker: made a spare token, and it works"
```

A spare key: if you only revoke the token you know about, they keep a way in. In real life you wouldn't have `$SPARE`; below you find it in the audit log. (Keep the variable only to check at the end that it's dead.)

## 3. The report: "this token was in the chat"

Now you're the namespace's admin again. You have the token itself (from the chat), so start there, without using it: look it up (as your own token), and keep its **accessor**:

```bash
bao token lookup "$LEAKED"
ACC="$(bao token lookup -format=json "$LEAKED" | jq -r .data.accessor)"
echo "$ACC"
```

The **accessor** is the token's reference number: it's in every audit entry the token made, and it can look the token up or revoke it, but it can't be used to log in. It's what you pass around during an incident, never the token.

## 4. What did it do?

Every request is in the vault's audit log. `bao-audit` shows your namespace's part of it (your own sign-in proves you're this namespace's admin):

```bash
bao-audit --accessor "$ACC"
```

Read it top to bottom:

- **You** made the token (`auth/token/create`, *made token ...*). The audit log also answers "who created this?".
- **It** read `team/data/app` and `team/data/ci`: both are now **known to the attacker**.
- It was **denied** `team/data/admin`: least privilege (Rule 1) limited the damage.
- It **made a token** (`made token ...`): the spare.

Follow the spare. The audit entry where the token made it records the new token's accessor (`created_accessor`); pick it out with `jq`, then show what the spare did:

```bash
CHILD="$(bao-audit --accessor "$ACC" --json | jq -r --arg a "$ACC" '.[] | select(.accessor == $a) | .created_accessor // empty')"
echo "$CHILD"
bao-audit --accessor "$CHILD"
```

## 5. Contain: revoke the whole tree

Revoking a token revokes every token it made. Revoke the leaked one by its accessor, then check the spare, and both tokens:

```bash
bao token revoke -accessor "$ACC"
bao token lookup -accessor "$CHILD"                  # invalid accessor: the spare died with its parent
BAO_TOKEN=$SPARE bao kv get team/app                 # permission denied
BAO_TOKEN=$LEAKED bao kv get team/app                # permission denied
```

## 6. Rotate what it read

Revoking stops *new* reads. It doesn't un-read `team/app` and `team/ci`: those values are out, so they change now, to new random values. (At work you'd also change them at their source, e.g. issue a new API key at the provider; the vault holds the copy the apps use.)

```bash
printf '{"api_key": "rotated-%s", "db_password": "rotated-%s"}' "$(date +%s)" "$RANDOM$RANDOM" | bao kv patch team/app -
printf '%s' "deploy-$USER-$RANDOM$RANDOM" | bao kv patch team/ci deploy_token=-
```

`team/admin` was refused, so it stays: the audit log tells you what you *don't* need to rotate, too.

## 7. The app recovers by itself

If you did Lab 11, your app on `app-host` picks up the new values with no deploy and no restart. Give the Agent a few seconds, then compare the app's fingerprint with the vault's:

```bash
sleep 12
curl -s http://app-host:8080/$USER/ | grep fingerprint
printf %s "$(bao kv get -field=api_key team/app)" | sha256sum | cut -c1-12
```

The CI pipeline needs nothing either: it never held `team/ci`'s value, it reads it at run time (Lab 9).

## 8. Write it up

A short post-incident review answers four questions. Yours:

1. **What happened?** A 24-hour token was pasted in a chat and used to read `team/app` and `team/ci` and to make a spare token.
2. **How did we find out what it did?** The audit log, by the token's accessor, including the spare.
3. **What did we do?** Revoked the token tree, rotated both secrets; the app and CI picked them up with no deploy.
4. **What stops it next time?** Give the job an **identity** instead of a token (Labs 9-11); if a token is unavoidable, a short TTL, no `auth/token/create`, and `token_bound_cidrs` so it only works from where the job runs.

Here every terminal shares one address, so the audit's `remote_address` can't tell you who the attacker was; at work it's often the first clue.

```bash
bao-audit --accessor "$ACC" --json | jq '.[0] | {time, remote_address, path, display_name}'
unset BAO_NAMESPACE LEAKED SPARE ACC CHILD
```

## Check yourself

1. Why look the leaked token up by its accessor from then on? *(The accessor can't log in; passing the token around during the incident would leak it further.)*
2. You revoked the token. Why rotate the secrets anyway? *(Revoking stops new reads; the values it already read are known to the attacker.)*
3. Why didn't you rotate `team/admin`? *(The audit log shows the read was denied: the value never left the vault.)*

**Rules used:** 6 (audit everything, and use it), 7 (plan for leaks: revoke, rotate, recover), 3 (a short-lived token would have limited it), 1 (least privilege kept `team/admin` safe), 2 (identity instead of a token is the real fix).

---

## Capstone: Zero Standing Secrets (bonus)

A new app with no secret in git, CI or on disk: identity from the platform, its own least-privilege policy, one
static secret, one dynamic database login, and a rotation with no deploy. Starting the capstone unlocks your second
app slot, `$USER-capstone` (see **My App**): a push to `main` of your capstone repo deploys there, and your lab app
keeps running.

Only when your class has achievements on (you see a score on your landing page).
Click **Start challenge** below, or run `dojo-challenge start capstone`: it makes your own repo `$USER/capstone` and
clones it to `~/lab/capstone`. The goal is printed there, with your own names in it. When you think it's done, run
`dojo-check capstone`. A wrong answer costs nothing; `dojo-check hint capstone` gives a hint for part of the points, and
`dojo-challenge reset capstone` starts you over from a fresh copy.

<!-- dojo-challenge: capstone -->
