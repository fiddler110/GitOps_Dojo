# Lab 4 — Automate Renewal

This is the actual point of the workshop: a certificate that
renews itself before it expires, with no one watching it happen. By the end
of this lab you'll have a cron job doing that for real, and you'll have
watched it fire.

> **Starting here?** This lab renews Lab 2's certificate, so it needs that site serving HTTPS. Run `lab-prep 4` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Build your renewal script

```sh
me="$(whoami)"
cp ~/lab/sample-repo/renew-and-reload.sh ~/renew-and-reload.sh
chmod +x ~/renew-and-reload.sh
```

Edit `~/renew-and-reload.sh`:

- Set `YOUR_STUDENT_ID` to your own account name.
- Keep **one** of the two option blocks (certbot or acme.sh — whichever you
  used in Lab 2/3) and delete the other.
- If you're using certbot, also export `REQUESTS_CA_BUNDLE` at the top of
  the script (it won't inherit your shell's environment when cron runs it —
  see step 3).

Run it once by hand first — never trust an automation script's first run to
cron:

```sh
REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt ~/renew-and-reload.sh
```

certbot's `renew` subcommand only actually renews a certificate that's
inside its renewal window — but that window (30 days before expiry, by
default) is longer than this whole certificate's lifetime, so in this lab
specifically, **every run renews**. In production, with month-long certs,
only the ones genuinely close to expiry would. Worth noticing once, not
something to fix.

> **Tip: `--dry-run`.** In production you'd test renewal without touching
> the real certificate first: `certbot renew --dry-run`. On its own that
> flag switches to Let's Encrypt's staging server, which this lab can't
> reach, so name `step-ca` as well:
> `certbot renew --dry-run --server https://step-ca:9443/acme/acme/directory`
> plus the same `--config-dir`/`--work-dir`/`--logs-dir` as your script.

---

## 2. Confirm it actually installs

```sh
openssl x509 -in "/srv/webroot/${me}/certs/fullchain.pem" -noout -dates
```

Run it again a minute later — `notBefore` should be different. That's a
real renewal, not the same file re-copied.

---

## 3. Wire it into cron

cron jobs run with almost no environment — `REQUESTS_CA_BUNDLE` and any
other variable your interactive shell has won't be there unless you set it
inside the script or the crontab line itself:

```sh
crontab -e
```

Add:

```cron
* * * * * REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt /home/USERNAME/renew-and-reload.sh >> /home/USERNAME/renew.log 2>&1
```

(Replace `USERNAME` with your own account name — cron doesn't expand `~` or
`$HOME`.) Every minute is aggressive for a real cert; it's exactly right
for a 5-10 minute one, so you see it happen inside this lab instead of
taking it on faith.

---

## 4. Watch it happen

```sh
watch -n 5 openssl x509 -in "/srv/webroot/${me}/certs/fullchain.pem" -noout -enddate
```

Leave that running for a few minutes. When `notAfter` jumps forward, that's
cron firing your script, your ACME client renewing against `step-ca`, the
new cert landing in your subdirectory of the shared volume, and
`demo-app`'s watcher reloading nginx to pick it up — all without you
touching anything. Confirm the site is still serving correctly through
that transition:

```sh
demo_ip="$(dig @dns-server "${me}.certs.dojo.test" +short)"
curl --resolve "${me}.certs.dojo.test:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${me}.certs.dojo.test/"
```

Check `~/renew.log` if anything looks off — that's where cron's output
landed.

Watch it from the homepage's **Site Inspector** too: visit your name
every few minutes and the certificate's serial and **Time left** change
each time cron renews it, while the page keeps loading throughout. Or
rerun the `curl` above (or the `openssl x509 -enddate` check) after
`notAfter` jumps forward.

---

## Checkpoint

Certs are rotating on their own on a schedule you set, and you've watched
at least one full rotation without manually re-running anything. This is
the whole workshop's goal, achieved with three open-source pieces (a CA, a
client, a scheduler) — the same shape as what a managed platform automates
for you, minus the vendor.

Next: [lab5.md](lab5.md), the dns-01 challenge.

---

## Challenge c2: The Short Fuse (bonus)

Keep your site's certificate valid for 20 minutes straight without touching it. Once renewal is in place,
run `dojo-check c2` once: from then on it keeps watching by itself and clears when 20 minutes have passed with at least two
renewals and no gap.

Only when your class has achievements on (you see a score on your landing page).
Click **Start challenge** below, or run `dojo-challenge start c2`: it makes your own repo `$USER/cert-fuse` and
clones it to `~/lab/cert-fuse`, with a brief and starter files. The goal is printed there, with your own names in it.
When you think it's done, push your files and run `dojo-check c2`. A wrong answer costs nothing;
`dojo-check hint c2` gives a hint for part of the points, and `dojo-challenge reset c2` starts the repo over.
Keep keys out of the repo: the check looks through its whole history for a private key.

<!-- dojo-challenge: c2 -->
