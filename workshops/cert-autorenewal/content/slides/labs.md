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
    font-size: 28px;
    padding: 54px 68px;
  }
  section::after {
    color: var(--muted);
    font-size: 18px;
  }
  h1, h2, h3 { color: var(--text); letter-spacing: 0; }
  h1 { font-size: 54px; }
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
    font-size: 23px;
  }
  pre code { background: transparent; color: inherit; }
  blockquote {
    background: rgba(61, 214, 195, 0.08);
    border-left: 7px solid var(--teal);
    color: var(--text);
    font-size: 32px;
    font-weight: 600;
    padding: 16px 24px;
  }
  table {
    background: var(--surface);
    border: 1px solid var(--line);
    font-size: 24px;
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
    margin-top: 40px;
  }
  .flow span {
    background: var(--surface);
    border: 2px solid var(--line);
    border-top: 5px solid var(--teal);
    border-radius: 6px;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
    padding: 18px 12px;
    text-align: center;
  }
  .flow b { color: var(--amber); font-size: 34px; }
  .flow small { color: var(--muted); }
  .required { color: var(--amber); font-weight: 700; }
  .cards {
    display: grid;
    gap: 20px;
    grid-template-columns: 1fr 1fr;
    margin-top: 30px;
  }
  .cards > div {
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 6px solid var(--blue);
    border-radius: 6px;
    padding: 18px 22px;
  }
  .cards h3 { margin: 0 0 6px; }
  .cards p { color: var(--muted); font-size: 22px; margin: 0; }
  .nav { color: var(--muted); font-size: 20px; margin-top: 50px; }
  footer { color: var(--muted); font-size: 16px; }
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Certificate Autorenewal | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Five short, self-contained labs. **Labs 1, 2, and 4 are required** and
cover the end-to-end workflow: trust the CA, issue and install a
certificate, then automate its renewal. Labs 3 and 5 are optional and go
deeper on one topic each.

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```sh
whoami
step version
certbot --version
acme.sh --version
openssl version
dig -v
```

Preinstalled in your terminal: `step`, `certbot`, `acme.sh`, `openssl`,
`dig`, `jq` — nothing to install. Your username (`studentNN`) is also your
DNS label — `studentNN.certs.dojo.test` — for the rest of this lab.

> Full detail lives in `~/lab/README.md` once you're in the terminal.

---

## The five labs

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | --------- |
| **1** | Trusting the CA: bootstrap, inspect the root cert | ~10 min | <span class="required">Yes — start here</span> |
| **2** | Issue and install a certificate with certbot | ~20 min | <span class="required">Yes</span> |
| 3 | The same task with acme.sh — comparing ACME clients | ~15 min | Optional |
| **4** | Automating renewal, and watching it actually happen | ~15 min | <span class="required">Yes</span> |
| 5 | Capstone: the dns-01 challenge, against real DNS records | ~15 min | Optional |

---

<!-- _class: section-title -->

# The required path

## Labs 1, 2, 4 — trust, issue, automate

<div class="flow">
<span><b>1</b><br>trust<br><small>step ca bootstrap</small></span>
<span>→</span>
<span><b>2</b><br>issue<br><small>certbot, http-01</small></span>
<span>→</span>
<span><b>2</b><br>install<br><small>copy into your vhost</small></span>
<span>→</span>
<span><b>2</b><br>verify<br><small>real HTTPS, curl</small></span>
<span>→</span>
<span><b>4</b><br>automate<br><small>cron renews it live</small></span>
</div>

Bootstrap trust in the `step` CLI, get a real certificate onto a real
HTTPS site, then wire up cron and watch that certificate renew itself
before it expires — the whole point of the workshop, in one pass.

---

## Labs 3 & 5 — optional, either order, after Lab 2

<div class="cards">
<div>
<h3>Lab 3 — acme.sh</h3>
<p>Issue a second certificate with a different client and compare what each one shows you about the ACME exchange underneath.</p>
</div>
<div>
<h3>Lab 5 — dns-01 capstone</h3>
<p>Prove control of your hostname via a DNS TXT record instead of a web server — the challenge type you'd need for a wildcard cert or an unreachable service.</p>
</div>
</div>

Lab 3 only needs Lab 2 done first. Lab 5 only needs Lab 1 (trust) — it can
be done any time after that, independent of Labs 2-4.

---

## Getting unstuck

- `openssl x509 -in <cert> -noout -dates` always tells you exactly when a
  certificate is valid from/until — your fastest sanity check at any point.
- Nothing here can break another student's site — your vhost, docroot, and
  certificate all live only in your own subdirectory of the shared volume.
- Client can't reach `step-ca`'s ACME directory? Double-check you're using
  `https://step-ca:9000/...`, not `http://` — step-ca has no plain-HTTP
  listener.
- Stuck more than a minute or two? Ask the facilitator.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav">Next: <a href="cheat-sheet.md">Cheat sheet &rarr;</a> &middot; <a href="index.md">&larr; Back to hub</a></p>
