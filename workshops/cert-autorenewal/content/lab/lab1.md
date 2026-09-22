# Lab 1 — Trust the CA

**Required.** Before any ACME client will talk to `step-ca`, it has to trust
it — the same way your laptop trusts a public CA's root, or the way this
org's systems trust whatever root Venafi issues from. By the end of this
lab you'll have fetched and verified `step-ca`'s root certificate, told the
`step` CLI to trust it, and inspected what's actually in it.

---

## 1. Get the CA's root certificate

`step-ca`'s public root certificate (never its private key — that never
leaves the CA container) is mounted read-only in your terminal at
`/opt/step-ca-root/root_ca.crt`:

```sh
ls -l /opt/step-ca-root/root_ca.crt
step certificate inspect /opt/step-ca-root/root_ca.crt --short
```

This is exactly the out-of-band distribution step a real org has to solve
too — a client needs the root cert (or at least its fingerprint) from
*somewhere* it already trusts before ACME can bootstrap trust for
everything else. Here, that's a read-only file; at work, it might be a
wiki page, an MDM push, or a Venafi-managed trust bundle.

---

## 2. Compute its fingerprint

```sh
step certificate fingerprint /opt/step-ca-root/root_ca.crt
```

This SHA-256 fingerprint is what `step ca bootstrap` uses to verify it's
actually talking to the right CA before trusting anything it says —
without it, a client bootstrapping against `https://step-ca:9000` would
have no way to know it isn't being handed a different root by something
in the middle.

---

## 3. Bootstrap trust

```sh
step ca bootstrap \
  --ca-url https://step-ca:9000 \
  --fingerprint "$(step certificate fingerprint /opt/step-ca-root/root_ca.crt)"
```

This writes the CA's config and root cert into your own `step` config
directory (`~/.step` by default — check with `step path`). From here on,
`step` commands against this CA work without re-specifying the URL or
fingerprint every time.

Confirm it worked:

```sh
step ca health --ca-url https://step-ca:9000
```

Should print `ok`.

---

## 4. certbot and acme.sh need to trust it too — separately

`step ca bootstrap` only configures the `step` CLI itself. certbot and
acme.sh are independent tools with their own HTTPS trust — each one needs
to be told about this root separately, which you'll do the first time you
use each in Labs 2 and 3 (`REQUESTS_CA_BUNDLE` for certbot, `--ca-bundle`
for acme.sh). This split — one root cert, three tools that each need
telling about it in their own way — is a small, hands-on version of a
problem a real internal-CA rollout has to solve at much larger scale.

---

## Checkpoint

You should be able to run `step ca health --ca-url https://step-ca:9000`
and get `ok`, and explain in one sentence why `step ca bootstrap` needs a
fingerprint, not just a URL.

Nothing to see on the homepage's **Demo Site** link yet — that
becomes useful starting next lab, once you actually have a vhost.

Next: [lab2.md](lab2.md) — issue your first certificate.
