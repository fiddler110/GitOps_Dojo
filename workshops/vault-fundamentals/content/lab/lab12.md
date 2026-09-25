# Lab 12 — Incident drill: a token leaked

**Goal:** practise the leak you'll one day get a message about. A vault token was pasted where it shouldn't be, and someone used it. Find out **what it did** from the audit log, **cut it off** (and anything it made), **rotate** what it saw, and check that the app recovers **by itself**.

---

## 1. Before the incident

A "nightly report" job got a token of its own, the way many teams still do it: a person made it, it lives a day, and it can make tokens for the job's workers.

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
bao kv get team/app >/dev/null 2>&1 || until bao kv put team/app db_password=app-db-pass api_key=app-api-key; do sleep 2; done
bao kv get team/ci >/dev/null 2>&1 || bao kv put team/ci deploy_token="deploy-$USER-$RANDOM"
bao kv get team/admin >/dev/null 2>&1 || bao kv put team/admin root_password=do-not-share
cat > ~/lab/nightly-report.hcl <<'EOF'
path "team/data/app" { capabilities = ["read"] }
path "team/data/ci"  { capabilities = ["read"] }
# "The report starts workers, and each one needs a token."
path "auth/token/create" { capabilities = ["update"] }
EOF
bao policy write nightly-report ~/lab/nightly-report.hcl
LEAKED="$(bao token create -orphan -policy=nightly-report -ttl=24h -display-name=nightly-report -field=token)"
```

## 2. The leak (you play the attacker)

Someone pasted `$LEAKED` into a team chat to "help debug the job". Someone else copied it. With it, they:

```bash
BAO_TOKEN=$LEAKED bao kv get -field=api_key team/app >/dev/null && echo "attacker: read team/app"
BAO_TOKEN=$LEAKED bao kv get -field=deploy_token team/ci >/dev/null && echo "attacker: read team/ci"
BAO_TOKEN=$LEAKED bao kv get team/admin >/dev/null 2>&1 || echo "attacker: team/admin refused"
SPARE="$(BAO_TOKEN=$LEAKED bao token create -policy=nightly-report -ttl=24h -display-name=backup -field=token)"
BAO_TOKEN=$SPARE bao kv get -field=api_key team/app >/dev/null && echo "attacker: made a spare token, and it works"
```

A spare key: if you only revoke the token you know about, they keep a way in. In real life you wouldn't have `$SPARE`; below you find it in the audit log. (Keep the variable only to check at the end that it's dead.)

## 3. The report: "this token was in the chat"

You're the namespace's admin. You have the token itself (from the chat), so start there, without using it:

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

Follow the spare:

```bash
CHILD="$(bao-audit --accessor "$ACC" --json | jq -r --arg a "$ACC" '.[] | select(.accessor == $a) | .created_accessor // empty')"
echo "$CHILD"
bao-audit --accessor "$CHILD"
```

## 5. Contain: revoke the whole tree

Revoking a token revokes every token it made:

```bash
bao token revoke -accessor "$ACC"
bao token lookup -accessor "$CHILD"                  # invalid accessor: the spare died with its parent
BAO_TOKEN=$SPARE bao kv get team/app                 # permission denied
BAO_TOKEN=$LEAKED bao kv get team/app                # permission denied
```

## 6. Rotate what it read

Revoking stops *new* reads. It doesn't un-read `team/app` and `team/ci`: those values are out, so they change now. (At work you'd also change them at their source, e.g. issue a new API key at the provider; the vault holds the copy the apps use.)

```bash
bao kv patch team/app api_key="rotated-$(date +%s)" db_password="rotated-$RANDOM$RANDOM"
bao kv patch team/ci deploy_token="deploy-$USER-$RANDOM$RANDOM"
```

`team/admin` was refused, so it stays: the audit log tells you what you *don't* need to rotate, too.

## 7. The app recovers by itself

If you did Lab 10, your app on `app-host` picks up the new values with no deploy and no restart:

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
4. **What stops it next time?** Give the job an **identity** instead of a token (Labs 9-10); if a token is unavoidable, a short TTL, no `auth/token/create`, and `token_bound_cidrs` so it only works from where the job runs.

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
