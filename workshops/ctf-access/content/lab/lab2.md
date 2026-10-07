# Lab 2: Password self-service (`weak-auth-portal`)

By the end of this lab you'll have taken over the `ops-admin` account through its own "forgot password"
flow, without ever seeing their password or receiving the reset token "sent" to them.

---

## The briefing

Glasswing's self-service portal lets anyone reset their own password without calling the help desk: enter
your username, get a token, enter the token plus a new password. Convenient -- for whoever can produce a
valid token.

## 1. Start the target and scan it

Open the **Attack Range** card, start `weak-auth-portal`, note your slot's IP, and scan it before you touch
anything:

```sh
nmap -sV -p- <your-slot-ip>
```

Same as last time: more than one port, only one worth your attention.

## 2. Read the reset flow like an attacker, not a user

`POST /reset` takes a username, a token, and a new password. As a normal user you'd get the token by email
or SMS -- there's no such channel here, which is exactly why this flow is worth examining: **something on
the server has to compute the token from *something*, and whatever that something is, you may already
have all of it.**

Think about what a reset token is *for*: it has to prove the requester is really that user, using
information an attacker couldn't also produce. Ask yourself what the token in this system actually depends
on, and whether every one of those inputs is already public.

> **Hint 1.** Time-based tokens are common because "give me a few minutes" feels safer than "forever" --
> but a token that's *purely* a function of the username and the current time is reproducible by anyone
> who knows both, without ever requesting it. What's the actual window size, and could you compute today's
> value yourself?

> **Hint 2.** If you can derive the token independently -- no network request needed to "get" it -- you
> can reset `ops-admin`'s password directly. You'll need to figure out the exact inputs and the hash/window
> scheme it's built from; read the response from a normal reset attempt closely, it may tell you more than
> it should.

## 3. Submit

Once you've reset `ops-admin`'s password and logged in, the flag is on their landing page.

```sh
dojo-flag submit weak-auth-portal '<flag>'
```

## Still stuck?

Read [exploit-guide/weak-auth-portal.md](exploit-guide/weak-auth-portal.md) for the full walkthrough -- try
the hints above for real first.
