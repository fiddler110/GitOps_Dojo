"""Entry point for the dojo CLI. Standard library only.

Makes the pinned dependencies in requirements.lock importable, then hands over
to dojo.cli. The first run downloads each wheel, checks its sha256 and unpacks
it into engine/.cache/pylib-<hash of the lock file>/; later runs only add that
folder to sys.path. No pip, no venv (Debian/WSL pythons often have neither).
A corporate TLS-inspection CA is honoured the same way the image builds do it:
CORP_CA_BUNDLE, else REQUESTS_CA_BUNDLE, else SSL_CERT_FILE.
"""
import hashlib
import os
import shutil
import ssl
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in engine/

MIN_PYTHON = (3, 9)
HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
LOCK = HERE / "requirements.lock"
CACHE = ENGINE / ".cache"


def _fail(msg):
    sys.stderr.write(f"dojo: {msg}\n")
    sys.exit(1)


def _locked():
    rows = []
    for line in LOCK.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, version, sha, url = line.split()
            rows.append((name, version, sha, url))
    return rows


def _ssl_context():
    cafile = next((os.environ[v] for v in ("CORP_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE")
                   if os.environ.get(v) and os.path.isfile(os.environ[v])), None)
    return ssl.create_default_context(cafile=cafile)


def _install(target):
    """Download, verify and unpack every locked wheel into target (atomically:
    a half-finished run leaves nothing that looks complete)."""
    CACHE.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="pylib-staging-", dir=CACHE))
    ctx = _ssl_context()
    try:
        for name, version, sha, url in _locked():
            sys.stderr.write(f"dojo: fetching {name} {version} (first run only)\n")
            try:
                with urllib.request.urlopen(url, timeout=60, context=ctx) as resp:
                    data = resp.read()
            except OSError as exc:
                _fail(f"could not download {url}: {exc}\n"
                      "  The first run needs internet access to PyPI (files.pythonhosted.org).\n"
                      "  Behind TLS inspection, point CORP_CA_BUNDLE at your CA bundle.")
            got = hashlib.sha256(data).hexdigest()
            if got != sha:
                _fail(f"{name} {version}: sha256 {got} does not match the pinned {sha}; not using it.")
            whl = staging / url.rsplit("/", 1)[1]
            whl.write_bytes(data)
            with zipfile.ZipFile(whl) as zf:
                zf.extractall(staging)
            whl.unlink()
        (staging / ".complete").write_text("ok\n")
        try:
            staging.rename(target)
        except OSError:
            if not (target / ".complete").exists():  # lost a race to another run that finished: fine
                raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    # Older lock files' folders are no longer used.
    for old in CACHE.glob("pylib-*"):
        if old != target and not old.name.startswith("pylib-staging-"):
            shutil.rmtree(old, ignore_errors=True)


def ensure_dependencies():
    target = CACHE / f"pylib-{hashlib.sha256(LOCK.read_bytes()).hexdigest()[:16]}"
    if not (target / ".complete").exists():
        _install(target)
    sys.path.insert(0, str(target))
    sys.path.insert(0, str(ENGINE))


def main():
    if sys.version_info < MIN_PYTHON:
        _fail(f"needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer (this is {sys.version.split()[0]}).")
    ensure_dependencies()
    from dojo.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
