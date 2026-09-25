# Lab 0 — Sign in, meet your token, take the tour

**Goal:** sign in to the vault in the browser and in the terminal, and read what your token says about you. Nothing you do here changes anything.

---

## 1. Sign in to the web UI with Forgejo

On your landing page, open the **Vault** card. You land on OpenBao's sign-in page with **OIDC** already chosen.

1. Click **Sign in with OIDC Provider**. A small window opens on Forgejo, the class git server.
2. The first time only, Forgejo asks you to **Authorize Application** for "OpenBao". Click **Authorize**.
3. The window closes by itself and you are in the vault.

You never typed a password for the vault. OpenBao asked Forgejo who you are, and Forgejo already knew, because you are signed in to it. This is **single sign-on (OIDC)**, the same thing that happens when a work app says "Sign in with Microsoft Entra ID" or "Sign in with Google".

Click **Secrets engines** if you aren't there already. You see `secret/`, the class's shared vault, and `cubbyhole/`, a private scratch space every token gets.

## 2. The terminal is already signed in

Open your terminal and ask the vault who you are:

```bash
bao token lookup
```

```text
Key                 Value
---                 -----
display_name        jwt-student01
entity_id           3f6e0c1a-...
expire_time         2026-09-25T20:14:07Z
identity_policies   [student]
policies            [default]
renewable           true
ttl                 7h58m12s
...
```

Read it line by line:

| Field | What it tells you |
| ----- | ----------------- |
| `entity_id` | **You**, as the vault knows you. The browser sign-in and this terminal land on the same entity. |
| `identity_policies` | What you're allowed to do, attached to *you* (the entity), not to this one token. |
| `policies` | Attached to the token itself. `default` lets a token look itself up and not much more. |
| `ttl` | How long this token lives. When it reaches zero the token is dead, leaked or not. |
| `display_name` | How you signed in: `jwt-…` here, `oidc-…` in the browser. |

Where did this token come from? You didn't type a password. Look:

```bash
ls -l ~/.vault-token
```

When your shell started, a small helper asked a service in this terminal container to vouch for your Linux account, and traded that proof for a token. Nobody else's account can get yours, and it expires by itself. At work the same idea is called **workload identity** or **managed identity**: the platform vouches for who is asking, so there is no password to store.

## 3. Your first secret

Setup left a secret for you in the shared vault:

```bash
bao kv get secret/students/$USER/welcome
```

Now find the same secret in the UI: **Secrets engines → secret → students → your name → welcome**. The eye icon shows the value.

Try the same path with a neighbour's name, for example:

```bash
bao kv get secret/students/student02/welcome
```

`permission denied` (a 403). You can see that the folder exists, but not what is in it. Lab 3 shows you the rule that did that.

## Check yourself

1. Your token's TTL runs out in the middle of a job. What happens to the job's next vault call? *(It fails: the token is dead. Long jobs renew their token, or sign in again.)*
2. Why is it better that `student` sits in `identity_policies` rather than on each token? *(Change it once on the entity and every sign-in, browser or terminal, gets the change.)*

**Rules used:** 2 (identity over secrets), 3 (short-lived), 4 (secret zero: your first credential came from the platform).

**Next:** [lab1.md](lab1.md)
