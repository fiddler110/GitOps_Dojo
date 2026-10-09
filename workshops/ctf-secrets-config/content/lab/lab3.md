# Lab 3: Infrastructure state (`tfstate-treasure`)

By the end of this lab you'll have reached a secret in the vault that your own login has no access to --
using something that was never meant to be a secret store at all.

---

## The briefing

There's no target to scan for this one either. Your team keeps its infrastructure code in your own
`infra-state` repository in Forgejo, and the vault (OpenBao) holds a secret for you at
`secret/data/tfstate-treasure/<your-username>`. Log in to the vault as yourself and try to read it: your own
identity is allowed to sign in and nothing more. Somewhere there is another way in.

(Forgejo doesn't actually stop a classmate from reading your `infra-state` repo either -- the one check that
really holds here is the flag itself: `dojo-flag submit` only credits a flag to the student it was derived
for, so finding someone else's secret doesn't get you their points. Keep that in mind if you go looking at a
classmate's repo out of curiosity.)

## 1. Check what your own login can do

```sh
# sign in to the vault as yourself (the Vault card, or `bao` in your terminal), then:
bao kv get secret/tfstate-treasure/<your-username>
```

Expect a permission error. That's the starting position, not a dead end: now go and look at what your team
actually keeps in `infra-state`.

## 2. Read the repo like an attacker would

Clone `infra-state` from Forgejo (or browse it there) and list every file, not just the README. Ask of each
one: could a machine have written this? Does it hold values rather than instructions?

> **Hint 1.** Infrastructure tools remember what they built. That memory has to live somewhere, and by default
> it is a plain file next to the code. Look for a file with a name you'd recognise from the `tofu-basics`
> workshop.

> **Hint 2.** That file records every resource's attributes, including the ones that were passed in as
> credentials. Read its `resources` section for anything that looks like an identity: an id and a secret
> that belong together.

## 3. Use what you found

The vault has more than one way to sign in. Your own login is one; a **role-based** method meant for
automation is another, and it takes two values rather than a password. Find the method's login endpoint in
the vault's documentation (or `bao auth list`), sign in with what you found, and note which token comes back
and what it is allowed to read.

```sh
curl -s -X POST "http://openbao:8200/v1/auth/<method>/login" -d '{"role_id":"...","secret_id":"..."}'
```

Then read your secret with *that* token (`X-Vault-Token` header, path under `/v1/secret/data/`).

## 4. Submit

```sh
dojo-flag submit tfstate-treasure '<flag>'
```

## 5. Debrief

Ask the facilitator to open the **Vault Audit** tab, and find your own two events: the role login and the
read. Nobody stopped you, and the vault did its job; the breach is visible only afterwards, in the log. What
would have prevented it? (A remote, access-controlled state backend; a state file that never holds the
credential; a short-lived secret id.)

Notice, too, that the vault wasn't the only place with no access control today: Forgejo let you read a
repo that wasn't yours just as readily. In a real team, repo permissions would be the first line of
defense, before the state file's contents ever mattered.

## Still stuck?

Read [exploit-guide/tfstate-treasure.md](exploit-guide/tfstate-treasure.md) for the full walkthrough -- try
the hints above for real first.
