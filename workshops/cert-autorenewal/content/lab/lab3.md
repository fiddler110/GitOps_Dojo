# Lab 3 — The Same Task with acme.sh

certbot is a full Python application with plugins and a
config system; acme.sh is a single shell script that speaks ACME directly.
Same protocol, same CA, very different level of transparency into what's
actually happening. This lab issues a second certificate for comparison —
it won't touch the live site you built in Lab 2.

> **Starting here?** This lab needs Lab 2's port-80 site on demo-app (steps 1-2). Run `dojo prep 3` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Issue, into a separate directory

`--ca-bundle` is acme.sh's equivalent of certbot's `REQUESTS_CA_BUNDLE` —
same problem (trust `step-ca`'s own HTTPS listener), different flag.
`--cert-home` keeps this lab's output separate from anything else, and
acme.sh needs no `--config-dir`-style root-avoidance flags at all: its
state (`~/.acme.sh` by default, or wherever `--cert-home` points) is
plain, per-user files from the start.

```text
acme.sh --issue --webroot <webroot> -d <host> --server <acme-directory> --ca-bundle <root>
```

**Your turn:** before you run it, predict: will you see the same four ACME
steps certbot showed in Lab 2?

```sh
me="$(whoami)"
host="${me}.certs.dojo.test"

acme.sh --issue \
  --webroot "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9443/acme/acme/directory \
  --ca-bundle /opt/step-ca-root/root_ca.crt \
  --cert-home ~/acmesh-lab3 \
  --accountemail "${me}@example.com"
```

<!-- dojo-reveal: Result of acme.sh --issue -->

- The issue succeeds and acme.sh prints the certificate paths under `~/acmesh-lab3`.

<!-- /dojo-reveal -->

---

## 2. Read the output

Scroll back through what acme.sh printed. Compare it against certbot's
output from Lab 2 — same four ACME steps (account, order, challenge,
finalize), but acme.sh shows more of the raw HTTP exchange rather than
summarizing it. Look for:

- The account registration/lookup against `step-ca`'s ACME directory.
- The order it creates for `${host}`.
- It placing the challenge response file, then telling `step-ca` to
  validate it.
- The final certificate download once validation succeeds.

acme.sh keeps track of every certificate it manages. `--list` asks it what
it has (the `--cert-home` must match the one you issued with). certbot's
equivalent is `certbot certificates`.

acme.sh makes an ECC key by default and keeps that certificate in a folder
named after the host with `_ecc` on the end.

**Your turn:** before you run it, predict: how many rows will `--list`
show, and will `-issuer` match the certbot certificate from Lab 2?

```sh
acme.sh --list --cert-home ~/acmesh-lab3
openssl x509 -in ~/acmesh-lab3/${host}_ecc/${host}.cer -noout -dates -subject -issuer
```

<!-- dojo-reveal: Results of the list and openssl -->

- One row for `${host}`: the key type, the CA it came from, when it was made and when acme.sh plans to renew it.
- `-issuer` is the same CA as Lab 2's certificate — same CA, same claims, different client.

<!-- /dojo-reveal -->

This lab never copies its output into `/srv/webroot/${me}/certs/`, so
`demo-app` is still serving Lab 2's certificate, not this one — the acme.sh
cert exists (you can inspect it above), it's just not installed. The
`curl --cacert` check from Lab 2 step 5 would confirm that if you ran it
again here, and so would the homepage's **Site Inspector**: its
certificate's serial and dates are still Lab 2's.

---

## Checkpoint

You can name at least one thing acme.sh showed you directly that certbot
summarized. (There's no single right answer — that's the point: different
tools, same protocol underneath.)

Next: [lab4.md](lab4.md), automating renewal.

---

## Challenge c1: The Second Site (bonus)

Give a second name, `shop.$USER.certs.dojo.test`, its own trusted certificate, with either tool, and leave your
first site alone. The name already points at the demo site; the vhost is yours to write.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c1
cd ~/lab/cert-shop
```

That makes your own repo `$USER/cert-shop` and clones it to `~/lab/cert-shop`, with a brief and starter files, and prints the goal, with your own names in it. When you think it's done, push your files and run:

```sh
dojo check c1
```

Keep keys out of the repo: the check looks through its whole history for a private key.

A wrong answer costs nothing. `dojo check hint c1` gives a hint for part of the points, and
`dojo challenge reset c1` throws the repo away and starts you over from a fresh copy.


---

## Challenge c3: Members Only (bonus)

Mutual TLS: serve `https://members.$USER.certs.dojo.test` only to clients that present a certificate from the lab
CA, and turn everyone else away. Until now only the server proved who it was; here the client does too, the way
services talk to each other without passwords. Any fresh certificate from the lab CA doubles as the client
certificate to test with.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c3
cd ~/lab/cert-members
```

That makes your own repo `$USER/cert-members` and clones it to `~/lab/cert-members`, with a brief and starter files, and prints the goal, with your own names in it. When you think it's done, push your files and run:

```sh
dojo check c3
```

Keep keys out of the repo: the check looks through its whole history for a private key.

A wrong answer costs nothing. `dojo check hint c3` gives a hint for part of the points, and
`dojo challenge reset c3` throws the repo away and starts you over from a fresh copy.

