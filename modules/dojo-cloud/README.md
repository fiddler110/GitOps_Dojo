# dojo-cloud module

Azure-inspired training cloud (API, portal, real containers) at /cloud.

**Dojo Cloud**: an Azure-inspired training cloud with an ARM-style API, a portal and
real containers. Students deploy to it with the `azurerm` provider. Add it with
`MODULES="dojo-cloud"` in a `workshop.env`. The design and its history are in
`workshops/tofu-basics/PLAN.md`.

| Part | What it does |
|---|---|
| `compose.yml` | `cloud-api` (control plane, on `workshop_lab` + `cloud_net`), `cloud-host` (privileged Docker-in-Docker, `cloud_net` only), their volumes, and the terminal's read-only CA and signing-key mounts. |
| `extensions.json` | Landing card **Dojo Cloud**, the facilitator's `/admin` tab, the `/cloud` route (identity gate) and the status-strip check on `/readyz`. |
| `terminal/` | The terminal link: root-owned credential broker, `dojo-env` (sourced from zshenv, gives each shell its own `ARM_*`), and `start.d/50-dojo-cloud.sh` (writes the CA trust bundle when the cloud is up, keeps the broker running). |
| `cloud-api/`, `cloud-host/` | The service sources and their unit tests. |
| `test_parity.py` | Checks that the broker and `cloud-api` derive identical ids and secrets for a username. |

**Settings** (set in `engine/.env` or `workshop.env`): `CLOUD_HOST_MEM_LIMIT` (3g),
`CLOUD_HOST_PIDS_LIMIT` (4096), `CLOUD_API_MEM_LIMIT` (256m). Needs `PUBLIC_BASE_URL` and
`GATEWAY_TOKEN`, which `./run.sh setup` writes.

**Tests** (host Python, no containers):

```sh
cd modules/dojo-cloud/cloud-api && python3 -B -m unittest test_portal_api test_executor test_policy_auth test_readiness
cd .. && python3 -B -m unittest test_parity
```

## Rate limit (tripwire)

CloudAPI keeps a token bucket per student for ARM calls (never keyed by source IP), far above a `tofu apply` or a
`--test` run. Knobs in module.env: `CLOUD_API_RATE_BURST` (default `200`) and `CLOUD_API_RATE_PER_SEC` (default
`20`); `0` = off. A refusal is a 429 with `Retry-After` and a `rate limit: <account> ...` log line. Test:
`python3 -B -m unittest test_ratelimit`.

Used by: `tofu-basics`.

## Docker socket and DinD (FIND-15, T5.1)

The socket `/run/cloud/docker.sock` is `0660 root:cloud` (gid 1900, `cloud-host/entrypoint.sh`); `cloud-api` joins
the group with `group_add`. The `cloud_run` volume is mounted only by `cloud-api` and `cloud-host`, so the socket
has no "other" access. Check: `podman exec workshop_cloud_host stat -c '%a %G' /run/cloud/docker.sock` prints
`660 cloud`.

`cloud-host` stays a privileged Docker-in-Docker daemon. Rootless DinD / podman-in-container was **not adopted**
(accepted residual risk, decision D9): the box is what limits it (`internal: true` network, no published port,
the socket shared with `cloud-api` alone, fixed-template executor) and a rootless variant was not spiked on WSL2.
