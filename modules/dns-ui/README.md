# dns-ui module

Live, read-only view of the workshop's PowerDNS zones at /dns, plus PowerDNS-Admin for the facilitator at /dns-admin.

**DNS Zones**: every record in every zone on the workshop's PowerDNS, refreshed
every few seconds, with records added, changed or removed since the page was
opened highlighted. Students watch a merged PR go live (dns-as-code) or an ACME
`_acme-challenge` TXT record come and go (cert-autorenewal). Add it with
`MODULES="dns-ui"` in a `workshop.env`.

**DNS Admin** (facilitator only): PowerDNS-Admin in the `/admin` workspace, already
signed in, for making the "dashboard edit" that the next `dnscontrol push` removes.

Needs the workshop to run PowerDNS as service `dns-server` on `workshop_lab`,
with its HTTP API on `:8081` and the key in `POWERDNS_API_KEY`. The workshop must
declare `dns-server`'s `networks:` in **map form** (`workshop_lab: {}`): this module adds
`dns_admin_net` to it in map form, and podman-compose fails when the forms mix.

| Part | What it does |
|---|---|
| `compose.yml` | `zone-viewer` (on `workshop_lab`, read-only root filesystem, no capabilities); `dns-admin` on `dns_admin_net` only, which just the gateway and `dns-server` join, so students can't reach it round the gate. |
| `extensions.json` | Landing card **DNS Zones**, the facilitator's `/admin` tab, the `/dns` route (`shared` gate: the data is what `dig` already returns, so no identity) and the status-strip check on `/dns/readyz`. The route passes the path through unstripped: the viewer serves everything under `PATH_PREFIX` (`/dns`) and redirects a bare `/dns` to `/dns/`. |
| `dns-admin/` | `powerdnsadmin/pda-legacy` pinned by digest, unpatched. `dojo_wsgi.py` mounts it under `/dns-admin` (the route doesn't strip the prefix), answers only requests with the gateway token, and signs in only `FACILITATOR_USERNAME` through PowerDNS-Admin's trusted remote-user login. `dojo-entrypoint.sh` and `dojo_seed.py` set the API URL and key, turn off sign-up and the local login form, and create the facilitator as Administrator with a random unused password. SQLite on a tmpfs, reset on every start like `dns-server`. Hardening: random `SECRET_KEY` per start (the upstream default is shared by every install), its own session cookie name, and every cookie scoped to `/dns-admin` with `SameSite=Strict`, `X-Frame-Options: SAMEORIGIN` and CSP `frame-ancestors 'self'` on every response, read-only root filesystem, no capabilities but binding `:80`, 2 workers. No status check: the allocator isn't on `dns_admin_net`. |
| `zone-viewer/` | Stdlib Python server: one thread polls PowerDNS every `ZONE_VIEWER_POLL_SECONDS`, requests only read that snapshot. The page renders every record value with `textContent`. |

**Settings** (set in `engine/.env` or `workshop.env`): `ZONE_VIEWER_POLL_SECONDS` (2),
`ZONE_VIEWER_MEM_LIMIT` (64m), `DNS_ADMIN_MEM_LIMIT` (384m), `DNS_ADMIN_WORKERS` (2).

**Tests** (host Python, no containers):

```sh
cd modules/dns-ui/zone-viewer && python3 -B -m unittest test_server
```

Used by: `dns-as-code`, `cert-autorenewal`.
