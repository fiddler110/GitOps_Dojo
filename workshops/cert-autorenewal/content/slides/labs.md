---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; Certificate Autorenewal | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Five short, self-contained labs. Every lab is part of the
workshop. They cover the end-to-end workflow: trust the CA, issue and install a
certificate, then automate its renewal, with a second client and the dns-01
challenge to go deeper. Do them in order.

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

| Lab | Topic | Time |
| --- | ----- | ---- |
| **1** | Trusting the CA: bootstrap, inspect the root cert | ~10 min |
| **2** | Issue and install a certificate with certbot | ~20 min |
| 3 | The same task with acme.sh — comparing ACME clients | ~15 min |
| **4** | Automating renewal, and watching it actually happen | ~15 min |
| 5 | The dns-01 challenge, against real DNS records | ~15 min |

---

<!-- _class: section-title -->

# The core path

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

Trust the CA, put a real certificate on a real HTTPS site, then let cron renew it before it expires: the whole workshop in one pass.

---

## Labs 3 & 5 — going deeper

<div class="cards">
<div>
<h3>Lab 3 — acme.sh</h3>
<p>Issue a second certificate with a different client and compare what each one shows you about the ACME exchange underneath.</p>
</div>
<div>
<h3>Lab 5 — dns-01</h3>
<p>Prove control of your hostname via a DNS TXT record instead of a web server — the challenge type you'd need for a wildcard cert or an unreachable service.</p>
</div>
</div>

Do them in order: Lab 3 after Lab 2, Lab 5 last. Lab 5 only depends on
Lab 1 (trust), so it still works if you joined partway with `lab-prep`.

---

## Getting unstuck

- `openssl x509 -in <cert> -noout -dates` always tells you exactly when a
  certificate is valid from/until — your fastest sanity check at any point.
- Nothing here can break another student's site — your vhost, docroot, and
  certificate all live only in your own subdirectory of the shared volume.
- Client can't reach `step-ca`'s ACME directory? Double-check you're using
  `https://step-ca:9443/...`, not `http://` — step-ca has no plain-HTTP
  listener.
- Stuck more than a minute or two? Ask the facilitator.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav">Next: <a href="cheat-sheet.md">Cheat sheet &rarr;</a> &middot; <a href="lab-index.md">&larr; Back to labs</a></p>
