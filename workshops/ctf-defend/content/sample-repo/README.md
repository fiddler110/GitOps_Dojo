# customer-portal

A small internal lookup tool for support staff: search customers by name, or
log in as one. Product wants it live, and InfoSec just opened an incident
against it — see your lab for the briefing.

## Running it yourself

```sh
python3 seed.py                 # builds data/portal.db (idempotent)
python3 app.py                  # listens on :5000 (PORT to change it)
```

```sh
# the same check the PR gate runs
python3 exploit/dump.py --url http://127.0.0.1:5000
```

## What happens on a PR / merge

`.forgejo/workflows/defend-pr.yml` scans the source (informational — it never
blocks a PR on its own) and re-runs the check above as the actual gate: the
PR can only merge once that check comes back clean. `defend-main.yml` rebuilds
and redeploys your live instance the moment your fix lands on `main`.
