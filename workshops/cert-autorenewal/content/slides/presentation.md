---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Manrope:wght@400;600;700&display=swap');
  :root {
    --canvas: #111820;
    --surface: #18242e;
    --surface-raised: #21313c;
    --line: #38505d;
    --text: #e8f0f2;
    --muted: #a9bac2;
    --teal: #3dd6c3;
    --teal-deep: #137f7a;
    --blue: #69aee8;
    --amber: #f0b95b;
  }
  section {
    background:
      linear-gradient(135deg, rgba(61, 214, 195, 0.05), transparent 42%),
      var(--canvas);
    color: var(--text);
    font-family: 'Manrope', sans-serif;
    font-size: 30px;
    padding: 54px 68px;
  }
  section::after {
    color: var(--muted);
    font-size: 18px;
  }
  h1, h2, h3 { color: var(--text); letter-spacing: 0; }
  h1 { font-size: 58px; }
  h2 { border-bottom: 4px solid var(--teal); padding-bottom: 8px; }
  h3 { color: var(--blue); }
  strong { color: var(--teal); }
  a { color: var(--teal); }
  li::marker { color: var(--teal); }
  code {
    background: var(--surface-raised);
    color: #b8f4ea;
    font-family: 'IBM Plex Mono', monospace;
  }
  pre {
    background: #0a1117;
    border: 1px solid var(--line);
    border-left: 7px solid var(--teal);
    border-radius: 4px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
    color: var(--text);
    font-size: 25px;
  }
  pre code { background: transparent; color: inherit; }
  blockquote {
    background: rgba(61, 214, 195, 0.08);
    border-left: 7px solid var(--teal);
    color: var(--text);
    font-size: 38px;
    font-weight: 600;
    padding: 16px 24px;
  }
  table {
    background: var(--surface);
    border: 1px solid var(--line);
    font-size: 26px;
  }
  th, td { color: var(--text); }
  th { background: var(--surface-raised); color: var(--teal); }
  td { background: var(--surface); border-color: var(--line); }
  tr:nth-child(even) { background: rgba(105, 174, 232, 0.05); }
  .lead {
    background:
      linear-gradient(125deg, rgba(19, 127, 122, 0.34), transparent 55%),
      #0c131a;
    color: var(--text);
    text-align: left;
  }
  .lead h1, .lead h2 { color: var(--text); }
  .lead strong { color: var(--teal); }
  .lead h1 { border-bottom: 7px solid var(--teal); padding-bottom: 18px; }
  .section-title {
    background:
      linear-gradient(135deg, rgba(61, 214, 195, 0.14), transparent 50%),
      var(--surface);
    color: var(--text);
  }
  .section-title h1, .section-title h2 { color: var(--text); }
  .section-title h1 { border-left: 9px solid var(--teal); padding-left: 28px; }
  .flow {
    align-items: center;
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 50px;
  }
  .flow span {
    background: var(--surface);
    border: 2px solid var(--line);
    border-top: 5px solid var(--teal);
    border-radius: 6px;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
    padding: 20px 14px;
    text-align: center;
  }
  .flow b { color: var(--amber); font-size: 38px; }
  .flow small { color: var(--muted); }
  .required { color: var(--amber); font-weight: 700; }
  .small { font-size: 23px; }
  .two-column { columns: 2; column-gap: 64px; }
  .command { color: var(--amber); }
  footer { color: var(--muted); font-size: 16px; }
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Certificate Autorenewal | Engineering & IT Operations'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Certificate Autorenewal

## The protocol behind automated TLS — issue, install, and renew a real certificate, on a schedule, without touching it again

The open-source pattern a tool like Venafi automates for you at work

**Talk + hands-on lab**

<!--
No ties to any corporate CA service in this lab — step-ca, certbot, and
acme.sh are all open-source, self-hosted, and run entirely inside this
workshop's own containers. The point isn't "here's Venafi" — it's "here's
what issuance/renewal automation actually does under the hood," so the
Venafi case at work reads as an instance of a pattern, not a black box.
-->

---

## Today

1. Why certificate renewal deserves the same automation as everything else
2. What ACME actually does — the protocol, not a specific tool
3. What's running in this lab
4. Issuing your first certificate — two clients, one protocol
5. Automating renewal — the actual point of this workshop
6. Hands-on practice

> Same shape as any automation story: a manual, easy-to-forget task becomes
> a scheduled job that just runs.

---

<!-- _class: section-title -->

# Part 1

## Why automate renewal

---

## The core problem

> A certificate is a promise with an expiry date. Nothing enforces that the
> promise gets renewed before it lapses — except whoever remembers to do it.

- Certificates expire. Expired certificates break HTTPS, hard, with no
  graceful fallback — browsers and API clients alike refuse the connection
- "Who owns renewing this cert?" is a question a lot of outages start with
- The fix teams reach for is usually a calendar reminder, a ticket, or a
  tool like Venafi doing this centrally — all three are the same idea:
  **something has to notice the expiry and act, before a human has to**

This is the whole workshop in one sentence: replace "someone remembers" with
"something runs."

<!--
Worth pausing here — this is the motivating problem everything else in the
deck answers. Everyone in the room has probably seen an expired-cert outage
at some point; let that land before moving to the mechanism.
-->

---

## How this usually goes wrong

<div class="two-column">

- A cert is issued once, by hand, during a project's setup
- It works. Nobody touches it again
- Months later, it expires — often on a weekend, often on the one service
  nobody's looked at recently
- The person who issued it has moved teams, or forgotten how
- Renewal becomes an emergency instead of a non-event

</div>

> The manual process isn't wrong on issuance day. It's wrong every day after
> that, silently, until it isn't.

---

## What changes with automation

- A client (certbot, acme.sh, or anything else that speaks ACME) can
  request, prove control of, and install a certificate **without a human
  clicking anything**
- A scheduler (cron, in this lab — a systemd timer or a controller's
  reconcile loop in production) re-runs that request before expiry
- The "prove control" step is the actual security guarantee: **anyone**
  can ask a CA for a cert for `example.com` — only whoever controls
  `example.com` can complete the challenge
- Once this loop is running, renewal isn't a task anyone does — it's a
  property the system has

<!--
This is the pivot into Part 2: the "prove control" step above is exactly
what ACME's challenge/response exchange formalizes. Everything in Part 2
is mechanism for the claim just made here.
-->

---

<!-- _class: section-title -->

# Part 2

## What ACME does

---

## ACME, in one sentence

> A protocol (RFC 8555) a client uses to prove it controls a domain, then
> request, and later renew, an X.509 certificate for it — automatically,
> with no human in the loop once it's set up.

**A**utomatic **C**ertificate **M**anagement **E**nvironment. Let's Encrypt
made it famous; it's an open standard any CA can implement — including the
one running in this lab (`step-ca`), entirely disconnected from any public
CA or corporate service.

---

## The exchange, every time

<div class="flow">
<span><b>1</b><br>account<br><small>register/lookup</small></span>
<span>→</span>
<span><b>2</b><br>order<br><small>"I want a cert for X"</small></span>
<span>→</span>
<span><b>3</b><br>challenge<br><small>prove you control X</small></span>
<span>→</span>
<span><b>4</b><br>finalize<br><small>CSR → issued cert</small></span>
</div>

Every ACME client — certbot, acme.sh, the `step` CLI, anything else — does
exactly these four things. The tools differ in how much of this they show
you; the protocol underneath never changes. You'll watch this exact
exchange happen twice in Lab 2 and Lab 3, once per client.

---

## Two ways to prove control

| Challenge | Proves control by... | Needs |
| --------- | --------------------- | ----- |
| **http-01** | Serving a specific file at a well-known HTTP path on the domain | A reachable web server on port 80 |
| **dns-01** | Publishing a specific TXT record under the domain | Write access to the domain's DNS zone |

http-01 is what Labs 1-4 use — simplest to reason about, and what most
real-world issuance looks like. dns-01 (Lab 5, optional capstone) is what
you reach for when there's **no web server to answer at all** — an
internal service, a mail server, or a wildcard certificate, none of which
http-01 can validate.

---

<!-- _class: section-title -->

# Part 3

## What's running in this lab

---

## The moving pieces

| Service | Role |
| ------- | ---- |
| `step-ca` | The shared ACME certificate authority (Smallstep, open source). Issues **short-lived certs — 5-10 minutes** on purpose, so renewal is something you watch happen today, not a fact you're told about |
| `demo-app` | A shared nginx container. Your own vhost, docroot, and certificate live in your own subdirectory — structurally isolated from every other student, even though the container is shared |
| `dns-server` | A bundled PowerDNS instance, pre-seeded with a DNS name for every student. Labs 1-4 never touch it directly; Lab 5's dns-01 capstone does |

Nothing here is Venafi, or talks to Venafi. It's the same shape — a CA, a
client, a scheduler — with every piece open source and self-contained in
this lab's own containers.

---

## The loop every lab follows

<div class="flow">
<span><b>1</b><br>trust<br><small>the CA's root</small></span>
<span>→</span>
<span><b>2</b><br>request<br><small>prove control</small></span>
<span>→</span>
<span><b>3</b><br>install<br><small>into your vhost</small></span>
<span>→</span>
<span><b>4</b><br>verify<br><small>real HTTPS</small></span>
<span>→</span>
<span><b>5</b><br>automate<br><small>before it expires again</small></span>
</div>

Step 1 happens once (Lab 1). Steps 2-4 happen by hand first (Labs 2-3), so
you see exactly what's being automated before you automate it. Step 5
(Lab 4) is the point of the whole workshop.

---

<!-- _class: section-title -->

# Part 4

## Issuing your first certificate

---

## Two clients, same protocol

| | certbot | acme.sh |
| - | ------- | ------- |
| What it is | Full Python application, plugin-based | A single POSIX shell script |
| Industry position | The most widely deployed ACME client | Popular where a shell-only footprint matters |
| What you see | A summarized log of each ACME step | More of the raw HTTP exchange, less summarized |
| State | `~/certbot/config/` (this lab keeps it out of the system-wide default) | `~/.acme.sh` or wherever `--cert-home` points — plain per-user files |

Lab 2 uses certbot. Lab 3 (optional) redoes the *same* issuance with
acme.sh, so you can compare the two side by side — same CA, same result,
different level of transparency into how it got there.

---

## Trust has to be established twice

- `step ca bootstrap` (Lab 1) teaches the **`step` CLI** to trust this
  lab's CA — it does not teach certbot or acme.sh anything
- certbot and acme.sh each speak HTTPS to `step-ca` independently, and each
  needs **its own** way to trust that connection:

| Client | How it trusts `step-ca`'s HTTPS listener |
| ------ | ------------------------------------------ |
| certbot | `REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt` (env var) |
| acme.sh | `--ca-bundle /opt/step-ca-root/root_ca.crt` (flag) |

One root certificate, three tools, three separate ways of being told about
it — a small, hands-on version of exactly the rollout problem an internal
CA has to solve at much larger scale.

---

<!-- _class: section-title -->

# Part 5

## Automating renewal

---

## Why this lab's certs expire in minutes

`step-ca`'s ACME provisioner in this lab is configured with a
**5-10 minute** certificate lifetime — nowhere close to a real cert's
weeks-to-months. That's deliberate:

> A renewal you have to wait a month to see isn't something you watch
> happen — it's something you take on faith. A renewal you can watch fire
> inside a lab session is something you understand.

Everything about *how* renewal works — the client, the scheduler, the
reload — is identical whether the cert lives for 8 minutes or 90 days.
Only the waiting changes.

---

## The automation loop

<div class="flow">
<span><b>cron</b><br><small>fires on schedule</small></span>
<span>→</span>
<span><b>renew</b><br><small>client re-runs ACME</small></span>
<span>→</span>
<span><b>copy</b><br><small>into your vhost dir</small></span>
<span>→</span>
<span><b>reload</b><br><small>demo-app picks it up</small></span>
</div>

Your renewal script does the middle two steps. `demo-app` already watches
your subdirectory for changes — the moment a new cert/key lands, it
reloads nginx itself. You never issue a reload command directly; **writing
the file is the deploy**.

---

## One flag that matters in production too

certbot's `renew` subcommand defaults to a **random delay before an
unattended renewal actually runs** — real protection against every server
on the internet renewing at the top of the hour and hammering the CA at
once.

- At Let's Encrypt's scale, that default is correct and should stay on
- In *this* lab, with a 5-10 minute cert lifetime, that same default could
  stall a renewal past the certificate's entire life — so Lab 4's script
  disables it (`--no-random-sleep-on-renew`) for exactly this session

Same flag, opposite call, once you know why the default exists — worth
knowing before you turn it off anywhere else.

---

## dns-01 — the optional capstone

Every certificate up to this point proves control over HTTP. Lab 5 proves
the same thing a different way: publishing a TXT record under
`_acme-challenge.<your-host>` that only the zone's owner could write.

Reach for dns-01 instead of http-01 when:

- There's no web server to answer at all (an internal service, a mail
  server)
- You need a **wildcard** certificate (`*.example.com`) — http-01 cannot
  prove control of a wildcard; dns-01 is the only option
- The DNS zone is already automated (sound familiar? — same PowerDNS API
  `dns-as-code` wraps in `dnscontrol`, driven here by hand)

---

<!-- _class: section-title -->

# Part 6

## Hands-on practice

---

## The five labs

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | --------- |
| 1 | Trust the CA: bootstrap, inspect the root cert | ~10 min | <span class="required">Yes — start here</span> |
| 2 | Issue and install a certificate with certbot | ~20 min | <span class="required">Yes</span> |
| 3 | The same task with acme.sh — comparing clients | ~15 min | Optional |
| 4 | Automating renewal, and watching it actually happen | ~15 min | <span class="required">Yes</span> |
| 5 | Capstone: the dns-01 challenge, against real DNS | ~15 min | Optional |

**Full steps are in `~/lab/README.md`** inside your terminal — it's the
menu for all five labs plus a command cheat-sheet.

<!-- _footer: "[&larr; Hub](index.md)" -->

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Let's go

## Next: [labs.md](labs.md) for what each lab covers, then your terminal

Keep [cheat-sheet.md](cheat-sheet.md) open in another tab. Ask for help
any time — this is a lab, not a test.
