# Lab 0 — Sign in, meet your token, take the tour

**Goal:** find your way around the workspace, sign in to the vault in the browser and in the terminal, and read what your token says about you. Nothing you do here changes anything.

**In this lab you will:**

1. Get to know VS Code, the terminal and how a lab page is laid out.
2. Sign in to the vault's web UI with single sign-on.
3. Find out how your terminal got signed in, with no password.
4. Read your first secret, and get refused one that isn't yours.

---

## 1. Your workspace

Everything happens in your browser, in three places:

- **VS Code**, from the **VS Code** card on your landing page. The **Explorer** on the left shows your `~/lab` folder: every file you make in these labs goes there. **Ctrl+`** opens a **terminal** at the bottom.
- **The vault** (the **Vault** card), and **Forgejo**, the class git server (the **Forgejo** card).
- **This lab page.** Keep it side by side with VS Code if your screen allows.

Each lab mixes three kinds of block, and the sentence before a block tells you which it is:

- **Commands** to run in the terminal. Paste a few lines at a time, and read what comes back before going on. Text after a `#` is a comment.
- **A file** to create or change in VS Code. You'll write your first in Lab 1.
- **Output**: roughly what you should see. Your IDs, names and times differ.

Try one command now. Click in the terminal, paste this, and press **Enter**:

```bash
echo "I am $USER and my lab folder is ~/lab"
```

`$USER` is a **shell variable**: the shell replaces it with your user name before running the line. You'll see `$USER` in many commands, so each of you can paste the same line and still work in your own space.

(The [README](README.md) has more on making and editing files, and what to do if you only have the plain **Terminal** tab.)

## 2. Sign in to the web UI with Forgejo

On your landing page, open the **Vault** card. You land on OpenBao's sign-in page with **OIDC** already chosen.

1. Click **Sign in with OIDC Provider**. A small window opens on Forgejo, the class git server.
2. The first time only, Forgejo asks you to **Authorize Application** for "OpenBao". Click **Authorize**.
3. The window closes by itself and you are in the vault.

You never typed a password for the vault. OpenBao asked Forgejo who you are, and Forgejo already knew, because you are signed in to it. This is **single sign-on (OIDC)**, the same thing that happens when a work app says "Sign in with Microsoft Entra ID" or "Sign in with Google".

Click **Secrets engines** if you aren't there already. You see `secret/`, the class's shared vault, and `cubbyhole/`, a private scratch space every token gets.

## 3. The terminal is already signed in

The vault's command-line tool is `bao`. Ask the vault who you are:

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

Your token is the vault's answer to "who is this, and what may they do?". Every request you make carries it. Read it line by line:

| Field | What it tells you |
| ----- | ----------------- |
| `entity_id` | **You**, as the vault knows you. The browser sign-in and this terminal land on the same entity. |
| `identity_policies` | What you're allowed to do, attached to *you* (the entity), not to this one token. |
| `policies` | Attached to the token itself. `default` lets a token look itself up and not much more. |
| `ttl` | How long this token lives. When it reaches zero the token is dead, leaked or not. |
| `display_name` | How you signed in: `jwt-…` here, `oidc-…` in the browser. |

Where did this token come from? You didn't type a password. The `bao` command reads it from a file in your home folder:

```bash
ls -l ~/.vault-token
```

Don't open or copy that file: whoever has its contents *is* you to the vault, until it expires. When your shell started, a small helper asked a service in this terminal container to vouch for your Linux account, and traded that proof for a token. Nobody else's account can get yours, and it expires by itself. At work the same idea is called **workload identity** or **managed identity**: the platform vouches for who is asking, so there is no password to store.

## 4. Your first secret

A secret lives at a **path**, like a file in a folder. Setup left one for you in the shared vault, in a folder named after you (`$USER` again):

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
