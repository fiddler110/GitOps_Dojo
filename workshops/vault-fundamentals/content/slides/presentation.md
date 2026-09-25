---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
  .split { align-items: center; display: flex; gap: 48px; }
  .split > div { flex: 1; min-width: 0; }
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Vault Fundamentals | Engineering & IT Operations'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Vault Fundamentals

## Secrets in code, git, pipelines and deployments

Builds on Git Fundamentals: the same repos, now without the passwords in them

**Talk + hands-on lab**

<!--
Parts 1-6 (labs 0-11) are written; the facilitator notes and demo come with P5.
Assumes the room knows clone/commit/push.
-->

---

## Today

1. Why secrets end up where they shouldn't
2. What a vault is, and the rules we'll use all day
3. Signing in without a password: identity, tokens, policies
4. **Labs 0-2:** the shared vault
5. Namespaces: your own vault
6. **Lab 3:** you are the admin
7. Secrets in code: **labs 4-5**
8. Secrets in git: **lab 6**
9. Secrets in pipelines: **labs 7-8**

---

<!-- _class: section-title -->

# Part 1

## Where secrets leak

---

## A secret is anything that lets you in

- Passwords and database connection strings
- API keys and access tokens
- Private keys and certificates
- Cloud credentials (a service principal's secret, an access key)

If someone else has a copy, they **are** you, as far as the system can tell.

---

## Where they end up

<div class="split">
<div>

- In the code: `API_TOKEN = "ghp_..."`
- In git history, after "removing" them
- In CI logs, printed by accident
- In container images and their layers
- In a `.env` file shared over chat
- On a server, readable by every process

</div>
<div>

Every copy is one more place to leak from, and one more place to change when you rotate.

**Once it's pushed, it's leaked.** Deleting the line doesn't reach clones, forks or backups.

</div>
</div>

---

## The rules we'll use all day

| # | Rule | In one line |
| - | ---- | ----------- |
| 1 | Least privilege | Read only what you need; deny by default |
| 2 | Identity over secrets | Prove who you are instead of holding a password |
| 3 | Short-lived, revocable | A leaked credential should expire by itself |
| 4 | Secret zero | The first credential comes from somewhere: know where |
| 5 | Separation of duties | Who deploys the app needn't read its secrets |
| 6 | Audit everything | "Who read this, and when?" has an answer |
| 7 | Plan for leaks | Rotation and revocation are routine |
| 8 | Never in git, logs or images | Including history and build output |

---

<!-- _class: section-title -->

# Part 2

## What a vault does

---

## One place for secrets, and a gate in front of it

<div class="split">
<div>

- Secrets are stored **encrypted**, in one place
- Every request carries a **token**
- A **policy** says what each token may do
- Every request is **audited**
- Secrets can be **versioned**, **rotated**, or made **on demand** and expire

</div>
<div>

We use **OpenBao**, the open-source fork of HashiCorp Vault: same commands, same API. `bao` = `vault`.

Tools built for Vault (sops, Python's `hvac`) work unchanged.

</div>
</div>

---

## Signing in: an identity, then a token

```text
  you --prove who you are--> auth method --> entity (you) --> token (TTL, policies)
      browser: Forgejo SSO   oidc            student01        8 hours
      terminal: the platform jwt             student01        8 hours
```

- **Auth method:** how you prove who you are. No vault password today.
- **Entity:** you, however you signed in. Policies can hang here.
- **Token:** what every request carries. It has a TTL and can be revoked.

---

## Policies: paths and capabilities

```hcl
# The class's policy (lab 2): each student's own folder
path "secret/data/students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}
```

- A **path** says where; **capabilities** say what: `create`, `read`, `update`, `patch`, `delete`, `list`, `sudo`, `deny`
- Nothing matches? **Denied.** Least privilege is the default.
- `{{identity.entity.name}}` is filled in per request: one policy, the whole class

---

## KV v2: secrets with history

| You run | What happens | Azure Key Vault |
| ------- | ------------ | --------------- |
| `kv put` / `kv patch` | a new version | a new secret version |
| `kv get -version=1` | an old version | get a version |
| `kv delete` / `kv undelete` | hidden, recoverable | soft delete / recover |
| `kv destroy` | that version wiped | purge |

A leaked secret: **rotate first**, then destroy the old versions.

---

## Labs 0-2: the shared vault

| Lab | You will | Time |
| --- | -------- | ---- |
| **0** | sign in (browser and terminal), read your token | ~8 min |
| **1** | leak a token into git, find it, block the next one | ~12 min |
| **2** | put, version, delete vs destroy, meet the policy | ~15 min |

Open the **Vault** card; the first time, click **Authorize** in Forgejo.

<!--
Hand over to the room. Lab 1 doesn't touch the vault at all: it's the
"why" for everything after it.
-->

---

## Namespaces: a vault inside the vault

<div class="split">
<div>

- Its own engines, policies, tokens and auth methods
- Invisible from its neighbours
- An admin of one namespace is nobody anywhere else

</div>
<div>

**At work:** each team gets its own, and the platform team runs the root.

**On Azure:** a Key Vault per team or environment.

**Today:** you are admin of `students/<you>`.

</div>
</div>

---

## Lab 3: you are the admin

- Enable a KV engine in **your** namespace
- Write a least-privilege policy **in the UI**, then **as a file** (review, history, rollback)
- Create a 15-minute token with only that policy
- Prove it reads one secret and nothing else, then **revoke** it

About **15 minutes**.

---

<!-- _class: section-title -->

# Part 3

## Secrets in code

---

## Three places an app's secret can live

| Where | Good | The catch |
| ----- | ---- | --------- |
| In the code | nothing to set up | in git forever (lab 1) |
| A git-ignored `.env` | out of git | plaintext on every laptop, shared by hand, never expires, inherited by every child process |
| **The vault** | one copy, access by policy, audited, rotated in one place | the app needs an identity and a token that stays fresh |

**Never log a secret:** log *that* you loaded the config, not *what* it holds.

---

## OpenBao Agent: the vault work, done for the app

```text
  role ID + secret ID --> Agent --login--> OpenBao (AppRole)
                            |  renews the token, logs in again at max TTL
                            |  re-reads team/app every few seconds
                            v
                 /dev/shm/<you>/app.env  (0600, memory) --> the app reads a file
```

- The app knows nothing about vaults: no SDK, no token
- **Rotate** in the vault and the file changes: no commit, no restart
- The secret ID is **secret zero**: someone still had to deliver it (labs 8-9 remove it)

---

## Labs 4-5: secrets in code

- **Lab 4:** one app, three versions (code, `.env`, `hvac`); a debug line that leaks; a token's TTL
- **Lab 5:** AppRole in your namespace, the Agent renders to memory, rotate it live

About **30 minutes** for both.

---

<!-- _class: section-title -->

# Part 4

## Secrets in git

---

## sops + transit: encrypted files, keys in the vault

<div class="split">
<div>

```yaml
database:
  host: db.internal
  password: ENC[AES256_GCM,data:...]
sops:
  hc_vault:
    - enc: vault:v1:...
```

</div>
<div>

- Keys stay readable, **values** are encrypted
- sops makes a **data key** per file; **transit** wraps it (envelope encryption)
- The transit key **never leaves the vault**
- Who can decrypt is a **policy**, and every decrypt is **audited**

</div>
</div>

---

## Lab 6: encrypted config in the repo

- Transit in your namespace, a `.sops.yaml` that points at your key
- Encrypt, commit, and a **readable diff** for those who can decrypt
- An **encrypt-only** token: CI can write config it can't read
- **Rotate** the key, re-wrap the file, retire version 1: old copies stop opening

About **15 minutes**.

---

<!-- _class: section-title -->

# Part 5

## Secrets in pipelines

---

## CI secrets: masked is not hidden

<div class="split">
<div>

```yaml
steps:
  - env:
      API_KEY: ${{ secrets.DEMO_API_KEY }}
    run: |
      echo "$API_KEY"            # *** in the log
      echo "$API_KEY" | base64   # readable
```

</div>
<div>

- A **repository secret** goes to every job in the repo
- The log **masks exact matches** only
- **Anyone who can push a workflow** can read it: a branch is enough
- Fork pull requests get no secrets; `pull_request_target` does, so never run PR code in it
- It never expires by itself

</div>
</div>

---

## Single-use runners

<div class="split">
<div>

- A controller keeps a few **warm** runners ready, more when jobs queue
- Each runner takes **one job**, then it is deleted with all it left behind
- No job sees another's files or processes
- The **Runners** panel: ready, busy or broken

</div>
<div>

**At work:** GitHub's Actions Runner Controller on Kubernetes, Azure DevOps scale-set agents, GitLab's autoscaling runners.

Long-lived shared runners are how one team's job reads another team's leftovers.

</div>
</div>

---

## The job's own identity

<div class="split">
<div>

```json
{
  "iss": ".../git/api/actions",
  "aud": "openbao",
  "repository": "student07/vault-fundamentals",
  "ref": "refs/heads/main",
  "actor": "student07",
  "exp": 1790000000
}
```

</div>
<div>

1. Forgejo **signs a token for this run**: repo, branch, who
2. The job hands it to the vault's **JWT auth**
3. The vault checks its **signature** and the role's **bound claims**
4. It gets a **5-minute** token with one policy

Nothing stored in CI. A branch isn't `main`: refused.

</div>
</div>

---

## At work: the same, ready-made

```yaml
# GitHub Actions
permissions:
  id-token: write
steps:
  - uses: hashicorp/vault-action@v3      # works with OpenBao too
    with:
      url: https://vault.example.com
      method: jwt
      role: ci-main
      secrets: team/data/ci deploy_token | DEPLOY_TOKEN
```

**Azure:** `azure/login` or an Azure DevOps service connection with **workload identity federation**.
**GitLab:** `id_tokens:` in the job. The lab uses `curl` + `bao` so you can see each step.

---

## Labs 7-8: secrets in pipelines

- **Lab 7:** fork the repo, add a repository secret, watch it get masked, then print it anyway
- **Lab 8:** CI reads the vault with **AppRole**: works, but the login secret sits in Forgejo (secret zero)
- Then with the **job's own token**, bound to your repo on `main`; a branch is refused
- Retire the AppRole path: role, stored secrets, workflow

About **35 minutes**.

---

<!-- _class: section-title -->

# Part 6

## Secrets in deployments

---

## How should an app on a server get its secrets?

1. **Platform identity.** The platform vouches for the app (managed identity, a Kubernetes service account); the app trades that for a short-lived vault token. **Nothing is handed over.**
2. **Dynamic credentials** on top: a database login made for this app, with a lease.
3. **AppRole + a trusted deliverer**, when there's no platform identity: a single-use, response-wrapped secret ID.
4. **Anti-patterns:** secrets in the image, a committed `.env`, env vars pushed by the pipeline, one shared token.

---

## Platform identity: app-host

<div class="split">
<div>

```json
{
  "iss": "http://app-host:8080",
  "aud": "openbao",
  "sub": "slot:student07",
  "exp": 1790000600
}
```

</div>
<div>

- One **slot** per student: its own Linux user
- The platform writes each slot a **10-minute token**, only that slot can read it
- The vault trusts the platform's **public keys**; a role binds `sub` to **one slot**
- The **Agent** logs in with it and writes the secrets to a file

</div>
</div>

---

## Deploy, but don't read

<style scoped>
table { font-size: 24px; }
</style>

| | Identity | May | May not |
| --- | --- | --- | --- |
| **Pipeline** | Forgejo job token, `aud: app-host` | deploy to *its owner's* slot, from `main` | read `team/app` |
| **Pipeline** | Forgejo job token, `aud: openbao` | read `team/ci` | read `team/app` |
| **App** | platform token, `sub: slot:<you>` | read `team/app` | deploy anything |

**Separation of duties:** whoever ships the code never holds production's secrets, and a branch can't ship.

---

## Dynamic credentials and leases

<div class="split">
<div>

```bash
bao read database/creds/app
# username  v-...-app-...
# password  (random)
# lease     database/creds/app/...  5m
bao lease renew  <lease>
bao lease revoke <lease>   # DROP ROLE, now
```

</div>
<div>

- The vault logs in to Postgres as a user **only it** knows (`rotate-root`)
- Every caller gets **its own login**, gone when the lease ends
- A leaked login is worth **minutes**, and each one has its own name in the database's logs

</div>
</div>

---

## When a token leaks

1. **Find** the token's **accessor**: it can revoke, it can't log in
2. **Read the audit log** by accessor: what it read, what it was refused, what tokens it made
3. **Contain:** revoke the token, and every token under it goes too
4. **Rotate** what it read (not what it was refused)
5. **Recover:** apps using the Agent pick up the new values with no deploy
6. **Review:** why a long-lived token existed at all

---

## Labs 9-11: secrets in deployments

- **Lab 9:** deploy to your slot on app-host; the app's Agent logs in with the **platform's identity**; the pipeline can deploy but not read; rotate with no deploy; a branch can't deploy
- **Lab 10 (optional):** database logins made on demand: role, lease, renew, revoke; then the app gets its own
- **Lab 11:** the incident drill: a leaked token, the audit trail, revoke, rotate, recover

About **50 minutes** (35 without lab 10).

---

## OpenBao and Azure, side by side

<style scoped>
table { font-size: 21px; }
th, td { padding: 5px 14px; }
</style>

| OpenBao | Azure |
| ------- | ----- |
| Namespace | A Key Vault per team or environment |
| KV v2: versions, delete / undelete / destroy | Key Vault: versions, soft delete / recover / purge |
| ACL policy (paths + capabilities) | RBAC roles (Secrets User, Secrets Officer) |
| OIDC auth method | Entra ID sign-in |
| JWT auth for the platform (terminal, app-host) | Managed identity |
| AppRole | Service principal with a client secret |
| JWT auth for CI jobs (lab 8) | Workload identity federation |
| Transit engine (sops) | Key Vault keys (sops `azure_kv`) |
| Database engine (lab 10) | Entra ID sign-in to Azure SQL / Postgres |
| Audit device | Diagnostic settings to Log Analytics |

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Let's go

## Next: [labs.md](labs.md), then your terminal

---

<!-- _class: section-title -->

# Wrap-up

## After the labs

---

## The rules, and where you used them

| # | Rule | Where you did it |
| - | ---- | ---------------- |
| 1 | Least privilege | The templated policy (2), `app-read` (3), `ci-read` (8) |
| 2 | Identity over secrets | The job's OIDC token (8), the platform's identity (9) |
| 3 | Short-lived, revocable | Token TTLs (3), leases (10), revoking a tree (11) |
| 4 | Secret zero | AppRole's secret in the pipeline (8), gone with OIDC |
| 5 | Separation of duties | The pipeline deploys but can't read `team/app` (9) |
| 6 | Audit everything | `bao-audit`: who read what, by accessor (3, 11) |
| 7 | Plan for leaks | Rotate the key (6), rotate with no deploy (5, 9), the drill (11) |
| 8 | Never in git, logs or images | gitleaks (1), masking (7), sops (6), no DEBUG dumps (4) |

---

## At work on Monday

- **Scan** your repos' history with gitleaks, and add the pre-commit hook
- **Find your secret zero**: every stored credential in a pipeline is a candidate for OIDC
- **Ask for the identity** your platform already has: workload identity federation, managed identity
- **Shorten TTLs** and prefer dynamic credentials where the engine exists
- **Know who can read the audit log**, and rehearse a leak before you have one
- **Keep policies in git** and change them by pull request

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Thank you

## Questions?
