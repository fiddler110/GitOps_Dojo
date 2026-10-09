---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-3: Secrets and Misconfiguration'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# CTF-3: Secrets and Misconfiguration

## Leaked credentials and how far they reach

**Talk + hands-on lab**

<!--
Speaker notes: this deck is the briefing, not the walkthrough. It sets the
scenario, the rules and the tools -- it never names a specific bug or a
payload. That's deliberate: the labs guide toward the technique, and a
separate exploit guide exists for anyone who's genuinely stuck after trying.
Don't improvise extra hints from the stage; if someone's stuck, point them
at the lab's own hints first.
-->

---

## Today

1. The engagement: who you are, what you're looking at
2. Rules of engagement (read this slide even if you skip everything else)
3. Your attack box and how the range works
4. Scanning before guessing
5. Flags, scoring, and what to do when you're stuck
6. Hands-on lab

---

## The engagement

**Glasswing Systems** wants two more systems assessed: an internal ops dashboard used by the platform
team, and a deploy-trigger service that's meant to be reachable only by their own CI. Neither one has an
obvious front door that's broken -- the problem, if there is one, is what got left lying around.

You are not told which one is broken, or how. That's the job.

Each of you gets your **own private copy** of both systems -- nothing you do touches anyone else's, and
nothing anyone else does touches yours.

---

## Rules of engagement

Same rules as any real engagement, scaled down to this room:

- **Scope is your own slot, full stop.** The firewall only lets your attack box reach your own target
  (and, for Lab 2, your own repo) -- scanning for anyone else's is pointless and against the rules even
  where it isn't blocked.
- **The box in front of you is the whole scope.** Don't look for a way out of it -- there isn't one, and
  that's intentional (the range has no route to the internet or anything else in this lab).
- **In the real world, this requires written authorization.** Everything you learn today is only legal to
  use against systems you own or are explicitly authorized to test.

---

## Your attack box

Your terminal already has the tools this session needs: `nmap`, `curl`, `git`, `jq`, and more. The **Lab
Info** card is a reference for every one of them -- mechanics, not answers -- and it's worth a look before
you start.

<p class="nav">Lab 2 uses git and your own Forgejo account -- the only lab in this series so far where the
foothold lives in a repo, not on the network.</p>

---

## The Attack Range card

One target is **live** in your slot at a time, picked from the card on the landing page:

- **Start** boots the target you picked; **Stop** tears it down; **Reset** returns it to its untouched
  state (your progress on *solved* flags is kept either way).
- The card shows your slot's **IP only** -- never the ports. Finding those is your first step, every time.
- Starting a different target stops the current one. Only one is ever live, so plan your time.

---

## Scan before you guess

Every target publishes more than one port. Some are real; some are decoys that exist purely so scanning
tells you something, the way a real box would. **Don't skip this step** -- it's not filler, it's the first
real skill this session teaches.

```sh
nmap -sV -p- <your-slot-ip>
```

Read what comes back before you touch anything else.

---

## Flags and scoring

Each solved target hands you a flag, `flag{...}`, unique to you -- a classmate's flag will never work for
you and vice versa.

```sh
dojo-flag submit <target-id> '<flag>'
```

Solving earns points on the room's leaderboard (the achievements module you may already know from other
sessions). A wrong flag just tells you to keep looking -- it never costs you anything.

---

## Two systems, today

| System | What it is |
|---|---|
| **Internal ops dashboard** | Logs, status, and a backup folder nobody meant to publish |
| **Deploy trigger** | A service that only accepts requests carrying its own deploy token |

No further hints here -- what's wrong with each one, if anything in the code at all, is for you to find.

---

## If you get stuck

1. **Re-read the lab.** Each one has two rounds of hints built in before it tells you anything close to an
   answer.
2. **Check Lab Info** for the tool you're trying to use.
3. **Ask.** A facilitator would rather talk you through *where to look* than watch you stall.
4. Only once you've genuinely tried: each lab's last line points at an **exploit guide** with the full
   walkthrough. Using it isn't a failure, but using it *first* skips the part that actually teaches you
   something.

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Your turn

## Open the Labs tab, or `~/lab/README.md` in the terminal

<p class="nav">Next: <a href="lab-index.md">Labs &rarr;</a></p>
