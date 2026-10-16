# Lab 5 — The dns-01 Challenge

Every certificate so far proved you control `${host}` by
serving a file over HTTP. dns-01 proves the same thing a completely
different way: by writing a DNS TXT record only the domain's owner could
write. It's what you reach for when there's no web server to answer
http-01 at all (an internal service, a wildcard cert, a mail server) — and
it's the one challenge type that needs `dns-server` (PowerDNS) directly,
the same zone [Lab 1's README](README.md) mentioned but Labs 1-4 never
actually touched.

If you did the `dns-as-code` workshop, the DNS half of this will feel
familiar — same PowerDNS, same idea of "the zone is the source of truth" —
just driven by a raw API call here instead of `dnscontrol`.

You'll want a second terminal pane for this one — split one if you don't
already have one open (`Ctrl+b %`).

> **Starting here?** This lab needs Lab 2's certbot certificate: step 3 reads the `-0001` copy certbot makes next to it. Run `dojo prep 5` to set that up; it's safe to run even if you did the earlier labs.

> **Did Lab 4?** Remove its cron job first: `crontab -r`. It runs `certbot renew` every minute on the same `~/certbot` folder, so it can hold certbot's lock ("Another instance of Certbot is already running") and renew the certificate you're about to create.

---

## 1. Start the challenge

`--manual` is what makes certbot stop and show you the challenge instead of
completing it itself — certbot has no built-in way to talk to PowerDNS, so
a real dns-01 setup would use a DNS-provider plugin instead; here, you're
standing in for that plugin. `--preferred-challenges dns-01` is what tells
it to request a dns-01 challenge from `step-ca` instead of the http-01 one
Labs 2-3 used — same ACME order and finalize steps underneath, just a
different way of proving control in the middle.

```text
certbot certonly --manual --preferred-challenges dns-01 -d <host> --server <acme-directory>
```

**Your turn:** before you run it, predict: what will certbot ask you to
do, and what will it wait for?

```sh
me="$(whoami)"
host="${me}.certs.dojo.test"
mkdir -p ~/certbot/{config,work,logs}

REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt \
certbot certonly --manual --preferred-challenges dns-01 \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  -d "${host}" \
  --server https://step-ca:9443/acme/acme/directory \
  --agree-tos --email "${me}@example.com"
```

certbot pauses and prints something like:

```text
Please deploy a DNS TXT record under the name:

_acme-challenge.studentNN.certs.dojo.test.

with the following value:

<a long random-looking string>

Press Enter to Continue
```

**Don't press Enter yet.** Copy that domain name and value — you need them
in the next step.

---

## 2. Deploy the TXT record

This `PATCH` call is PowerDNS's own REST API for editing a zone — the same
API `dns-as-code` drives through `dnscontrol` instead of raw HTTP. It goes
through `dns-api`, a gate in front of PowerDNS, with `$DNS_API_KEY`: your
own key, set by your terminal. The whole class shares `certs.dojo.test`,
but your key only changes names under your own (`studentXX.certs.dojo.test`),
so nobody else can answer a dns-01 challenge for your name, or you for theirs.

`changetype: REPLACE` sets (or overwrites) the `_acme-challenge` TXT
record to exactly the value in `records`, which is what lets `step-ca`
find it when it looks the name up in the next step.

Two things that trip people up the first time: the `_acme-challenge.`
prefix is fixed by the ACME spec (not something you choose), and a TXT
record's `content` field needs the value wrapped in **literal, escaped
double quotes** (`\"...\"` inside the JSON string) — that's DNS's own TXT
syntax, not a PowerDNS quirk.

**Your turn:** in your other pane, replace `PASTE-THE-VALUE-HERE` with the
exact value certbot printed. Before you run it, predict: what will `dig`
return afterwards?

```sh
curl -s -H "X-API-Key: $DNS_API_KEY" -H "Content-Type: application/json" \
  -X PATCH "http://dns-api:8081/api/v1/servers/localhost/zones/certs.dojo.test." \
  -d '{
    "rrsets": [{
      "name": "_acme-challenge.'"${host}"'.",
      "type": "TXT",
      "ttl": 60,
      "changetype": "REPLACE",
      "records": [{"content": "\"PASTE-THE-VALUE-HERE\"", "disabled": false}]
    }]
  }'

dig @dns-server "_acme-challenge.${host}" TXT +short
```

<!-- dojo-reveal: Result of the PATCH and dig -->

- The PATCH returns without an error.
- `dig` prints your challenge value in quotes, so it's live before you go back to the other pane.

<!-- /dojo-reveal -->

---

## 3. Finish the issuance

Back in the first pane, press Enter. `step-ca` looks up that exact TXT
record itself (it's configured to query `dns-server` directly — see the
lab README) — no propagation delay to wait out, unlike a real public DNS
provider.

**Your turn:** press Enter in the first pane. Before you run the `openssl`
check, predict: why is the folder called `${host}-0001`?

```sh
openssl x509 -in ~/certbot/config/live/${host}-0001/fullchain.pem -noout -dates -subject
```

<!-- dojo-reveal: Result of the openssl check -->

- certbot reports success, and `openssl` shows your name as the subject and a short validity window.

<!-- /dojo-reveal -->

(`-0001` because certbot won't reuse the same lineage name as your Lab 2
certificate for the same domain — that's certbot's own bookkeeping, not
anything to fix.) This lab doesn't copy that cert into
`/srv/webroot/${me}/certs/` either, so `demo-app` is still serving whatever
Lab 2/4 last installed there — `openssl` above is your real check for this
one (the homepage's **Site Inspector** would still show the certificate
Lab 2/4 installed).

---

## Checkpoint

You can explain, to someone who's only seen http-01, why dns-01 doesn't
need a reachable web server at all — and you've now driven the same
PowerDNS API `dns-as-code` wraps in `dnscontrol`, by hand.

You've completed every lab in this workshop.

---

## Capstone (bonus)

Only when your class has achievements on (you see a score on your landing page). A capstone is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start capstone
cd ~/lab/cert-heist
```

That makes your own repo `$USER/cert-heist`, clones it to `~/lab/cert-heist` with starter files, and shows your brief. The brief is
saved as `~/capstone.md` with your own names filled in; read it again any time with `glow ~/capstone.md`. When you think it's
done, push your files and run:

```sh
dojo check capstone
```

Keep keys out of the repo: the check looks through its whole history for a private key.

A wrong answer costs nothing. `dojo check hint capstone` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset capstone` deletes `~/lab/cert-heist` (including any uncommitted work), builds a fresh
copy and clones it, as often as you like. Use it if the repo is in a mess, or if you fixed it a way the check can't recognise.

## The Wildcard Heist

One wildcard certificate, two sites. Issue `*.$USER.certs.dojo.test` with dns-01 and serve both `www` and `api` under your name with it, with renewal that covers both. Then make HTTPS the only way in: plain HTTP redirects to HTTPS for good, and HTTPS tells browsers never to try plain HTTP again (HSTS). `api` also sends two headers from the slides' bonus wall, to harden it.

**End result (what the check looks for)**

- Work in your own repo `$USER/cert-heist`.
- `www` and `api` under `$USER.certs.dojo.test` both serve the same wildcard certificate (`*.$USER.certs.dojo.test`).
- Plain HTTP on both redirects to HTTPS.
- HTTPS on both sends HSTS with a max-age of at least one day (86400).
- `api` sends `X-Content-Type-Options: nosniff` and a `Content-Security-Policy` with a `default-src`.
- `www.conf` and `api.conf` on `main` listen on 443 ssl and set a real `ssl_certificate` (not the `TODO`).
- `renew.cron` on `main` has a real (uncommented) schedule line.
- No private key appears anywhere in the repo's history.


