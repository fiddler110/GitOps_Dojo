# leaky-config

A small service with an ops dashboard: `/status` and `/healthz` are public, and `/admin/...` is for the ops
team, behind a login. Its logs and config sit on disk beside the app.

## Running it yourself

```sh
python3 app.py      # listens on :5000 (PORT to change it)
```

## What the platform does

- The **PR gate** starts your branch, tries to read what an outsider should not, and sends one legitimate
  ops request. Pass means the outsider is refused and the ops request still works (advisory: it never blocks the merge).
- Merging to `main` rebuilds and redeploys your slot. `dojo-check leaky-config` checks your live slot.
