# cert-autorenewal sample repo

This repo is where you keep the pieces of your lab that are worth
version-controlling — your nginx vhost and your renewal script — the same
way `dns-as-code` used git as the source of truth for DNS records. Nothing
here runs automatically (no CI in this workshop); it's just where your work
lives so you (and a facilitator, if asked) can see what you did and why.

- `vhost-http.conf.template` — the port-80 vhost you write in Lab 2, before
  you have a certificate yet (this is what serves the ACME http-01
  challenge file).
- `vhost-tls.conf.template` — the same vhost extended with a `listen 443
  ssl` server block, once you have a certificate to point at.
- `renew-and-reload.sh` — the renewal script you build out in Lab 4:
  attempt renewal with your ACME client of choice, and only reload nginx if
  a new certificate actually landed.

In each template, replace `studentNN` with your own account name (run
`whoami` to confirm it) — that's both your Linux account and your DNS
label (`studentNN.certs.dojo.test`), so there's nothing to invent and
nothing that can collide with another student's.

Copy a template into your own subdirectory of the shared demo-app volume,
don't edit it in place — see Lab 2 for the exact commands.
