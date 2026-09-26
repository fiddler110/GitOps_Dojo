e ---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
@import url('assets/themes/presentation.css');
.split { align-items: center; display: flex; gap: 48px; }
.split > div { flex: 1; min-width: 0; }
.split-40 > div:first-child { flex: 0 0 40%; }
.split-60 > div:first-child { flex: 0 0 58%; }
.mermaid { text-align: center; margin: 8px 0; }
.mermaid:not([data-processed]) { visibility: hidden; }
.mermaid svg { max-height: 420px; }
.mermaid foreignObject p, .mermaid foreignObject div { margin: 0 !important; line-height: 1.35 !important; }
.small { font-size: 0.85em; }
.lede { color: var(--muted); font-size: 0.9em; }
footer: "[&larr; Hub](index.md) &nbsp;|&nbsp; Vault Fundamentals | Engineering & IT Operations"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Vault Fundamentals

## Secrets in code, git, pipelines and deployments

Builds on Git Fundamentals: the same repos, now without the passwords in them

**Talk, then hands-on labs**

<!--
The talk is the "what" and the "why": every idea the labs use, in the order the
labs use it. The labs are the "how". Assumes the room knows clone/commit/push.
-->

---

## Today

<style scoped>
ol { font-size: 0.88em; }
</style>

<div class="split split-60">
<div>

**The talk**

1. **Foundations:** why secrets leak, and what a vault does about it
2. **From a shared vault to your own:** namespaces, policies as code
3. **Secrets in code:** how an app gets its secret
4. **Secrets in git:** encrypted config
5. **Secrets in pipelines:** CI without stored secrets
6. **Secrets in deployments:** identity, dynamic logins, incidents

</div>
<div>

**Then the labs (0-13)**

Each part of the talk has labs that let you do it yourself, on a real vault.

**Then a wrap-up**

The rules again, and where you used each one.

</div>
</div>

---

<!-- _class: section-title -->

# Part 1

## Foundations: why secrets leak, and what a vault does

---

## A secret is anything that lets you in

- Passwords and database connection strings
- API keys and access tokens
- Private keys and certificates
- Cloud credentials (a service principal's secret, an access key)

If someone else has a copy, they **are** you, as far as the system can tell.

The system can't tell a stolen copy from the real one. So the question is never "is it strong?" but **"how many copies are there, and who has them?"**

---

## How one secret becomes ten copies

<div class="mermaid">
flowchart LR
  s["The database password"] --> code["Hard-coded in the app"]
  code --> git["git history"]
  git --> clones["Every clone and fork"]
  git --> ci["A CI job"]
  ci --> logs["Build logs"]
  ci --> img["Image layers"]
  s --> env[".env file sent in chat"]
  env --> laptops["Every teammate's laptop"]
</div>

Each copy is **one more place to leak from**, and one more place to change when you rotate.

<label for="leaks-wall" class="pop-trigger">Once it's pushed, it's leaked.</label> Deleting the line makes a new commit; the old one still holds it, in every clone, fork and backup.

<div class="pop">
<input type="checkbox" id="leaks-wall" class="pop-toggle">
<div class="pop-overlay">
<label for="leaks-wall" class="pop-close">close &#10005;</label>
<h3>Once it's pushed, it's leaked: it keeps happening</h3>
<p class="pop-sub">Real incidents where a leaked secret, most often in a repo or its history, was the way in.</p>
<div class="leak-grid">
<div class="leak"><i>2016</i><b>Datadog</b>Production AWS keys leaked.<em>Every customer integration credential had to be revoked</em></div>
<div class="leak"><i>2019</i><b>Starbucks</b>A JumpCloud API key in a GitHub repo.<em>Found by a security researcher</em></div>
<div class="leak"><i>2022</i><b>Toyota</b>A key public on GitHub for five years.<em>~300K customers' data exposed</em></div>
<div class="leak"><i>2023</i><b>Mercedes-Benz</b>A token in a public repo, Sept 2023 to Jan 2024.<em>Full read access to internal source</em></div>
<div class="leak"><i>2024</i><b>New York Times</b>An exposed GitHub token.<em>270 GB: 5,000 repos, with secrets</em></div>
<div class="leak"><i>2024</i><b>Internet Archive</b>GitLab tokens left exposed for nearly two years.<em>31M user accounts breached</em></div>
<div class="leak"><i>2025</i><b>xAI</b>A hard-coded API key pushed to GitHub.<em>60+ private LLMs open for weeks</em></div>
<div class="leak"><i>2025</i><b>Docker Hub images</b>10,000+ public images with secrets baked in.<em>101 orgs, incl. a Fortune 500 firm and a national bank</em></div>
<div class="leak"><i>2025</i><b>Home Depot</b>A GitHub token exposed for a year.<em>Cloud, order systems and pipelines</em></div>
<div class="leak"><i>2026</i><b>CISA contractor</b>A private repo left public for six months.<em>AWS GovCloud admin keys, SSH keys, passwords</em></div>
</div>
<p class="pop-src">Sources: GitGuardian's <a href="https://www.gitguardian.com/breaches" target="_blank" rel="noopener">Timeline of Secrets Breaches</a> (80+ more), <a href="https://flare.io/learn/resources/docker-hub-secrets-exposed" target="_blank" rel="noopener">Flare</a>, <a href="https://whitetuque.com/private-cisa-five-failures/" target="_blank" rel="noopener">White Tuque</a>.</p>
</div>
</div>

<!--
Walk the arrows: nobody did anything unusual, and still the password is in
eight places, most of which nobody will remember to clean up.
Click "Once it's pushed, it's leaked." for the wall of real incidents
(from GitGuardian's breach timeline); "close" at the top right hides it.
-->

---

## The rules we'll use all day

| #   | Rule                         | In one line                                           |
| --- | ---------------------------- | ----------------------------------------------------- |
| 1   | Least privilege              | Read only what you need; deny by default              |
| 2   | Identity over secrets        | Prove who you are instead of holding a password       |
| 3   | Short-lived, revocable       | A leaked credential should expire by itself           |
| 4   | Secret zero                  | The first credential comes from somewhere: know where |
| 5   | Separation of duties         | Who deploys the app needn't read its secrets          |
| 6   | Audit everything             | "Who read this, and when?" has an answer              |
| 7   | Plan for leaks               | Rotation and revocation are routine                   |
| 8   | Never in git, logs or images | Including history and build output                    |

<!--
Every idea in the rest of the talk is one of these rules put into practice.
The wrap-up comes back to this table.
-->

---

## Step one: encrypt it on your own machine

<style scoped>
.split > div:last-child { font-size: 0.9em; }
</style>

<div class="split split-60">
<div>

```text
~/.password-store/
├── .gpg-id          who it's encrypted for
└── dojo/
    ├── api-token.gpg
    └── db.gpg       ← the path dojo/db
```

```text
$ pass show dojo/db        # your key opens it
first-password
username: app
host: db.internal
```

</div>
<div>

**`pass`** (passwordstore.org): each secret is an **encrypted file** in a folder tree.

- a **path** = folders + a file name
- the file holds **key/value lines**
- only **your key** opens it

**The shape to remember:** a path, an encrypted file, key/value pairs.

Windows: **gopass**, same store.

</div>
</div>

<!--
Lab 2. The simplest fix for rule 8 on your own machine. The point for the rest
of the talk is the shape: a vault's KV store is exactly this, a path pointing
at key/value pairs, only on a server. gopass (Windows, macOS, Linux) reads and
writes the same store, so this isn't a Linux/macOS-only habit.
-->

---

## Why that stops at your own machine

<div class="split split-60">
<div>

<div class="mermaid">
flowchart TB
  f["db.gpg: for you, A and B"] --> y["You: a copy"]
  f --> a["A: a copy"]
  f --> b["B: a copy"]
  b -.->|"B leaves"| r["New db.gpg:<br/>for you and A"]
  b -.-> o["B's old copy<br/>still opens"]
</div>

</div>
<div>

To share, you **encrypt it again for each person**, and each of them keeps a copy.

- **Removing someone** takes nothing back: rotate everything they saw
- **No record** of who read what, or when
- **Nothing expires** by itself
- An **app or a pipeline** would need a private key: one more secret to hide

</div>
</div>

<!--
Lab 2 ends here too: take a teammate off and their old copy still opens. For
your own secrets, pass is great. For a team, the copies are the problem, which
is exactly what the next slide fixes.
-->

---

## A vault: one copy, behind one gate

<div class="split split-60">
<div>

<div class="mermaid">
flowchart LR
  p["People"] --> gate
  a["Apps"] --> gate
  c["CI jobs"] --> gate
  gate["The gate<br/>Who are you?<br/>What may you do?<br/>Written down."] --> store[("Encrypted<br/>storage:<br/>the only copy")]
</div>

</div>
<div>

- Stored **encrypted**, in one place
- Nobody keeps a copy: they **ask** each time
- Every ask is checked and **recorded**
- Change it once; everyone gets it

**OpenBao:** the open-source fork of HashiCorp Vault. `bao` = `vault`.

</div>
</div>

<!--
The point isn't the encryption, it's that copies stop multiplying. People and
programs fetch the secret when they need it, so rotating means changing one
place. Tools built for Vault (sops, Python's hvac) work unchanged with OpenBao.
-->

---

## Every request passes the same checks

<div class="mermaid">
flowchart LR
  r["A request: token + path + operation"] --> t{"Is the token valid, and not expired?"}
  t -- no --> d1["Denied"]
  t -- yes --> p{"Does a policy allow this operation on this path?"}
  p -- no --> d2["Denied"]
  p -- yes --> e["The engine at that path does the work"]
  r -.-> a[("Audit log")]
</div>

- **Token:** who is asking. **Path:** what they want, e.g. `secret/students/student07/db`. **Operation:** read, write, list, delete.
- Allowed or denied, every request **and its answer** go to the audit log.

<!--
This slide is the mental model for the whole day. Every "permission denied"
in the labs is one of these two diamonds saying no.
-->

---

## Signing in: an identity, then a token

<div class="mermaid">
flowchart LR
  b["You, in a browser"] -->|"Forgejo sign-in"| m1["Auth method: oidc"]
  t["You, in the terminal"] -->|"a JWT the platform signed"| m2["Auth method: jwt"]
  m1 --> e["Entity: student07"]
  m2 --> e
  e --> tok["Token: policies + TTL"]
</div>

- **Auth method:** how you prove who you are. Something else vouches for you, so there's no vault password.
- **Entity:** _you_, however you came in. Two doors, one person.
- **Token:** what you get back, and what every request carries. Machines sign in the same way (AppRole, JWT).

<!--
Like the front desk at an office: you show ID (auth method), they look you up
(entity), and hand you a visitor badge that expires tonight (token).
-->

---

## Tokens: short-lived by design

- A token has a **TTL** (time to live): when it runs out, the token is useless
- It can be **renewed** while in use, but only up to a **max TTL**; then you sign in again
- It can be **revoked** at any time, and stops working at once
- It carries **policies**: they, not the token, decide what it can do
- Its **accessor** is a reference to it: good for looking it up or revoking it, useless for logging in

**Why:** a password works until someone changes it. A token that leaks stops working **by itself**, and you can kill it the moment you know.

<!--
Rule 3: short-lived, revocable. Contrast with a password in a .env file, which
has no expiry at all. The accessor comes back in the incident part.
-->

---

## Policies: paths and capabilities

```hcl
# The class's policy: each student may use their own folder, nothing else
path "secret/data/students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}
```

- A **path** says _where_; **capabilities** say _what_: `create`, `read`, `update`, `patch`, `delete`, `list`, `sudo`, `deny`
- **Nothing matches? Denied.** Least privilege is the default, not something you add.
- `{{identity.entity.name}}` is filled in on each request with the caller's name: **one policy** for 30 students or 3,000, no per-person rule to maintain

<!--
Read the policy aloud as a sentence: "anyone may create, read, update... under
secret/data/students/ followed by their own name". student07 asking for
student02's folder matches no rule, so it's denied.
-->

---

## Secrets engines: several tools behind one gate

<style scoped>
table { font-size: 19px; }
th, td { padding: 6px 12px; }
section > p { font-size: 0.9em; }
</style>

OpenBao isn't only a store. It runs several **secrets engines**, each at its own path, all behind the same token and policy checks.

| A path you'll use              | Engine       | What it does                                             | Where it comes back                                 |
| ------------------------------ | ------------ | -------------------------------------------------------- | --------------------------------------------------- |
| `secret/students/student07/db` | **KV**       | Keeps a secret you give it, and hands it back            | Next few slides                                     |
| `transit/encrypt/sops`         | **Transit**  | Encrypts what you send; its key never leaves the vault   | Later: secrets in git, config files safe to commit |
| `database/creds/app`           | **Database** | Makes a new DB login per request, deleted when time's up | Later: deployments, no shared DB password          |

Only **KV** keeps what you gave it. The others **do a job** with keys that stay inside the vault. The **first part** of the path (`secret/`, `transit/`, `database/`) picks the engine; the rest means something to that engine. Sign-in methods work the same way, under `auth/`.

<!--
Read the first path aloud: "the KV engine at secret/, the secret named
students/student07/db". Then the others: "the transit engine, encrypt, with
the key called sops"; "the database engine, credentials for the role app".
Same gate for all three: a token, a policy that allows that path.
KV is where you'll spend the next few slides. Transit comes back later
(sops, lab 7): it locks config files so they're safe to commit, and the
key that opens them never leaves the vault. Database comes back later
(lab 12): instead of one shared DB password, every caller gets its own
login that expires in minutes. The point to land now: a vault is more than
a password safe; some engines hand out things that never existed before
you asked.
-->

---

## KV v2: the vault's key-value store (Git~ish)

<style scoped>
.split > div:last-child { font-size: 0.88em; }
</style>

<div class="split">
<div>

A **secret** is a small set of key/value pairs, kept at a **path**:

```text
path:  secret/students/student07/db

username = app
password = s3cr3t-pa55
```

Like `pass`'s store: the path works like a folder, the value is key/value pairs. The difference: it's **one copy on a server**, and policies grant access by path.

</div>
<div>

**KV v2:** version 2 of the key/value engine. v1 just overwrites; v2 adds:

- **Versioning:** each write is a **new version**; old ones stay (10 by default), so a bad change is a **rollback** away
- **History:** each version records **when** it was written, deleted or destroyed
- **Soft delete:** delete **hides** a version, `undelete` brings it back; only **destroy** is final

</div>
</div>

<!--
KV v1 just overwrites: one value per path, no history. v2 is what you use in
practice. The labs' shared vault, secret/, is KV v2.
-->

---

## KV v2: every write is a new version

<div class="mermaid">
flowchart LR
  v1["v1: password = first"] -->|"put"| v2["v2: password = second"]
  v2 -->|"patch"| v3["v3: password = third"]
  v3 -->|"rollback to v2"| v4["v4: password = second (current)"]
</div>

- **put** writes a whole new version; **patch** changes only the keys you give
- **Reading** gets the newest version, unless you ask for an older one
- **Rollback** doesn't rewrite history: it copies an old version's data as a **new** version, so even the rollback is on record

<!--
Nothing here ever loses data: every step adds a version. That's the property
you want from anything that holds credentials.
-->

---

## KV v2: delete is not destroy

<style scoped>
.split > div:last-child { font-size: 0.9em; }
</style>

<div class="split">
<div>

<div class="mermaid">
stateDiagram-v2
  direction LR
  [*] --> Current: put
  Current --> Deleted: delete
  Deleted --> Current: undelete
  Current --> Destroyed: destroy
  Deleted --> Destroyed: destroy
</div>

| KV v2             | Azure Key Vault       |
| ----------------- | --------------------- |
| delete / undelete | soft delete / recover |
| destroy           | purge                 |

</div>
<div>

- **delete** hides a version. Anyone allowed can `undelete` it: **the value is still there**
- **destroy** wipes that version's data. Nothing brings it back
- **metadata delete** removes every version and the history

<label for="destroy-wall" class="pop-trigger">A secret leaked?</label> Deleting does nothing, and destroying doesn't reach copies already taken. **Rotate and revoke first**, then destroy the old versions so nobody can roll back to them.

</div>
</div>

<div class="pop">
<input type="checkbox" id="destroy-wall" class="pop-toggle">
<div class="pop-overlay">
<label for="destroy-wall" class="pop-close">close &#10005;</label>
<h3>A secret leaked: rotate, revoke, then destroy</h3>
<p class="pop-sub">Rotating is the fix. Destroying is the clean-up, and it still matters.</p>
<div class="leak-grid cols-3">
<div class="leak"><i>1 &middot; the fix</i><b>Rotate</b>Write a new value to the vault; apps using the Agent pick it up in seconds.<em>This is what protects you</em></div>
<div class="leak"><i>2 &middot; the fix</i><b>Revoke at the source</b>Change the DB password, revoke the API key. A new version in KV doesn't turn the old value off.<em>Until then, the old value still works</em></div>
<div class="leak"><i>3 &middot; clean-up</i><b>Destroy the old versions</b><code>bao kv destroy -versions=3,4</code> wipes their data. KV drops versions past 10 on its own; this does it now.<em>Nothing brings them back</em></div>
<div class="leak"><i>why destroy</i><b>Rollback or undelete</b>One command puts the leaked value back in use, and the Agent ships it to the app.<em>A known-leaked value, live again</em></div>
<div class="leak"><i>why destroy</i><b>Every reader can fetch it</b><code>read</code> on the path is enough for <code>-version=N</code>: often many people and apps.<em>Same permission as the current value</em></div>
<div class="leak"><i>why destroy</i><b>Some can't be rotated away</b>Signing keys, keys that open old backups, recovery codes. And patterns: <code>Summer2025!</code> hints at <code>Autumn2025!</code><em>The old value stays dangerous</em></div>
</div>
<p class="pop-src">Protect it: grant <code>undelete/</code> and <code>destroy/</code> to the few who run incidents, not to every reader, and keep <code>max_versions</code> low for secrets that rotate often.</p>
</div>
</div>

<!--
The common mistake: "I deleted it" after a leak. Deleted versions come back
with one command. Also: KV v2 splits the permissions (data/ for the value,
metadata/, delete/, destroy/ for the history), so a policy can let an app read
a secret without letting it wipe the history. That's why the policy on the
earlier slide says secret/data/...
For a deeper dive, click "A secret leaked?": the order (rotate, revoke,
destroy), why destroying still matters once you've rotated, and how to guard
undelete/ and destroy/. "close" at the top right hides it.
-->

---

<!-- _class: section-title -->

# Part 2

## From a shared vault to your own

---

## Where most companies start: one shared vault

<style scoped>
.split > div:last-child { font-size: 0.85em; }
</style>

<div class="split split-40">
<div>

<div class="mermaid">
flowchart TB
  pt["The platform team: owns everything"] --> kv["secret/ : one engine for all"]
  kv --> a["students/student01/"]
  kv --> b["students/student02/"]
  kv --> c["students/student07/"]
  pol["One templated policy"] -.->|"your folder only"| kv
</div>

</div>
<div>

**One vault, a folder per team**, one policy keeping each team in its folder. Lab 3 works here, and it's a good start: one copy, least privilege by path.

**Where it strains as teams grow:**

- Only the **platform team** can add an engine, a policy or a sign-in: every change is a ticket
- **One policy mistake** reaches every team
- `list` shows every team's **secret names**
- Everyone shares **one set** of engines and settings

</div>
</div>

<!--
Lab 3 is this model: secret/students/<you>/, and the one templated policy
from Part 1. Nothing wrong with it; plenty of companies stay here. The
strains are about ownership: the team that owns the secrets can't run their
own access. That's what namespaces fix, next.
-->

---

## Namespaces: a vault inside the vault

<div class="split">
<div>

<div class="mermaid">
flowchart TB
  root["root: the platform team"] --> shared["secret/ : the shared class vault"]
  root --> s["students/"]
  s --> n1["students/student01"]
  s --> n2["students/student02"]
  s --> n3["students/student07"]
</div>

</div>
<div>

Each namespace has its **own** engines, policies, tokens and auth methods.

- Invisible to its neighbours
- An admin of one namespace is **nobody** anywhere else
- The platform team runs the root and hands out namespaces

**At work:** one per team. **On Azure:** a Key Vault per team or environment. **Today:** you are admin of `students/<you>`.

</div>
</div>

<!--
Multi-tenancy without running a vault per team: each strain on the last
slide goes away, because the team runs its own engines, policies and
sign-ins, and a mistake stays inside one namespace.
-->

---

## Policies as code

<div class="mermaid">
flowchart LR
  e["Edit the policy file"] --> pr["Pull request and review"]
  pr --> m["Merge to main"]
  m --> a["Applied to the vault"]
  m -.->|"a bad change?"| r["git revert"]
</div>

- A policy **is** a security decision: who can read production's password
- Changed by clicking in a UI: no review, no history, no way back
- Changed as a file in git: **reviewed**, **recorded**, **reversible**, and the same everywhere
- The same workflow you learned in Git Fundamentals, for access instead of code

<!--
The UI is fine for learning and looking. Changes that matter go through a pull
request. Lab 4 has you do both so you feel the difference.
-->

---

<!-- _class: section-title -->

# Part 3

## Secrets in code

---

## Three places an app's secret can live

| Where                | Good                                                      | The catch                                                                               |
| -------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| In the code          | nothing to set up                                         | in git forever                                                                          |
| A git-ignored `.env` | out of git                                                | plaintext on every laptop, shared by hand, never expires, passed to every child process |
| **The vault**        | one copy, access by policy, audited, rotated in one place | the app needs **an identity**, and a token that stays fresh                             |

**Never log a secret:** log _that_ you loaded the config, not _what_ it holds.

<!--
The vault's catch is the rest of this part: how does an app prove who it is,
and who keeps its token alive?
-->

---

## An app needs an identity of its own

<style scoped>
.split > div:last-child { font-size: 0.9em; }
</style>

<div class="split split-40">
<div>

<div class="mermaid">
flowchart TB
  you["You"] -->|"sign in: Forgejo,<br/>a browser, a click"| t1["Your token:<br/>your policies"]
  app["The app"] -->|"no browser,<br/>nobody to click"| q["???"]
</div>

</div>
<div>

Every request needs a **token**, and a token comes from **signing in**. You sign in through Forgejo. An app runs **unattended**: it has to sign in **by itself**.

**Why not just give it your token?**

- It could read **everything you can**
- It **stops working** when yours expires, or you leave
- The audit log says **you** did what the app did

**So the app gets its own account**, with its own policy and short-lived tokens: an **AppRole** role.

</div>
</div>

<!--
Rules 1 and 2. The question to ask the room: "how does a program that nobody
is watching prove who it is?" A person has a browser and a Forgejo login; a
program has neither. Borrowing a person's token is the usual shortcut, and it
breaks least privilege, breaks when the person leaves, and makes the audit
log lie. The answer is a machine account, the same idea as a service account
or an Azure service principal.
-->

---

## AppRole: a username and a password, for a program

<style scoped>
.mermaid { margin: 0; }
.mermaid svg { max-height: 300px; }
table { font-size: 18px; display: table; overflow: visible; }
th, td { padding: 3px 12px; }
</style>

<div class="mermaid">
sequenceDiagram
  participant Ad as You (admin)
  participant B as OpenBao
  participant App as The app
  Ad->>B: once: create role "app" with policy app-read
  B-->>Ad: its role ID, and a new secret ID
  Ad->>App: hand over both
  App->>B: at each start: log in with both
  B-->>App: a token with app-read, 2 minutes
  App->>B: read team/app, with the token
</div>

| Piece                                                            | Like a     | Secret? | Kept where, and for how long                            |
| ---------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------- |
| **Role ID**                                                      | username   | no      | the app's config, for good; fine in git                 |
| <label for="secretid-wall" class="pop-trigger">Secret ID</label> | password   | **yes** | a memory-only file, for **seconds**: used once, deleted |
| **Token**                                                        | a day pass | yes     | the Agent's memory; minutes, renewed while the app runs |

<div class="pop">
<input type="checkbox" id="secretid-wall" class="pop-toggle">
<div class="pop-overlay">
<label for="secretid-wall" class="pop-close">close &#10005;</label>
<h3>The secret ID is a secret outside the vault: keep it small</h3>
<p class="pop-sub">AppRole doesn't make secret zero go away. It makes the secret short-lived, single-use, and tied to one place.</p>
<div class="leak-grid cols-3">
<div class="leak"><i>time</i><b>It expires</b><code>secret_id_ttl</code>: an hour in lab 6, minutes in production.<em>A stolen copy goes stale</em></div>
<div class="leak"><i>use</i><b>It works once</b><code>secret_id_num_uses=1</code>: spent at login; then the app holds only a token.<em>A thief who uses it first makes the app's login fail: your alarm</em></div>
<div class="leak"><i>place</i><b>It only works from given addresses</b><code>secret_id_bound_cidrs</code>, and <code>token_bound_cidrs</code> for the token.<em>A copy used anywhere else is refused</em></div>
<div class="leak"><i>transit</i><b>It's wrapped on the way</b>Response wrapping: the deliverer carries a single-use wrapper, and only the app opens it.<em>Already opened? Intercepted, and you know</em></div>
<div class="leak"><i>disk</i><b>It's deleted after reading</b>The Agent's <code>remove_secret_id_file_after_reading</code>, as in lab 6.<em>Nothing useful left on disk</em></div>
<div class="leak"><i>who</i><b>The halves travel apart</b>Role ID in config; secret ID at deploy, from a deliverer that may <strong>make</strong> secret IDs, not <strong>read</strong> secrets.<em>One half alone logs nobody in</em></div>
</div>
<p class="pop-src"><b>Weak:</b> a long-lived secret ID in a CI variable (lab 9). <b>Good:</b> wrapped, single-use, minutes long, delivered at deploy. <b>Best:</b> no secret ID at all: the platform vouches for the app (labs 9 and 11).</p>
</div>
</div>

<!--
Walk the diagram top to bottom. The top half happens once, and it's done by
someone who already has a token (you, in lab 6). The bottom half happens on
every start: the app trades its two halves for a short-lived token, and uses
that token, not the halves, for every read. Neither half alone logs in, so
they can travel by different routes: the role ID in the app's config, the
secret ID delivered at deploy. The weak spot is the arrow "hand over both":
someone has to give the app its secret ID. Keep that thought; it's secret
zero, two slides on. Click "Secret ID" in the table for how it's kept small
(expiry, single use, address binding, wrapping, deleted after reading,
split delivery); "close" at the top right hides it.
-->

---

## OpenBao Agent: the vault work, done for the app

<div class="mermaid">
flowchart LR
  cred["Role ID + secret ID"] --> agent["OpenBao Agent"]
  agent -->|"logs in, renews the token"| bao["OpenBao"]
  bao -->|"team/app, checked every few seconds"| agent
  agent -->|"writes"| file["app.env: in memory, only the app's user can read"]
  file --> app["The app just reads a file"]
</div>

- The app knows **nothing** about vaults: no SDK, no token, no code change
- **Rotate** in the vault and the file changes: no commit, no restart
- The Agent runs **next to** the app (a sidecar), and handles logins, renewals and re-reads

<!--
This is the usual pattern at work: Vault Agent, the Kubernetes Vault injector,
the Secrets Store CSI driver on AKS. The app reads a file or env; something
beside it does the vault work.
-->

---

## Secret zero: where the chain starts

<div class="split split-40">
<div>

<div class="mermaid">
flowchart TB
  app["The app needs the DB password"] -->|"it's in the vault"| tok["The vault wants a token"]
  tok -->|"a token needs a login"| sid["The login needs a secret ID"]
  sid -->|"who delivers that?"| q["Secret zero"]
</div>

</div>
<div>

Every credential is protected by another one. **Something has to be first.** Ranked, best first:

1. **Nothing handed over:** the platform vouches for the workload (coming up: CI jobs, then deployed apps)
2. **A trusted deliverer** hands over a single-use, short-lived secret ID
3. **Stored forever** in a CI setting or a file: the usual, and the weakest

</div>
</div>

<!--
Rule 4. Asking "what's our secret zero?" about any system shows where the real
risk sits. The rest of the talk is about making option 1 possible.
-->

---

## Option 2 in practice: who hands over the secret ID?

<style scoped>
.mermaid { margin: 0; }
.mermaid svg { max-height: 310px; }
ul { font-size: 0.8em; margin-top: 4px; }
</style>

<div class="mermaid">
sequenceDiagram
  participant D as Deploy pipeline (the deliverer)
  participant B as OpenBao
  participant A as Agent, beside the app
  D->>B: 1. log in with the job's own identity (nothing stored)
  D->>B: 2. request a new secret ID for "app", **wrapped**
  B-->>D: a single-use wrapper, good for 60 seconds
  D->>A: 3. put wrapper in memory-only file, start the app
  A->>B: 4. unwrap it (one use only); log in: role ID + secret ID
  B-->>A: a token; secret ID is now spent and worthless
  A->>B: 5. renew token, re-read secrets (secret ID no longer needed)
</div>

- **Every deploy, a fresh secret ID** (not stored, made on demand)
  - Contrast: **Option 3 is storing the secret ID in the CI library permanently** and handing it out the same way every deploy—no rotation, so it's worth stealing
- **The deliverer (pipeline) can mint secret IDs, not read them.** The wrapper means it never even sees the real secret ID
- **Single-use and wrapped.** If someone else intercepted it and tried to unwrap it first, they'd get "token already unwrapped" (alarm). Once the app unwraps it, it's worthless
- The running app renews its token, so the secret ID only matters at that one login

<!--
This answers "so where does the secret ID live, and who rotates it?"
Pipeline flow: it logs in with its job identity (from lab 9, nothing stored),
asks for a wrapped secret ID for the "app" role, and puts the wrapper into
the app bundle. The app's Agent unwraps it once and logs in; the secret ID
is spent after that first use. The app then keeps renewing its token for
the rest of its life. No second login, no second secret ID.

Option 3 ("just store it"): a company stores the secret ID in their CI
library, hard-coded or in a vault. Every deploy uses the same one. It's
never rotated, so it's worth stealing and exploiting offline.

Option 2 (this slide): every deploy mints a new secret ID. It's single-use,
so even if someone intercepted the wrapper, they can't exploit it the same
way twice. The interception also fails loudly ("already unwrapped"), so
you catch it.

For a long-running app, give the role a periodic token (token_period):
it lives as long as the Agent keeps renewing it, so no second login,
no second secret ID. If the app stops, the token lapses by itself.

Lab 10 does this with a real pipeline. Lab 6 did steps 2-4 by hand: you
were the deliverer, with a one-hour, reusable secret ID.
-->

---

<!-- _class: section-title -->

# Part 4

## Secrets in git

---

## Config belongs in git; secret values don't

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

GitOps wants **all** config in git: reviewed, versioned, deployable. Passwords are config too.

**sops** encrypts only the **values**:

- Keys stay readable, so diffs and reviews still work
- The file is safe to commit, push and fork
- The key that opens it is in the **vault**, not in the repo

</div>
</div>

---

## Envelope encryption: the key never leaves the vault

<div class="mermaid">
sequenceDiagram
  participant S as sops
  participant B as OpenBao transit
  Note over S: Encrypting
  S->>S: make a random data key, encrypt each value with it
  S->>B: encrypt this data key with the key "sops"
  B-->>S: vault:v1:... (the wrapped data key)
  S->>S: keep the wrapped key in the file, forget the plain one
  Note over S: Decrypting, later
  S->>B: decrypt vault:v1:...
  B-->>S: the data key, if your policy allows
</div>

<div class="small">

**Envelope:** a data key locks the file; the vault's key locks the data key. The file never goes to the vault, and the vault's key never comes out.

</div>

---

## Who can open it, and closing old copies

- **Decrypt is a policy.** Take someone's policy away and they can't open the file, even the copies they already cloned
- **Encrypt-only** is a policy too: CI can write config it can never read
- **Every decrypt is audited:** who opened production's config, and when
- **Rotate** the transit key: new files use version 2, and old ones are re-wrapped with it
- **Retire** version 1 (`min_decryption_version`): old copies in forks and backups **stop opening**

Compare: a password committed in plaintext can't be un-leaked. An encrypted one can be **locked out**.

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

- A **repository secret** is given to every job in the repo
- The log **masks exact matches** only
- **Anyone who can push a workflow** can read it: a branch is enough
- Fork pull requests get no secrets; `pull_request_target` does, so never run PR code in it
- It **never expires** by itself: it's a secret zero

</div>
</div>

<!--
Stored CI secrets are the most common secret zero at work. The rest of this
part replaces them with the job's own identity.
-->

---

## Single-use runners

<div class="split split-60">
<div>

<div class="mermaid">
flowchart TB
  q["Queued jobs"] --> c["Controller"]
  c -->|"keeps a few warm"| r["Fresh runner"]
  r -->|"takes exactly one job"| j["The job runs"]
  j --> x["Runner deleted, with all it left behind"]
</div>

</div>
<div>

- No job sees another's files, processes or leftover credentials
- More runners start when jobs queue
- The **Runners** panel shows ready, busy or broken

**At work:** GitHub's Actions Runner Controller, Azure DevOps scale-set agents, GitLab's autoscaling runners.

</div>
</div>

<!--
Long-lived shared runners are how one team's job reads another team's
leftovers: a token in a temp file, a cached credential.
-->

---

## The job's own identity

<div class="mermaid">
sequenceDiagram
  participant J as CI job
  participant F as Forgejo
  participant B as OpenBao
  J->>F: a token for this run, please
  F-->>J: signed JWT: this repo, this branch, this user
  J->>B: log in to auth/jwt-ci with the JWT
  Note over F,B: OpenBao checks Forgejo's signature, then the role's bound claims
  B-->>J: a 5-minute token, one policy
  J->>B: read team/ci
</div>

**Nothing is stored in CI.** The proof is made fresh for each run, and expires in minutes.

---

## What the vault checks

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

- **Signature:** only Forgejo could have made it (`iss`)
- **Audience:** it was made **for** the vault (`aud`), so it can't be replayed elsewhere
- **Bound claims:** the role says which **repository** and **ref** may log in
- **Expiry:** minutes, not months

A branch isn't `main`: **refused**. Another repo: **refused**.

</div>
</div>

<!--
A JWT is a signed statement: "this job is running for this repo on this
branch". The vault doesn't need a shared secret, only Forgejo's public keys.
-->

---

## At work: the same, ready-made

```yaml
# GitHub Actions
permissions:
    id-token: write
steps:
    - uses: hashicorp/vault-action@v3 # works with OpenBao too
      with:
          url: https://vault.example.com
          method: jwt
          role: ci-main
          secrets: team/data/ci deploy_token | DEPLOY_TOKEN
```

**Azure:** `azure/login` or an Azure DevOps service connection with **workload identity federation**.
**GitLab:** `id_tokens:` in the job. The labs use plain `curl` + `bao`, so you can see each step.

---

<!-- _class: section-title -->

# Part 6

## Secrets in deployments

---

## How should an app on a server get its secrets?

1. **Platform identity.** The platform vouches for the app (managed identity, a Kubernetes service account); the app trades that for a short-lived vault token. **Nothing is handed over.**
2. **Dynamic credentials** on top: a database login made for this app, with a lease.
3. **AppRole + a trusted deliverer**, when there's no platform identity: a single-use, short-lived secret ID.
4. **Anti-patterns:** secrets in the image, a committed `.env`, env vars pushed by the pipeline, one shared token.

<!--
Best first. Most real systems are a mix; the goal is to move each app up the
list.
-->

---

## Platform identity: the host vouches for the app

<div class="mermaid">
sequenceDiagram
  participant P as app-host
  participant A as Agent in your slot
  participant B as OpenBao
  P->>A: a 10-minute JWT, sub = slot:student07, readable only by this slot
  A->>B: log in with the JWT
  Note over A,B: OpenBao checks the platform's signature, and that sub is this role's slot
  B-->>A: a token with the app's policy
  A->>B: read team/app
  A->>A: write app.env for the app
</div>

Same idea as the CI job, for a running app. **On Azure:** managed identity. **On Kubernetes:** a service account token.

---

## Deploy, but don't read

<style scoped>
table { font-size: 24px; }
</style>

|              | Identity                           | May                                       | May not         |
| ------------ | ---------------------------------- | ----------------------------------------- | --------------- |
| **Pipeline** | Forgejo job token, `aud: app-host` | deploy to _its owner's_ slot, from `main` | read `team/app` |
| **Pipeline** | Forgejo job token, `aud: openbao`  | read `team/ci`                            | read `team/app` |
| **App**      | platform token, `sub: slot:<you>`  | read `team/app`                           | deploy anything |

**Separation of duties:** whoever ships the code never holds production's secrets, and a branch can't ship.

<!--
Rule 5. If the pipeline is compromised, the attacker can deploy (bad), but
can't read the production secrets (much less bad).
-->

---

## Dynamic credentials: a login made on demand

<div class="split split-60">
<div>

<div class="mermaid">
sequenceDiagram
  participant App
  participant B as OpenBao
  participant DB as Postgres
  App->>B: a login, please
  B->>DB: create user v-app-x7k2
  B-->>App: username, password, 5-minute lease
  App->>B: renew the lease
  Note over B,DB: the lease ends, or is revoked
  B->>DB: drop user v-app-x7k2
</div>

</div>
<div>

- No shared password: every caller gets **its own** login
- A **lease** is its time limit: renew it while you need it
- A leaked login is worth **minutes**, and its name shows exactly who had it
- The vault's own admin login is rotated so **only the vault** knows it

</div>
</div>

---

## Audit: every request leaves a trace

- Every request **and its answer** is logged: who, what path, allowed or denied, when
- Secret **values** are hashed in the log, so the log isn't a leak itself
- Each entry names the token's **accessor**, so you can follow one token's actions
- Guard the log: who can read it, and where it's shipped

**The question it answers:** "this token leaked, what did it do?", in minutes, not guesses.

<!--
Rule 6. At work the audit log goes to the SIEM (on Azure: diagnostic settings
to Log Analytics).
-->

---

## Tokens form a tree

<div class="split split-40">
<div>

<div class="mermaid">
flowchart TB
  p["Leaked token"] --> c1["A child it made"]
  p --> c2["Another child"]
  c1 --> g["Its child"]
</div>

</div>
<div>

- A token that can create tokens makes **children**
- An attacker's first move: make a **spare** token
- **Revoke the parent, and the whole tree goes**, including children you didn't know about
- Revoking only the token you know about leaves the spare working

</div>
</div>

---

## When a token leaks

1. **Find** the token's **accessor**: pass that around during the incident, never the token
2. **Investigate:** the audit log by accessor: what it read, what it was refused, what tokens it made
3. **Contain:** revoke the token, and its whole tree with it
4. **Rotate** what it read (not what it was refused)
5. **Recover:** apps using the Agent pick up the new values with no deploy
6. **Review:** why a long-lived, token-making token existed at all

<!--
The order matters: investigate before you revoke only if it's quick; the audit
log survives the revoke, so when in doubt, contain first.
-->

---

## OpenBao and Azure, side by side

<style scoped>
table { font-size: 21px; }
th, td { padding: 5px 14px; }
</style>

| OpenBao                                        | Azure                                              |
| ---------------------------------------------- | -------------------------------------------------- |
| Namespace                                      | A Key Vault per team or environment                |
| KV v2: versions, delete / undelete / destroy   | Key Vault: versions, soft delete / recover / purge |
| ACL policy (paths + capabilities)              | RBAC roles (Secrets User, Secrets Officer)         |
| OIDC auth method                               | Entra ID sign-in                                   |
| JWT auth for the platform (terminal, app-host) | Managed identity                                   |
| AppRole                                        | Service principal with a client secret             |
| JWT auth for CI jobs                           | Workload identity federation                       |
| Transit engine (sops)                          | Key Vault keys (sops `azure_kv`)                   |
| Database engine                                | Entra ID sign-in to Azure SQL / Postgres           |
| Audit device                                   | Diagnostic settings to Log Analytics               |

---

## One map: who reads what today

<style scoped>
.split > div:last-child { font-size: 0.85em; }
</style>

<div class="split split-60">
<div>

<div class="mermaid">
flowchart LR
  you["You: terminal and UI"] --> s["secret/students/you"]
  agent["The Agent, for your app"] --> app["team/app"]
  job["A CI job"] --> ci["team/ci"]
  att["A leaked token"] -.->|"refused"| adm["team/admin"]
  subgraph shared["Shared vault: secret/"]
    s
  end
  subgraph ns["Your namespace: team/"]
    app
    ci
    adm
  end
</div>

</div>
<div>

- The class shares `secret/`; in your namespace you mount your own `team/`
- Each reader has **its own identity** and a policy for **one path**
- The leaked token is **refused** at `team/admin`: least privilege did its job
- Every **rotate** today is a **new version** of one of these

</div>
</div>

<!--
The whole talk on one slide, just before the labs. team/app is read by the
Agent (labs 6, 11) and the attacker in the drill (13); team/ci by the CI job
(9); team/admin is the one nobody should get, and labs 4 and 13 show it
refused. secret/students/you is where labs 0-3 happen.
-->

---

## Your labs: the talk, hands-on

<style scoped>
table { font-size: 22px; }
</style>

| Part               | Labs      | You'll see                                                                           |
| ------------------ | --------- | ------------------------------------------------------------------------------------ |
| 1. Foundations     | **0-3**   | signing in, a leak in git, `pass`, versions, delete vs destroy, the templated policy |
| 2. Your own vault  | **4**     | a namespace you run: engine, policy as code, a token you revoke                      |
| 3. Secrets in code | **5-6**   | the three places, AppRole, the Agent, rotation with no restart                       |
| 4. Secrets in git  | **7**     | sops + transit, encrypt-only, retiring a key version                                 |
| 5. Pipelines       | **8-9**   | masking, AppRole in CI, then the job's own identity                                  |
| 6. Deployments     | **11-13** | platform identity, dynamic logins (optional), the incident drill                     |

About **2-3 hours** in all. Details and timings: [labs.md](labs.md).

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Let's go

## Next: [labs.md](labs.md), then your terminal

Open the **Vault** card; the first time, click **Authorize** in Forgejo.

---

<!-- _class: section-title -->

# Wrap-up

## After the labs

---

## The rules, and where you used them

<style scoped>
table { font-size: 21px; }
</style>

| #   | Rule                         | Where you did it                                                               |
| --- | ---------------------------- | ------------------------------------------------------------------------------ |
| 1   | Least privilege              | The templated policy (3), `app-read` (4), `ci-read` (9)                        |
| 2   | Identity over secrets        | The job's OIDC token (9), the platform's identity (11)                         |
| 3   | Short-lived, revocable       | Token TTLs (4), leases (12), revoking a tree (13)                              |
| 4   | Secret zero                  | Your GPG key (2), AppRole's secret in CI (9), gone with OIDC                   |
| 5   | Separation of duties         | The pipeline deploys but can't read `team/app` (11)                            |
| 6   | Audit everything             | `bao-audit`: who read what, by accessor (4, 13)                                |
| 7   | Plan for leaks               | Removing a teammate (2), key rotation (7), no redeploy (6, 11), the drill (13) |
| 8   | Never in git, logs or images | gitleaks (1), `pass` (2), masking (8), sops (7), no DEBUG dumps (5)            |

---

## At work on Monday

- **Scan** your repos' history with gitleaks, and add the pre-commit hook
- **Move your own tokens** out of `.env` files and notes into `pass` (gopass on Windows)
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

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    fontFamily: "Manrope, sans-serif",
    flowchart: { htmlLabels: true, curve: "basis" },
    sequence: { mirrorActors: false, actorFontSize: 18, messageFontSize: 18, noteFontSize: 18, boxMargin: 8 },
    themeVariables: {
      fontSize: "18px",
      background: "#18242e",
      primaryColor: "#21313c",
      primaryTextColor: "#e8f0f2",
      primaryBorderColor: "#3dd6c3",
      secondaryColor: "#18242e",
      tertiaryColor: "#18242e",
      lineColor: "#a9bac2",
      edgeLabelBackground: "#18242e",
      clusterBkg: "#18242e",
      actorBkg: "#21313c",
      actorBorder: "#3dd6c3",
      actorTextColor: "#e8f0f2",
      signalColor: "#a9bac2",
      signalTextColor: "#e8f0f2",
      noteBkgColor: "#137f7a",
      noteTextColor: "#e8f0f2",
      noteBorderColor: "#3dd6c3",
    },
  })
  // Mermaid sizes each box from the text it measures, so it must measure
  // unscaled, in the real font. mermaid.run() measures inside the slide,
  // which Marp scales to the window: a window smaller than 1280x720 got boxes
  // too small and labels cut off. mermaid.render() draws in a scratch element
  // on <body> instead; the finished SVG then goes into the slide.
  async function draw() {
    const decode = document.createElement("textarea")
    let n = 0
    for (const el of document.querySelectorAll(".mermaid:not([data-processed])")) {
      decode.innerHTML = el.innerHTML
      const src = decode.value.replace(/<br\s*\/?>/gi, "<br/>").trim()
      const { svg, bindFunctions } = await mermaid.render(`mermaid-${n++}`, src)
      el.innerHTML = svg
      bindFunctions?.(el)
      el.setAttribute("data-processed", "true")
    }
  }
  document.fonts.load('18px Manrope').catch(() => {}).then(() => document.fonts.ready).then(draw)
</script>
