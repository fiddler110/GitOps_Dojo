# Capstone: The Wildcard Heist (a friendly one)

**Goal:** issue one wildcard certificate for `*.{user}.certs.dojo.test` using dns-01, serve it on two sites,
`www.{user}.certs.dojo.test` and `api.{user}.certs.dojo.test`, and set up renewal that works for both. Then make
HTTPS the only way in: plain HTTP must send every visitor to HTTPS, and HTTPS must tell browsers never to use plain
HTTP for these names again. Last, harden the API with two more security headers. Both names already point at the
demo site.

## What each site must do

- **Serve the wildcard certificate over HTTPS.** One certificate, valid for both names.
- **Redirect HTTP to HTTPS, permanently.** `http://www.{user}.certs.dojo.test/` answers a permanent redirect
  (301 or 308) to the same name over `https://`. A temporary one (302, 307) isn't enough: it tells browsers and
  search engines that plain HTTP is still the real address.
- **Send HSTS.** Every HTTPS response carries a `Strict-Transport-Security` header with a `max-age` of at least a day
  (86400 seconds). A redirect still lets the very first request go out in clear text, where someone on the network can
  answer it instead of your site (an SSL-stripping attack). HSTS tells the browser to go straight to HTTPS for this
  name from then on, without asking over HTTP first.

- **`api` only: two more headers** (the slides' bonus wall). `X-Content-Type-Options: nosniff`, so a browser
  never second-guesses the `Content-Type` an API sends; and a `Content-Security-Policy` with a `default-src`
  (`default-src 'none'` suits an API that serves no page assets), so even if something an attacker controls
  ends up in a response, the browser won't load or run anything from it.

The **Site Inspector** on the workshop homepage shows all of it the way a browser sees it: the redirect, the
certificate, HSTS (and the browser remembering it) and every security header, present or missing.

Redirecting all of port 80 is safe here because dns-01 never uses it. A site that renews with http-01 (your first
site, `shop`) must keep `/.well-known/acme-challenge/` answering on plain HTTP, or its next renewal fails.

## What's here

- `www.conf` and `api.conf`: each site's vhost. The HTTPS block is commented out, with its certificate lines left
  as `TODO`, so the file is safe to copy in now; the port-80 block serves the site in plain HTTP until you change it.
- `dns-hook.sh`: the start of a certbot `--manual-auth-hook`, so dns-01 can run without you pasting a TXT value
  (Lab 5 step 2, automated). Its body is yours to write. Using acme.sh instead is fine too.
- `renew.cron`: your crontab, empty apart from comments. Install it with `crontab ~/lab/cert-heist/renew.cron`.

Put the vhosts where the demo site reads them:

```sh
mkdir -p /srv/webroot/{user}/www-html /srv/webroot/{user}/api-html
cp ~/lab/cert-heist/www.conf ~/lab/cert-heist/api.conf /srv/webroot/{user}/conf.d/
```

## Done when

Both sites serve the same valid wildcard certificate, redirect HTTP to HTTPS permanently and send HSTS, `api` sends
`nosniff` and a CSP; and
`www.conf` and `api.conf` (HTTPS block uncommented, certificate lines filled in) and an installed `renew.cron` are
pushed to `main` here. Then `dojo-check capstone`.

## Keep keys out of git

Certificates and private keys live in `/srv/webroot/{user}/certs/` and in your ACME client's own folder, never in this
repo. The check scans the repo's **whole history** for a private key: deleting one in a later commit doesn't remove it.
If one gets in, `dojo-challenge reset capstone` rebuilds the repo from scratch (in a real team you'd also replace the key).

`dojo-challenge reset capstone` only rebuilds this repo. Files you copied into `/srv/webroot/{user}/`, certificates you
issued and cron entries stay as they are.
