# Challenge c3: Members Only

**Goal:** serve `https://members.{user}.certs.dojo.test` only to clients that present a certificate issued by the
lab CA. Everyone else is turned away. This is **mutual TLS** (mTLS): the server proves who it is with its
certificate, as on every HTTPS site, and the client proves who *it* is with one too. Services use it to talk to each
other without passwords.

## What's here

- `members.conf`: the vhost. The port-80 block is done (the http-01 challenge, and a redirect for everything else).
  The HTTPS block is commented out with `TODO`s: that part is yours.

## Steps

1. Put the vhost in place and give the site a page:

   ```sh
   mkdir -p /srv/webroot/{user}/members-html
   echo '<h1>Members only</h1>' > /srv/webroot/{user}/members-html/index.html
   cp ~/lab/cert-members/members.conf /srv/webroot/{user}/conf.d/members.conf
   ```

2. Issue a certificate for `members.{user}.certs.dojo.test` (Lab 2, with `-w /srv/webroot/{user}/members-html`)
   and copy it into `/srv/webroot/{user}/certs/`, under names of its own.
3. Copy the lab CA's root next to it, so demo-app can read it: `cp /opt/step-ca-root/root_ca.crt
   /srv/webroot/{user}/certs/`.
4. Fill in the `TODO`s, uncomment the HTTPS block, copy the file in again. Before you copy, check that it is
   complete: no line in the HTTPS block may still say `TODO`.
5. Try it as a stranger and as a member. Any certificate from the lab CA is a client certificate too (it puts both
   *server* and *client* use in every certificate it issues), so the one you just issued for `members` will do:

   ```sh
   me=$(whoami); host="members.${me}.certs.dojo.test"; demo_ip="$(dig @dns-server "${host}" +short)"
   curl -s --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/"
   curl -s --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt \
     --cert ~/certbot/config/live/${host}/fullchain.pem \
     --key  ~/certbot/config/live/${host}/privkey.pem "https://${host}/"
   ```

   The first gets nginx's `400 No required SSL certificate was sent`; the second gets your page. `400 The SSL
   certificate error` means the client certificate didn't verify: usually it has expired (this CA's last minutes),
   so issue a fresh one.

## Done when

`members.{user}.certs.dojo.test` serves its own valid certificate, refuses a client without a certificate and lets in
one with a certificate from the lab CA (the checker has its own), and the `members.conf` you run is pushed to `main`
here. Then `dojo-check c3`.

## Keep keys out of git

Certificates and private keys live in `/srv/webroot/{user}/certs/` and in your ACME client's own folder, never in this
repo. The check scans the repo's **whole history** for a private key. If one gets in, `dojo-challenge reset c3`
rebuilds the repo from scratch (in a real team you'd also replace the key).
