# Lab 4: Internal ops API (`cert-trust-bypass`)

By the end of this lab you'll have talked your way past a client-certificate check using a certificate you
made yourself, thirty seconds ago, with no help from anyone who trusts you.

---

## The briefing

Glasswing has one internal API meant to be reachable only by other services it already trusts, proven by
presenting a client certificate on every request. "It checks for a certificate" and "it checks the
certificate is one it should trust" are two different claims -- this lab is about the gap between them.

## 1. Start the target and scan it

Open the **Attack Range** card, start `cert-trust-bypass`, note your slot's IP, and scan it:

```sh
nmap -sV -p- <your-slot-ip>
```

As before: more than one port, and only one is the API you care about.

## 2. Make something that looks trusted

The endpoint, `POST /internal/ops`, takes a certificate in the request body and decides whether to let you
through. A real trust check has (at least) two parts: **who signed this certificate**, and **is it still
valid right now**. Work out which of those two the endpoint actually checks, and which it only *looks* like
it checks.

This workshop already covers generating your own certificates with `openssl req -x509` (see
`cert-autorenewal` if you want a refresher) -- nothing stops you from creating one yourself. The question is
what it needs to *say* about itself to pass, since nobody is going to vouch for it.

> **Hint 1.** "Self-signed" means exactly what it sounds like: you are your own certificate authority for
> a cert you make this way. A real verifier checks the signer against a trusted CA bundle. Does this one?

> **Hint 2.** The one field the handler is checking is the certificate's identity -- its Subject Common
> Name. If a self-signed cert with the *right* CN is accepted with no chain check at all, the exact CN this
> endpoint expects is the only unknown left, and the response from a wrong attempt may tell you more than
> you'd expect.

## 3. Submit

Once the endpoint accepts your certificate, the flag is in the response body.

```sh
dojo-flag submit cert-trust-bypass '<flag>'
```

## Still stuck?

Read [exploit-guide/cert-trust-bypass.md](exploit-guide/cert-trust-bypass.md) for the full walkthrough --
try the hints above for real first.
