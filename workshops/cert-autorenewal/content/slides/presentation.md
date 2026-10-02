---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
  .required { color: var(--amber); font-weight: 700; }
  .https-only { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-top: 14px; }
  .https-only > div, .wall > div { background: var(--surface-raised); border: 1px solid var(--line); border-top: 4px solid var(--teal); border-radius: 6px; padding: 12px 20px; }
  .https-only h3 { margin: 0 0 6px; font-size: 30px; }
  .https-only p, .https-only li { font-size: 22px; }
  .wall { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 10px; }
  .wall b { display: block; font-size: 21px; color: var(--cyan); }
  .wall code { font-size: 15px; }
  .wall p { margin: 4px 0 0; font-size: 18px; color: var(--muted); }
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

> A certificate is a promise with an expiry date. Nothing renews it except whoever remembers to.

- Expired certificates break HTTPS hard: browsers and API clients refuse the connection
- "Who owns renewing this cert?" is a question a lot of outages start with
- The usual fix is a calendar reminder, a ticket, or a central tool like Venafi; all the same idea: **something has to notice the expiry and act, before a human has to**

The whole workshop in one sentence: replace "someone remembers" with "something runs."

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
- <label for="cert-outages" class="pop-trigger">Months later, it expires</label> — often on a weekend, often on the one service
  nobody's looked at recently
- The person who issued it has moved teams, or forgotten how
- Renewal becomes an emergency instead of a non-event

</div>

> The manual process isn't wrong on issuance day. It's wrong every day after
> that, silently, until it isn't.

<div class="pop">
<input type="checkbox" id="cert-outages" class="pop-toggle">
<div class="pop-overlay">
<label for="cert-outages" class="pop-close">close &#10005;</label>
<h3>Expired certificates, real outages</h3>
<p class="pop-sub">Every one of these had a known expiry date. Nothing acted on it in time.</p>
<div class="leak-grid cols-4">
<div class="leak"><i>2013</i><b>Microsoft Azure</b>Storage's HTTPS certificates expired.<em>Worldwide storage outage, Xbox services hit, SLA credits paid</em></div>
<div class="leak"><i>2017</i><b>Equifax</b>An expired certificate had turned off traffic inspection.<em>The breach went unseen for 76 days</em></div>
<div class="leak"><i>2018</i><b>Oculus</b>The Rift's code-signing certificate expired.<em>Every Rift headset stopped working until a manual patch</em></div>
<div class="leak"><i>2018</i><b>Ericsson (O2, SoftBank)</b>An expired certificate in core network software.<em>Mobile data down for millions, in about 11 countries</em></div>
<div class="leak"><i>2020</i><b>Microsoft Teams</b>An authentication certificate expired.<em>About 3 hours down, for 20M daily users</em></div>
<div class="leak"><i>2021</i><b>Epic Games</b>A wildcard certificate used by hundreds of internal services expired.<em>Fortnite, Rocket League and store logins down</em></div>
<div class="leak"><i>2021</i><b>Let's Encrypt's old root</b>DST Root CA X3 expired, on schedule.<em>Older devices that didn't trust the new root broke</em></div>
<div class="leak"><i>2023</i><b>Starlink</b>An expired ground-station certificate.<em>Global outage lasting hours</em></div>
</div>
<p class="pop-src">Sources: <a href="https://azure.microsoft.com/en-in/blog/windows-azure-service-disruption-from-expired-certificate/" target="_blank" rel="noopener">Microsoft</a>, <a href="https://oversight.house.gov/wp-content/uploads/2018/12/Equifax-Report.pdf" target="_blank" rel="noopener">US House Oversight</a>, <a href="https://techcrunch.com/2018/03/07/all-of-oculuss-rift-headsets-have-stopped-working-due-to-an-expired-certificate/" target="_blank" rel="noopener">TechCrunch</a>, <a href="https://www.theregister.com/2018/12/06/ericsson_o2_telefonica_uk_outage/" target="_blank" rel="noopener">The Register</a>, <a href="https://www.geekwire.com/2020/microsofts-slack-competitor-teams-due-expired-authentication-certificate/" target="_blank" rel="noopener">GeekWire</a>, <a href="https://www.epicgames.com/site/en-US/expiration-date-4-6-2021" target="_blank" rel="noopener">Epic Games</a>, <a href="https://letsencrypt.org/docs/dst-root-ca-x3-expiration-september-2021/" target="_blank" rel="noopener">Let's Encrypt</a>, <a href="https://www.datacenterdynamics.com/en/news/spacex-starlink-outage-caused-by-expired-ground-station-certificates/" target="_blank" rel="noopener">DCD</a>.</p>
</div>
</div>

<!--
Click "Months later, it expires" for the wall of real expired-certificate
outages; "close" at the top right hides it.
-->

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
real-world issuance looks like. dns-01 (Lab 5) is what
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

Lab 2 uses certbot. Lab 3 redoes the *same* issuance with
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

`step-ca`'s ACME provisioner in this lab is configured with a **5-10 minute** certificate lifetime, nowhere close to a real cert's weeks-to-months. That's deliberate:

> A renewal you wait a month to see is one you take on faith. A renewal you watch fire inside a lab session is one you understand.

Everything about *how* renewal works (the client, the scheduler, the reload) is identical whether the cert lives for 8 minutes or 90 days. Only the waiting changes.

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

## dns-01 — the last lab

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

## HTTPS only: redirect, then HSTS

A certificate protects nobody while the site still answers on plain HTTP.

<div class="https-only">
<div>

### Redirect (port 80)

`http://` answers **`301 Moved Permanently`** with `Location: https://` + the same name and path.

- Permanent (301/308), not 302: plain HTTP stops being the real address
- A site renewing with **http-01** keeps `/.well-known/acme-challenge/` on plain HTTP, or its next renewal fails

</div>
<div>

### HSTS (port 443)

**`Strict-Transport-Security: max-age=86400`** on every HTTPS response.

- The browser remembers: no more plain HTTP for this name, not even the first request, so nobody on the network can answer it instead (SSL stripping)
- One-way: start with a short `max-age`; `includeSubDomains` and `preload` only once every name has HTTPS

</div>
</div>

---

## Bonus: the security-header wall

Beyond HSTS: one line of server config each, only worth having over HTTPS.

<div class="wall">
<div><b>Content-Security-Policy</b><code>default-src 'self'</code><p>Where scripts, styles and images may load from: the main defence against cross-site scripting.</p></div>
<div><b>X-Content-Type-Options</b><code>nosniff</code><p>Use the declared content type; never guess that a text file is a script.</p></div>
<div><b>Frame protection</b><code>frame-ancestors 'self'</code><p>Who may put your page in a frame (CSP, or the older X-Frame-Options): stops clickjacking.</p></div>
<div><b>Referrer-Policy</b><code>strict-origin-when-cross-origin</code><p>How much of your URL other sites see when someone follows a link away.</p></div>
<div><b>Permissions-Policy</b><code>camera=(), geolocation=()</code><p>Switch off browser features the page never uses.</p></div>
<div><b>Cookie flags</b><code>Secure; HttpOnly; SameSite=Lax</code><p>HTTPS only, out of reach of scripts, not sent with requests from other sites.</p></div>
</div>

<p class="small">See any site's: <code>curl -sI https://example.com</code> (this dojo's pages send a strict CSP and <code>nosniff</code>)</p>

---

<!-- _class: section-title -->

# Part 6

## Hands-on practice

---

## The five labs

| Lab | Topic | Time |
| --- | ----- | ---- |
| 1 | Trust the CA: bootstrap, inspect the root cert | ~10 min |
| 2 | Issue and install a certificate with certbot | ~20 min |
| 3 | The same task with acme.sh — comparing clients | ~15 min |
| 4 | Automating renewal, and watching it actually happen | ~15 min |
| 5 | The dns-01 challenge, against real DNS | ~15 min |

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
