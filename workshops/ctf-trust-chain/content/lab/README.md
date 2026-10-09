# CTF-4: Trusting the Wrong Thing

Welcome! You're working in your own student account, with your own private copy of every target in this
session -- nothing you do touches a classmate's, and nothing they do touches yours.

**Glasswing Systems** has brought you in to assess two systems that both passed their own checks and are
still wrong: an internal service that trusts whatever a DNS lookup tells it, and a cloud resource policy
that's correctly enforced but incorrectly written. You aren't told what's wrong with either of them, or
how to find it -- that's the job. (Full scenario and the rules of engagement are in the slides -- see the
Presentation if you haven't watched it yet.)

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
| [lab1.md](lab1.md) | Internal DNS-backed agent | A real CVE in a pinned-old resolver's transaction IDs -- two flags | ~45 min |
| [lab2.md](lab2.md) | Cloud resource policy | A rule with no bug, just the wrong logic | ~40 min |
| [lab3.md](lab3.md) | CI pipeline | A PR's own workflow file runs on a shared runner | ~40 min |

Like `ctf-access`, **these labs don't build on each other** -- do them in any order, and start each one
fresh from the Attack Range card whenever you're ready. Budget roughly 125 minutes across all three, plus the
`nmap`/Linux primer at the start of the session.

Open any lab file with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md
```

The same files are in the browser too: the Labs tab, or the Slides hub's "Labs" page.

## Submitting a flag

```sh
dojo-flag submit <target-id> '<flag>'
```

`<target-id>` is the short name on the Attack Range card for the target (`dns-resolver-cve`,
`policy-bypass`) -- but `dns-resolver-cve` hands you **two separate flags**, each with its own id to
submit: `dns-resolver-cve-token` for the captured credential, then `dns-resolver-cve` for the replay. A
wrong flag just tells you to keep looking -- it never costs you anything.

## Stuck?

Every lab has two rounds of hints built into its own text, closer to an answer each time -- read those
before anything else. The **Lab Info** card is a mechanics reference for every tool in your terminal
(`nmap`, `curl`, `openssl`, `jq`, and more), not a solution for this session's targets.

If you've genuinely tried and you're still stuck, each lab's last section points at that target's
**exploit guide** under `exploit-guide/` -- the full walkthrough, written up plainly. It'll always be there;
using it after a real attempt is normal, using it first just means you skip the part that teaches you
something.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane (`Ctrl+b %` in tmux) while you work.
