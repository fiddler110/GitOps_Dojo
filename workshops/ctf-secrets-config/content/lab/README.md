# CTF-3: Secrets and Misconfiguration

Welcome! You're working in your own student account, with your own private copy of both targets in this
session -- nothing you do touches a classmate's, and nothing they do touches yours.

**Glasswing Systems** wants two more systems assessed: an internal ops dashboard, and a deploy-trigger
service meant to be reachable only by their own CI. You aren't told what's wrong with either one, or
whether the problem is even in the running code -- that's the job. (Full scenario and the rules of
engagement are in the slides -- see the Presentation if you haven't watched it yet.)

## Rules of engagement

- **Scope is your own slot.** The firewall only lets your attack box reach your own target.
- **This box is the whole scope.** There's nothing outside it to find.
- **In the real world, this needs written authorization.** These techniques are only legal against systems
  you own or are explicitly authorized to test.

## How the Attack Range works

One target is **live** in your slot at a time, from the **Attack Range** card on the landing page:

- **Start** boots the target; **Stop** tears it down; **Reset** returns it to its untouched state (solved
  flags stay solved either way).
- The card shows your slot's **IP only** -- never the ports. `nmap` it first, every time. Some published
  ports are decoys, there on purpose, the way a real box would have noise too.
- Only one target is live at a time -- starting another stops the current one.

Lab 2 is different: it has no Attack Range target of its own. Instead, you already have your own
`internal-tools` repository in Forgejo -- the lab is entirely about that repo's history.

## What you'll do

| Lab | Target | Topic | Time |
| --- | ------ | ----- | ---- |
| [lab1.md](lab1.md) | Internal ops dashboard | A debug log that says a little too much | ~35 min |
| [lab2.md](lab2.md) | Deploy trigger | A secret git remembers even after it's "removed" | ~45 min |

**These labs don't build on each other** -- do them in any order, and start each one fresh whenever you're
ready. Budget roughly 115 minutes across both, plus the `nmap`/Linux primer at the start of the session.

Open any lab file with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md
```

The same files are in the browser too: the Labs tab, or the Slides hub's "Labs" page.

## Submitting a flag

```sh
dojo-flag submit <target-id> '<flag>'
```

`<target-id>` is the short name on the Attack Range card (`leaky-config`, `git-secrets`). A wrong flag
just tells you to keep looking -- it never costs you anything.

## Stuck?

Every lab has two rounds of hints built into its own text, closer to an answer each time -- read those
before anything else. The **Lab Info** card is a mechanics reference for every tool in your terminal
(`nmap`, `curl`, `git`, and more), not a solution for this session's targets.

If you've genuinely tried and you're still stuck, each lab's last section points at that target's
**exploit guide** under `exploit-guide/` -- the full walkthrough, written up plainly. It'll always be there;
using it after a real attempt is normal, using it first just means you skip the part that teaches you
something.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane (`Ctrl+b %` in tmux) while you work.
