# Lab 2 — Issue and Install a Certificate with certbot

**Required.** certbot is the most widely used ACME client in the industry —
this is the most transferable skill in the whole workshop. By the end of
this lab you'll have a real certificate, issued by `step-ca`, actually
serving HTTPS for your own site on the shared `demo-app`.

---

## 1. Set up your own space on demo-app

```sh
me="$(whoami)"
host="${me}.certs.dojo.test"
mkdir -p "/srv/webroot/${me}/conf.d" "/srv/webroot/${me}/html" "/srv/webroot/${me}/certs"
```

`/srv/webroot` is shared with `demo-app`, but sticky-bit permissions (the
same mechanism `/tmp` uses) mean only you can write inside
`/srv/webroot/${me}/` — no other student can touch it, and you can't touch
theirs.

Add something to actually serve:

```sh
echo "<h1>${host}</h1>" > "/srv/webroot/${me}/html/index.html"
```

---

## 2. Write your port-80 vhost

Copy the template and fill in your own hostname:

```sh
sed "s/studentNN/${me}/g" ~/lab/sample-repo/vhost-http.conf.template \
  > "/srv/webroot/${me}/conf.d/${me}.conf"
```

(`~/lab/sample-repo/` is a copy of this workshop's sample repo, seeded into
your home directory — see its `README.md` for what's in it.)

The moment you save that file, `demo-app`'s watcher notices and reloads
nginx — no restart, no facilitator action, nothing else to do. Confirm:

```sh
demo_ip="$(dig @dns-server "${host}" +short)"
curl --resolve "${host}:80:${demo_ip}" "http://${host}/"
```

You should see your `<h1>`. (`--resolve` pins curl's DNS answer for this
one request without needing your own resolver to know about the private
`certs.dojo.test` zone — `step-ca` is configured to query it directly,
your terminal isn't, so this is the same trick a real client uses to test
a vhost before DNS has actually propagated for it.)

---

## 3. Issue the certificate

certbot's **webroot** plugin proves you control `${host}` by writing a
file into the path nginx already serves — no port-binding, no root needed.
`--config-dir`/`--work-dir`/`--logs-dir` point certbot's own state at your
home directory instead of the system-wide `/etc/letsencrypt` (which you
don't have permission to write to, and shouldn't need to):

```sh
mkdir -p ~/certbot/{config,work,logs}

REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt \
certbot certonly \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  --webroot -w "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --agree-tos --non-interactive --email "${me}@example.com"
```

`REQUESTS_CA_BUNDLE` is what tells certbot to trust `step-ca`'s own HTTPS
listener — separate from the `step ca bootstrap` trust you set up in Lab 1
(see that lab's step 4). Watch the output: certbot prints each ACME step —
account registration, order creation, the http-01 challenge, validation,
and finalization — the exact protocol exchange the slides describe.

If it succeeds, inspect what you got:

```sh
openssl x509 -in ~/certbot/config/live/${host}/fullchain.pem -noout -dates -subject
```

Notice how short `notAfter` is relative to `notBefore` — that's the
provisioner's 5-10 minute claim from the slides, not a mistake.

---

## 4. Install it

Copy the issued cert/key into your subdirectory of the shared volume —
this is the only "installation" step there is, since `demo-app` picks up
changes automatically:

```sh
cp ~/certbot/config/live/${host}/fullchain.pem "/srv/webroot/${me}/certs/fullchain.pem"
cp ~/certbot/config/live/${host}/privkey.pem  "/srv/webroot/${me}/certs/privkey.pem"

sed "s/studentNN/${me}/g" ~/lab/sample-repo/vhost-tls.conf.template \
  >> "/srv/webroot/${me}/conf.d/${me}.conf"
```

Appending the TLS block to the same `.conf` file (rather than a separate
one) is what triggers demo-app's watcher again.

---

## 5. Verify

```sh
curl --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/" -v
```

Look for `SSL certificate verify ok` in the verbose output — that means
curl validated the full chain up to `step-ca`'s root, the same validation
any real client does. Compare that against what happens with
`--insecure`/`-k` instead of `--cacert`: it still connects, but it's no
longer *verifying* anything — worth seeing the difference once.

You can also open the **View Demo Site** link on the workshop homepage
(new tab) to confirm the same vhost content — it's a quick sanity check
that nginx picked up your config. It's plain HTTP only, though, so it
never actually touches your certificate; the `curl` above (not the
browser link) is what tells you whether the certificate itself is valid.

---

## Checkpoint

You have a live HTTPS site, an issued certificate you can inspect, and
you've watched the full ACME http-01 exchange happen. You also now know
that certificate expires in minutes, not months — which is exactly what
Lab 4 automates.

Next: [lab3.md](lab3.md) (optional — same task with acme.sh) or skip ahead
to [lab4.md](lab4.md) (required — automate renewal).
