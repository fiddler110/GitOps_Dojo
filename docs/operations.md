# Operations and troubleshooting

Day-to-day care of a running stack and what to do when it misbehaves. Start with `./dojo status` and
`./dojo doctor <workshop>`; they answer most questions.

## 1. Health at a glance

| Tool | Tells you |
|---|---|
| `./dojo status` | Workshop, address, each service's health, students signed in, and whether another `./dojo` holds the lock |
| `/admin` status strip | Per-service **Ready / Starting / Down**, computed by the allocator (green on a good probe; yellow while never-OK inside the startup grace, or OK within the last 30 s; red otherwise) |
| `./dojo logs <service> -f` | One service's log. Service names are Compose names: `gateway`, `allocator`, `web-terminal`, `git-server`, `bootstrap`, `presentation`, plus module and workshop services |
| `.build-state/history.jsonl` | One JSON line per start, restart, build and stop with duration and outcome |
| `./dojo doctor` | Pre-flight: engine present, ports free, passwords safe for the address, manifests valid |

Status probes run in a background thread every 5 s, so a hung service never slows sign-in. Slides are probed through
the gateway at `PUBLIC_BASE_URL` exactly as a browser would.

## 2. Engine choice

`./dojo` uses **podman with podman-compose** when both are installed (rootless, no root daemon) and falls back to
**Docker with the Compose plugin**. There is no flag; `./dojo doctor` says which. Behaviours to know on podman:

- Builds use Docker image format so the `HEALTHCHECK` survives; a plain `podman build` drops it. Always build and start
  through `./dojo`.
- Never `up` a subset of service names with raw `podman-compose`: it re-derives the pod and removes containers you did
  not name. Use `./dojo restart <service>`.
- `restart <service>` also recreates services linked to it, and says which.
- Rootless podman cannot bind ports below 1024; the defaults are 8080/8443.
- On macOS with rootful Podman use `--env mac-podman` (runner-pool needs `unmask=/proc/*`).

## 3. Sizing

```sh
./dojo capacity <workshop> --students 30     # on the target machine, ideally with --test bots live
```

Cost scales with **concurrently active** students, not `student_count`: code-server starts on first `/ide` visit and
is released when students leave. The three bounds are `mem_limit`/`pids_limit` (the container-wide ceiling),
`code_server_max_heap_mb` (per node process), and the grace/idle timers (see [Configuration](configuration.md#dojotoml-sections-and-the-variables-they-set)).
Without measurement the rule is RAM = students × 650 MB × 1.15 + 512 MB and pids = students × 40 + 200. The Zellij
flavor needs far less. A pack that applies infrastructure in every lab (cloud-policy-as-code) raises its own ceilings.
Vault-fundamentals needs about 2 GiB extra for 10 demo bots.

## 4. Restarting things

| Goal | Command | Volumes |
|---|---|---|
| A hung stack | `./dojo restart` | kept |
| One misbehaving service | `./dojo restart web-terminal` | kept |
| Back to a clean class | `./dojo restart --clean` | wiped |
| After editing `.env`/TOML | `./dojo <workshop>` or `./dojo restart` | kept |
| After changing a Dockerfile/Caddyfile | `./dojo stop`, then start | wiped |
| New workshop | `./dojo stop` first (a different workshop over a running one is refused) | wiped |

`restart` re-runs the last start's arguments from `.build-state/last-start`, so `--test`, `--env`, `--terminal` and
`--pass` carry over, and adds `--force-recreate`.

### Between back-to-back sessions

To hand a running stack to a new group without touching student homes:

```sh
podman exec workshop_allocator rm -f /var/lib/dojo-allocator/slots.json
./dojo restart allocator
```

The slot table survives a plain restart (so a crash never gives a live student's slot to someone else); deleting the
file first clears it. Browsers with old cookies are simply asked for a name again. For a truly clean class use
`./dojo restart --clean`.

### Changing student count or passwords

Edit `dojo.local.toml` / `.env`, then re-run `./dojo <workshop>` (not a partial `up`). Rotate only the class
password with `./dojo setup --rotate-class` and restart.

## 5. Cleanup

`./dojo stop` is `compose down --volumes` for the recorded file set plus housekeeping of superseded images. It
removes accounts, repos, homes, CA keys and DNS zones. Check first with `--dry-run`. Because every volume is named,
nothing is left over; if you find an anonymous volume after a stop, a service declared an unnamed `VOLUME`
(`podman image inspect <img> --format '{{json .Config.Volumes}}'` shows which).

## 6. Troubleshooting table

### Start-up

| Symptom | Cause and fix |
|---|---|
| "Refused: default passwords on a non-loopback address" | Run `./dojo setup` for real values, or `--allow-default-passwords` for a VPN-only lab |
| "A different workshop is running" | `./dojo stop` first |
| Start fails at manifest rendering | The message names the file and rule (overlapping path, unknown service, duplicate id, off-site link). Fix the `extensions.json` and `--dry-run` |
| `--dry-run` fails on pins | An external image or tool is unpinned. Pin by digest/sha256 (`engine/scripts/check-pins.sh`, `check-tool-pins.sh`) |
| Lock held / "build in flight" | Another `./dojo` (or a worktree) is mid-start. Wait; `./dojo status` shows it |
| Mixed list/map `networks:` error at `up` | Under podman-compose use list form on engine services, map form on `web-terminal` |
| Build fails with `wget`/TLS errors fetching extensions | TLS inspection. Set `build.corp_ca_bundle` or `CORP_CA_BUNDLE`; it is passed as a BuildKit secret, only for that step |
| Port already in use | Another stack or process; change `network.http_port` and keep `public_base_url` in step |
| Terminals chip yellow for a minute | Normal on first start: it creates every account. Red after that: `./dojo logs web-terminal` |
| Runners red on Ubuntu 24.04 | AppArmor blocks unprivileged user namespaces. Relax `kernel.apparmor_restrict_unprivileged_userns` on the host |
| Container `unhealthy` forever | A workshop Dockerfile restated `HEALTHCHECK` with `wget`; use `web-terminal-healthcheck` (sends the control token) |
| macOS: `unshare: mount /proc failed` | `--env mac-podman` |

### During a class

| Symptom | Cause and fix |
|---|---|
| `/ide` or `/term` bounces to `/` | `/auth-check` found no live slot: expected after Release, an allocator restart, or opening the URL without going through `/`. `./dojo logs allocator` |
| VS Code or terminal 502s right after Open | The process is spawned on first request; reload after a couple of seconds. Still failing: `./dojo logs web-terminal` and `pgrep -a -u student01` inside it |
| "Reload window" in VS Code | Student returned after the grace period; harmless |
| Student cannot clone or push | Use `git-server:3000`, not `localhost`. Check the account exists (`getent passwd student01` in `web-terminal`) and `./dojo logs bootstrap` |
| Push asks for a password | `~/.git-credentials` missing/empty: re-provision with **Reset**, or use **Password** on the roster tile as a stop-gap |
| Student sees "try again in N seconds" | Assignment rate limit; wait a few seconds |
| Slow sign-in or 502 from the gateway | Allocator slow: gateway allows 3 s dial and 10 s headers before returning 502. Check `./dojo logs allocator` |
| Sign-in loops / everyone signed out | A password changed (the cookie is derived from both passwords and `GATEWAY_TOKEN`) |
| Login rate limiting hits a whole room | Behind a proxy, set `network.trusted_proxies` to the proxy's single address |
| Forgejo shows a login page after SSO | `Authorization` reaching Forgejo (do not remove the strip in the Caddyfile), or the `/forgejo-login` step failed; check allocator logs |
| Gateway cannot get a certificate | `public_base_url`'s host must already resolve to the VM; inbound 80/443 open (Let's Encrypt http-01); set `http_port=80`, `https_port=443` |
| LAN students warned about certificates | Using Caddy's local CA; hand out `root.crt` or use a real name |
| One student's state is a mess | **Reset** from the roster |
| Roster tile status dot is grey/red | No process for that account; the student has not opened a tool, or was Released |
| Runner pool: jobs queue forever | `/admin` **Runners** is red or Manual with none; click + or switch to Auto |
| PowerDNS changes not appearing | CI apply only fires after the merge to `main`; check the "DNS Apply" status on the commit and the Runners tab |
| Cert lab: certificate expires in minutes | By design (5-10 minute lifetime) so renewals are visible |
| CTF: attack target will not start | Queue limit (`CTF_ATTACK_MAX_CONCURRENT`); one target per student is live at a time; check the Attack Range tab |

### Diagnosing inside the stack

```sh
./dojo logs allocator -n 200
./dojo logs web-terminal -f
podman exec workshop_terminal getent passwd student01
podman exec workshop_terminal pgrep -a -u student01
podman exec workshop_terminal sh -c 'ls /home/testuser*/.dojo-bot-done | wc -l'   # bots done
./dojo config <workshop> PUBLIC_BASE_URL                                          # which layer set a value
```

If you must run raw Compose, include the base file and every file listed in `.build-state/current.json`'s `files`,
and set `WEB_TERMINAL_IMAGE` to the last terminal link (`gitopsdojo/web-terminal:<workshop>`); otherwise you recreate
`web-terminal` without that workshop's tools. `./dojo restart web-terminal` does this correctly.

## 7. What a reboot or crash does

| Event | Effect |
|---|---|
| Allocator restart | Slots preserved (state volume); active sessions continue |
| `web-terminal` restart | Processes die; tmux/Zellij sessions and homes (volumes) survive; students reconnect |
| `git-server` restart | Reconnect; data is on the volume |
| Host reboot | Containers stop. Check `./dojo status`; if the stack is gone or half-up, `./dojo restart` (keeps surviving volumes) or `./dojo restart --clean` for a fresh class |
| Unseal after restart (vault) | Handled by `openbao-setup` on every start |
| Cloud-api restart | State mirrored to `cloud_data`; deployed sites persist until `stop` |
