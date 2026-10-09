# Configuration

Three files at the repo root hold every setting; nothing lives under `engine/`.

| File | In git? | Holds |
|---|---|---|
| `dojo.toml` | yes | Non-secret defaults that suit any machine, in sections |
| `dojo.local.toml` | no | This machine's overrides (same layout) and your **profiles** (`home`, `live` ...). `./dojo setup` writes the machine sizing here |
| `.env` | no, mode 0600 | Secrets only: passwords, tokens, seeds. `.env.example` is the template. A `[name]` header starts a profile's secrets |

## Precedence

Later wins:

```text
dojo.toml  <  dojo.local.toml  <  .env  <  profile (--env NAME)  <  workshop.env  (module.env is sourced first, so workshop.env overrides it)
```

- Unknown sections or keys in TOML are an **error with file and line**, so a typo can never silently do nothing.
- `[env]` is an escape hatch: any `SOME_VARIABLE = "value"` is passed through as written.
- `.env` is read literally (a password with `$`, a backquote or spaces arrives as typed).
- `workshop.env` and `module.env` are **shell code** (they derive tokens with `$(...)`), run by `sh`.
- `./dojo config <workshop> KEY [--env NAME]` prints every value a key was given, in load order, and which file won.
  `--show-secrets` prints values instead of lengths.
- A checkout from before this layout is migrated automatically; old `engine/.env*` files are kept as `*.migrated`.

## `dojo.toml` sections and the variables they set

| Section.key | Environment variable | Meaning (default) |
|---|---|---|
| `general.student_count` | `STUDENT_COUNT` | `studentNN` Linux + Forgejo accounts (3; 1-99) |
| `general.student_prefix` | `STUDENT_PREFIX` | Account prefix (`student`) |
| `general.class_username` | `TTYD_USERNAME` | Shared class sign-in name (`student`); its password is `TTYD_PASSWORD` in `.env` |
| `general.facilitator_username` | `FACILITATOR_USERNAME` | Facilitator sign-in; has sudo in the terminal (`facilitator`) |
| `general.forgejo_admin_user` / `_email` | `FORGEJO_ADMIN_USER` / `_EMAIL` | Machine admin in Forgejo; avoid the reserved name `admin` (`workshop-admin`) |
| `general.achievements` | `ACHIEVEMENTS_ENABLED` | Toasts, leaderboard, support desk for workshops with a catalog (true) |
| `network.public_base_url` | `PUBLIC_BASE_URL` | What students type; port must match `http_port` (`http://localhost:8080`) |
| `network.lab_host_ip` | `LAB_HOST_IP` | Interface the gateway binds on this machine (`127.0.0.1`; `0.0.0.0` for LAN/VM) |
| `network.http_port` / `https_port` | `GATEWAY_HTTP_PORT` / `_HTTPS_PORT` | Published ports (8080/8443; rootless podman can't bind below 1024) |
| `network.gateway_listen` | `GATEWAY_LISTEN` | Behind a TLS-terminating proxy, e.g. `http://:8080` |
| `network.trusted_proxies` | `GATEWAY_TRUSTED_PROXIES` | The proxy's address only, e.g. `10.0.0.2/32`, never a range |
| `network.allow_default_passwords` | `ALLOW_DEFAULT_PASSWORDS` | Permit public defaults off loopback (VPN-only labs) |
| `network.terminal_ingress_subnet` | `TERMINAL_INGRESS_SUBNET` | Gateway-to-terminal private network (`172.30.9.0/24`) |
| `terminal.flavor` | `TERMINAL_FLAVOR` | `code-server` (alias `web`) or `zellij` |
| `terminal.font_family` / `font_size` | `TERMINAL_FONT_*` | Zellij browser terminal font |
| `terminal.mem_limit` | `WEB_TERMINAL_MEM_LIMIT` | Container-wide RAM ceiling for all students (`4g`) |
| `terminal.pids_limit` | `WEB_TERMINAL_PIDS_LIMIT` | Container-wide pid ceiling (2048) |
| `terminal.nproc_limit` | `TERMINAL_NPROC_LIMIT` | Per-student `RLIMIT_NPROC`, a fork-bomb tripwire (1024; 0 off) |
| `terminal.code_server_max_heap_mb` | `CODE_SERVER_MAX_HEAP_MB` | V8 heap cap per code-server node process (384) |
| `terminal.reconnection_grace_seconds` | `CODE_SERVER_RECONNECTION_GRACE_SECONDS` | Free the extension host this long after a tab closes (300) |
| `terminal.idle_timeout_seconds` | `CODE_SERVER_IDLE_TIMEOUT_SECONDS` | Exit the whole code-server after this idle time (900; if non-zero must exceed 60; keep grace below it) |
| `bots.count` / `prefix` | `BOT_COUNT` / `BOT_PREFIX` | Demo bots (0; `testuser`) |
| `build.corp_ca_bundle` | `CORP_CA_BUNDLE` | CA bundle for TLS-inspecting networks, passed as a BuildKit secret, never baked into an image |
| `engine.workshop_content_dir`, `workshop_name`, `forgejo_org`, `forgejo_repo` | `WORKSHOP_*`, `FORGEJO_*` | Fallbacks so `stop` can read the compose file; a workshop sets the real values |

## Secrets in `.env`

| Variable | Purpose |
|---|---|
| `TTYD_PASSWORD` | The class login password (shown on a slide) |
| `FACILITATOR_PASSWORD` | Facilitator login and Linux sudo; required, keep private |
| `CONTROL_TOKEN` | Proves a request to `web-terminal`'s control API came from the allocator |
| `GATEWAY_TOKEN` | Proves a request came through Caddy; the root from which per-upstream tokens are derived |
| `FORGEJO_ADMIN_PASSWORD` | The machine admin (the facilitator reaches Forgejo through SSO) |
| `STUDENT_PASSWORD_SEED` | Seed for every derived per-student secret (Forgejo password, DNS key). Without it every student shares `STUDENT_PASSWORD` and `dojo` warns |
| `BOT_PASSWORD` | Optional demo bot password (`testuser123`) |

`./dojo setup` generates unguessable values. **A start refuses** when any of these is a public default (`change-me`,
`student`, `student123`, `admin`) unless both `PUBLIC_BASE_URL`'s host and `LAB_HOST_IP` are loopback, or you pass
`--allow-default-passwords`. Machine secrets (`CONTROL_TOKEN`, `GATEWAY_TOKEN`) are random even in `--default` mode.

## Other tunables (set under `[env]` or in `workshop.env`)

| Variable | Default | Effect |
|---|---|---|
| `ASSIGN_BURST`, `ASSIGN_PER_MINUTE` | 10, 20 | Slot-assignment token bucket; bots, facilitator and slot-holders exempt |
| `STATUS_INTERVAL_SECONDS` | 5 | Status-strip probe interval |
| `STATUS_STARTUP_GRACE_SECONDS` | 300 | Yellow (Starting) window before a never-OK service turns red |
| `STATUS_LOSS_GRACE_SECONDS` | 30 | Yellow window after a service was last OK |
| `ZONE_VIEWER_POLL_SECONDS`, `ZONE_VIEWER_MEM_LIMIT` | 2, 64m | dns-ui zone viewer |
| `CLOUD_HOST_MEM_LIMIT`, `CLOUD_HOST_PIDS_LIMIT`, `CLOUD_API_MEM_LIMIT` | 3g, 4096, 256m | dojo-cloud |
| `CLOUD_API_RATE_BURST`, `CLOUD_API_RATE_PER_SEC` | 200, ... | Per-student ARM call tripwire |
| `OPENBAO_MEM_LIMIT` | 512m | openbao |
| `SENSEI_REPO`, `SENSEI_FILE`, `SENSEI_MODE`, `SENSEI_INTERVAL`, `SENSEI_PATIENCE_SECONDS` | per workshop | Sensei behaviour |
| `DNS_GATE_USER_PARENTS`, `_SHARED_ZONES`, `_CI_ZONES`, `_CI_REPO`, `_RESET_RECORDS` | per workshop | dns-gate ownership rules |
| `FORGEJO_FORK_WORKFLOW` | 0 | Each student forks the team repo (bots too) |
| `MODULES`, `COMPOSE_OVERLAY`, `TERMINAL_FLAVOR` | per workshop | Pack wiring |
| `CTF_*` | per CTF pack | Range tokens, host image target, attack targets |

Each module's `module.env` lists its own knobs; `./dojo config <workshop>` shows everything that applies.

## Profiles (`--env NAME`)

A profile repeats the sections as `[profiles.NAME.<section>]` in `dojo.toml` or `dojo.local.toml`, with that
profile's secrets under a `[NAME]` header in `.env`. It only needs the values that differ; settings it does not name
are untouched (so the terminal flavor applies to every profile). Join profiles with commas; the last wins:
`--env mac-podman,home`. An unknown profile stops the start and lists the known names.

```toml
# dojo.local.toml
[profiles.home.network]
public_base_url = "https://dojoh.example.com"
gateway_listen = "http://:8080"
trusted_proxies = "10.0.0.2/32"
lab_host_ip = "0.0.0.0"
allow_default_passwords = true
```

```ini
# .env
[home]
TTYD_PASSWORD=student
FACILITATOR_PASSWORD=dojo-admin
```

`dojo.toml` ships one profile, `mac-podman`, for macOS with rootful Podman (it sets
`RUNNER_POOL_SECURITY_OPT_*` so runner-pool runners can mount `/proc`). The maintainer's `home` and `live` profiles
(a disposable rehearsal with known logins, and the real public run with generated passwords) are examples of the
pattern and live in the git-ignored files.

## Deployment scenarios

### Local machine (default)

```toml
[network]
public_base_url = "http://localhost:8080"
lab_host_ip = "127.0.0.1"
http_port = 8080
```

Plain http, reachable only from this machine. The port in the URL must match `http_port` (`dojo` warns otherwise).

### A cloud VM (for example Azure)

```toml
[network]
public_base_url = "https://<label>.<region>.cloudapp.azure.com"
lab_host_ip = "0.0.0.0"
http_port = 80
https_port = 443
```

Set the public IP's DNS label **before** starting, because Caddy requests a Let's Encrypt certificate on first boot.
The real access boundary is the network security group, scoped to your corporate range for the class. Let's Encrypt
http-01 needs inbound 80 from the internet. On rootless podman map 80/443 to 8080/8443 instead.

### Behind another reverse proxy

The proxy terminates TLS and forwards to the gateway on plain http:

```toml
[network]
public_base_url = "https://dojo.example.com"
gateway_listen = "http://:8080"
lab_host_ip = "0.0.0.0"
trusted_proxies = "10.0.0.2/32"
```

On the proxy: `dojo.example.com { reverse_proxy <this-host>:8080 }`. Restrict a firewall rule so only the proxy
reaches 8080. `public_base_url` stays what browsers use (links, Forgejo clone URLs, the Secure cookie flag).

### A LAN class over https

Over plain `http://`, the class login, cookies and keystrokes cross the network in the clear; `dojo` warns. Either:

- **A real name** with a certificate from a proxy you run or Let's Encrypt (best); or
- **Caddy's local CA**: `public_base_url = "https://<lan-ip>:8443"`, `lab_host_ip = "0.0.0.0"`. Browsers warn until they
  trust the root: `podman cp workshop_gateway:/data/caddy/pki/authorities/local/root.crt .`. The root is new every run.

With an `https://` URL the gateway sends `Strict-Transport-Security: max-age=86400`, behind a proxy too.

### Access code in front of everything

`./dojo <workshop> --pass CODE` puts an access-code page before every URL, including sign-in. It sets a `dojo_gate`
cookie (sha256 of `dojo-gate:CODE`, 12 hours); the gateway admits only a matching cookie; wrong cookies are counted
(10 a minute per address, then 429). It needs https or localhost (the page hashes in the browser). It is a speed
bump, not a substitute for the real logins.

## Terminal flavor

Set `flavor` under `[terminal]` for the machine, in a workshop's `workshop.env` (`TERMINAL_FLAVOR`, which wins), or
for one run with `--terminal`. It is independent of `--env`. `zellij` removes code-server (the big per-student cost):
the VS Code tab, landing card and `/ide` route disappear, and the facilitator's watch tile uses `zellij watch`.

## Sizing the terminal

Run `./dojo capacity <workshop> --students N` on the target machine; `setup` offers to do it and writes the result
to `dojo.local.toml`. Three knobs bound the cost of code-server (see [Architecture](architecture.md#10-scale-and-capacity)):
the container-wide `mem_limit`/`pids_limit`, the per-process heap cap, and the grace/idle timers that release memory
from students who have left.
