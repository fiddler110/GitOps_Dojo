# Lab 1: Incident triage

Three of your apps are live, and all three are going to be attacked, in an order that is different for each of
you. This is not three exercises in a row. It is one incident with three things on fire, and the skill is
working them in the right order with the evidence in front of you.

---

## 1. The briefing

You own three small services. Each is already running on your own slot, nobody else's:

| App | What it is | Severity |
|---|---|---|
| `customer-portal` | support staff look up customers and log in as one | **high** |
| `policy-bypass` | a cloud provisioning API with a policy that gates protected resource groups | **medium** |
| `leaky-config` | an ops dashboard with a status page, admin pages and logs on disk | **low** |

Each is attacked on its own timer, staggered, so a second and third problem arrive while you are still on the
first. Severity is the impact if it is breached, and it sets how many points the target is worth. It is not how
hard the fix is: every fix here is a small diff.

The facilitator starts the clock. Until then, read.

---

## 2. The loop

Work every target through the same five steps. Say them out loud; the order is the point.

1. **Detect.** Something is wrong. Find it in the evidence, not in the code.
2. **Triage.** Which target, how bad, what is exposed? Decide what to do first when more than one is burning.
3. **Contain.** Stop the bleeding, even if only for now. (Containment is optional here, and you may not need it.)
4. **Fix.** The real fix, in source, through a branch and a pull request.
5. **Verify.** Prove it, with the check and the SIEM. A fix you have not verified is a guess.

Your toolset is deliberately small: `git`, an editor, `python3`, `curl`, the **SIEM** panel on your landing page,
and **`dojo-check`**. There is no scanner and no internet, because real incidents rarely come with a perfect tool.

---

## 3. Your tools

### The SIEM panel

Each target emits a different kind of signal, because finding the signal is the defender's job. Expect a request
log for one, an audit log for another, and file-access and login events for the third. Benign traffic is mixed
in on purpose. A strong indicator is something specific, repeated, and different from the normal traffic around
it; a count that is "a bit high" is not.

### `dojo-check`

```sh
dojo-check                    # all three targets, one line each
dojo-check policy-bypass      # just one
```

It asks the platform to run the attack against your **live** slot, and sends one legitimate request as well. A
target is `contained` only when the attack is blocked **and** normal use still works. If you "fix" it by turning
the app off, you will see `broke-normal-use`. It never shows you the payload or the data, so it tells you whether,
not how. Do not expect it to find the bug for you.

| Verdict | Meaning |
|---|---|
| `exploitable` | the attack still works |
| `contained` | blocked, and normal use still works |
| `broke-normal-use` | the attack is blocked but so is a legitimate request |
| `unreachable` | the check could not reach your slot |

---

## 4. Clone, read, and open a note

```sh
cd ~/lab
for t in customer-portal policy-bypass leaky-config; do
  git clone http://git-server:3000/$USER/$t.git
done
```

Each repo's `README.md` says what the app is and what the platform provides around it. Read it before the code.
A header or a service the platform provides is part of the contract you are fixing against.

---

## 5. Triage, then fix

For each target, in the order your evidence tells you, not the order of this page:

```sh
cd ~/lab/<target>
git checkout -b fix-<target>
# investigate, edit, then write the incident note
git add -A
git commit -m "Fix <target>"
git push -u origin fix-<target>
```

Open a pull request in Forgejo. The gate has three parts:

- `INCIDENT.md` exists at the repo root with three headings, each with something under it:
  `What was hit`, `How I know`, `Impact`. Write it from your triage, in your own words. The gate only checks it
  is there; a reviewer will care that it is true.
- The checker runs the attack against **your branch** and one normal request, and the PR can only merge when
  the attack is blocked and normal use works.
- Its note tells you what it saw, one sentence, never the payload.

Merge. The merge rebuilds the image and redeploys that slot in place, with nothing for you to ask anyone.
Then **verify**: `dojo-check <target>` and the SIEM.

---

## 6. If you are stuck

These nudge. None of them is the only place a fact appears: the README, the app's own routes and the SIEM
already show everything you need. Take them one at a time.

### customer-portal

> **Hint 1.** In the request log, which path is hit far more than normal, and what is odd about the part after
> the `?` on those requests?
>
> **Hint 2.** Find the code for that path. Follow what the visitor sent to where it is finally used. What is it
> joined to, and by what means?

### policy-bypass

> **Hint 1.** In the audit log, look for a write that was allowed but should not have been, usually after one or
> more refusals. Who was the caller, and what did the request claim about itself?
>
> **Hint 2.** `GET /api/policy` shows the rule. Where does the rule get the thing it is checking from, and who
> controls that thing?

### leaky-config

> **Hint 1.** In the access log, an unauthenticated request got a `200` for something that looks like it
> should be private. Then a login succeeded from a client you do not see anywhere else.
>
> **Hint 2.** Two things are wrong, one after the other. Ask where the credential came from, and what let a
> stranger read it. Which of the two can your PR fix?

---

## 7. Debrief

Read the one for a target once it is `contained`.

### customer-portal

The query was built by pasting visitor input into the SQL text, so the database could not tell data from
instruction. The fix is a parameterised query: the statement is fixed and the value travels separately. Note
also what the dump held. A fixed query stops new dumps but not the damage already done, and plaintext passwords
should not have been stored at all.

### policy-bypass

The rule trusted a tag the request carried about itself, so any caller could claim to be the security team. The
fix is to decide on the **caller identity the platform sets**, `X-Caller-Role`, and never on the request body.
That header is only as trustworthy as the proxy that sets it. If a caller can reach the app without going
through the proxy, or the proxy can be told to pass the header through, the header means nothing. The app can
only trust what it knows came from the gateway, so check the gateway token too and never read the role from
anywhere else.

### leaky-config

Two failures chained. A log was readable by anyone, and it held a live credential in plain text. Closing the
route stops the next reader; scrubbing the secret from logs stops it recurring; and the credential that was
already exposed must be treated as burned and rotated, which is an operational step no PR can do alone.

### Overall

- **Order mattered.** You had three things at once. Compare your order with the room's on the SOC summary.
  Severity, evidence and time to breach all point somewhere; a good triage names why.
- **Evidence over intuition.** Each signal was different, and the strong indicator was specific and countable.
- **A verified fix is a different thing from a fix you believe in.** `dojo-check` and the gate are the same
  question the attacker asks.
- **The merge is the deploy.** The repo is the source of truth for what runs, and the incident note is part of
  the change.
