# Certificate Autorenewal Lab

Welcome! This lab teaches the mechanics behind automated TLS certificate
issuance and renewal — the open-source, protocol-level version of what a
tool like Venafi automates for you at work. Everything here runs against a
real, local ACME server (`step-ca`) and a real shared web app (`demo-app`),
so the certificates you issue are real X.509 certificates, actually
installed, actually serving HTTPS.

You are working in your own student account, and — unlike a normal Linux
account — your work here also lives in a **shared** location,
`/srv/webroot`, because that's what the demo web app actually serves from.
Your own subdirectory there (`/srv/webroot/$(whoami)/`) is yours alone —
same idea as your home directory, just also reachable by `demo-app`.

## What you'll do

The session slides cover the *why*. This lab is the *how* — five short,
self-contained labs. **Every lab is part of the workshop.** Together they
cover the end-to-end workflow (trust the CA, issue and install a
certificate, then automate its renewal), with a second ACME client and the
dns-01 challenge to go deeper. Work through them in order.

| Lab                | Topic                                                              | Time    |
| ------------------ | ------------------------------------------------------------------ | ------- |
| [lab1.md](lab1.md) | Trusting the CA: bootstrap, inspect the root cert                  | ~10 min |
| [lab2.md](lab2.md) | Issue and install a certificate with certbot                       | ~25 min |
| [lab3.md](lab3.md) | The same task with acme.sh — comparing ACME clients                | ~15 min |
| [lab4.md](lab4.md) | Automating renewal, and watching it actually happen                | ~15 min |
| [lab5.md](lab5.md) | The dns-01 challenge, against real DNS records you write           | ~15 min |

**Starting partway through?** Run `lab-prep <N>` in the terminal to set up what lab N needs from the earlier labs (for example `lab-prep 4`). It's safe to run more than once and never undoes your own work.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane or another tab
while you work — it's a condensed reference to every command used across
all five labs.

Open any lab file (or the cheat sheet) with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md, etc.
```

---

## Challenges (bonus)

When your class has achievements on (you see a score on your landing page), some labs end with a challenge: a goal
with no steps, in a space of your own, for extra points. They never count towards finishing the workshop.

| Id | Challenge | Where |
| -- | --------- | ----- |
| `c1` | The Second Site | end of [Lab 3](lab3.md) |
| `c3` | Members Only (mutual TLS) | end of [Lab 3](lab3.md) |
| `c2` | The Short Fuse | end of [Lab 4](lab4.md) |
| `capstone` | The Wildcard Heist | end of [Lab 5](lab5.md) |

Start one from its box in the lab or with `dojo-challenge start <id>`, and check it with `dojo-check <id>`. A wrong
answer costs nothing; `dojo-check hint <id>` gives a hint for part of the points. `dojo-check` on its own lists them
with what each is worth.

## 1. Check your shell

```sh
whoami
step version
certbot --version
acme.sh --version
openssl version
dig -v
```

Your username should look like `student01`, `student02`, and so on — note
it down, it's also your DNS label (`studentNN.certs.dojo.test`) for the
rest of this lab. `step`, `certbot`, `acme.sh`, `openssl`, `dig`, and `jq`
are all preinstalled — nothing to download.

---

## 2. What's actually running

| Service      | Role                                                                                                                                                                                                                                                                                                                  |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `step-ca`    | The shared ACME certificate authority. Its ACME provisioner is configured to issue **short-lived certificates (5-10 minutes)** — not a mistake, that's what makes automated renewal (Lab 4) something you actually watch happen, instead of a fact you're told about.                                                 |
| `demo-app`   | A shared nginx container. Your own vhost, docroot, and certificate live in your own subdirectory of the volume it serves from (`/srv/webroot/$(whoami)/`) — a watcher inside it reloads nginx automatically whenever you change any of those files. You never need to (and can't) reach into that container directly. |
| `dns-server` | A PowerDNS instance. Already seeded with an A record for every student pointing at `demo-app`, so Labs 1-4 need no DNS work at all. Lab 5 is where you edit records against it yourself.                                                                                                                              |

The loop every lab in this series follows:

```text
trust the CA → request a cert (prove you control your hostname) →
install it → verify it → automate the next renewal before this one expires
```

The workshop homepage also has a **Site Inspector** card: your browser
for this lab. Type one of your names and it visits it the way a browser
would, showing each step: the plain `http://` request, any redirect, the
HTTPS connection with the certificate it was served (and whether that
chains to the lab CA), the `Strict-Transport-Security` header and the other
security headers, and finally the page itself. Like a browser, it
remembers HSTS. It can only visit your own names. `curl --cacert`/`-v`
(Lab 2 step 5) is the same check from the terminal.

---

## Getting unstuck

- `openssl x509 -in <cert> -noout -dates` always tells you exactly when a
  certificate is valid from/until — your fastest sanity check at any point
  in this lab.
- Nothing here can break another student's site — your vhost, docroot, and
  certificate all live only in your own subdirectory of the shared volume.
- If a client can't reach `step-ca`'s ACME directory at all, double-check
  you're using `https://step-ca:9443/...`, not `http://` — step-ca has no
  plain-HTTP listener.
- Stuck for more than a minute or two? Ask the facilitator.

## Quick reference

```sh
step ca bootstrap --ca-url https://step-ca:9443 --fingerprint <fp>   # trust the CA (Lab 1)
certbot certonly --webroot -w <dir> -d <host> --server <acme-dir-url>  # issue (Lab 2)
openssl x509 -in <cert> -noout -dates                                  # check validity
nginx -t                                                                # (inside demo-app only — you won't run this)
```

See [cheat-sheet.md](cheat-sheet.md) for the full version of this.
