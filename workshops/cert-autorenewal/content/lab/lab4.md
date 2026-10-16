# Lab 4 — Automate Renewal

This is the actual point of the workshop: a certificate that
renews itself before it expires, with no one watching it happen. By the end
of this lab you'll have a cron job doing that for real, and you'll have
watched it fire.

> **Starting here?** This lab renews Lab 2's certificate, so it needs that site serving HTTPS. Run `dojo prep 4` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Build your renewal script

The sample repo has a script that renews and then reloads nginx. You copy
it into your home directory, make it executable, then edit it to be yours.

```sh
me="$(whoami)"
cp ~/lab/sample-repo/renew-and-reload.sh ~/renew-and-reload.sh
chmod +x ~/renew-and-reload.sh
```

Open `~/renew-and-reload.sh` in your editor and change:

- Set `YOUR_STUDENT_ID` to your own account name.
- Keep **one** of the two option blocks (certbot or acme.sh — whichever you
  used in Lab 2/3) and delete the other.
- If you're using certbot, also export `REQUESTS_CA_BUNDLE` at the top of
  the script (it won't inherit your shell's environment when cron runs it —
  see step 3).

certbot's `renew` subcommand only actually renews a certificate that's
inside its renewal window — but that window (30 days before expiry, by
default) is longer than this whole certificate's lifetime, so in this lab
specifically, **every run renews**. In production, with month-long certs,
only the ones genuinely close to expiry would. Worth noticing once, not
something to fix.

Run it once by hand first — never trust an automation script's first run to
cron.

**Your turn:** before you run it, predict: will this run renew the
certificate, given the renewal window described above?

```sh
REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt ~/renew-and-reload.sh
```

<!-- dojo-reveal: Result of the manual run -->

- The script runs without errors and certbot renews the certificate (every run renews in this lab).

<!-- /dojo-reveal -->

> **Tip: `--dry-run`.** In production you'd test renewal without touching
> the real certificate first: `certbot renew --dry-run`. On its own that
> flag switches to Let's Encrypt's staging server, which this lab can't
> reach, so name `step-ca` as well:
> `certbot renew --dry-run --server https://step-ca:9443/acme/acme/directory`
> plus the same `--config-dir`/`--work-dir`/`--logs-dir` as your script.

---

## 2. Confirm it actually installs

The script's last step copies the new certificate into your subdirectory
of the shared volume, so the dates there tell you whether renewal landed.

**Your turn:** run the check, wait a minute, run it again. Predict what
changes between the two runs.

```sh
openssl x509 -in "/srv/webroot/${me}/certs/fullchain.pem" -noout -dates
```

<!-- dojo-reveal: Result of the repeated check -->

- `notBefore` is different the second time. That's a real renewal, not the same file re-copied.

<!-- /dojo-reveal -->

---

## 3. Wire it into cron

cron jobs run with almost no environment — `REQUESTS_CA_BUNDLE` and any
other variable your interactive shell has won't be there unless you set it
inside the script or the crontab line itself. The five leading `*` fields
mean minute, hour, day, month and weekday; all stars is every minute.

```text
* * * * * <command>
```

**Your turn:** run `crontab -e` and add the line below. Before you save,
predict how soon the first run will appear in `~/renew.log`.

```sh
crontab -e
```

```cron
* * * * * REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt /home/USERNAME/renew-and-reload.sh >> /home/USERNAME/renew.log 2>&1
```

(Replace `USERNAME` with your own account name — cron doesn't expand `~` or
`$HOME`.) Every minute is aggressive for a real cert; it's exactly right
for a 5-10 minute one, so you see it happen inside this lab instead of
taking it on faith.

---

## 4. Watch it happen

`watch -n 5` reruns a command every five seconds, so you see the
expiry date change the moment cron renews.

**Your turn:** before you run it, predict: roughly how long until
`notAfter` jumps?

```sh
watch -n 5 openssl x509 -in "/srv/webroot/${me}/certs/fullchain.pem" -noout -enddate
```

Leave that running for a few minutes, then confirm the site is still
serving correctly through the transition:

```sh
demo_ip="$(dig @dns-server "${me}.certs.dojo.test" +short)"
curl --resolve "${me}.certs.dojo.test:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${me}.certs.dojo.test/"
```

Check `~/renew.log` if anything looks off — that's where cron's output
landed.

<!-- dojo-reveal: What the watch and curl show -->

- When `notAfter` jumps forward, that's cron firing your script, your ACME client renewing against `step-ca`, the new cert landing in your subdirectory of the shared volume, and `demo-app`'s watcher reloading nginx to pick it up, all without you touching anything.
- The curl keeps succeeding throughout.

<!-- /dojo-reveal -->

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
run `dojo check c2` once: from then on it keeps watching by itself and clears when 20 minutes have passed with at least two
renewals and no gap.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c2
cd ~/lab/cert-fuse
```

That makes your own repo `$USER/cert-fuse` and clones it to `~/lab/cert-fuse`, with a brief and starter files, and prints the goal, with your own names in it. When you think it's done, push your files and run:

```sh
dojo check c2
```

Keep keys out of the repo: the check looks through its whole history for a private key.

A wrong answer costs nothing. `dojo check hint c2` gives a hint for part of the points, and
`dojo challenge reset c2` throws the repo away and starts you over from a fresh copy.

