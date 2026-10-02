# Challenge c2: The Short Fuse

**Goal:** certificates from this CA last only 5-10 minutes. Make `{user}.certs.dojo.test` renew on its own and stay
valid for 20 minutes without you touching it.

## What's here

- `renew-and-reload.sh`: Lab 4's renewal script, with your name already in it. Pick the block for the client you
  issued with and delete the other.
- `renew.cron`: your crontab, empty apart from comments. Install it with `crontab ~/lab/cert-fuse/renew.cron`
  (that replaces your whole crontab; `crontab -l` shows what is installed).

## Done when

Push `renew-and-reload.sh` and `renew.cron` to `main` here, then run `dojo-check c2` **once**. From then on the
service watches your site by itself: it clears when 20 minutes have passed with at least two renewals and no moment
without a valid certificate. `dojo-check c2` shows how far the watch has got.

## Keep keys out of git

Certificates and private keys live in `/srv/webroot/{user}/certs/` and in your ACME client's own folder, never in this
repo. The check scans the repo's **whole history** for a private key: deleting one in a later commit doesn't remove it.
If one gets in, `dojo-challenge reset c2` rebuilds the repo from scratch (in a real team you'd also replace the key).

`dojo-challenge reset c2` only rebuilds this repo. Files you copied into `/srv/webroot/{user}/`, certificates you
issued and cron entries stay as they are.
