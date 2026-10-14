# The defend loop and `dojo-check`

For the defend session (CTF-5). This is a method and a tool reference, not a walkthrough of any target.

## The loop

Every incident, every target, the same five steps, in this order:

1. **Detect.** Find what is wrong in the evidence (the SIEM panel, the app's own responses), not by reading the
   code first.
2. **Triage.** Which target, how bad, what is exposed, what comes first. When several things are burning,
   severity and evidence decide the order.
3. **Contain.** Stop further damage, even temporarily. Optional here, but it is a real step in a real incident.
4. **Fix.** The real fix, in source, on a branch, through a pull request.
5. **Verify.** Prove it with `dojo-check` and the SIEM. A fix you have not verified is a guess.

## Reading a signal

Each target shows a different kind of signal. Benign traffic is mixed in on purpose. A strong indicator is
specific (it names one path, caller or account), countable (it repeats) and different from the normal traffic
around it. Look for what does not belong, then ask what it tried to do and whether it worked.

## `dojo-check`

```text
$ dojo-check
customer-portal  HIGH    still exploitable
policy-bypass    MEDIUM  contained
leaky-config     LOW     unreachable
```

```sh
dojo-check                  # every target on your slot
dojo-check leaky-config     # one target
```

It asks the platform to run the attack against your **live** slot and send one legitimate request. It reports a
verdict only, never a payload or data, so it tells you whether, not how.

| Verdict | Meaning |
|---|---|
| `exploitable` | the attack still works |
| `contained` | the attack is blocked and normal use still works |
| `broke-normal-use` | the attack is blocked but a legitimate request is too |
| `unreachable` | the checker could not reach the slot |

It checks the **running** app, so merge first (the merge redeploys). The pull-request gate runs the same checks
against your branch before it lets you merge.

## The incident note

The PR gate wants an `INCIDENT.md` at the repo root with three headings, each with something under it:
`What was hit`, `How I know`, `Impact`. Write what you saw, which log line told you, and what an attacker
could have done. It is a note a teammate could act on, not a ritual.
