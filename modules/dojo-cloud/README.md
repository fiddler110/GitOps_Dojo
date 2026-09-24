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

Used by: `tofu-basics`.
