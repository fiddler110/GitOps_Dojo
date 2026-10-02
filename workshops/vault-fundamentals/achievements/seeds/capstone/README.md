# Zero Standing Secrets

Build a new app for your slot with no secret stored in git, CI or on disk. Names to use: policy `capstone-app`,
platform role `capstone-app` (on `jwt-platform`), database role `capstone-app`, KV mount `capstone/`, secret
`capstone/app`.

- The app logs in with its platform identity (no AppRole, no CI secret).
- Its policy names only `capstone/data/app` and `database/creds/capstone-app`.
- It reads one static secret and gets one dynamic database credential (read `database/creds/capstone-app` once).
- Rotate the static secret (write `capstone/app` again) without deploying.
- `capstone/agent.hcl` in this repo is your Agent config: it must never hold a role id or secret id.

Starting the capstone unlocked your second app slot, `{user}-capstone` (see **My App**). A push to `main` of this repo
deploys there, with the platform identity `slot:{user}-capstone`, so bind your `capstone-app` role to that subject.
The app from the labs keeps running in your first slot.

This repo starts with only `capstone/agent.hcl`: the app and its pipeline are yours to add, as in Labs 9, 11 and 12.

- `capstone/` is the folder that gets deployed: it needs a `start.sh` that starts the Agent and the app, like
  `app/` in Lab 11.
- `.forgejo/workflows/deploy.yml` deploys it: Lab 11's workflow, with `tar -C src/capstone` (its last step, the
  pipeline's own vault login, isn't needed here).
- A new KV mount refuses writes for a few seconds while it upgrades ("Upgrading from non-versioned to versioned
  data"): wait and write again, as in Lab 9.

Work in your own namespace: `export BAO_NAMESPACE=students/$USER`. Then run `dojo-check capstone`.
