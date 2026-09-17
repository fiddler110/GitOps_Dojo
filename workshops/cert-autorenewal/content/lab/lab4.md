# Lab 4 — Automate Renewal

**Required.** This is the actual point of the workshop: a certificate that
renews itself before it expires, with no one watching it happen. By the end
of this lab you'll have a cron job doing that for real, and you'll have
watched it fire.

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

The homepage's **View Demo Site** link still loads the page throughout —
it's plain HTTP, so it never touches the certificate and won't show you
the renewal happening. Rerun the `curl` above (or just re-run the
`openssl x509 -enddate` check) after `notAfter` jumps forward to confirm
the new certificate is what's actually being served.

---

## Checkpoint

Certs are rotating on their own on a schedule you set, and you've watched
at least one full rotation without manually re-running anything. This is
the whole workshop's goal, achieved with three open-source pieces (a CA, a
client, a scheduler) — the same shape as what a managed platform automates
for you, minus the vendor.

Next: [lab5.md](lab5.md) (optional capstone — the dns-01 challenge), or
you're done with the required path.
