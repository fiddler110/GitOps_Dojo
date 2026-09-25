# Local PowerDNS Stack — Free Alternative to a Real Domain

This is the **recommended path** if you want to keep doing all five DNS-as-
Code labs without spending any money or owning a real domain. It mimics
the workshop's PowerDNS container on your own machine, using the same
`dojo.test` reserved test zone you already practiced against.

If you'd rather practice against a real domain and real Cloudflare DNS
instead (more realistic, but costs a small amount and takes longer to set
up), see [02-cloudflare-domain-setup.md](02-cloudflare-domain-setup.md).
You can also do both — nothing here conflicts with that.

---

## What you need

- **Docker Desktop** (Mac/Windows) or **Docker Engine + Compose plugin**
  (Linux) — free. <https://docs.docker.com/get-started/get-docker/>
- **dnscontrol** — the CLI tool that reads `dnsconfig.js` and reconciles
  PowerDNS to match it.
- **dig** — for querying DNS records directly (part of `dnsutils` /
  `bind-utils` depending on your OS).
- Everything from [00-github-setup.md](00-github-setup.md) — Git, and a
  GitHub account for the actual clone/branch/PR workflow.

### Install dnscontrol

```sh
# macOS (Homebrew)
brew install dnscontrol

# Linux / manual install (any OS) — grab a release binary
# https://github.com/DNSControl/dnscontrol/releases
```

Verify:

```sh
dnscontrol version
```

### Install dig

```sh
# macOS (Homebrew)
brew install bind

# Debian/Ubuntu
sudo apt install dnsutils

# Fedora/RHEL
sudo dnf install bind-utils
```

Verify:

```sh
dig -v
```

---

## 1. Start the local PowerDNS stack

Copy [`docker-compose.yml`](docker-compose.yml) from this handout folder
into an empty directory (or leave it here and just point `docker compose`
at it), then:

```sh
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml ps    # confirm dns-server is "running"
```

This starts a single PowerDNS authoritative server, with:

- Its HTTP API (what `dnscontrol` actually talks to) on `127.0.0.1:8081`.
- DNS itself on `127.0.0.1:5353` (not the standard port 53 — see the
  comment in the compose file for why).

It's ephemeral by design, same as the workshop: `docker compose down`
wipes it, and `docker compose up -d` again starts a fresh, empty
PowerDNS. `dnsconfig.js` is always your real source of truth — after a
reset, just `dnscontrol push` again to repopulate it.

---

## 2. Set up your DNS-as-code repo

Follow [00-github-setup.md](00-github-setup.md) if you haven't — you need
a GitHub repo, cloned locally, before continuing. Then copy this
handout's [`starter-repo/`](starter-repo/) contents into it:

```sh
# from inside your cloned dns-as-code-practice/ repo
cp -r /path/to/handouts/dns-as-code/starter-repo/. .

git add .
git commit -m "Initial dnsconfig.js"
git push -u origin main
```

`starter-repo/creds.json` already points at `http://127.0.0.1:8081` with
the same API key the compose file sets by default (`local-practice-key`)
— no editing needed unless you changed one of them.

---

## 3. Run the same workflow as the workshop

From here, every step in [lab1.md](lab1.md) through [lab5.md](lab5.md)
works exactly as written, with one difference: **there's no CI
automatically running `dnscontrol push` for you on merge** (see "Why
there's no automatic CI" below), so after merging a pull request, pull
`main` and run `dnscontrol push` yourself:

```sh
dnscontrol preview     # dry-run diff — safe, changes nothing
dnscontrol push        # apply it for real
dig @127.0.0.1 -p 5353 dojo.test A +short   # verify it's actually live
```

Each lab file and [cheat-sheet.md](cheat-sheet.md) call out `@dns-server`
as the workshop's query target — on your own machine, that's
`@127.0.0.1 -p 5353` instead. Everything else (record syntax, `preview`
output, `dnsctl.py`) is identical.

---

## Why there's no automatic CI

The workshop's "merge triggers CI which runs `dnscontrol push`
automatically" step relied on a Forgejo Actions runner living on the
*same internal Docker network* as the PowerDNS container. A GitHub-hosted
Actions runner lives in GitHub's cloud — it has no route to
`127.0.0.1:8081` on your laptop, so it can't reach your local PowerDNS no
matter how you configure the workflow file.

Running `dnscontrol push` by hand after each merge (step 3, above) is the
honest, simple equivalent and is exactly what a lot of small real-world
setups do. If you want the full "merge → CI applies it" experience
anyway, see the advanced section below.

---

## Advanced (optional): wiring up real GitHub Actions CI

This is a stretch goal for after you're comfortable with the manual
loop — not required to complete any of the five labs.

GitHub Actions can run jobs on **your own machine** instead of GitHub's
cloud, via a *self-hosted runner*, which _does_ have a route to
`127.0.0.1:8081`. Rough shape (expect to spend real time on this — it's
a genuinely more advanced setup):

1. In your repo on GitHub: **Settings → Actions → Runners → New
   self-hosted runner**, and follow GitHub's own instructions to
   download, configure, and start the runner on your machine
   (<https://docs.github.com/en/actions/hosting-your-own-runners>).
2. This handout's [`advanced-github-actions/`](advanced-github-actions/)
   folder has `preview.yml` and `apply.yml` already written for this
   (`runs-on: self-hosted`, real `actions/checkout@v4`, GitHub's own REST
   API instead of the workshop's internal Forgejo one — filenames match
   what `scripts/dnsctl.py` already expects at
   `.github/workflows/apply.yml`, see its `APPLY_TRIGGER_PATHS`). They're
   kept separate from `starter-repo/` on purpose — copy them into your
   repo's `.github/workflows/` only once you actually have a self-hosted
   runner registered and running; otherwise every PR gets a check that
   queues forever with nothing to run it.
3. Push and open a PR — the preview workflow should comment on it; merge
   should trigger the apply workflow.

Keep the runner process running only while you're actively practicing —
stop it (`Settings → Actions → Runners` → remove, or just stop the local
process) when you're done, since it's a process on your machine with
access to your GitHub repo.

---

## Tearing down / resetting

```sh
docker compose -f docker-compose.yml down     # stop and remove the container
docker compose -f docker-compose.yml up -d    # start a fresh, empty PowerDNS
```

After a reset, `dnscontrol push` repopulates everything from
`dnsconfig.js` — nothing is lost, since the file (in git) was always the
real source of truth, not whatever happened to be loaded into PowerDNS.
