# Lab 1: Internal ops dashboard (`leaky-config`)

By the end of this lab you'll have read a service's own debug log out loud, found a credential nobody
meant to leave there, and reused it to unlock an endpoint it was never supposed to open.

---

## The briefing

Brightwave Ops runs a small internal dashboard: a status page, and an "admin" area meant to be reachable
only from inside their office network, through a reverse proxy that used to add a login check. The proxy's
gone now. The dashboard is not.

## 1. Start the target and scan it

Open the **Attack Range** card, start `leaky-config`, and note your slot's IP. Then:

```sh
nmap -sV -p- <your-slot-ip>
```

You'll see more than one open port. Only one of them is the dashboard; the other is a decoy there purely
to see what scanning tells you -- that's the point of scanning before guessing.

## 2. Look at what the dashboard is willing to hand you

Open the real port in a browser or with `curl`. The front page doesn't ask you to log in to anything.
Poke around the paths it links to, and the paths it doesn't -- an "admin" area that lists files is worth
trying even without a link to it.

Once you find a directory of files, you'll see two: a config backup and a log. Read both.

> **Hint 1.** One of those two files is a believable red herring -- it looks exactly like a leaked secret
> (a database connection string), but nothing on this target actually checks it against anything. Don't
> stop at the first secret-shaped string you find; ask whether it actually *unlocks* something.

> **Hint 2.** The other file is a log, and logs record what happened -- including, sometimes, a failed
> attempt that a developer "helpfully" logged in full for debugging. Read every line of it, not just the
> `INFO` ones. Somewhere in there is a username and a password, in plain text, that were typed into a
> login attempt that failed. Why would it fail *then* but work *now*?

## 3. Reuse it

That credential was good enough to authenticate somewhere once. There's a second endpoint on this same
dashboard, gated by the exact kind of check you'd expect (HTTP Basic Auth) -- correctly implemented, no
bug in the check itself. The only way in is already having a valid credential.

## 4. Submit

```sh
dojo-flag submit leaky-config '<flag>'
```

## Still stuck?

Read [exploit-guide/leaky-config.md](exploit-guide/leaky-config.md) for the full walkthrough -- try the
hints above for real first.
