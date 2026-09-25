# Vault Fundamentals Lab

Welcome! This is your personal workspace for the **Vault Fundamentals** session. You will learn how to keep secrets out of code, git, pipelines and servers, and how a vault replaces long-lived passwords with **identity** and **short-lived credentials**.

You are working in your own student account. Keep all lab work under this `~/lab` folder.

## OpenBao, Vault: what should I type?

This lab runs **OpenBao** (`bao`), the open-source fork of HashiCorp Vault. The commands, the API and the ideas are the same as Vault's, so everything here carries over. Tools built on the Vault client (sops, Python's `hvac`) work against it unchanged.

```bash
bao version
bao status
```

## What you'll do

| Lab | Topic | Time | Part |
| --- | ----- | ---- | ---- |
| [lab0.md](lab0.md) | Sign in (web UI and terminal), your token, a tour | ~8 min | 1: Foundations |
| [lab1.md](lab1.md) | Leak a secret into git, find it, and block the next one | ~12 min | 1: Foundations |
| [lab2.md](lab2.md) | The shared vault: KV secrets, versions, delete vs destroy, the policy that fences you in | ~15 min | 1: Foundations |
| [lab3.md](lab3.md) | You are the admin: your own namespace, an engine, a least-privilege policy and a token | ~15 min | 2: Administering |

Do them in order. Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane (`Ctrl+b %` in tmux) while you work.

Open any lab file with:

```bash
glow lab0.md   # or: nano lab0.md, batcat lab0.md, etc.
```

## The rules every lab comes back to

1. **Least privilege**: every token can read only what it needs. Policies deny by default.
2. **Identity over secrets**: prove *who you are* instead of holding a password.
3. **Short-lived and revocable**: a leaked credential should expire by itself.
4. **The "secret zero" problem**: the first credential has to come from somewhere; know where yours comes from.
5. **Separation of duties**: whoever deploys the app doesn't need to read its secrets.
6. **Audit everything**: you can answer "who read this, and when?"
7. **Plan for leaks**: rotation and revocation are normal operations, not emergencies.
8. **Never in git, never in logs, never in images**: including history, CI output and container layers.

Each lab ends by naming the rules it used.
