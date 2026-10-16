# Lab 1 — Trust the CA

Before any ACME client will talk to `step-ca`, it has to trust
it — the same way your laptop trusts a public CA's root, or the way this
org's systems trust whatever root Venafi issues from. By the end of this
lab you'll have fetched and verified `step-ca`'s root certificate, told the
`step` CLI to trust it, and inspected what's actually in it.

---

## 1. Get the CA's root certificate

`step-ca`'s public root certificate (never its private key — that never
leaves the CA container) is mounted read-only in your terminal at
`/opt/step-ca-root/root_ca.crt`.

This is exactly the out-of-band distribution step a real org has to solve
too — a client needs the root cert (or at least its fingerprint) from
*somewhere* it already trusts before ACME can bootstrap trust for
everything else. Here, that's a read-only file; at work, it might be a
wiki page, an MDM push, or a Venafi-managed trust bundle.

`step certificate inspect` decodes a certificate and prints its contents;
`--short` trims the output to the essentials:

```text
step certificate inspect <cert-file> --short
```

**Your turn:** before you run it, predict: whose name will appear as both
the subject and the issuer of a root certificate?

```sh
ls -l /opt/step-ca-root/root_ca.crt
step certificate inspect /opt/step-ca-root/root_ca.crt --short
```

<!-- dojo-reveal: Results of the inspect -->

- The file exists and is read-only to you.
- Subject and issuer match: a root certificate signs itself.

<!-- /dojo-reveal -->

---

## 2. Compute its fingerprint

A fingerprint is a SHA-256 hash of the certificate. It is what
`step ca bootstrap` uses to verify it's actually talking to the right CA
before trusting anything it says — without it, a client bootstrapping
against `https://step-ca:9443` would have no way to know it isn't being
handed a different root by something in the middle.

```text
step certificate fingerprint <cert-file>
```

**Your turn:** before you run it, predict: how long is the output, and
would a different certificate give the same value?

```sh
step certificate fingerprint /opt/step-ca-root/root_ca.crt
```

<!-- dojo-reveal: Result of the fingerprint -->

- One 64-character hex string (SHA-256).
- Any other certificate would give a different value, which is what makes it useful for pinning trust.

<!-- /dojo-reveal -->

---

## 3. Bootstrap trust

`step ca bootstrap` writes the CA's config and root cert into your own
`step` config directory (`~/.step` by default — check with `step path`).
From here on, `step` commands against this CA work without re-specifying
the URL or fingerprint every time. `step ca health` then asks the CA
whether it is up.

```text
step ca bootstrap --ca-url <url> --fingerprint <sha256>
step ca health --ca-url <url>
```

**Your turn:** before you run it, predict: what will `step ca health`
print once bootstrap has succeeded?

```sh
step ca bootstrap \
  --ca-url https://step-ca:9443 \
  --fingerprint "$(step certificate fingerprint /opt/step-ca-root/root_ca.crt)"
step ca health --ca-url https://step-ca:9443
```

<!-- dojo-reveal: Results of bootstrap and health -->

- Bootstrap reports that the root was written under your `~/.step`.
- The health check prints `ok`.

<!-- /dojo-reveal -->

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

You should be able to run `step ca health --ca-url https://step-ca:9443`
and get `ok`, and explain in one sentence why `step ca bootstrap` needs a
fingerprint, not just a URL.

Nothing to see in the homepage's **Site Inspector** yet — that
becomes useful starting next lab, once you actually have a vhost.

Next: [lab2.md](lab2.md) — issue your first certificate.
