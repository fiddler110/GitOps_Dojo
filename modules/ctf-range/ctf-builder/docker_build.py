"""The build/push half of the S6 loop, run ONLY by ctf-builder — never by
ctf-controller (see ../ctf-controller/docker_api.py's docstring for why build
stays out of the controller's reach: it is the most dangerous call of all).

ctf-builder's reach into ctf-host is narrow in a different, equally fixed way:
it can build and push exactly ONE tag it derives itself — the slot's own name
under the approved registry prefix (image_tag_for) — from a tar it made
itself of a clone it made itself (gitref.py). It never accepts an arbitrary
build context, Dockerfile or tag from its caller, and it never creates,
starts, stops or removes a container; that whole capability stays
ctf-controller's alone. See tests/test_docker_build.py.
"""
import http.client
import json
import socket
from urllib.parse import quote, urlencode

IMAGE_NAME = "ctf-customer-portal"


class DockerError(Exception):
    pass


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def repo_ref(registry_prefix, image=IMAGE_NAME):
    """The repo (no tag) ctf-builder is ever allowed to push to — always
    under the approved in-lab registry prefix, never a Hub name."""
    return f"{registry_prefix}/{image}"


def image_tag_for(user, registry_prefix, image=IMAGE_NAME):
    """The ONE tag a build for `user` may ever produce: the slot's own name
    under the approved prefix. Matches docker_api.allowed_image's check in
    ctf-controller, so whatever ctf-builder pushes, a redeploy is allowed to
    pull — and nothing else is."""
    return f"{repo_ref(registry_prefix, image)}:{user}"


def build_query(tag):
    """Query string for the Engine API's POST /build. `pull=0`: never
    re-fetch the base image from outside at build time (offline posture,
    CTF-D24); rm/forcerm clean up intermediate containers even on failure."""
    return urlencode({"t": tag, "rm": "1", "forcerm": "1", "pull": "0"})


def push_query(user):
    """`user` IS the tag (image_tag_for ties them together one-to-one)."""
    return urlencode({"tag": user})


def stream_had_error(raw):
    """The Engine API's /build and .../push responses are a stream of JSON
    objects (one per progress line); a failed step still comes back as HTTP
    200 with {"error": ...}/{"errorDetail": ...} IN the stream, never as a
    non-200 status. Pure, so a canned stream is testable with no daemon."""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict) and ("error" in doc or "errorDetail" in doc):
            return True
    return False


class Executor:
    """ctf-builder's whole reach into ctf-host: build a tar it made itself,
    then push the one tag the build just produced. No pull, no create, no
    container, ever — that is ctf-controller's job."""

    def __init__(self, socket_path):
        self.socket_path = socket_path

    def _call(self, method, path, body=None, headers=None, timeout=30):
        conn = _UnixConnection(self.socket_path, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read()
        except OSError as exc:
            raise DockerError(f"ctf-host unreachable: {exc}") from exc
        finally:
            conn.close()

    def ping(self):
        try:
            return self._call("GET", "/_ping")[0] == 200
        except DockerError:
            return False

    def build(self, tar_bytes, tag, timeout=180):
        status, data = self._call(
            "POST", f"/build?{build_query(tag)}", body=tar_bytes,
            headers={"Content-Type": "application/x-tar"}, timeout=timeout)
        if status != 200:
            raise DockerError(f"build failed ({status}): {data[:200]!r}")
        if stream_had_error(data):
            raise DockerError(f"build reported an error: {data[-400:]!r}")

    def push(self, user, registry_prefix, image=IMAGE_NAME, timeout=120):
        repo = repo_ref(registry_prefix, image)
        path = f"/images/{quote(repo, safe='')}/push?{push_query(user)}"
        # The in-lab registry is unauthenticated (internal-only, CTF-D24), but
        # the Engine API still wants an X-Registry-Auth header present; an
        # empty auth config is the documented way to say "no credentials".
        status, data = self._call(
            "POST", path, body=None,
            headers={"X-Registry-Auth": "e30="},  # base64("{}")
            timeout=timeout)
        if status != 200:
            raise DockerError(f"push failed ({status}): {data[:200]!r}")
        if stream_had_error(data):
            raise DockerError(f"push reported an error: {data[-400:]!r}")
