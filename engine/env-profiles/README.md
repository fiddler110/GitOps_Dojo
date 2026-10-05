# Env profiles: settings that travel

`engine/.env` is gitignored and is rebuilt by `./run.sh setup`, so anything set
by hand in it stays on one machine and is lost on the next `setup --default`.
Settings that are not secrets go here instead, in git, so they reach every
computer and every session.

## What goes where

| Kind | Example | Where it lives |
|---|---|---|
| Passwords, tokens, seeds | `TTYD_PASSWORD`, `GATEWAY_TOKEN`, `STUDENT_PASSWORD_SEED` | `engine/.env` only. Never here: `setup` makes new ones on each machine |
| Repo-wide defaults | `ACHIEVEMENTS_ENABLED=1` | `engine/.env.example`, so `setup` writes them everywhere |
| Machine or run settings | the Mac's runner options, the Zellij flavor | A profile in this folder |
| Sized per machine | `WEB_TERMINAL_MEM_LIMIT`, `WEB_TERMINAL_PIDS_LIMIT`, `CODE_SERVER_MAX_HEAP_MB` | Nowhere: `setup --default` sizes them for the machine it runs on |

## Profiles

| File | Use it for |
|---|---|
| `mac-podman.env` | macOS with rootful Podman: without it no runner or vault app starts |
| `zellij.env` | The Zellij terminal flavor instead of VS Code |

## On a new computer, or after `setup --default`

A profile becomes an `--env` overlay: `./run.sh` loads `engine/.env`, then
`engine/.env.NAME` on top of it, and the overlay's values win. Only one
`--env` is allowed per run, so join the profiles that run needs:

```sh
./run.sh setup --default --force                       # secrets and machine sizing
cp engine/env-profiles/mac-podman.env engine/.env.mac  # gitignored, like every .env.*
./run.sh git-fundamentals --env mac

# The Zellij flavor on the same Mac: both profiles in one overlay
cat engine/env-profiles/mac-podman.env engine/env-profiles/zellij.env > engine/.env.zj
./run.sh git-fundamentals --env zj
```

`./run.sh restart` reuses the last start's flags, `--env` included.
`./run.sh config <workshop> --env NAME KEY` shows the value a key ends up with
and which file set it.

## Adding a setting

Put it in the profile it belongs to (or a new `<name>.env` here), with a
comment saying why it is needed. Keep secrets out: anything named like a
password, token or seed belongs in `engine/.env`.
