"""Building only what changed, and cleaning up what rebuilds leave behind.

Change detection: each build context is hashed (hash_dir) and the hash is baked
into the image as the dojo.src-hash label; an image whose label matches is
reused as-is. Docker's own layer cache can't say "nothing changed" (apt-get
update layers bust on every upstream index change). The hash text is exactly
what dojo's shell version produced, so images it built stay valid.

Old-image cleanup: rebuilding a tag leaves the image it used to point at as an
untagged <none> image. Each build is wrapped in tracking that notes what it
displaced (one of our tagged images that lost its tag) or created untagged (a
multi-stage build's earlier stages); reap() removes them after `up -d`, when no
container pins them any more. Anything still pinned is retried next run.

Concurrency: the engine images build alongside the terminal chain (images()). The
chain streams its output, as the long build; each engine image's goes to a log
file, shown only when its build fails.

Shared files: one copy of a helper several module services use lives in
modules/_shared/. A module lists what it needs in its own module.env, as
SHARED="<context>/<file> ...": each lands in modules/<m>/<context>/_shared/
before anything is hashed, so a change to the shared copy rebuilds every user.
Those _shared/ folders are git-ignored and synced exactly (extra files removed).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set

from . import paths
from .envfiles import parse_literal
from .runtime import Runtime
from .ui import changed, console, ok

SUPERSEDED = paths.STATE / "superseded-images"
ENGINE_IMAGES = (("gitopsdojo/allocator:local", "./allocator"), ("gitopsdojo/gateway:local", "./gateway"),
                 ("gitopsdojo/presentation:local", "./presentation"))
_record_lock = threading.Lock()  # concurrent builds append to SUPERSEDED


def _files(context: str) -> List[str]:
    """Every regular file under context (symlinks not followed), as `find` names
    them, minus __pycache__/ and *.pyc (local Python runs leave those; images
    COPY named files)."""
    found = []
    for root, dirs, files in os.walk(paths.ENGINE / context):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in files:
            full = os.path.join(root, name)
            if os.path.islink(full) or not os.path.isfile(full) or name.endswith(".pyc"):
                continue
            rel = os.path.relpath(full, paths.ENGINE / context)
            shown = f"{context}/{rel}" if rel != "." else context
            if "/__pycache__/" in f"/{shown}/":
                continue
            found.append(shown)
    return sorted(found, key=lambda p: p.encode())


def hash_dir(context: str, salt: str = "") -> str:
    """sha256 over "<sha256>  <path>" per file (plus "exec <path>" for an
    executable one: COPY keeps the bit) and the salt line."""
    lines = []
    for f in _files(context):
        full = paths.ENGINE / f
        lines.append(f"{hashlib.sha256(full.read_bytes()).hexdigest()}  {f}\n")
        if os.stat(full).st_mode & 0o100:
            lines.append(f"exec {f}\n")
    if salt:
        lines.append(f"{salt}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()

def build_input_hash(build: Dict[str, object], salt: str = "", aliases: Optional[Dict[str, str]] = None) -> str:
    """Fingerprint a local Compose build context and its resolved build options."""
    context = build.get("context")
    if not isinstance(context, str):
        raise BuildError("a build context must be a local path to fingerprint")
    if "://" in context or context.startswith("git@"):
        raise BuildError(f"cannot fingerprint remote build context {context!r}; use a pinned local context")
    context_root = Path(context)
    if not context_root.is_absolute():
        context_root = paths.ENGINE / context_root
    if not context_root.is_dir():
        raise BuildError(f"build context does not exist: {context}")
    entries = []
    for path in _files(context):
        full = paths.ENGINE / path
        relative = Path(path).relative_to(Path(context)).as_posix()
        entries.append(f"{hashlib.sha256(full.read_bytes()).hexdigest()}  {relative}\n")
        if os.stat(full).st_mode & 0o100:
            entries.append(f"exec {relative}\n")
    context_hash = hashlib.sha256(("".join(entries) + salt + "\n").encode()).hexdigest()
    options = dict(build)
    options.pop("context", None)
    args = options.get("args")
    if isinstance(args, dict) and aliases:
        options["args"] = {key: aliases.get(str(value), value) for key, value in args.items()}
    serialized = json.dumps(options, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{context_hash}\n{serialized}".encode()).hexdigest()


def terminal_input_hashes(links: List[tuple], salt: str = "") -> Dict[str, str]:
    """Fingerprint terminal layers for normalizing their use as build args."""
    parent_hash = hashlib.sha256((hash_dir("./web-terminal", salt) + "\n").encode()).hexdigest()
    hashes = {}
    for image, context in links:
        build = {"context": context, "args": {"BASE": parent_hash}}
        parent_hash = build_input_hash(build, salt)
        hashes[image] = parent_hash
    return hashes


@dataclass
class Builder:
    rt: Runtime
    dry_run: bool = False
    ca_bundle: Optional[str] = None
    salt: str = ""
    would_build: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.rt.cli == "podman":
            # Podman's default OCI format has no HEALTHCHECK: it would drop the
            # images' health checks. Mixed into the hash so images an old run
            # cached in OCI format were rebuilt once.
            self.salt = "podman-build-format-docker"

    @property
    def env(self) -> Dict[str, str]:
        env = dict(os.environ)
        if self.rt.cli == "podman":
            env["BUILDAH_FORMAT"] = "docker"
        return env

    # --- image queries -----------------------------------------------------
    def label(self, image: str, key: str) -> str:
        return self.rt.out("inspect", "-f", f'{{{{ index .Config.Labels "{key}" }}}}', image).strip()

    def image_id(self, image: str) -> str:
        return self.rt.out("inspect", "-f", "{{.Id}}", image).strip()

    def image_with_label(self, key: str, value: str) -> str:
        ids = self.rt.out("images", "--filter", f"label={key}={value}", "--format", "{{.ID}}").split()
        return next((image_id for image_id in ids if self.label(image_id, key) == value), "")

    def tag_image(self, source: str, target: str) -> None:
        source_id = self.image_id(source)
        if source_id and source_id == self.image_id(target):
            return
        with self.tracking():
            res = self.rt.run("tag", source, target)
        if res.returncode != 0:
            raise BuildError(f"tagging {source} as {target} failed (exit {res.returncode}).")

    def _ids(self, dangling: bool) -> Set[str]:
        return set(self.rt.out("images", "--filter", f"dangling={str(dangling).lower()}", "--format", "{{.ID}}").split())

    def _ours(self) -> Set[str]:
        """Tagged images this project builds: gitopsdojo/* and Compose's names for
        overlay services (engine_x / engine-x). Only these are ever reaped."""
        ids = set()
        for line in self.rt.out("images", "--filter", "dangling=false", "--format", "{{.ID}} {{.Repository}}").splitlines():
            parts = line.split()
            if len(parts) == 2 and ("gitopsdojo/" in parts[1] or parts[1].split("/")[-1].startswith(("engine_", "engine-"))):
                ids.add(parts[0])
        return ids

    @contextmanager
    def tracking(self) -> Iterator[None]:
        before_ours, before_untagged = self._ours(), self._ids(True)
        try:
            yield
        finally:  # a failed or interrupted build can still have displaced a tag
            new = [i for i in self._ids(True) if i in before_ours or i not in before_untagged]
            if new:
                paths.STATE.mkdir(exist_ok=True)
                with _record_lock, SUPERSEDED.open("a") as fh:
                    fh.writelines(f"{i}\n" for i in new)

    def reap(self) -> None:
        if not SUPERSEDED.is_file():
            return
        untagged = self._ids(True)
        # Only an image untagged right now: a recorded ID can be tagged again (a
        # reverted change rebuilds the very same image).
        pending = [i for i in dict.fromkeys(SUPERSEDED.read_text().split()) if i in untagged]
        removed, progress = 0, True
        while pending and progress:  # a superseded image can be the parent of another
            progress, still = False, []
            for i in pending:
                if self.rt.run("rmi", i).returncode == 0:
                    removed, progress = removed + 1, True
                else:
                    still.append(i)
            pending = still
        if pending:
            SUPERSEDED.write_text("".join(f"{i}\n" for i in pending))
        else:
            SUPERSEDED.unlink(missing_ok=True)
        if removed:
            console.print(f"Removed {removed} superseded image(s) left behind by rebuilds.")
        if pending:
            console.print(f"Could not remove {len(pending)} superseded image(s) (still in use?); will retry on the next run.")

    # --- builds --------------------------------------------------------------
    def build_if_changed(self, image: str, context: str, extra: Optional[List[str]] = None,
                         salt_extra: str = "", with_ca: bool = False, quiet: bool = False,
                         input_hash: Optional[str] = None) -> None:
        """quiet: the build's output goes to a log file, shown only if it fails."""
        new_hash = input_hash or hash_dir(context, self.salt + salt_extra)
        if self.label(image, "dojo.src-hash") == new_hash:
            ok(f"{image}: unchanged")
            return
        existing = self.image_with_label("dojo.src-hash", new_hash)
        if existing:
            if self.dry_run:
                ok(f"{image}: matching image available, would reuse")
            else:
                self.tag_image(existing, image)
                ok(f"{image}: reused matching image")
            return
        if self.dry_run:
            changed(f"{image}: changed, would build")
            self.would_build.add(image)
            return
        changed(f"{image}: changed, building (this can take a few minutes)...")
        args = list(extra or [])
        if with_ca and self.ca_bundle:
            args += ["--secret", f"id=corp_ca_cert,src={self.ca_bundle}"]
        start = time.time()
        log, log_path = _open_build_log(image) if quiet else (None, "")
        try:
            with self.tracking():
                res = subprocess.run([self.rt.cli, "build", *args, "--label", f"dojo.src-hash={new_hash}",
                                      "-t", image, context], cwd=str(paths.ENGINE), env=self.env,
                                     stdout=log, stderr=subprocess.STDOUT if log else None)
        finally:
            if log:
                log.close()
        if res.returncode != 0:
            if log:
                tail = "\n".join(Path(log_path).read_text(errors="replace").splitlines()[-25:])
                console.print(tail, markup=False)
                raise BuildError(f"building {image} failed (exit {res.returncode}); the last lines of its output "
                                 f"are above, all of it is in {log_path}.")
            raise BuildError(f"building {image} failed (exit {res.returncode}); its output is above.")
        if log:
            os.unlink(log_path)
        secs = int(time.time() - start)
        ok(f"{image}: built in {secs // 60}:{secs % 60:02d}")

    def images(self, links: List[tuple], input_hashes: Optional[Dict[str, str]] = None) -> None:
        """The terminal chain and the engine images, built concurrently. Every build
        runs to the end, then the first failure is raised."""
        if self.dry_run:  # nothing builds: keep the report in a stable order
            self.terminal_chain(links, input_hashes)
            for image, context in ENGINE_IMAGES:
                self.build_if_changed(image, context)
            return
        with ThreadPoolExecutor(max_workers=1 + len(ENGINE_IMAGES)) as pool:
            jobs = [pool.submit(self.terminal_chain, links, input_hashes)]
            jobs += [pool.submit(self.build_if_changed, image, context, quiet=True) for image, context in ENGINE_IMAGES]
            errors = [j.exception() for j in jobs]
        for exc in errors:
            if exc is not None:
                raise exc

    def terminal_chain(self, links: List[tuple], input_hashes: Optional[Dict[str, str]] = None) -> None:
        """:core (the flavor-agnostic root both leaves build from), then each
        (image, context) link built FROM the one before -- the first link is
        always the one flavor leaf (web-terminal-vscode or zellij-terminal)
        this run selected (see start.py), so :core's code-server-free build
        never costs the Zellij flavor anything. A rebuilt parent rebuilds its
        children: the parent's image ID is part of each child's hash."""
        self.build_if_changed("gitopsdojo/web-terminal:core", "./web-terminal")
        parent = "gitopsdojo/web-terminal:core"
        for image, context in links:
            if parent in self.would_build:
                changed(f"{image}: parent changed, would build")
                self.would_build.add(image)
            else:
                self.build_if_changed(image, context, ["--build-arg", f"BASE={parent}"],
                                      salt_extra=self.image_id(parent), with_ca=True,
                                      input_hash=(input_hashes or {}).get(image))
            parent = image

    def overlay_if_changed(self, dirs: List[str], state_file, compose_cmd: List[str], env: Dict[str, str],
                           services: List[str], images: Optional[Dict[str, str]] = None,
                           hashes: Optional[Dict[str, str]] = None) -> None:
        """The modules' and overlay's own build: blocks (runner-pool, step-ca, ...).
        Compose labels each stable image alias with its build-input hash; one hash over their directories is kept in a
        state file. web-terminal/allocator/gateway/presentation are left out: Compose's
        build would overwrite their tags without our label.

        images ({service: stable image alias}) and hashes ({service: build input hash})
        are part of the state. A matching input hash under another pack's alias is
        re-tagged locally instead of rebuilt."""
        images = images or {}
        hashes = hashes or {}
        tags = "".join(f"{s}={images[s]}:{hashes.get(s, '')}\n" for s in sorted(images))
        new_hash = hashlib.sha256((tags + "".join(f"{hash_dir(d, self.salt)}\n" for d in dirs)).encode()).hexdigest()
        missing = {}
        for service, image in images.items():
            if self.label(image, "dojo.src-hash") == hashes.get(service):
                continue
            source = self.image_with_label("dojo.src-hash", hashes.get(service, "")) if hashes.get(service) else ""
            if source:
                if not self.dry_run:
                    self.tag_image(source, image)
                continue
            missing[service] = image
        unchanged = state_file.is_file() and state_file.read_text().strip() == new_hash
        if unchanged and not missing:
            ok("overlay images: unchanged")
            return
        if not missing:
            ok("overlay images: reused matching images")
            if not self.dry_run:
                state_file.parent.mkdir(exist_ok=True)
                state_file.write_text(new_hash + "\n")
            return
        if self.dry_run:
            changed("overlay images: changed, would build")
            return
        changed("overlay images: changed, building...")
        others = list(missing)
        if others:
            with self.tracking():
                res = subprocess.run([*compose_cmd, "build", *others], cwd=str(paths.ENGINE),
                                     env={**env, **({"BUILDAH_FORMAT": "docker"} if self.rt.cli == "podman" else {})})
            if res.returncode != 0:
                raise BuildError(f"building the overlay images failed (exit {res.returncode}); its output is above.")
        state_file.parent.mkdir(exist_ok=True)
        state_file.write_text(new_hash + "\n")


def shared_copies(modules: List[str]) -> Dict[Path, Path]:
    """{destination: source} for each module's SHARED= list. SHARED is read literally
    from the module's own module.env: every module.env is sourced into one run
    environment, where one module's list would overwrite another's."""
    wanted: Dict[Path, Path] = {}
    for m in modules:
        module_env = paths.MODULES / m / "module.env"
        rows = parse_literal(module_env) if module_env.is_file() else []
        for entry in next((v for k, v, _ in reversed(rows) if k == "SHARED"), "").split():
            context, _, name = entry.rpartition("/")
            src = paths.MODULES / "_shared" / name
            where = f"modules/{m}/module.env: SHARED entry '{entry}'"
            if not context or ".." in entry.split("/") or entry.startswith("/"):
                raise BuildError(f"{where} must be <context>/<file>, inside the module.")
            if not src.is_file():
                raise BuildError(f"{where}: no modules/_shared/{name}.")
            if not (paths.MODULES / m / context).is_dir():
                raise BuildError(f"{where}: no folder modules/{m}/{context}.")
            wanted[paths.MODULES / m / context / "_shared" / name] = src
    return wanted


def sync_shared(modules: List[str]) -> None:
    """Make each listed module's <context>/_shared/ hold exactly its SHARED files,
    copied byte for byte with their mode (hash_dir counts the exec bit)."""
    wanted = shared_copies(modules)
    for m in modules:
        for folder in (paths.MODULES / m).glob("**/_shared"):
            for f in folder.iterdir():
                if f not in wanted:
                    shutil.rmtree(f) if f.is_dir() and not f.is_symlink() else f.unlink()
            if not any(folder.iterdir()):
                folder.rmdir()
    for dst, src in wanted.items():
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            dst.parent.mkdir(exist_ok=True)
            shutil.copyfile(src, dst)
        shutil.copymode(src, dst)


def _open_build_log(image: str):
    for old in Path(tempfile.gettempdir()).glob("dojo-build.*"):  # failed builds keep their log a day
        try:
            if time.time() - old.stat().st_mtime > 86400:
                old.unlink()
        except FileNotFoundError:  # a concurrent build's log, gone with its success
            pass
    fd, log_path = tempfile.mkstemp(prefix=f"dojo-build.{image.split('/')[-1].replace(':', '-')}.")
    return os.fdopen(fd, "w"), log_path


class BuildError(Exception):
    pass
