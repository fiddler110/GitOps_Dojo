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
Parts 1-5 (labs 0-8) are written; later parts come with later build phases.
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

## OpenBao and Azure, side by side

| OpenBao | Azure |
| ------- | ----- |
| Namespace | A Key Vault per team or environment |
| KV v2: versions, delete / undelete / destroy | Key Vault: versions, soft delete / recover / purge |
| ACL policy (paths + capabilities) | RBAC roles (Secrets User, Secrets Officer) |
| OIDC auth method | Entra ID sign-in |
| Terminal sign-in (JWT from the platform) | Managed identity |
| AppRole | Service principal with a client secret |
| JWT auth for CI jobs (lab 8) | Workload identity federation |
| Transit engine (sops) | Key Vault keys (sops `azure_kv`) |
| Audit device | Diagnostic settings to Log Analytics |

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Let's go

## Next: [labs.md](labs.md), then your terminal
