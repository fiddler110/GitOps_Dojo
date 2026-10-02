"""Starting a workshop: `./run.sh <workshop> [flags]`, `restart`, `build-all`.

The steps, in order (each stops the run with a message that says what to do):
  1. resolve the environment (envfiles.resolve) and apply the safety gates:
     public passwords off loopback, the published port, plain HTTP;
  2. refuse a start over a different running workshop, take the run lock;
  3. build what changed (build.Builder): the terminal image chain, the engine
     images, the modules' and overlay's own images;
  4. check and render the extensions manifests (and the achievements catalog);
  5. record the run, mirror the lab docs, `compose up -d` (with
     --force-recreate for a restart), watch it settle (monitor.StartMonitor),
     explain anything that didn't, and reap superseded images.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import checks, paths, state
from .build import Builder, BuildError
from .envfiles import EnvError, Resolution, parse_literal, resolve
from .monitor import StartMonitor, explain_not_ready
from .runtime import Container, Runtime, project_name
from .stack import compose_args, extra_files, services
from .ui import bad, changed, console, fail, ok, step

MAX_BOTS = 35


class StartError(Exception):
    """Stops the run; the message is shown as is."""


@dataclass
class StartOptions:
    workshop: str
    test: Optional[str] = None            # None: no --test; "": bare --test; "N": N bots
    env_name: Optional[str] = None
    dry_run: bool = False
    build_only: bool = False
    allow_default_passwords: bool = False
    recreate: Optional[List[str]] = None  # restart: [] every container, [names] only those

    @property
    def flags(self) -> List[str]:
        """The flags as a start is recorded (for `restart` to repeat)."""
        out: List[str] = []
        if self.test is not None:
            out += ["--test"] + ([self.test] if self.test else [])
        if self.env_name:
            out += ["--env", self.env_name]
        if self.allow_default_passwords:
            out.append("--allow-default-passwords")
        return out


def parse_recorded(words: List[str]) -> StartOptions:
    """StartOptions from a recorded start ([workshop, *flags])."""
    o = StartOptions(words[0])
    i = 1
    while i < len(words):
        w = words[i]
        if w == "--test":
            o.test = ""
            if i + 1 < len(words) and words[i + 1].isdigit():
                o.test = words[i + 1]
                i += 1
        elif w.startswith("--test="):
            o.test = w.split("=", 1)[1]
        elif w == "--env" and i + 1 < len(words):
            o.env_name = words[i + 1]
            i += 1
        elif w.startswith("--env="):
            o.env_name = w.split("=", 1)[1]
        elif w == "--allow-default-passwords":
            o.allow_default_passwords = True
        i += 1
    return o


def bot_count(o: StartOptions, env: Dict[str, str]) -> Optional[str]:
    if o.test is None:
        return None
    if o.test == "":
        return env.get("BOT_COUNT") or "3"
    n = o.test.lstrip("0")
    if not n.isdigit() or not 1 <= int(n) <= MAX_BOTS:
        raise StartError(f"--test N: N must be between 1 and {MAX_BOTS}")
    return n


def sync_lab_docs(content_dir: Path) -> None:
    """content/lab/*.md -> content/slides/lab/*.md.txt: the slides server serves a
    .md.txt as a plain file (a .md it would render as a deck), and the lab reader
    renders it. Copies whose source is gone are removed."""
    src, dst = content_dir / "lab", content_dir / "slides" / "lab"
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("*.md.txt"):
        if not (src / old.name[:-len(".txt")]).is_file():
            old.unlink()
    for md in src.glob("*.md"):
        shutil.copyfile(md, dst / f"{md.name}.txt")


def run_once_cmd(rt: Runtime) -> List[str]:
    # Rootless podman already maps the container's root to us; rootful docker
    # needs --user or the files it writes into engine/ end up owned by root.
    if rt.cli == "podman":
        return ["podman", "run", "--rm"]
    return ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}"]


def _check_fragments(files: List[str]) -> None:
    """terminal_ingress is the gateway's only path to the students' IDE and
    terminal ports (remediation T2.2a); no module or overlay may join it.
    Comment lines may mention it."""
    for f in files:
        for n, line in enumerate((paths.ENGINE / f).read_text().splitlines(), 1):
            if ("terminal_ingress" in line or "web-terminal-ingress" in line) and not line.lstrip().startswith("#"):
                raise StartError(f"Refusing to start: {f}:{n} joins terminal_ingress, the gateway's private path to the\n"
                                 "students' IDE and terminal ports. Use workshop_lab (see workshops/README.md).")


def _env_keys(files: List[Path]) -> List[str]:
    keys = set()
    for f in files:
        keys.update(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=", f.read_text(), re.M))
    return sorted(keys)


@dataclass
class Plan:
    """What one start resolved, handed from step to step."""
    o: StartOptions
    rt: Runtime
    res: Resolution
    project: str
    links: List[Tuple[str, str]]   # the terminal image chain: (image, build context)
    files: List[str]               # the extra Compose files, relative to engine/
    overlay_dirs: List[str]        # the modules' and overlay's own build contexts
    ca: str                        # corporate CA bundle for the terminal build, or ""
    running: List[Container] = field(default_factory=list)
    _services: List[str] = field(default_factory=list)

    @property
    def env(self) -> Dict[str, str]:
        return self.res.env

    @property
    def workshop_dir(self) -> Path:
        return paths.WORKSHOPS / self.o.workshop

    @property
    def compose(self) -> List[str]:
        return [*self.rt.compose_cmd, *compose_args(self.files)]

    def services(self) -> List[str]:
        """This run's Compose services (asked once: it runs `compose config`)."""
        if not self._services:
            try:
                self._services.extend(services(self.rt, self.files, self.env))
            except RuntimeError as exc:
                raise StartError(f"Could not list this run's Compose services ('compose {' '.join(compose_args(self.files))} "
                                 f"config --services' failed):\n{exc}")
        return self._services


def run_start(o: StartOptions) -> int:
    t_start = time.time()
    try:
        code = _start(o)
    except (StartError, EnvError, BuildError) as exc:
        fail(str(exc))
        code = 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/]")
        code = 130
    if not o.dry_run:
        action = "restart" if o.recreate is not None else "build" if o.build_only else "start"
        state.record(action, o.workshop, o.flags, time.time() - t_start, "ok" if code == 0 else f"exit {code}")
    return code


def _start(o: StartOptions) -> int:
    from .workshops import NAME_RE
    if not NAME_RE.match(o.workshop):
        raise StartError(f"'{o.workshop}' is not a workshop name (lowercase letters, digits and '-').\n"
                         "Run './run.sh list' to see available workshops.")
    if o.env_name is not None and not NAME_RE.match(o.env_name):
        raise StartError("--env expects a name (lowercase letters, digits and '-'), e.g. --env home")
    rt = Runtime()
    if not rt.available:
        raise StartError("Neither podman (with podman-compose) nor docker was found; './run.sh doctor' explains.")

    p = _plan(o, rt)
    _check_running(p)
    lock = None if o.dry_run else state.RunLock(o.workshop)
    if lock:
        lock.acquire()
    try:
        return _build_and_up(p)
    finally:
        if lock:
            lock.release()


def _plan(o: StartOptions, rt: Runtime) -> Plan:
    """Step 1: the environment, the safety gates, and what this run will build and start."""
    res = resolve(o.workshop, o.env_name)
    env = res.env
    for w in res.warnings:
        console.print(f"[yellow]WARNING: {w}[/]")
    _safety_gates(o, env)

    if o.dry_run:
        console.print("DRY RUN -- nothing will be built or started (manifests are checked in .generated/dry-run/).")
        console.print(f"Workshop:  {o.workshop} ({env.get('WORKSHOP_NAME') or o.workshop})")
        console.print(f"Content:   {env.get('WORKSHOP_CONTENT_DIR') or '<unset>'}")
        console.print(f"Modules:   {' '.join(res.modules) or 'none'}")
        console.print(f"Overlay:   {env.get('COMPOSE_OVERLAY') or 'none'}")
        console.print()

    bots = bot_count(o, env)
    if bots is not None:
        env["BOT_COUNT"] = bots
        verb = "would start" if o.dry_run else "starting"
        console.print(f"Test mode: {verb} {bots} demo bot student(s) (prefix: {env.get('BOT_PREFIX') or 'testuser'}).")
        if int(bots) > 3:
            console.print(f"           testuser1-3 = expert/intermediate/novice; the other {int(bots) - 3} get a random one of those.")

    ca = env.get("CORP_CA_BUNDLE") or env.get("REQUESTS_CA_BUNDLE") or ""
    if ca and os.path.isfile(ca):
        console.print(f"Using corporate CA bundle for the web-terminal build: {ca}")
    else:
        ca = ""

    # The terminal image chain: :base -> each module's terminal/ -> the workshop's.
    links = [(f"gitopsdojo/web-terminal:{o.workshop}.{m}", f"../modules/{m}/terminal")
             for m in res.modules if (paths.MODULES / m / "terminal").is_dir()]
    if (paths.WORKSHOPS / o.workshop / "compose" / "terminal").is_dir():
        links.append((f"gitopsdojo/web-terminal:{o.workshop}", f"../workshops/{o.workshop}/compose/terminal"))
    env["WEB_TERMINAL_IMAGE"] = links[-1][0] if links else "gitopsdojo/web-terminal:base"

    files = extra_files(res)
    overlay_dirs = [f"../modules/{m}" for m in res.modules if (paths.MODULES / m / "compose.yml").is_file()]
    if env.get("COMPOSE_OVERLAY"):
        overlay_dirs.append(os.path.dirname(env["COMPOSE_OVERLAY"]))
    _check_fragments(files)
    return Plan(o, rt, res, project_name(env), links, files, overlay_dirs, ca)


def _safety_gates(o: StartOptions, env: Dict[str, str]) -> None:
    mismatch = checks.port_mismatch(env)
    if mismatch:
        console.print(f"[yellow]WARNING: {mismatch} Links the lab prints won't load.[/]")
    weak = checks.default_passwords(env)
    if weak and not checks.local_only(env) and not o.build_only:
        if o.allow_default_passwords or env.get("ALLOW_DEFAULT_PASSWORDS") == "1":
            console.print(f"[yellow]WARNING: default passwords in use ({' '.join(weak)}) on {env.get('PUBLIC_BASE_URL')},\n"
                          "         reachable beyond this machine (--allow-default-passwords / ALLOW_DEFAULT_PASSWORDS=1).[/]")
        else:
            raise StartError(
                f"Refusing to start: default passwords ({' '.join(weak)}) with PUBLIC_BASE_URL={env.get('PUBLIC_BASE_URL')}\n"
                f"and LAB_HOST_IP={env.get('LAB_HOST_IP') or '<unset>'}, i.e. reachable beyond this machine. Anyone who has seen\n"
                "'./run.sh setup --default' can sign in. Generate real ones with './run.sh setup --force'\n"
                "(then set PUBLIC_BASE_URL/LAB_HOST_IP again if engine/.env had them), or pass\n"
                "--allow-default-passwords (or ALLOW_DEFAULT_PASSWORDS=1 in .env.<name>) to start anyway.")
    if not env.get("STUDENT_PASSWORD_SEED"):
        console.print("[yellow]WARNING: no STUDENT_PASSWORD_SEED in engine/.env: every student's Forgejo password is the\n"
                      "         shared STUDENT_PASSWORD. Add one ('openssl rand -hex 32') or run './run.sh setup'.[/]")
    if checks.plain_http_offbox(env):
        console.print(f"[yellow]WARNING: PUBLIC_BASE_URL={env.get('PUBLIC_BASE_URL')} is plain HTTP beyond this machine: passwords,\n"
                      "         cookies and terminal input travel unencrypted. For a class, use HTTPS: a real\n"
                      "         name, or a TLS proxy in front (engine/README.md, \"LAN class over HTTPS\").[/]")


def _check_running(p: Plan) -> None:
    """Step 2: refuse a start over a different running stack; check restart's service names."""
    o = p.o
    p.running = p.rt.containers(p.project)
    if p.running and not o.build_only:
        cur = state.read_current()
        if cur is None or cur.workshop != o.workshop or cur.files != p.files:
            who = cur.workshop if cur and cur.workshop else "a stack this checkout didn't start"
            if cur is not None and cur.workshop == o.workshop and not o.dry_run:
                added = [f for f in p.files if f not in cur.files]
                gone = [f for f in cur.files if f not in p.files]
                raise StartError(f"Refusing to start: {o.workshop} is running with other Compose files "
                                 f"(now adds {' '.join(added) or 'nothing'}, drops {' '.join(gone) or 'nothing'}).\n"
                                 "Start it with the same settings (MODULES, ACHIEVEMENTS_ENABLED), or './run.sh stop' "
                                 "first (it deletes every volume).")
            if o.dry_run:
                bad(f"{who} is still running: a real start would refuse until './run.sh stop'.")
                console.print()
            else:
                raise StartError(f"Refusing to start: {who} is still running. Starting {o.workshop} over it\n"
                                 "would leave its extra services and volumes behind. Run './run.sh stop' first\n"
                                 "(it deletes every volume: student homes and Forgejo data).")
    if o.recreate:
        unknown = [s for s in o.recreate if s not in p.services()]
        if unknown:
            raise StartError(f"restart: {', '.join(unknown)} is not a service of {o.workshop}. "
                             f"Its services: {' '.join(p.services())}")
        if not p.running:
            raise StartError(f"restart: {o.workshop} isn't running; './run.sh restart' (no service names) starts all of it.")


def _build_and_up(p: Plan) -> int:
    """Steps 3-5, under the run lock."""
    b = _build_images(p)
    if p.o.build_only:
        if not p.o.dry_run:
            b.reap()
        return 0
    _render_extensions(p)
    if p.o.dry_run:
        return _dry_run_checks(p)
    rc = _compose_up(p)
    if rc == 0:
        b.reap()
    return rc


def _build_images(p: Plan) -> Builder:
    """Step 3: build what changed. The Builder is returned to reap superseded images once the start succeeds."""
    step("Checking images (dry run)" if p.o.dry_run else "Checking images")
    b = Builder(p.rt, dry_run=p.o.dry_run, ca_bundle=p.ca or None)
    b.images(p.links)
    if p.overlay_dirs:
        b.overlay_if_changed(p.overlay_dirs, paths.STATE / f"{p.o.workshop}.overlay-hash", p.compose, p.env, p.services())
    return b


def _render_extensions(p: Plan) -> None:
    """Step 4: check the achievements catalog, render the manifests into .generated/,
    and add each routed upstream's token to the environment."""
    gen = paths.ENGINE / (".generated/dry-run" if p.o.dry_run else ".generated")
    shutil.rmtree(gen / "in", ignore_errors=True)
    for d in ("in", "gateway", "allocator"):
        (gen / d).mkdir(parents=True, exist_ok=True)
    modules = p.res.modules
    for n, m in enumerate(modules, 10):  # modules first (50-...), in MODULES order, then the workshop (90-...)
        manifest = paths.MODULES / m / "extensions.json"
        if manifest.is_file():
            shutil.copyfile(manifest, gen / "in" / f"50-{n}-module-{m}.json")
    if (p.workshop_dir / "extensions.json").is_file():
        shutil.copyfile(p.workshop_dir / "extensions.json", gen / "in" / f"90-workshop-{p.o.workshop}.json")
    if not p.rt.out("image", "inspect", "--format", "{{.Id}}", "gitopsdojo/allocator:local"):
        console.print("Extensions: not checked (the allocator image isn't built yet; a real run builds it first).")
    else:
        once = run_once_cmd(p.rt)
        _check_catalog(p, once)
        # ${NAME} in a manifest may name any variable workshop.env or a module.env sets:
        # those are passed through by name (never .env, which holds the secrets).
        env_files = [p.workshop_dir / "workshop.env"] + [paths.MODULES / m / "module.env" for m in modules
                                                         if (paths.MODULES / m / "module.env").is_file()]
        ext_env = [a for k in _env_keys(env_files) for a in ("-e", k)]
        # GATEWAY_TOKEN (by name, never on the command line) derives each upstream's own token (FIND-16).
        r = subprocess.run([*once, "--network", "none", *ext_env, "-e", "GATEWAY_TOKEN",
                            "-v", f"{gen}:/gen", "-v", f"{paths.ENGINE / 'allocator' / 'render_extensions.py'}:/render_extensions.py:ro",
                            "gitopsdojo/allocator:local", "python3", "-B", "/render_extensions.py",
                            "--in", "/gen/in", "--out", "/gen", "--services", " ".join(p.services()) + " "], env=p.env)
        if r.returncode != 0:
            raise StartError("The workshop's extensions.json was rejected (see above); nothing was started.")
    tokens = gen / "upstream-tokens.env"
    if tokens.is_file():  # GATEWAY_TOKEN_<SERVICE>: each routed upstream's own token (FIND-16)
        p.env.update({k: v for k, v, _ in parse_literal(tokens)})


def _check_catalog(p: Plan, once: List[str]) -> None:
    catalog = p.workshop_dir / "achievements"
    if p.env.get("ACHIEVEMENTS_ENABLED") != "1" or not (catalog / "catalog.json").is_file():
        return
    r = subprocess.run([*once, "--network", "none",
                        "-v", f"{paths.MODULES / 'achievements'}:/opt/achievements:ro",
                        "-v", f"{catalog}:/w/{p.o.workshop}/achievements:ro",
                        "gitopsdojo/allocator:local", "python3", "-B", "/opt/achievements/catalog/validate.py",
                        f"/w/{p.o.workshop}"], env=p.env)
    if r.returncode != 0:
        raise StartError("The workshop's achievements catalog was rejected (see above); nothing was started.")


def _dry_run_checks(p: Plan) -> int:
    console.print()
    step("Checking the Compose config")
    ok(f"valid ({len(p.services())} services)")
    console.print()
    step("Checking image pins")
    pins = subprocess.run(["sh", "scripts/check-pins.sh"], cwd=str(paths.ENGINE), capture_output=True, text=True)
    if pins.returncode == 0:
        ok("every external image pinned by digest")
    else:
        for line in (pins.stdout + pins.stderr).strip().splitlines()[:-2]:
            bad(line)
        bad("not pinned: add @sha256:<digest> (see scripts/check-pins.sh)")
    console.print()
    console.print(f"Would run: compose {' '.join(compose_args(p.files))} up -d")
    if pins.returncode != 0:
        fail("Dry run complete: nothing was built or started, but unpinned images were found.")
        return 1
    console.print("Dry run complete: nothing was built or started.")
    return 0


def _compose_up(p: Plan) -> int:
    """Step 5: record the run, mirror the lab docs, `compose up -d` and watch it settle."""
    state.write_current(state.Current(p.o.workshop, p.o.flags, p.files, p.o.env_name, time.time()))
    for d in paths.WORKSHOPS.glob("*/content"):  # dojo-introduction shows other packs' labs too
        sync_lab_docs(d)
    content = p.env.get("WORKSHOP_CONTENT_DIR", "")
    if content:
        sync_lab_docs(paths.ENGINE / content)

    up_extra = _up_args(p)
    step("Creating networks and volumes, then starting containers in dependency order")
    live = console.is_terminal
    log_file, log_path = _open_up_log() if live else (None, "")
    if not live:
        console.print("A line appears below whenever a container changes state or logs progress; "
                      "'still waiting on' names what is holding things up.")
    mon = StartMonitor(p.rt, p.project, p.services(), live)
    t0 = time.time()
    mon.start()
    proc = None
    try:
        proc = subprocess.Popen([*p.compose, "up", "-d", *up_extra], cwd=str(paths.ENGINE), env=p.env,
                                stdout=log_file or None, stderr=subprocess.STDOUT if log_file else None)
        rc = proc.wait()
        if rc == 0:
            mon.wait_until_ready(float(p.env.get("STARTUP_WAIT") or 300))
    except KeyboardInterrupt:
        if proc is not None and proc.poll() is None:
            proc.terminate()
        mon.stop(final=False)
        raise
    mon.stop()
    if log_file:
        log_file.close()
        if rc != 0:
            bad(f"compose failed (exit {rc}); the last lines of its output:")
            console.print("\n".join(Path(log_path).read_text().splitlines()[-20:]), markup=False)
        else:
            os.unlink(log_path)
    secs = int(time.time() - t0)
    ok(f"Compose finished in {secs // 60}:{secs % 60:02d}")
    problems = mon.not_ready()
    if problems:
        changed("not ready yet: " + ", ".join(f"{c.service} ({c.status})" for c in problems))
        explain_not_ready(p.rt, problems)
    if rc != 0:
        console.print("The run stays recorded so `./run.sh stop` can remove what did start; "
                      "fix the error, then `./run.sh stop` and start again.")
    return rc


def _up_args(p: Plan) -> List[str]:
    """Says what is being started; returns the extra `compose up` arguments for a restart."""
    o = p.o
    if o.recreate:
        also = p.rt.dependents(p.running, o.recreate)
        step(f"Restarting {' '.join(o.recreate)} in '{o.workshop}' (volumes kept)")
        if also:
            console.print(f"Also recreating {' '.join(also)}: they depend on it, and podman can't replace a "
                          "container others depend on.")
        return ["--force-recreate", "--no-deps", *o.recreate, *also]
    if o.recreate is not None:
        step(f"Restarting workshop '{o.workshop}' ({p.env.get('WORKSHOP_NAME') or o.workshop}): every container recreated, volumes kept")
        return ["--force-recreate"]
    step(f"Starting workshop '{o.workshop}' ({p.env.get('WORKSHOP_NAME') or o.workshop})")
    return []


def _open_up_log():
    """A temp file for compose's own output while the live view owns the screen."""
    for old in Path(tempfile.gettempdir()).glob("dojo-up.*"):  # failed starts keep their log a day
        if time.time() - old.stat().st_mtime > 86400:
            old.unlink(missing_ok=True)
    fd, log_path = tempfile.mkstemp(prefix="dojo-up.")
    console.print(f"Compose output is in {log_path} (deleted once the start succeeds)")
    return os.fdopen(fd, "w"), log_path


def run_restart(services_: List[str], clean: bool) -> int:
    last = state.last_start()
    if not last:
        fail("Nothing to restart: no workshop has been started from this checkout yet ('./run.sh <workshop>').")
        return 1
    o = parse_recorded(last)
    if clean:
        if services_:
            fail("--clean restarts the whole stack; leave out the service names.")
            return 1
        from .stop import run_stop
        console.print(f"Clean restart: './run.sh stop', then './run.sh {' '.join(last)}'.")
        code = run_stop(dry_run=False)
        if code != 0:
            return code
        return run_start(o)
    o.recreate = list(services_)
    # Achievements are the one module the environment (not workshop.env) switches on:
    # repeat what the running start did unless this shell says otherwise.
    cur = state.read_current()
    if cur and cur.workshop == o.workshop and "ACHIEVEMENTS_ENABLED" not in os.environ:
        on = any(f.endswith("/achievements/compose.yml") for f in cur.files)
        os.environ["ACHIEVEMENTS_ENABLED"] = "1" if on else "0"
    return run_start(o)


def run_build_all(env_name: Optional[str], dry_run: bool) -> int:
    from .workshops import workshops
    from .ui import ok as say_ok
    built, failed = [], []
    for w in workshops():
        step(f"Building {w.name}")
        code = run_start(StartOptions(w.name, env_name=env_name, dry_run=dry_run, build_only=True))
        (built if code == 0 else failed).append(w.name)
    console.print()
    if built:
        say_ok("built or up to date: " + " ".join(built))
    if failed:
        bad("failed: " + " ".join(failed))
        return 1
    return 0
