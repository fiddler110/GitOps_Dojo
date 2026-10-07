# Lab 2: Cloud resource policy (`policy-bypass`)

By the end of this lab you'll have walked straight through a deny rule without breaking anything -- the
policy engine will have done exactly what it was told to do.

---

## The briefing

Glasswing runs a policy-as-code rule in front of one protected resource group, meant to stop anyone
except the security team from provisioning into it. The rule passes its own test suite. There is no bug
in how it's evaluated -- the engine isn't fooled, confused, or bypassed by any trick. The question this
lab asks is simpler and harder: **is the rule itself checking the right thing?**

## 1. Start the target and scan it

Open the **Attack Range** card, start `policy-bypass`, and note your slot's IP. Then:

```sh
nmap -sV -p- <your-slot-ip>
```

As before: more than one port, and only one is the API you care about.

## 2. Read the rule -- it's not hidden

`GET /api/policy` returns the deployed policy definition, in full. This isn't an oversight; read it the
way you'd read any policy document before deciding whether to comply with it. Find the condition that
decides whether a write to the protected resource group gets denied.

Then ask: what, specifically, does that condition check? And **who controls the value it's checking**?

> **Hint 1.** The rule denies the write *unless* a particular field on the request already says the right
> thing. Look closely at where that field lives -- is it something the platform attaches on the request's
> way in, or something the person making the request gets to write themselves?

> **Hint 2.** If the field the rule trusts is inside the request body you send -- a tag you attach to your
> own resource -- then nothing stops you from attaching the value the rule is looking for. `POST
> /api/provision` into the protected resource group with that tag set to whatever the rule treats as
> proof is the entire bypass. No escalation, no second step.

## 3. Submit

A successful provision into the protected resource group returns the flag directly in the response body.

```sh
dojo-flag submit policy-bypass '<flag>'
```

## Still stuck?

Read [exploit-guide/policy-bypass.md](exploit-guide/policy-bypass.md) for the full walkthrough -- try the
hints above for real first.
