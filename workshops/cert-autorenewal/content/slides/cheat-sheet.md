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
    font-size: 26px;
    padding: 46px 64px;
  }
  section::after {
    color: var(--muted);
    font-size: 18px;
  }
  h1, h2, h3 { color: var(--text); letter-spacing: 0; }
  h1 { font-size: 50px; }
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
    font-size: 21px;
  }
  pre code { background: transparent; color: inherit; }
  blockquote {
    background: rgba(61, 214, 195, 0.08);
    border-left: 7px solid var(--teal);
    color: var(--text);
    font-size: 28px;
    font-weight: 600;
    padding: 14px 22px;
  }
  table {
    background: var(--surface);
    border: 1px solid var(--line);
    font-size: 21px;
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
  .two-column { columns: 2; column-gap: 48px; }
  .command { color: var(--amber); }
  .small { font-size: 21px; }
  .nav { color: var(--muted); font-size: 20px; margin-top: 40px; }
  footer { color: var(--muted); font-size: 16px; }
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Certificate Autorenewal | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Every command from Labs 1-5, in one place

Keep this open in a split pane or another tab while you work — you don't
need to memorize any of it. `me="$(whoami)"` and
`host="${me}.certs.dojo.test"` are assumed set, same as in the labs.

<p class="nav">Full detail: <code>~/lab/cheat-sheet.md</code> in your terminal.</p>

---

## Trust (Lab 1)

```sh
step certificate inspect /opt/step-ca-root/root_ca.crt --short   # what's in the root cert
step certificate fingerprint /opt/step-ca-root/root_ca.crt        # its SHA-256 fingerprint
step ca bootstrap --ca-url https://step-ca:9000 --fingerprint <fp> # trust it (step CLI only)
step ca health --ca-url https://step-ca:9000                      # confirm you can reach the CA
```

certbot and acme.sh each need telling about this root **separately**:

| Client | How it trusts `step-ca`'s own HTTPS listener |
| ------ | -------------------------------------------- |
| certbot | `REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt` |
| acme.sh | `--ca-bundle /opt/step-ca-root/root_ca.crt` |

---

## Issue — certbot, http-01 (Lab 2)

```sh
mkdir -p ~/certbot/{config,work,logs}
REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt \
certbot certonly \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  --webroot -w "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --agree-tos --non-interactive --email "${me}@example.com"
# cert lands at ~/certbot/config/live/${host}/{fullchain.pem,privkey.pem}
```

---

## Issue — acme.sh, http-01 (Lab 3)

```sh
acme.sh --issue \
  --webroot "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --ca-bundle /opt/step-ca-root/root_ca.crt \
  --cert-home ~/acmesh-lab3 \
  --accountemail "${me}@example.com"
```

## Issue — certbot, dns-01 (Lab 5)

```sh
certbot certonly --manual --preferred-challenges dns-01 \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  -d "${host}" --server https://step-ca:9000/acme/acme/directory \
  --agree-tos --email "${me}@example.com"
# pauses; deploy the printed TXT record (see below), then press Enter
```

---

## Install, verify

```sh
# Install (Labs 2 & 3) — copying into place is the entire "install" step,
# demo-app's watcher does the rest:
cp <issued-fullchain> "/srv/webroot/${me}/certs/fullchain.pem"
cp <issued-privkey>   "/srv/webroot/${me}/certs/privkey.pem"

# Verify
openssl x509 -in <cert> -noout -dates -subject -issuer
demo_ip="$(dig @dns-server "${host}" +short)"
curl --resolve "${host}:80:${demo_ip}"  "http://${host}/"
curl --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/" -v
```

`SSL certificate verify ok` in the verbose output means curl validated the
full chain up to `step-ca`'s root — the same check any real client does.

---

## DNS (Lab 5)

```sh
dig @dns-server "${host}" A +short                       # your seeded A record (already there, Labs 1-4)
dig @dns-server "_acme-challenge.${host}" TXT +short      # your dns-01 TXT record, once you've added one

curl -s -H "X-API-Key: workshop-not-a-secret" -H "Content-Type: application/json" \
  -X PATCH "http://dns-server:8081/api/v1/servers/localhost/zones/certs.dojo.test." \
  -d '{"rrsets":[{"name":"_acme-challenge.'"${host}"'.","type":"TXT","ttl":60,
        "changetype":"REPLACE","records":[{"content":"\"VALUE\"","disabled":false}]}]}'
```

<p class="small">TXT record <code>content</code> needs the value wrapped in
literal, escaped double quotes (<code>\"...\"</code>) — DNS's own TXT
syntax, not a PowerDNS quirk.</p>

---

## Automate (Lab 4)

```sh
crontab -e
# * * * * * REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt /home/USERNAME/renew-and-reload.sh >> /home/USERNAME/renew.log 2>&1
```

- `certbot renew` only renews within its renewal window (30 days before
  expiry by default) — shorter than this lab's whole cert lifetime, so
  every run renews here. In production, only near-expiry certs would.
- `--no-random-sleep-on-renew` turns off certbot's default random delay
  before an unattended renewal runs — real thundering-herd protection at
  Let's Encrypt's scale, but longer than this lab's entire cert lifetime.
- cron runs with almost no environment — set `REQUESTS_CA_BUNDLE` in the
  crontab line itself or inside the script, not just your shell.

---

## Glossary

<div class="two-column small">

- **ACME:** The protocol (RFC 8555) all three clients speak to `step-ca` —
  account, order, challenge, finalize.
- **http-01:** Prove domain control by serving a file at a well-known HTTP
  path.
- **dns-01:** Prove domain control by publishing a specific DNS TXT record.
- **Provisioner:** step-ca's term for a configured way of authenticating
  requests — ours is an ACME provisioner named `acme`.
- **Claims:** Per-provisioner limits/defaults — here, the 5-10 minute cert
  lifetime that makes Lab 4 observable.
- **Webroot:** The directory nginx already serves, where an http-01 client
  drops its challenge file.

</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Getting unstuck

- `openssl x509 -in <cert> -noout -dates` always tells you exactly when a
  certificate is valid from/until — your fastest sanity check.
- Nothing here can break another student's site — your vhost, docroot, and
  certificate all live only in your own subdirectory of the shared volume.
- Client can't reach `step-ca`'s ACME directory? Double-check you're using
  `https://step-ca:9000/...` — it has no plain-HTTP listener.
- Stuck for more than a minute or two? Ask the facilitator.

<p class="nav"><a href="index.md">&larr; Back to hub</a> &middot; <a href="labs.md">&larr; Lab overview</a> &middot; <a href="presentation.md">&larr; Deck</a></p>
