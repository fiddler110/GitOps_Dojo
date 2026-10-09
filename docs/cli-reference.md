# CLI reference

`./dojo` is the only entry point. It is a short launcher for the Python CLI in `engine/dojo/` (Click for commands and
completion, Rich for the live display). Python 3.9+ is the only host requirement besides a container engine. On first
run `dojo/boot.py` unpacks the hash-pinned wheels from `engine/dojo/requirements.lock` into `engine/.cache/`
(git-ignored); behind TLS inspection `CORP_CA_BUNDLE` works for that download as it does for image builds.

`./dojo --help` lists commands; `./dojo <command> --help` is the authority for flags. `./run.sh` still exists as a stub
that forwards to `./dojo`. Run from the repo root or from `engine/` (same result).

## Command summary

| Command | Purpose |
|---|---|
| `./dojo <workshop> [flags]` | Build and start a workshop (same as `start`) |
| `./dojo start <workshop>` | Explicit form of the above |
| `./dojo stop [--dry-run]` | Tear down the stack and **delete every volume** |
| `./dojo restart [SERVICE...] [--clean]` | Recreate the last start's containers, same flags |
| `./dojo status [--json]` / `ps` | What is running, health, students signed in |
| `./dojo list` | Workshops in learning-path order, with durations |
| `./dojo modules` | Modules and which workshops use them |
| `./dojo doctor [<workshop>] [--env NAME]` | Will a start work here? Exits 1 if not |
| `./dojo config <workshop> [KEY...] [--env NAME] [--show-secrets]` | Show each setting and which file set it |
| `./dojo logs <service> [-f] [-n N]` | A service's log, by Compose service name |
| `./dojo setup [--default] [--force] [--rotate-class]` | Create or update `.env` and `dojo.local.toml` |
| `./dojo capacity [<workshop>] --students N [...]` | Size the terminal resource limits for this machine |
| `./dojo build-all [--env NAME] [--dry-run]` | Build every workshop's images, start nothing |
| `./dojo new-workshop NAME [...]` | Scaffold a new pack |
| `./dojo alias-setup [--check\|--remove]` | Install the `dojo` command and tab completion |
| `./dojo completion {bash\|zsh}` | Print the completion script |
| `./dojo help` | Overview |

## Starting a workshop

```sh
./dojo tofu-basics                       # build what changed, start, watch it settle
./dojo tofu-basics --dry-run             # plan only: rebuilds, manifests, pins, compose validity
./dojo tofu-basics --test 5 --fast       # five demo bots, one quick round, for checks
./dojo tofu-basics --env home            # apply the "home" profile
./dojo tofu-basics --terminal zellij     # terminal flavor for this run only
./dojo tofu-basics --pass 'lunch42'      # access-code page in front of the whole site
```

| Flag | Effect |
|---|---|
| `--test [N]` | Add demo bots: 3, or N (max 35). `testuser1-3` are expert/intermediate/novice; the rest get one persona at random. They never use a student slot |
| `--fast` | With `--test`: no pacing, mistakes in every round for intermediate/novice, one round, then `~/.dojo-bot-done`. For checks, not demos |
| `--env NAME[,NAME]` | Apply profile(s); the last wins |
| `--terminal code-server\|zellij` | Terminal flavor for this run; beats every file; `restart` repeats it |
| `--dry-run` | Show what would be rebuilt and started, validate manifests, pins and Compose; change nothing |
| `--build-only` | Build or refresh images and stop (no password checks) |
| `--allow-default-passwords` | Start with public default passwords on a non-loopback address (warns) |
| `--pass`, `--cookie`, `--code CODE` | Access-code page in front of everything, sign-in included (same flag, three names). Recorded with the start flags, so `restart` keeps it. Needs https or localhost |

### What a start does, in order

1. Resolve settings (see [Configuration](configuration.md)) and apply safety gates: public default passwords off
   loopback, the published port, plain http beyond localhost.
2. Refuse if a **different** workshop is running (run `./dojo stop` first).
3. Take the run lock (one build or start at a time).
4. Build what changed, in chain order: core terminal, flavor leaf, each module link, the workshop link, and the
   gateway, allocator, presentation images.
5. Validate and render every manifest into `engine/.generated/`; add the achievements module if
   `ACHIEVEMENTS_ENABLED` and the workshop has a catalog.
6. Record the run in `.build-state/`, then `compose up -d` with the recorded file list.
7. Watch containers settle (a live table, driven by `podman events`); a one-shot job counts as ready only after exit 0.
8. Explain anything that did not come up (last log lines and health results), release the bots if `--test`, and remove
   superseded images.

In a terminal the display updates in place; piped or with `NO_COLOR` it prints plain lines.

## Stopping and restarting

| Command | Result |
|---|---|
| `./dojo stop` | `compose down --volumes` for exactly the recorded file set. Every student home and all Forgejo data are gone. No undo. `stop` loads only the operator files (`dojo.toml`, `dojo.local.toml`, `.env`, the recorded profile), not `workshop.env` |
| `./dojo stop --dry-run` | Lists files, services, volumes and containers it would act on |
| `./dojo restart` | Re-runs the last start (`.build-state/last-start`) with `--force-recreate`; volumes kept |
| `./dojo restart web-terminal` | Recreates only that service (`--no-deps`). Under podman, services linked to it are recreated too, and it says which |
| `./dojo restart --clean` | `stop` then a fresh start: the state a class begins from |

Rules of thumb: after changing an image's Dockerfile or the Caddyfile, `./dojo stop` first, then start. After
editing only `.env`/TOML, re-run the workshop or `restart`. Do not pass a subset of service names to a raw
`podman-compose up` (it silently removes containers you did not name).

## Inspecting

```sh
./dojo status            # workshop, address, per-service health, students signed in
./dojo status --json     # for scripts
./dojo logs allocator -f
./dojo logs web-terminal -n 300
./dojo doctor dns-as-code    # pre-flight: engine found? ports free? passwords safe? manifests valid?
./dojo config dns-as-code PUBLIC_BASE_URL --env home    # every value and which layer won
```

`config` without keys prints the resolved settings; secrets are shown as lengths unless `--show-secrets`.

## `setup`

Writes `.env` (secrets) and this machine's sizing into `dojo.local.toml`. Interactive mode walks every setting with a
short explanation and offers to run `capacity`. Existing values are defaults; settings it does not ask about
(including `[profile]` sections) are carried over; public defaults (`change-me`, `student`, `student123`, `admin`)
are replaced by generated values on a bare Enter. The file is built as `.env.new` and moved at the end, so Ctrl-C
leaves `.env` intact; the old file is kept as `.env.previous`. `.env` is mode 0600.

| Flag | Effect |
|---|---|
| `--default` | Non-interactive, fixed easy credentials (`student`/`student123`/`admin`/`admin`) for local throwaway use. Machine secrets are still random. Implies `--force`. Refused later off loopback |
| `--force` | Overwrite without asking (profile sections kept) |
| `--rotate-class` | Generate a new `TTYD_PASSWORD` only; restart to apply |

First-time setup on a bare machine is `./setup.sh` (Ubuntu/Debian/Fedora/macOS, asks before installing, `--check`
only reports) or `.\setup.ps1` on Windows (installs WSL2 + Ubuntu, clones inside, runs `setup.sh`).

## `capacity`

```sh
./dojo capacity dns-as-code --students 30
./dojo capacity --students 30 --host-mem-mb 16384     # plan for a machine you have not provisioned
```

Run it **on the target machine**, ideally with a couple of `--test` bots live so it can measure real private memory.
With a workshop name, every service that workshop starts counts against the memory left for students. Other
options: `--heap-mb`, `--margin-pct` (15), `--procs-per-student` (5), `--reserve-mb` (1024), `--other-services-mb`.
It prints `WEB_TERMINAL_MEM_LIMIT`, `WEB_TERMINAL_PIDS_LIMIT` and `CODE_SERVER_MAX_HEAP_MB`.

## `new-workshop`

```sh
./dojo new-workshop my-lab --title "My Lab" --description "One sentence." \
    --modules "runner-pool sensei" --order 8 --duration "~2 h" --terminal
./dojo new-workshop my-lab --dry-run
```

Copies `workshops/assets/template/` into `workshops/my-lab/`, wired together with TODOs. It starts as is. See the
[Authoring guide](authoring.md).

## `alias-setup` and completion

`./dojo alias-setup` installs `~/.local/bin/dojo` (a three-line script that runs this checkout with `DOJO_PROG=dojo`)
and one marked block in your shell profile (zsh: `~/.zshrc_aliases` or `~/.zshrc`; bash: `~/.bash_aliases` or
`~/.bashrc`) that loads completion and adds `~/.local/bin` to `PATH` if missing. Re-running replaces the block.
`--check` exits 0 if installed for this checkout; `--remove` undoes it. Move the repo? Re-run it. Completion covers
commands, workshop names, flags, `--env` profile names and the running stack's services; bash and zsh only.

## Files the CLI reads and writes

| Path | Role |
|---|---|
| `dojo.toml`, `dojo.local.toml`, `.env` | Settings (read) |
| `workshops/<name>/workshop.env`, `modules/<m>/module.env` | Workshop and module settings (sourced by `sh`) |
| `engine/.generated/` | Rendered gateway snippet, allocator manifest, upstream tokens (written) |
| `engine/.build-state/current.json` | The running stack: workshop, flags, compose files |
| `engine/.build-state/last-start` | Arguments `restart` repeats |
| `engine/.build-state/history.jsonl` | One line per start, restart, build, stop, with duration and outcome |
| `engine/.build-state/*.overlay-hash`, `superseded-images` | Change detection and image housekeeping |
| `/tmp/gitops-dojo-<uid>.lock` | The run lock |
| `engine/.cache/` | Unpacked, hash-checked Python dependencies |

An old checkout's `engine/.env` and `engine/.env.NAME` files are migrated automatically on the first command into the
three-file layout and kept as `*.migrated`.

## Exit behaviour worth knowing

- `doctor` exits 1 when anything would stop a start; use it in scripts.
- A bad manifest, an unpinned image, a default password off loopback, a clash with a running different workshop and a
  lock held by another `./dojo` all stop the start before anything changes.
- `restart` repeats the running start's achievements setting unless `ACHIEVEMENTS_ENABLED` is set in the shell.
