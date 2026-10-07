# CTF-1: Access and Identity

Welcome! You're working in your own student account, with your own private copy of every target in this
session -- nothing you do touches a classmate's, and nothing they do touches yours.

**Glasswing Systems** has brought you in to assess four small, independent systems: a staff login, a
password self-service portal, a support-ticket archive, and an internal API gated by client certificates.
You aren't told what's wrong with any of them, or how to find it -- that's the job. (Full scenario and the
rules of engagement are in the slides -- see the Presentation if you haven't watched it yet.)

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

## What you'll do

| Lab | Target | Topic | Time |
| --- | ------ | ----- | ---- |
| [lab1.md](lab1.md) | Staff login portal | A login form that trusts its input a little too much | ~25 min |
| [lab2.md](lab2.md) | Password self-service | A reset flow that's guessable, not just forgettable | ~25 min |
| [lab3.md](lab3.md) | Support ticket archive | An old ticket anyone can ask for, by number | ~30 min |
| [lab4.md](lab4.md) | Internal ops API | A certificate check that checks less than it looks like | ~30 min |

Unlike some other sessions here, **these labs don't build on each other** -- do them in any order, and start
each one fresh from the Attack Range card whenever you're ready. Budget roughly 130 minutes across all four,
plus the `nmap`/Linux primer at the start of the session.

Open any lab file with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md
```

The same files are in the browser too: the Labs tab, or the Slides hub's "Labs" page.

## Submitting a flag

```sh
dojo-flag submit <target-id> '<flag>'
```

`<target-id>` is the short name on the Attack Range card (`sqli-login`, `weak-auth-portal`, `idor-pcap`,
`cert-trust-bypass`). A wrong flag just tells you to keep looking -- it never costs you anything.

## Stuck?

Every lab has two rounds of hints built into its own text, closer to an answer each time -- read those
before anything else. The **Lab Info** card is a mechanics reference for every tool in your terminal
(`nmap`, `sqlmap`, `ffuf`, `tshark`, `john`, and more), not a solution for this session's targets.

If you've genuinely tried and you're still stuck, each lab's last section points at that target's
**exploit guide** under `exploit-guide/` -- the full walkthrough, written up plainly. It'll always be there;
using it after a real attempt is normal, using it first just means you skip the part that teaches you
something.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane (`Ctrl+b %` in tmux) while you work.
