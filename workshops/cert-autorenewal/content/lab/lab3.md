# Lab 3 — The Same Task with acme.sh

**Optional.** certbot is a full Python application with plugins and a
config system; acme.sh is a single shell script that speaks ACME directly.
Same protocol, same CA, very different level of transparency into what's
actually happening. This lab issues a second certificate for comparison —
it won't touch the live site you built in Lab 2.

---

## 1. Issue, into a separate directory

```sh
me="$(whoami)"
host="${me}.certs.dojo.test"

acme.sh --issue \
  --webroot "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --ca-bundle /opt/step-ca-root/root_ca.crt \
  --cert-home ~/acmesh-lab3 \
  --accountemail "${me}@example.com"
```

`--ca-bundle` is acme.sh's equivalent of certbot's `REQUESTS_CA_BUNDLE` —
same problem (trust `step-ca`'s own HTTPS listener), different flag.
`--cert-home` keeps this lab's output separate from anything else, and
acme.sh needs no `--config-dir`-style root-avoidance flags at all: its
state (`~/.acme.sh` by default, or wherever `--cert-home` points) is
plain, per-user files from the start.

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

```sh
openssl x509 -in ~/acmesh-lab3/${host}/${host}.cer -noout -dates -subject -issuer
```

Compare `-issuer` against the certbot-issued certificate from Lab 2 — same
CA, same claims, different client.

This lab never copies its output into `/srv/webroot/${me}/certs/`, so
`demo-app` is still serving Lab 2's certificate, not this one — the acme.sh
cert exists (you can inspect it above), it's just not installed. The
`curl --cacert` check from Lab 2 step 5 would confirm that if you ran it
again here; the homepage's **View Demo Site** link wouldn't tell you either
way, since it never touches HTTPS at all.

---

## Checkpoint

You can name at least one thing acme.sh showed you directly that certbot
summarized. (There's no single right answer — that's the point: different
tools, same protocol underneath.)

Next: [lab4.md](lab4.md) — required, automating renewal.
