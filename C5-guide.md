# C5 test guide: the dojo CLI on a Mac

Roadmap item C5 lists the paths only a Mac or Docker host can test: Docker instead of podman, macOS's system Python
3.9, `CORP_CA_BUNDLE` for the first-run download, and zsh completion in a real shell. Work through the steps in
order and note what each one printed. If a step fails, keep its full output; a failed engine-image build also prints
the path of its log. Delete this file once C5 is closed.

## 0. Get the branch

```bash
git clone <repo> && cd GitOps_Dojo    # or, in an existing clone:
git fetch && git switch feat/achievements && git pull
```

## 1. Prerequisites

- Docker Desktop, running (`docker info` works), and git.
- To test Docker, **don't install `podman-compose`**. The CLI uses podman only when both `podman` and `podman-compose`
  are on the PATH, and Docker otherwise.
- Nothing else: the CLI brings its own hash-pinned Python packages.

## 2. The system Python and the first-run download

```bash
/usr/bin/python3 --version      # expect 3.9.x (Xcode command-line tools)
which python3                   # if this isn't /usr/bin/python3, also try: PATH=/usr/bin:$PATH ./dojo list
./dojo list
```

The first run downloads the wheels into `engine/.cache/`, so `list` tests both Python 3.9 and the download.

**Behind TLS inspection** (a work network), test the corporate-CA path from a clean cache:

```bash
rm -rf engine/.cache
export CORP_CA_BUNDLE=/path/to/corporate-ca.pem
./dojo list
```

Also worth seeing once: the same thing *without* `CORP_CA_BUNDLE`, to check the error message says what to do.

## 3. Unit tests on Python 3.9

```bash
PYTHONPATH=engine:$(echo engine/.cache/pylib-*) /usr/bin/python3 -B -m unittest discover -s engine/dojo/tests -t engine
(cd engine/allocator && /usr/bin/python3 -B -m unittest discover -s tests)
```

## 4. Setup and a plain workshop under Docker

```bash
./dojo setup --default        # writes `.env`; also runs the capacity sizing
./dojo doctor                 # "Container engine" should say docker
./dojo git-fundamentals --dry-run
./dojo git-fundamentals       # the first build is cold and takes a while
```

- On Apple Silicon this also tests the arm64 downloads and checksums of the terminal tools.
- Open `http://localhost:8080`: the class login and the facilitator login (`/admin`) both work, and a student gets a
  terminal and VS Code.

Then the lifecycle commands:

```bash
./dojo status
./dojo logs gateway
./dojo restart gateway
./dojo restart
./dojo stop
docker ps -a                    # no dojo containers left
docker volume ls | grep engine_ # prints nothing
```

## 5. A workshop with modules

```bash
./dojo dns-as-code --dry-run
./dojo dns-as-code
./dojo restart dns-server     # also recreates what depends on it under podman
./dojo stop
```

This exercises module builds, overlays and container names under Docker. The one-service restart is where Docker
and podman differ most: podman won't remove a container others are linked to, so the CLI recreates them too; under
Docker only `dns-server` should be recreated, and the stack should keep working.

## 6. The `dojo` command and tab completion in zsh

```bash
./dojo alias-setup             # writes ~/.local/bin/dojo; on macOS also adds ~/.local/bin to PATH
exec zsh                         # a fresh interactive shell
which dojo                       # ~/.local/bin/dojo
cd ~ && dojo status              # works from any directory; help and advice say 'dojo ...'
dojo <Tab>                       # commands and workshops, with descriptions
dojo restart <Tab>               # needs a running stack: its services
dojo git-fundamentals --<Tab>    # the start options
./dojo <Tab>                   # the same completion for ./dojo
```

## 7. The shell scripts on macOS

`setup`, `capacity` and `alias-setup` are still shell scripts, so these are the likeliest to trip over macOS's bash
3.2 and the BSD tools (`sed`, `awk`, `mktemp`, `stat`):

```bash
./dojo capacity --students 10
./dojo setup                   # the interactive path: answer a few prompts, then check `.env`
./dojo alias-setup             # run it twice: the block in ~/.zshrc is replaced, not duplicated
./dojo alias-setup --remove    # then once more to put it back
```

## What to report back

For each step: passed, or the command plus its output. Also the macOS version, Intel or Apple Silicon, the Docker
Desktop version and `/usr/bin/python3 --version`.
