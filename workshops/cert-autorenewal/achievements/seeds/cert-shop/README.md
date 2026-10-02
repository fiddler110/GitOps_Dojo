# Challenge c1: The Second Site

**Goal:** give `shop.{user}.certs.dojo.test` its own trusted certificate, with certbot (Lab 2) or acme.sh (Lab 3),
without touching your first site, `{user}.certs.dojo.test`. The name already points at the demo site.

Start from a first site that already serves HTTPS (Lab 2 done, or `lab-prep 4`, which sets up all of Lab 2): the check also makes sure it
still serves its own certificate, and without one nginx answers its name with `shop`'s.

## What's here

- `shop.conf`: the port-80 vhost for `shop`. It serves the http-01 challenge from its own folder, so your first
  site's files stay as they are. It has no TLS yet: adding that is part of the challenge.

Put it where the demo site reads it (it reloads by itself when files there change):

```sh
mkdir -p /srv/webroot/{user}/shop-html
cp ~/lab/cert-shop/shop.conf /srv/webroot/{user}/conf.d/shop.conf
```

## Done when

`https://shop.{user}.certs.dojo.test` serves its own valid certificate, and the `shop.conf` you run, with its
`listen 443 ssl` block, is pushed to `main` here. Then `dojo-check c1`.

## Keep keys out of git

Certificates and private keys live in `/srv/webroot/{user}/certs/` and in your ACME client's own folder, never in this
repo. The check scans the repo's **whole history** for a private key: deleting one in a later commit doesn't remove it.
If one gets in, `dojo-challenge reset c1` rebuilds the repo from scratch (in a real team you'd also replace the key).

`dojo-challenge reset c1` only rebuilds this repo. Files you copied into `/srv/webroot/{user}/`, certificates you
issued and cron entries stay as they are.
