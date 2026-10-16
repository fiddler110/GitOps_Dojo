# Lab 2 — Issue and Install a Certificate with certbot

certbot is the most widely used ACME client in the industry —
this is the most transferable skill in the whole workshop. By the end of
this lab you'll have a real certificate, issued by `step-ca`, actually
serving HTTPS for your own site on the shared `demo-app`.

---

## 1. Set up your own space on demo-app

`/srv/webroot` is shared with `demo-app`, but your `${me}/` subdirectory
was already created for you, owned by your own account, before you ever
logged in — so `mkdir -p` below just confirms it's there. Normal file
permissions are what keep other students out of it: no other student can
write inside `/srv/webroot/${me}/`, and you can't write inside theirs.
It has three folders: `conf.d` (nginx config), `html` (the page) and
`certs` (the certificate and key).

**Your turn:** before you run it, predict: will `mkdir -p` complain that
the folders already exist? Then add an `index.html` for the site to serve
(this is a one-line file, so `echo` is the natural way).

```sh
me="$(whoami)"
host="${me}.certs.dojo.test"
mkdir -p "/srv/webroot/${me}/conf.d" "/srv/webroot/${me}/html" "/srv/webroot/${me}/certs"
echo "<h1>${host}</h1>" > "/srv/webroot/${me}/html/index.html"
```

<!-- dojo-reveal: Results of the setup -->

- `mkdir -p` is silent: it never complains about folders that exist.
- `/srv/webroot/${me}/html/index.html` now holds your `<h1>`.

<!-- /dojo-reveal -->

---

## 2. Write your port-80 vhost

A vhost is an nginx config block that says which hostname gets which site.
The workshop ships a template with a `studentNN` placeholder.
(`~/lab/sample-repo/` is a copy of this workshop's sample repo, seeded into
your home directory — see its `README.md` for what's in it.) `sed` swaps
the placeholder for your own name as it copies:

```text
sed "s/studentNN/<you>/g" <template> > <your .conf>
```

The moment that file is saved, `demo-app`'s watcher notices and reloads
nginx — no restart, no facilitator action, nothing else to do.

To test it, `curl --resolve` pins curl's DNS answer for one request
without needing your own resolver to know about the private
`certs.dojo.test` zone — `step-ca` is configured to query it directly,
your terminal isn't, so this is the same trick a real client uses to test
a vhost before DNS has actually propagated for it.

**Your turn:** before you run it, predict: what will curl print?

```sh
sed "s/studentNN/${me}/g" ~/lab/sample-repo/vhost-http.conf.template \
  > "/srv/webroot/${me}/conf.d/${me}.conf"
demo_ip="$(dig @dns-server "${host}" +short)"
curl --resolve "${host}:80:${demo_ip}" "http://${host}/"
```

<!-- dojo-reveal: Result of the curl -->

- You see your `<h1>${host}</h1>`, served by nginx after the automatic reload.

<!-- /dojo-reveal -->

---

## 3. Issue the certificate

certbot's **webroot** plugin proves you control `${host}` by writing a
file into the path nginx already serves — no port-binding, no root needed.
`--config-dir`/`--work-dir`/`--logs-dir` point certbot's own state at your
home directory instead of the system-wide `/etc/letsencrypt` (which you
don't have permission to write to, and shouldn't need to).

`REQUESTS_CA_BUNDLE` is what tells certbot to trust `step-ca`'s own HTTPS
listener — separate from the `step ca bootstrap` trust you set up in Lab 1
(see that lab's step 4).

```text
certbot certonly --webroot -w <webroot> -d <host> --server <acme-directory>
```

**Your turn:** before you run it, predict: which ACME steps will certbot
print? Then, with the result, predict how long the certificate lives.

```sh
mkdir -p ~/certbot/{config,work,logs}

REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt \
certbot certonly \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  --webroot -w "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9443/acme/acme/directory \
  --agree-tos --non-interactive --email "${me}@example.com"
openssl x509 -in ~/certbot/config/live/${host}/fullchain.pem -noout -dates -subject
```

<!-- dojo-reveal: Results of certbot and openssl -->

- certbot prints each ACME step — account registration, order creation, the http-01 challenge, validation, and finalization — the exact protocol exchange the slides describe.
- `notAfter` is only minutes after `notBefore`: that's the provisioner's 5-10 minute claim from the slides, not a mistake.

<!-- /dojo-reveal -->

---

## 4. Install it

Installing means copying the issued cert/key into your subdirectory of the
shared volume — this is the only "installation" step there is, since
`demo-app` picks up changes automatically. Then you append the TLS block
to the same `.conf` file (rather than a separate one), which is what
triggers demo-app's watcher again.

**Your turn:** before you run it, predict: what will make nginx reload?

```sh
cp ~/certbot/config/live/${host}/fullchain.pem "/srv/webroot/${me}/certs/fullchain.pem"
cp ~/certbot/config/live/${host}/privkey.pem  "/srv/webroot/${me}/certs/privkey.pem"

sed "s/studentNN/${me}/g" ~/lab/sample-repo/vhost-tls.conf.template \
  >> "/srv/webroot/${me}/conf.d/${me}.conf"
```

<!-- dojo-reveal: Result of the install -->

- The `.conf` changed, so the watcher reloads nginx with the certificate and TLS block in place.

<!-- /dojo-reveal -->

---

## 5. Verify

`--cacert` hands curl the root to validate against, so it checks the full
chain up to `step-ca`'s root, the same validation any real client does.
`--insecure`/`-k` instead still connects but no longer *verifies*
anything — worth seeing the difference once.

**Your turn:** before you run it, predict: what line in the verbose output
proves the chain validated?

```sh
curl --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/" -v
```

<!-- dojo-reveal: Result of the verify -->

- `SSL certificate verify ok` appears in the verbose output, followed by your `<h1>`.

<!-- /dojo-reveal -->

Now the same check the way a browser makes it: open the **Site
Inspector** card on the workshop homepage and visit `https://${host}`
(type your own name). It shows the certificate it was served (names,
issuer, serial, time left) and whether it chains to the lab CA, then the
page. Then visit just `${host}`, with no `https://`: a browser starts at
plain `http://`, and so does the inspector. Your site still answers there,
unencrypted. Step 6 fixes that.

---

## 6. HTTPS only: redirect, then HSTS

A certificate protects nobody while the site still answers on plain
HTTP. Two changes, both in your `.conf` (see the slide *HTTPS only:
redirect, then HSTS*):

- **Port 80 redirects.** Everything on `http://` gets a `301` to the same
  name and path on `https://`, *except* `/.well-known/acme-challenge/`:
  renewal (Lab 4) proves control of your name with a file there, over
  plain HTTP.
- **Port 443 sends HSTS.** `Strict-Transport-Security: max-age=300`
  tells the browser to skip `http://` for your name for the next five
  minutes, even when you type it without `https://`.

The template has both, marked `CHANGED`. After you read it, you replace
your file with it, and `-I` (headers only) lets you check both from the
terminal.

**Your turn:** before you run it, predict: what status and headers will
each of the three requests return, and why is the third not a `301`?

```sh
less ~/lab/sample-repo/vhost-https-only.conf.template
sed "s/studentNN/${me}/g" ~/lab/sample-repo/vhost-https-only.conf.template \
  > "/srv/webroot/${me}/conf.d/${me}.conf"
curl -sI --resolve "${host}:80:${demo_ip}" "http://${host}/"
curl -sI --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/"
curl -s  --resolve "${host}:80:${demo_ip}" -o /dev/null -w '%{http_code}\n' \
  "http://${host}/.well-known/acme-challenge/missing"
```

<!-- dojo-reveal: Results of the three curl checks -->

```text
HTTP/1.1 301 Moved Permanently
Location: https://student07.certs.dojo.test/
...
HTTP/1.1 200 OK
Strict-Transport-Security: max-age=300
...
404
```

The last one is `404`, not `301`: the challenge path still answers on
plain HTTP.

<!-- /dojo-reveal -->

Now watch it from the browser's side. In the **Site Inspector**, visit
`${host}` (no scheme) twice:

1. The first visit goes `http://` → `301` → `https://`, and the HTTPS
   response carries HSTS. The **HSTS memory** at the bottom now lists your
   name.
2. The second visit never sends the plain `http://` request: the
   inspector upgrades it to `https://` first, as a browser does. That
   skipped request is the one an attacker on the network would have
   answered (SSL stripping).

After five minutes the memory expires and the first visit's path comes
back; **Forget all** does the same at once.

---

## Checkpoint

You have a live HTTPS-only site, an issued certificate you can inspect,
and you've watched the full ACME http-01 exchange happen. Plain HTTP now
redirects (except the challenge path) and browsers remember HSTS. You also now know
that certificate expires in minutes, not months — which is exactly what
Lab 4 automates.

Next: [lab3.md](lab3.md), the same task with acme.sh.
