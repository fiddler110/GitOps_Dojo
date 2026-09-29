"""Fuzz and abuse tests for the Dojo Cloud control plane (PLAN.md T9.2). Offline: the REAL request
handler (`server.Handler`, real `App`, real policy, real portal) is served on 127.0.0.1 and hit with
thousands of hostile raw requests, over a FAKE cloud-host that records every call and checks it
against the allow-list. Run from this directory:

    python3 -B -m unittest test_fuzz            # about a minute
    DOJO_FUZZ_SEED=12345 python3 -B -m unittest test_fuzz       # reproduce a run
    DOJO_FUZZ_ITERATIONS=5000 python3 -B -m unittest test_fuzz  # more random bodies

For EVERY request the tests assert
  * a well-formed reply arrives (status line, Content-Length that matches, ARM-shaped JSON error),
  * the status is below 500 (a refusal or a success, never "InternalServerError"), no traceback text,
  * whatever reached the executor satisfies the allow-list: image in ALLOWED_IMAGES, host port from
    the pool, cpu/memory finite, positive and within caps, env names safe, exactly the three fixed
    labels, the caller's own account in the container name, and a Docker create request that is
    hardened (CapDrop ALL, not privileged, no mounts, no host network, memory/CPU/pids caps set),
  * a refusal (4xx) changed nothing and the records match the containers afterwards.
A failing test prints each distinct problem once with the smallest input that shows it.
Seeded with `random`; the seed is printed at the top of the run. What cannot be checked here
(a real dockerd, Caddy, podman) is in tests/security/README.md.
"""
import collections
import contextlib
import copy
import http.client
import json
import math
import os
import random
import re
import socket
import sys
import tempfile
import threading
import time
import traceback
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import auth
import docker_api
import policy
import portal_api
import server
import state as state_mod

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = int(os.environ.get("DOJO_FUZZ_SEED") or random.SystemRandom().randrange(1, 2 ** 31))
ITERATIONS = int(os.environ.get("DOJO_FUZZ_ITERATIONS") or 1500)
TOKEN = "gw-secret-token"
A, B, FAC = "student01", "student02", "admin"
USERS = [A, B, FAC]
KEY = b"k" * 32
SUB = {u: auth.subscription_id(u) for u in USERS}
TAGS = {"owner": "s", "env": "dev"}
RG = "rg-fuzz"
CG = "ci-fuzz"
LABEL = "hello-student01"
ARM_QS = "?api-version=2025-09-01"
DOCKER_MIN_MEMORY = 6 * 1024 * 1024     # dockerd refuses a non-zero memory limit below 6 MB
DOCKER_MIN_NANO_CPUS = 10_000_000       # 0.01 CPU: the smallest CFS quota that starts (>= 1 ms per 100 ms period)


def setUpModule():
    server.LIMIT = server.RateLimit(0, 0)  # the fuzzer sends thousands of requests as one user: rate limit off
    print(f"\ntest_fuzz: seed={SEED} iterations={ITERATIONS} "
          f"(reproduce with DOJO_FUZZ_SEED={SEED})", file=sys.stderr)


# ------------------------------------------------------------------------------------------------
# what a container create request must look like (used by the fake host AND the direct builder tests)
# ------------------------------------------------------------------------------------------------
HOST_CONFIG_KEYS = {"PortBindings", "Memory", "MemorySwap", "NanoCpus", "PidsLimit", "CapDrop", "SecurityOpt",
                    "RestartPolicy", "Privileged", "ReadonlyRootfs"}
FORBIDDEN_HOST_CONFIG = ("Binds", "Mounts", "Devices", "NetworkMode", "PidMode", "IpcMode", "UtsMode", "UsernsMode",
                         "CapAdd", "Links", "ExtraHosts", "VolumesFrom", "Tmpfs", "Sysctls", "CgroupParent",
                         "Runtime", "DeviceCgroupRules", "GroupAdd", "Init", "OomScoreAdj", "CpuShares", "Ulimits")
FIXED_LABELS = {"dojo.owner", "dojo.rg", "dojo.name", docker_api.LABEL_MANAGED}


def spec_violations(spec):
    """Everything wrong with a Docker create request from the point of view of the hardening rules."""
    v = []
    if set(spec) != {"Image", "Env", "Labels", "ExposedPorts", "HostConfig"}:
        v.append(f"unexpected top-level keys {sorted(spec)}")
    hc = spec.get("HostConfig") or {}
    for key in FORBIDDEN_HOST_CONFIG:
        if key in hc:
            v.append(f"HostConfig has forbidden key {key}")
    if set(hc) - HOST_CONFIG_KEYS:
        v.append(f"HostConfig has keys outside the fixed set: {sorted(set(hc) - HOST_CONFIG_KEYS)}")
    if hc.get("CapDrop") != ["ALL"]:
        v.append(f"CapDrop is {hc.get('CapDrop')!r}, not ['ALL']")
    if hc.get("Privileged") is not False:
        v.append(f"Privileged is {hc.get('Privileged')!r}")
    if hc.get("SecurityOpt") != ["no-new-privileges"]:
        v.append(f"SecurityOpt is {hc.get('SecurityOpt')!r}")
    if hc.get("PidsLimit") != 64:
        v.append(f"PidsLimit is {hc.get('PidsLimit')!r}")
    if hc.get("RestartPolicy") != {"Name": "unless-stopped"}:
        v.append(f"RestartPolicy is {hc.get('RestartPolicy')!r}")
    memory, swap, cpus = hc.get("Memory"), hc.get("MemorySwap"), hc.get("NanoCpus")
    cap_mem, cap_cpu = int(policy.MAX_MEMORY_GB * 1024 ** 3), int(policy.MAX_CPU * 1e9)
    if not isinstance(memory, int) or not 0 < memory <= cap_mem:
        v.append(f"Memory is {memory!r}: 0 means UNLIMITED to Docker; it must be in (0, {cap_mem}]")
    if swap != memory:
        v.append(f"MemorySwap {swap!r} differs from Memory {memory!r} (swap would lift the memory cap)")
    if not isinstance(cpus, int) or not 0 < cpus <= cap_cpu:
        v.append(f"NanoCpus is {cpus!r}: 0 means UNLIMITED to Docker; it must be in (0, {cap_cpu}]")
    ports = hc.get("PortBindings")
    if not (isinstance(ports, dict) and list(ports) == ["80/tcp"] and len(ports["80/tcp"]) == 1
            and set(ports["80/tcp"][0]) == {"HostPort"} and str(ports["80/tcp"][0]["HostPort"]).isdigit()):
        v.append(f"PortBindings is {ports!r}")
    if spec.get("ExposedPorts") != {"80/tcp": {}}:
        v.append(f"ExposedPorts is {spec.get('ExposedPorts')!r}")
    if spec.get("Image") not in policy.ALLOWED_IMAGES:
        v.append(f"Image {spec.get('Image')!r} is outside the allow-list")
    labels = spec.get("Labels") or {}
    if set(labels) - FIXED_LABELS:
        v.append(f"labels outside the fixed set: {sorted(set(labels) - FIXED_LABELS)}")
    if labels.get(docker_api.LABEL_MANAGED) != "true":
        v.append("dojo.managed label missing or not 'true'")
    return v


def create_violations(name, image, env_pairs, host_port, cpu, memory_gb, labels, expect_owner):
    """Everything wrong with the arguments the server hands the executor (the allow-list)."""
    v = []
    if image not in policy.ALLOWED_IMAGES:
        v.append(f"image {image!r} outside the allow-list")
    if not (type(host_port) is int and 20000 <= host_port <= 20999):
        v.append(f"host port {host_port!r} is not an int from the 20000-20999 pool")
    for value, cap, what in ((cpu, policy.MAX_CPU, "cpu"), (memory_gb, policy.MAX_MEMORY_GB, "memory")):
        if not isinstance(value, float) or not math.isfinite(value):
            v.append(f"{what} is not a finite float: {value!r}")
        elif not 0 < value <= cap:
            v.append(f"{what} {value!r} outside (0, {cap}]")
    if not isinstance(env_pairs, list) or len(env_pairs) > policy.MAX_ENV_VARS:
        v.append(f"env is not a list of at most {policy.MAX_ENV_VARS}: {type(env_pairs).__name__}")
    else:
        for pair in env_pairs:
            var, value = pair
            if not isinstance(var, str) or not policy.ENV_NAME.fullmatch(var):
                v.append(f"env name {var!r} does not fully match {policy.ENV_NAME.pattern}")
            elif var in policy.RESERVED_ENV or var.startswith("LD_"):
                v.append(f"env name {var!r} is reserved")
            if not isinstance(value, str) or len(value) > 256 or "\x00" in value:
                v.append(f"env value for {var!r} is not a str of at most 256 chars without NUL")
    if not isinstance(labels, dict) or set(labels) != {"dojo.owner", "dojo.rg", "dojo.name"}:
        v.append(f"labels are not exactly the three fixed keys: {labels!r}")
    else:
        if labels["dojo.owner"] != expect_owner:
            v.append(f"dojo.owner label {labels['dojo.owner']!r} is not the caller's own account {expect_owner!r}")
        if not policy.RG_NAME.fullmatch(str(labels["dojo.rg"]).lower()):
            v.append(f"dojo.rg label {labels['dojo.rg']!r} is not a valid resource group name")
        if not policy.CG_NAME.fullmatch(str(labels["dojo.name"]).lower()):
            v.append(f"dojo.name label {labels['dojo.name']!r} is not a valid container group name")
    if not re.fullmatch(rf"dojo-{re.escape(expect_owner)}-rg-[a-z0-9-]+-ci-[a-z0-9-]*", str(name)) or len(name) > 120:
        v.append(f"container name {name!r} is not dojo-<caller>-<rg>-<cg> (max 120)")
    return v


class FakeDaemon:
    """cloud-host as the executor sees it. It enforces what a real dockerd would (a container name
    is unique, a host port can be bound once, cgroup minimums), flags anything outside the allow-list
    in `violations`, and calls the REAL docker_api.build_create_request for the spec it stores."""

    def __init__(self):
        self.containers, self.calls, self.violations, self.creates = {}, [], [], []
        self.expect_owner = A

    def reset(self):
        self.containers.clear()
        self.calls.clear(), self.violations.clear(), self.creates.clear()
        self.expect_owner = A

    # ---- what the control plane calls -------------------------------------------------------
    def ping(self):
        return True

    def image_present(self, image):
        return image in policy.ALLOWED_IMAGES

    def list_managed(self):
        return list(self.containers)

    def list_running(self):
        return set(self.containers)

    def state(self, name):
        return "Running" if name in self.containers else None

    def inspect(self, name):
        return {"State": {"Running": True}} if name in self.containers else None

    def logs(self, name, tail=200):
        self.calls.append(("logs", name, tail))
        return "line\n" if name in self.containers else None

    def remove(self, name):
        self.calls.append(("remove", name))
        return self.containers.pop(name, None) is not None or True

    def create(self, name, image, env_pairs, host_port, cpu, memory_gb, labels):
        call = {"name": name, "image": image, "env": copy.deepcopy(env_pairs), "port": host_port, "cpu": cpu,
                "mem": memory_gb, "labels": dict(labels)}
        self.calls.append(("create", name))
        self.creates.append(call)
        for problem in create_violations(name, image, env_pairs, host_port, cpu, memory_gb, labels, self.expect_owner):
            self.violations.append(("executor argument outside the allow-list", problem, call))
        spec = docker_api.build_create_request(image, env_pairs, host_port, cpu, memory_gb, labels)  # may raise, as for real
        for problem in spec_violations(spec):
            self.violations.append(("docker create request is not hardened", problem, call))
        hc = spec["HostConfig"]
        if name in self.containers:
            raise docker_api.DockerError(f"create failed (409): container name {name} is already in use")
        if any(c["HostConfig"]["PortBindings"] == hc["PortBindings"] for c in self.containers.values()):
            raise docker_api.DockerError("create failed (500): host port is already allocated")
        if 0 < hc["Memory"] < DOCKER_MIN_MEMORY:
            raise docker_api.DockerError("create failed (500): Minimum memory limit allowed is 6MB")
        if 0 < hc["NanoCpus"] < DOCKER_MIN_NANO_CPUS:
            raise docker_api.DockerError("start failed (500): cpu quota below 1ms is refused by the runtime")
        if hc["Memory"] < 0 or hc["NanoCpus"] < 0:
            raise docker_api.DockerError("create failed (400): negative resource limit")
        self.containers[name] = spec


# ------------------------------------------------------------------------------------------------
# raw HTTP client: exact bytes out, every response back (http.client would refuse or fix most of these)
# ------------------------------------------------------------------------------------------------
class Resp:
    def __init__(self):
        self.responses = []   # [(status, {lower name: [values]}, body bytes)]
        self.error = None     # set when nothing (or half a reply) came back
        self.head = False     # the request was HEAD: the reply has headers only
        self.leftover = b""

    @property
    def status(self):
        return self.responses[0][0] if self.responses else None

    @property
    def headers(self):
        return self.responses[0][1] if self.responses else {}

    @property
    def body(self):
        return self.responses[0][2] if self.responses else b""

    def json(self):
        try:
            return json.loads(self.body)
        except ValueError:
            return None


def to_bytes(x):
    return x if isinstance(x, bytes) else x.encode("utf-8", "surrogatepass")


def request_bytes(method, path, headers=(), body=None, length=True, keepalive=False):
    """Serialise a request exactly as given. `headers` is a list of (name, value) pairs (repeats allowed)."""
    out = [to_bytes(method) + b" " + to_bytes(path) + b" HTTP/1.1", b"Host: cloud-api"]
    for name, value in headers:
        out.append(to_bytes(name) + b": " + to_bytes(value))
    if body is not None and length:
        out.append(b"Content-Length: " + str(len(body)).encode())
    if not keepalive:
        out.append(b"Connection: close")
    return b"\r\n".join(out) + b"\r\n\r\n" + (body or b"")


def parse_responses(data, head=False):
    """Split a byte stream into HTTP responses (Content-Length framed; interim 1xx responses are skipped and a
    reply to HEAD has no body). -> (responses, leftover, problem)."""
    out = []
    while data:
        end = data.find(b"\r\n\r\n")
        if end < 0:
            return out, data, "incomplete response headers"
        head_lines, rest = data[:end].split(b"\r\n"), data[end + 4:]
        parts = head_lines[0].split(b" ", 2)
        if len(parts) < 2 or not parts[0].startswith(b"HTTP/") or not parts[1].isdigit():
            return out, data, f"malformed status line {head_lines[0][:80]!r}"
        status = int(parts[1])
        if 100 <= status < 200:
            data = rest
            continue
        headers = collections.defaultdict(list)
        for line in head_lines[1:]:
            name, _, value = line.partition(b":")
            headers[name.strip().lower().decode("latin-1")].append(value.strip().decode("latin-1"))
        length = headers.get("content-length")
        if head or status in (204, 304):
            out.append((status, dict(headers), b""))
            data = rest
            continue
        if length is None:
            out.append((status, dict(headers), rest))
            return out, b"", None
        try:
            size = int(length[0])
        except ValueError:
            return out, data, f"bad Content-Length {length!r} in the reply"
        if len(rest) < size:
            return out, data, f"reply body shorter than its Content-Length ({len(rest)} < {size})"
        out.append((status, dict(headers), rest[:size]))
        data = rest[size:]
    return out, b"", None


def talk(port, payload, timeout=5.0, first_only=True, patience=0.0):
    """Send raw bytes, read the reply. `first_only`: stop after the first complete response.
    `patience`: after that, keep listening this long for further (unwanted) responses."""
    resp = Resp()
    head = payload.startswith(b"HEAD ")
    resp.head = head
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    data = b""
    try:
        try:
            sock.sendall(payload)
        except OSError as exc:  # the server may answer and hang up before it has read everything
            resp.error = f"send failed: {exc!r}"
        deadline = time.monotonic() + timeout
        quiet_since = None
        while time.monotonic() < deadline:
            parsed, left, problem = parse_responses(data, head)
            if parsed and problem is None and left == b"" and (first_only and patience == 0):
                break
            if parsed and problem is None and first_only and patience:
                quiet_since = quiet_since or time.monotonic()
                sock.settimeout(max(0.05, min(patience, deadline - time.monotonic())))
            else:
                sock.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                chunk = sock.recv(1 << 20)
            except socket.timeout:
                break
            except OSError as exc:
                resp.error = resp.error or f"connection error: {exc!r}"
                break
            if not chunk:
                break
            data += chunk
            quiet_since = None
    finally:
        sock.close()
    resp.responses, resp.leftover, problem = parse_responses(data, head)
    if not resp.responses:
        resp.error = resp.error or (problem or "no response (connection closed or timed out)")
    elif problem and not first_only:
        resp.error = problem
    elif problem and first_only and len(resp.responses) == 0:
        resp.error = problem
    return resp


# ------------------------------------------------------------------------------------------------
# problem collection: one report per distinct problem, smallest input that shows it
# ------------------------------------------------------------------------------------------------
def shown(value, limit=260):
    """repr() for everything except plain printable text, so control characters and NaN stay visible."""
    text = value if isinstance(value, str) and value.isprintable() else repr(value)
    return text if len(text) <= limit else f"{text[:limit]}... [{len(text)} chars in all]"


# Problems that are about safety (what reached the executor, another tenant's data, request smuggling, leaks) are
# listed before those that are about robustness (a 500 for a body the API should have refused with a 4xx).
SECURITY = ("executor argument", "docker create request", "records and containers", "an extra property", "leaks",
            "A got a success", "B's data", "the executor was called", "token was not refused", "the token endpoint issued",
            "the token issued", "the portal answered 200", "the portal answered as", "made the portal answer", "a body above",
            "the connection is out of step", "reached another container", "reached both", "not a clean origin-form",
            "a student got past", "an unknown method was not refused", "unexpected status", "builder output",
            "a non-allow-listed image", "a value that is not a number", "the host port in the request")


class Problems:
    def __init__(self):
        self.groups = collections.OrderedDict()   # kind -> {"count": n, "examples": [(size, request, detail)]}
        self.requests = 0
        self.statuses = collections.Counter()

    def add(self, kind, request, detail="", size=0):
        group = self.groups.setdefault(kind, {"count": 0, "examples": []})
        group["count"] += 1
        if all(request != e[1] for e in group["examples"]):
            group["examples"] = sorted(group["examples"] + [(size, request, detail)], key=lambda e: e[0])[:4]

    def report(self, seed=SEED):
        lines = [f"{len(self.groups)} distinct problem(s) in {self.requests} request(s) (seed {seed}); "
                 + (f"statuses seen: {dict(sorted(self.statuses.items()))}" if self.statuses else "")]
        ordered = sorted(self.groups.items(), key=lambda kv: not kv[0].startswith(SECURITY))
        n_safety = sum(1 for kind, _ in ordered if kind.startswith(SECURITY))
        for n, (kind, group) in enumerate(ordered, 1):
            _, request, detail = group["examples"][0]
            if n == 1 and n_safety:
                lines.append(f"\n ===== SAFETY: {n_safety} problem(s) about what reaches the executor, other tenants or the connection =====")
            if n == n_safety + 1:
                lines.append(f"\n ===== ROBUSTNESS: {len(ordered) - n_safety} problem(s), a refusal was expected but the server errored or hung up =====")
            lines.append(f"\n [{n}] x{group['count']}  {kind}")
            lines.append(f"      input : {shown(request)}")
            if detail:
                lines.append(f"      detail: {shown(detail, 400)}")
            for _, other, _ in group["examples"][1:]:
                lines.append(f"      also  : {shown(other, 120)}")
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------------
# the stack under test
# ------------------------------------------------------------------------------------------------
class Stack(unittest.TestCase):
    """Real Handler + App + Portal over a FakeDaemon. One server per test class; state is reset per request."""

    @classmethod
    def setUpClass(cls):
        cls.daemon = FakeDaemon()
        cls.state = state_mod.State(None)
        cls.app = server.App(auth.Auth(KEY, USERS, FAC, "https://login/"), cls.state, cls.daemon)
        cls.tmp = tempfile.TemporaryDirectory()
        for name in ("index.html", "app.js", "app.css", "favicon.svg"):
            with open(os.path.join(cls.tmp.name, name), "w") as f:
                f.write("x")
        cls.app.portal = portal_api.Portal(cls.app, {"GATEWAY_TOKEN": TOKEN, "PUBLIC_BASE_URL": "https://dojo.example"},
                                           cls.tmp.name)
        cls.app.reconciled.set()
        cls.app.readiness.refresh()
        assert cls.app.readiness.snapshot()[0], "the fake host should make Dojo Cloud ready"
        cls.lines, cls.unhandled = [], []
        cls.saved = (server.APP, server.log, server.CLOUD_HOST)
        server.APP, server.log = cls.app, cls.capture

        class Quiet(ThreadingHTTPServer):
            daemon_threads = True
            request_queue_size = 256

            def handle_error(self_, request, client_address):  # an exception escaped the request handler
                exc = sys.exc_info()[1]
                if not isinstance(exc, OSError):
                    cls.unhandled.append(f"{type(exc).__name__}: {exc}")

        cls.httpd = Quiet(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, args=(0.05,), daemon=True).start()
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def capture(cls, msg):
        """server.log: keeps every line, and for "internal error" adds WHERE it was raised (the innermost frame in
        the cloud-api sources), so equal bugs group together whatever the input."""
        if msg.startswith("internal error:"):
            tb = sys.exc_info()[2]
            if tb:
                frames = traceback.extract_tb(tb)
                mine = [f for f in frames if os.path.dirname(os.path.abspath(f.filename)) == HERE
                        and not f.filename.endswith("test_fuzz.py")]
                f = (mine or frames)[-1]
                msg += f" @ {os.path.basename(f.filename)}:{f.lineno} `{(f.line or '').strip()[:100]}`"
        cls.lines.append(msg)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.APP, server.log, server.CLOUD_HOST = cls.saved
        cls.tmp.cleanup()

    def setUp(self):
        self.problems = Problems()
        self.rng = random.Random(f"{SEED}:{self.id()}")
        self.reset()
        self.tokens = {u: self.app.auth.issue_token(u, "aud") for u in USERS}

    def tearDown(self):
        self.reset()

    # ---- state ------------------------------------------------------------------------------
    def reset(self, existing=None):
        """Empty baseline: resource groups for A and B, no container groups, no containers."""
        st = self.state
        with st.lock:
            st.cgs.clear()
            st.rgs.clear()
            st.data["activity"].clear()
            st._summary.clear()
            st.data.pop("settings", None)
            for user in (A, B):
                st.rgs[server.App.rg_key(SUB[user], RG)] = {"name": RG, "location": "canadacentral", "tags": dict(TAGS)}
        self.daemon.reset()
        self.lines.clear()
        self.unhandled.clear()
        if existing is not None:  # a first, valid deployment for the mutated request to replace
            resp = self.arm("PUT", self.cg_path(), cg_body(existing))
            assert resp.status == 201, (resp.status, resp.body)
            self.daemon.creates.clear(), self.daemon.calls.clear()

    def snapshot(self):
        with self.state.lock:
            return copy.deepcopy((self.state.cgs, self.state.rgs, self.state.data.get("settings"))), \
                copy.deepcopy(self.daemon.containers)

    # ---- requests ---------------------------------------------------------------------------
    def bearer(self, user=A):
        return [("Authorization", "Bearer " + self.tokens[user])]

    def gateway(self, user=A, token=TOKEN):
        return [("X-Auth-User", user), ("X-Gateway-Token", token)]

    def arm(self, method, path, body=None, user=A, raw=False, headers=None):
        payload = body if raw or body is None else json.dumps(body, allow_nan=True).encode()
        return talk(self.port, request_bytes(method, path, headers if headers is not None else self.bearer(user),
                                             payload))

    def cg_path(self, user=A, rg=RG, cg=CG, tail=""):
        return (f"/subscriptions/{SUB[user]}/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/"
                f"containerGroups/{cg}{tail}{ARM_QS}")

    def rg_path(self, user=A, rg=RG):
        return f"/subscriptions/{SUB[user]}/resourceGroups/{rg}{ARM_QS}"

    def judge(self, resp, request, kind_prefix="", *, json_reply=True, token_endpoint=False, size=0, before=None,
              mark=0, allow_status=(), responses=1):
        """Apply every per-request invariant; record whatever fails."""
        p = self.problems
        p.requests += 1
        req = shown(request, 600)
        if resp.error:
            time.sleep(0.2)  # let the handler thread report why it died
        signature = self.signature(mark)
        if resp.error:
            why = resp.error.split(":")[0] if not resp.error.startswith("bad") else "bad reply"
            p.add(f"{kind_prefix}no usable reply: {why}{' (' + signature + ')' if signature else ''}", req, resp.error, size)
        else:
            status = resp.status
            p.statuses[status] += 1
            if status >= 500 and status not in allow_status:
                p.add(f"{kind_prefix}HTTP {status} (must be a 4xx refusal or a success): {signature or 'no server log'}",
                      req, resp.body[:200], size)
            body = resp.body
            if len(resp.responses) != responses:
                p.add(f"{kind_prefix}{len(resp.responses)} responses where {responses} request(s) were sent "
                      f"(the connection is out of step)", req, f"statuses {[r[0] for r in resp.responses]}", size)
            if re.search(rb"Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|/usr/local/lib/python", body):
                p.add(f"{kind_prefix}reply leaks a traceback or a source path", req, body[:200], size)
            if json_reply and not resp.head and status not in (204, 301, 304) and not (status < 400 and not body):
                ctype = (resp.headers.get("content-type") or [""])[0]
                doc = resp.json()
                if not ctype.startswith("application/json") or doc is None:
                    p.add(f"{kind_prefix}reply is not JSON (status {status}, {ctype or 'no content type'})", req,
                          body[:160], size)
                elif status >= 400:
                    err = doc.get("error") if isinstance(doc, dict) else None
                    if token_endpoint:
                        ok = isinstance(err, str) and isinstance(doc.get("error_description"), str)
                    else:
                        ok = isinstance(err, dict) and isinstance(err.get("code"), str) and isinstance(err.get("message"), str)
                    if not ok:
                        p.add(f"{kind_prefix}error reply is not the expected shape", req, body[:200], size)
        for kind, problem, call in self.daemon.violations:
            p.add(f"{kind_prefix}{kind}: {problem.split(':')[0] if len(problem) > 90 else problem}", req,
                  f"{problem} | executor call: {shown(call, 300)}", size)
        self.daemon.violations.clear()
        if resp.status is not None and 400 <= resp.status < 500 and before is not None:
            after = self.snapshot()
            if after != before:
                p.add(f"{kind_prefix}a refused request (HTTP {resp.status}) changed state", req, "", size)
        self.check_consistency(req, kind_prefix, size)
        self.lines_seen = len(self.lines)

    def signature(self, mark=0):
        """What the server logged as the reason for a 500 (or an exception that escaped the handler), with the
        student's own values blanked out so equal bugs group together."""
        found = [l for l in self.lines[mark:] if l.startswith(("internal error:", "executor error:")) or "cloud-host error" in l]
        found += [f"unhandled in handler thread: {u}" for u in self.unhandled]
        if not found:
            return ""
        sig = re.sub(r"^internal error: (\w+)\(.*\) @ ", r"internal error: \1 @ ", found[0])
        sig = re.sub(r"float: '.*'", "float: '..'", sig)          # the student's own text in a conversion error
        sig = re.sub(r"\d{3,}", "N", sig)
        return sig[:190]

    def check_consistency(self, req, kind_prefix, size):
        """Every record has its container and every container has its record."""
        with self.state.lock:
            recorded = {rec["container"] for rec in self.state.cgs.values()}
        actual = set(self.daemon.containers)
        if recorded != actual:
            self.problems.add(f"{kind_prefix}records and containers disagree afterwards",
                              req, f"records without container: {sorted(recorded - actual)}; "
                                   f"containers without record: {sorted(actual - recorded)}", size)

    def check_after(self):
        if self.problems.groups:
            self.fail("\n" + self.problems.report())

    def send_judged(self, method, path, body=None, *, user=A, headers=None, raw=False, label=None, size=None,
                    existing=None, **kw):
        """reset -> one request -> judge. Returns the response."""
        self.reset(existing)
        before = self.snapshot()
        mark = len(self.lines)
        self.unhandled.clear()
        resp = self.arm(method, path, body, user=user, raw=raw, headers=headers)
        request = label or f"{method} {path.split('?')[0]} body={shown(body) if body is not None else None}"
        self.judge(resp, request, before=before, mark=mark,
                   size=size if size is not None else len(str(body)) if body is not None else 0, **kw)
        return resp


# ------------------------------------------------------------------------------------------------
# hostile values
# ------------------------------------------------------------------------------------------------
def nested_list(depth):
    node = []
    for _ in range(depth):
        node = [node]
    return node


def nested_dict(depth):
    node = {}
    for _ in range(depth):
        node = {"a": node}
    return node


NASTY = [
    None, True, False, 0, -1, 1, 2, 80, 8080, 65535, 65536, -0.0, 0.5, 1e308, 1e-320, 1e-12, 2 ** 31, 2 ** 63, 2 ** 64,
    -2 ** 63, float("nan"), float("inf"), float("-inf"),
    "", " ", "0", "0.1", "abc", "80", "1e-9", "NaN", "Infinity", "-1", "0x10", "١٢٣",
    "\x00", "a\x00b", "\n", "abc\n", "abc\r\nX-Injected: 1", "\t", "\x1b[31m", "\x7f", "\x01\x1f",
    "../../etc/passwd", "..", "%2e%2e/", "%00", "a/b", "a\\b", "${jndi:ldap://x}", "{{7*7}}", "; rm -rf /", "$(id)", "`id`",
    "é", "ǅ", "ｒｇ-fuzz", "‮", "​", "\ud800", "😀", "İ", "K",
    "A" * 300, "A" * 70000,
    [], {}, [[]], [{}], {"a": 1}, [1, 2, 3], ["a"], [None], {"": ""}, {"name": "X", "value": "y"},
    [{"name": "X", "value": "y"}], nested_list(100), nested_dict(100),
]
HUGE = "A" * 900_000  # stays under the 1 MB body cap
IMAGES = ["dojo/hello:1.0", "dojo/hello:2.0", "dojo/hello:3.0", "dojo/hello:latest", "dojo/hello", "dojo/hello:1.0 ",
          " dojo/hello:1.0", "dojo/hello:1.0\n", "dojo/hello:1.0\x00", "DOJO/HELLO:1.0", "dojo/hello:1.0 --privileged",
          "dojo/hello:1.0;id", "dojo/hello@sha256:" + "0" * 64, "dojo/hello:1.0@sha256:" + "0" * 64,
          "docker.io/dojo/hello:1.0", "registry.example/dojo/hello:1.0", "../dojo/hello:1.0", "dojo/../dojo/hello:1.0",
          "dojo/hello:1.0/../../etc", "alpine", "alpine:latest", "nginx:alpine", "busybox", "scratch", "docker:dind",
          "sha256:" + "0" * 64, "", "dojo/hello:1.0\ndojo/hello:2.0", "dojo/hello:１.0", "dojo/hello:1.0%00"]
ENV_NAMES = ["MESSAGE", "OWNER", "A=B", "A B", "A\nB", "A\n", "\nA", "A\r", "", "1A", "A-B", "A.B", "A" * 64, "A" * 65,
             "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_X", "PATH", "HOSTNAME", "HELLO_VERSION", "HOME", "ｍｅｓｓａｇｅ",
             "MESSAGÉ", "ǅ", "A\x00B", "A;B", "A$B", "=", "==", "PATH=/tmp:", "MESSAGE=x\nPATH", "_", "__", "a"]
NAMES = ["", ".", "..", "../rg-fuzz", "rg-fuzz/..", "%2e%2e", "%2E%2E%2Frg-fuzz", "%2f", "rg%2ffuzz", "RG-FUZZ", "Rg-Fuzz",
         "rg-fuzz\x00", "rg-fuzz%00", "rg-fuzz%0a", "rg-fuzz%0d%0a", "rg-", "rg-a", "rg-ab", "rg-" + "a" * 56,
         "rg-" + "a" * 57, "rg-" + "a" * 58, "rg-" + "a" * 4000, "ｒｇ-fuzz", "rg-é", "rg-ǅ", "rg-fuzz‮", "rg fuzz",
         "rg\tfuzz", "rg-fuzz;x", "rg-fuzz?x=1", "rg-fuzz#f", "..%2f..%2f", "\\..\\", "rg-fuzz.", "-rg-fuzz", "rg--",
         "ci-fuzz", "CI-FUZZ", "ci-", "ci-" + "a" * 56, "ci-" + "a" * 58, "*", "%", "%zz", "rg-fuzz%", "�", "rg-\x7f"]


def cg_body(label=LABEL, **props):
    body = {"location": "canadacentral", "tags": dict(TAGS), "properties": {
        "osType": "Linux",
        "containers": [{"name": "hello", "properties": {
            "image": "dojo/hello:1.0", "ports": [{"port": 80}],
            "environmentVariables": [{"name": "MESSAGE", "value": "hi"}],
            "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}],
        "ipAddress": {"type": "Public", "ports": [{"port": 80}], "dnsNameLabel": label}}}
    body["properties"].update(props)
    return body


RG_BODY = {"location": "canadacentral", "tags": dict(TAGS)}


def node_paths(node, path=()):
    """Every position in a JSON document: () for the root, then each dict key and list index."""
    yield path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from node_paths(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from node_paths(value, path + (i,))


def get_at(node, path):
    for step in path:
        node = node[step]
    return node


def replaced(doc, path, value):
    doc = copy.deepcopy(doc)
    if not path:
        return value
    parent = get_at(doc, path[:-1])
    parent[path[-1]] = copy.deepcopy(value)
    return doc


def deleted(doc, path):
    doc = copy.deepcopy(doc)
    parent = get_at(doc, path[:-1])
    if isinstance(parent, dict):
        del parent[path[-1]]
    else:
        del parent[path[-1]]
    return doc


EXTRA_KEYS = ["volumes", "volumeMounts", "command", "securityContext", "privileged", "hostNetwork", "networkMode", "pid",
              "ipc", "capabilities", "capAdd", "devices", "binds", "mounts", "user", "entrypoint", "args", "workingDir",
              "restartPolicy", "livenessProbe", "readinessProbe", "imageRegistryCredentials", "initContainers",
              "diagnostics", "dnsConfig", "subnetIds", "identity", "sku", "priority", "labels", "__proto__", "constructor",
              "$ref", "hostConfig", "HostConfig", "Privileged", "dockerArgs", "runtime", "sysctls", "extraHosts",
              "links", "tmpfs", "cgroupParent", "shmSize", "ulimits", "Env", "Cmd", "Labels", "Binds", "NetworkMode"]
EXTRA_VALUES = [True, {"privileged": True}, ["--privileged"], "--privileged", {"capabilities": {"add": ["SYS_ADMIN"]}},
                [{"name": "x", "azureFile": {"shareName": "s", "storageAccountName": "a", "storageAccountKey": "k"}}],
                {"hostPath": "/"}, ["/:/host"], "host", 1, ["sh", "-c", "id"], {"Privileged": True}]


def json_bytes(doc):
    return json.dumps(doc, allow_nan=True).encode()


def random_json(rng, depth=0):
    kinds = ["null", "bool", "int", "float", "str", "list", "dict"] if depth < 4 else ["null", "bool", "int", "str"]
    kind = rng.choice(kinds)
    if kind == "null":
        return None
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "int":
        return rng.choice([0, 1, -1, 80, 2 ** 40, rng.randrange(-10 ** 6, 10 ** 6)])
    if kind == "float":
        return rng.choice([0.0, 0.125, 0.25, 1e-9, 1e300, float("nan"), float("inf"), rng.random()])
    if kind == "str":
        return rng.choice(NASTY[23:52] + IMAGES[:6] + ["dojo/hello:1.0", "canadacentral", "hello-x", "ci-x", "Linux"])
    if kind == "list":
        return [random_json(rng, depth + 1) for _ in range(rng.randrange(0, 4))]
    return {rng.choice(["properties", "containers", "image", "ports", "port", "cpu", "resources", "requests", "name",
                        "value", "location", "tags", "owner", "env", "ipAddress", "dnsNameLabel", "environmentVariables",
                        "memoryInGB", "osType", "type", "x"] + EXTRA_KEYS[:8]): random_json(rng, depth + 1)
            for _ in range(rng.randrange(0, 5))}


def mutate(rng, base):
    """One to four random edits of a valid body: replace, delete, duplicate, or add a key."""
    doc = copy.deepcopy(base)
    for _ in range(rng.randrange(1, 5)):
        paths = [p for p in node_paths(doc) if p]
        kind = rng.choice(["replace", "replace", "replace", "delete", "dup", "extra", "random"])
        if not paths:
            break
        path = rng.choice(paths)
        if kind == "replace":
            doc = replaced(doc, path, rng.choice(NASTY))
        elif kind == "delete":
            doc = deleted(doc, path)
        elif kind == "dup":
            node = get_at(doc, path)
            parent = get_at(doc, path[:-1])
            if isinstance(parent, list):
                parent.append(copy.deepcopy(node))
        elif kind == "extra":
            dicts = [p for p in node_paths(doc) if isinstance(get_at(doc, p), dict)]
            get_at(doc, rng.choice(dicts))[rng.choice(EXTRA_KEYS)] = copy.deepcopy(rng.choice(EXTRA_VALUES))
        else:
            doc = replaced(doc, path, random_json(rng))
    return doc


# ================================================================================================
# 0. the harness must be able to fail (otherwise a green run would prove nothing)
# ================================================================================================
class HarnessSelfCheck(Stack):
    def test_a_valid_request_reaches_the_executor_exactly_as_expected(self):
        resp = self.send_judged("PUT", self.cg_path(), cg_body())
        self.assertEqual(resp.status, 201, resp.body)
        self.assertEqual(len(self.daemon.creates), 1)
        call = self.daemon.creates[0]
        self.assertEqual((call["image"], call["env"], call["port"], call["cpu"], call["mem"]),
                         ("dojo/hello:1.0", [("MESSAGE", "hi")], 20000, 0.25, 0.125))
        self.assertEqual(call["labels"], {"dojo.owner": A, "dojo.rg": RG, "dojo.name": CG})
        self.assertEqual(call["name"], f"dojo-{A}-{RG}-{CG}")
        self.check_after()

    def test_the_fake_host_and_the_checks_do_flag_bad_calls(self):
        bad = dict(name="dojo-x", image="alpine", env_pairs=[("A B", "x")], host_port=80, cpu=float("nan"),
                   memory_gb=1e-12, labels={"dojo.owner": "mallory", "extra": "1"}, expect_owner=A)
        found = create_violations(**bad)
        for needle in ("outside the allow-list", "20000-20999", "finite float", "does not fully match",
                       "fixed keys", "container name"):
            self.assertTrue(any(needle in f for f in found), (needle, found))
        with self.assertRaises(docker_api.DockerError):  # the builder itself refuses a request that would round to 0
            docker_api.build_create_request("dojo/hello:1.0", [], 20000, 1e-12, 1e-12, {})
        weak = docker_api.build_create_request("dojo/hello:1.0", [], 20000, .25, .125, {})
        weak["HostConfig"]["Memory"] = 0  # what the checker must still flag if it ever came back
        self.assertTrue(any("UNLIMITED" in f for f in spec_violations(weak)), spec_violations(weak))
        self.assertEqual(spec_violations(docker_api.build_create_request("dojo/hello:1.0", [], 20000, .25, .125, {})), [])
        self.daemon.create("dojo-student01-rg-ab-ci-ab", "dojo/hello:1.0", [("A", "b")], 20000, .25, .125,
                           {"dojo.owner": A, "dojo.rg": "rg-ab", "dojo.name": "ci-ab"})
        with self.assertRaises(docker_api.DockerError):  # a second one on the same name / port, as dockerd refuses
            self.daemon.create("dojo-student01-rg-ab-ci-ab", "dojo/hello:1.0", [], 20001, .25, .125,
                               {"dojo.owner": A, "dojo.rg": "rg-ab", "dojo.name": "ci-ab"})
        self.assertEqual(self.daemon.violations, [])
        self.daemon.reset()

    def test_a_500_is_reported_with_its_cause(self):
        original = policy.check_resource_group
        policy.check_resource_group = lambda *a, **k: 1 / 0
        try:
            resp = self.send_judged("PUT", self.rg_path(), RG_BODY)
        finally:
            policy.check_resource_group = original
        self.assertEqual(resp.status, 500)
        self.assertIn("ZeroDivisionError", self.problems.report())
        self.assertIn("HTTP 500", self.problems.report())

    def test_the_raw_client_sees_every_pipelined_response(self):
        many = request_bytes("GET", "/healthz", keepalive=True) * 2
        resp = talk(self.port, many, patience=0.5, first_only=True)
        self.assertEqual([r[0] for r in resp.responses], [200, 200])


# ================================================================================================
# 1. container-group and resource-group bodies
# ================================================================================================
class BodyFuzz(Stack):
    def corpus(self):
        """Single-field mutations: every position of a valid body x every hostile value, plus deletions,
        duplicated list entries and appended entries. Deterministic."""
        base = cg_body()
        for path in node_paths(base):
            if not path:
                continue
            original = get_at(base, path)
            for value in NASTY:
                yield f"{'.'.join(map(str, path))} = {shown(value, 60)}", replaced(base, path, value)
            if isinstance(original, str):
                yield f"{'.'.join(map(str, path))} = <900 kB string>", replaced(base, path, HUGE)
            yield f"delete {'.'.join(map(str, path))}", deleted(base, path)
            parent = get_at(base, path[:-1])
            if isinstance(parent, list):
                dup = copy.deepcopy(base)
                get_at(dup, path[:-1]).append(copy.deepcopy(original))
                yield f"duplicate {'.'.join(map(str, path))}", dup
        for node_path in [p for p in node_paths(base) if isinstance(get_at(base, p), list)]:
            for value in NASTY[:12] + [{"name": "extra"}, {"properties": {"image": "alpine"}}]:
                grown = copy.deepcopy(base)
                get_at(grown, node_path).append(value)
                yield f"append {shown(value, 40)} to {'.'.join(map(str, node_path))}", grown

    def run_corpus(self, existing):
        base_resp = self.send_judged("PUT", self.cg_path(), cg_body(), existing=existing)
        self.assertIn(base_resp.status, (200, 201), "the unmutated body must be accepted or the fuzz proves nothing")
        accepted = 0
        for label, body in self.corpus():
            resp = self.send_judged("PUT", self.cg_path(), body, label=f"PUT container group, {label}", existing=existing,
                                    size=len(json_bytes(body)))
            accepted += resp.status in (200, 201)
        self.assertGreater(accepted, 5, "a fuzz that never gets a body accepted does not reach the executor")
        self.check_after()

    def test_single_field_mutations_of_a_new_container_group(self):
        self.run_corpus(existing=None)

    def test_single_field_mutations_replacing_an_existing_container_group(self):
        self.run_corpus(existing="hello-first")

    def test_random_bodies_and_random_json(self):
        rng, base = self.rng, cg_body()
        for i in range(ITERATIONS):
            body = mutate(rng, base) if i % 5 else random_json(rng)
            method = rng.choice(["PUT", "PUT", "PUT", "PATCH"])
            self.send_judged(method, self.cg_path(), body, label=f"#{i} {method} container group body={shown(body, 200)}",
                             existing=rng.choice([None, None, "hello-first"]), size=len(json_bytes(body)))
        self.check_after()

    def test_random_resource_group_bodies(self):
        rng = self.rng
        for i in range(ITERATIONS // 3):
            body = mutate(rng, RG_BODY) if i % 3 else random_json(rng)
            method = rng.choice(["PUT", "PATCH"])
            self.send_judged(method, self.rg_path(), body, label=f"#{i} {method} resource group body={shown(body, 200)}",
                             size=len(json_bytes(body)))
        for path in [p for p in node_paths(RG_BODY) if p]:
            for value in NASTY:
                for method in ("PUT", "PATCH"):
                    self.send_judged(method, self.rg_path(), replaced(RG_BODY, path, value),
                                     label=f"{method} resource group, {'.'.join(map(str, path))} = {shown(value, 60)}",
                                     size=len(str(value)))
        self.check_after()

    def test_raw_bodies_that_are_not_documents(self):
        raw = [b"", b" ", b"null", b"[]", b'"str"', b"123", b"true", b"{", b"}", b'{"a":', b"\xff\xfe", b"\xef\xbb\xbf{}",
               '{"location":"canadacentral"}'.encode("utf-16"), b'{"a":1}garbage', b"{'a':1}", b'{"a":NaN}',
               b"\x00" * 100, b"[" * 100_000, b"{\"a\":" * 50_000 + b"1" + b"}" * 50_000, b"[" * 1000 + b"]" * 1000,
               b'{"a":1,"a":2}', b'{"properties":{"properties":' * 30, b'{"tags":' + b"[" * 200_000,
               b"{" + b",".join(b'"k%d":1' % i for i in range(60_000)) + b"}",  # 60k keys, about 700 kB
               b'{"location":"canadacentral","tags":{"owner":"a","env":"b"},"x":"' + b"\xc3\x28" + b'"}',
               b"\xf0\x9f\x98", b'{"location":"canad\xc3\xa1central"}', b"\r\n\r\n", b"0" * 5000, b"-" * 5000]
        for body in raw:
            for method, path in (("PUT", self.rg_path()), ("PATCH", self.rg_path()), ("PUT", self.cg_path()),
                                 ("PATCH", self.cg_path())):
                self.send_judged(method, path, body, raw=True, existing="hello-first" if "containerGroups" in path else None,
                                 label=f"{method} {path.split('?')[0].rsplit('/', 2)[-2]} raw body={shown(body, 80)}",
                                 size=len(body))
        self.check_after()

    def test_hostile_values_at_the_fields_that_reach_the_executor(self):
        """The fields the executor is built from, with pools shaped for each: image, env, cpu, memory, port, label."""
        base = cg_body()
        c = ("properties", "containers", 0, "properties")
        pools = {
            c + ("image",): IMAGES,
            c + ("environmentVariables",): (
                [[{"name": n, "value": "v"}] for n in ENV_NAMES]
                + [[{"name": "MESSAGE", "value": v}] for v in ("x" * 256, "x" * 257, "x" * 100000, "\x00", "a\x00b", "\n", "é", "\ud800")]
                + [[{"name": "MESSAGE", "secureValue": "s3cret"}], [{"name": "MESSAGE"}], [{"value": "v"}],
                   [{"name": "N%d" % i, "value": "v"} for i in range(10)], [{"name": "N%d" % i, "value": "v"} for i in range(11)],
                   [{"name": "MESSAGE", "value": "a"}, {"name": "MESSAGE", "value": "b"}], ["MESSAGE=x"], "MESSAGE=x",
                   {"MESSAGE": "x"}, [{"name": "MESSAGE", "value": {"a": 1}}], [{"name": "MESSAGE", "value": [1] * 200}],
                   [{"name": "MESSAGE", "value": None}], [{"name": "MESSAGE", "value": 12345678901234567890}]]),
            c + ("resources", "requests", "cpu"): [0, -1, 1e-12, 1e-9, 0.001, 0.009, 0.01, 0.25, 0.2500001, 0.26, 1, 64, 1e308,
                                                   float("nan"), float("inf"), float("-inf"), "0.25", "0.1", "abc", "", "nan",
                                                   "1e-12", True, False, None, [0.25], {"a": 0.25}, 2 ** 70, -0.0, "٠.٢"],
            c + ("resources", "requests", "memoryInGB"): [0, -1, 1e-12, 1e-9, 0.001, 0.0058, 0.006, 0.0059, 0.125, 0.1250001,
                                                          0.126, 1, 512, 1e308, float("nan"), float("inf"), float("-inf"),
                                                          "0.125", "abc", "", "nan", "1e-12", True, False, None, [0.125],
                                                          {"a": 1}, 2 ** 70, -0.0],
            c + ("resources", "limits"): [{"cpu": 64, "memoryInGB": 512}, {"cpu": "x"}, 5, None],
            c + ("ports",): [[], [{"port": 22}], [{"port": 80}, {"port": 22}], [{"port": 80, "protocol": "UDP"}], [{"port": "80"}],
                             [{"port": 80.0}], [{"port": True}], [{"port": None}], [{"port": [80]}], [80], "80", [{"proto": 1}],
                             [{"port": 8080}], [{"port": 0}], [{"port": -80}], [{"port": 2 ** 70}], [{}] * 500, None],
            ("properties", "ipAddress"): [{"type": "Private", "dnsNameLabel": LABEL}, {"type": "Public", "dnsNameLabel": LABEL,
                                                                                    "ports": [{"port": 22}]},
                                           {"dnsNameLabel": LABEL, "ports": [{"port": 80}], "ip": "10.0.0.1"},
                                           {"dnsNameLabel": LABEL, "autoGeneratedDomainNameLabelScope": "Unsecure"}, [], None],
            ("properties", "ipAddress", "dnsNameLabel"): [
                "abc", "ab", "a" * 41, "a" * 42, "a" * 4000, "Abc", "1abc", "-abc", "abc-", "ab_c", "abc\n", "abc\r\n", "abc ",
                " abc", "a.b", "a/b", "abc%2f", "../x", "ａｂｃ", "abç", "a\x00b", "hello-student02", "hello-first",
                "cloud", "api", "x" * 3, "abc\x7f", "abc.dojo-cloud.test"],
            ("properties", "osType"): ["Linux", "linux", "Windows", "", None, 1, [], "Linux\n"],
            ("properties", "containers"): [[], [copy.deepcopy(base["properties"]["containers"][0])] * 2,
                                           [copy.deepcopy(base["properties"]["containers"][0])] * 3,
                                           [copy.deepcopy(base["properties"]["containers"][0])] * 50, [None],
                                           [base["properties"]["containers"][0], {"name": "sidecar", "properties": {"image": "alpine"}}],
                                           {"0": base["properties"]["containers"][0]}, "containers", 1, None],
            ("properties", "volumes"): [[{"name": "v", "emptyDir": {}}], [{"name": "v", "secret": {"k": "v"}}], "x", {"a": 1}],
            ("location",): ["canadacentral", "CanadaCentral", "canadaeast", "canada central", "eastus", "", None, "canadacentral\n",
                            ["canadacentral"], {"a": 1}, 5],
            ("tags",): [{}, {"owner": "s"}, {"env": "dev"}, {"owner": "", "env": ""}, {"owner": " ", "env": "dev"},
                        {"owner": None, "env": None}, {"owner": ["x"], "env": {"y": 1}}, {"owner": "a" * 100000, "env": "e"},
                        {"OWNER": "s", "ENV": "dev"}, {"owner\n": "s", "env": "dev"}, [], "tags", None, 5,
                        {"owner": "s", "env": "dev", **{f"t{i}": "v" for i in range(2000)}}],
        }
        for path, values in pools.items():
            for value in values:
                body = replaced(base, path, value)
                for existing in (None, "hello-first"):
                    self.send_judged("PUT", self.cg_path(), body, existing=existing, size=len(json_bytes(body)),
                                     label=f"PUT container group, {'.'.join(map(str, path))} = {shown(value, 100)}")
        self.check_after()

    def test_extra_properties_are_ignored_never_honoured(self):
        """volumes, securityContext, privileged, hostNetwork and friends at every level: the request may be refused
        or accepted, but if accepted the executor must get EXACTLY the arguments of the plain body."""
        self.send_judged("PUT", self.cg_path(), cg_body())
        reference = copy.deepcopy(self.daemon.creates[0]) if self.daemon.creates else None
        self.assertIsNotNone(reference)
        base = cg_body()
        dicts = [p for p in node_paths(base) if isinstance(get_at(base, p), dict)]
        rng = self.rng
        combos = [(p, k, v) for p in dicts for k in EXTRA_KEYS for v in EXTRA_VALUES if k not in get_at(base, p)]
        rng.shuffle(combos)
        accepted = 0
        for path, key, value in combos[:max(1500, ITERATIONS)]:
            body = copy.deepcopy(base)
            get_at(body, path)[key] = copy.deepcopy(value)
            self.reset()
            before, mark = self.snapshot(), len(self.lines)
            resp = self.arm("PUT", self.cg_path(), body)
            request = f"PUT container group with extra {'.'.join(map(str, path)) or '<root>'}.{key} = {shown(value, 80)}"
            self.judge(resp, request, before=before, mark=mark, size=len(json_bytes(body)))
            if resp.status in (200, 201):
                accepted += 1
                got = self.daemon.creates[0] if self.daemon.creates else None
                if got != reference:
                    self.problems.add("an extra property changed what reached the executor", request,
                                      f"expected {reference}, got {got}")
                    self.daemon.creates.clear()
        self.assertGreater(accepted, 200, "most extra properties should be accepted and ignored, or the comparison proves nothing")
        self.check_after()

    def test_privileged_looking_requests_are_refused_or_ignored_never_forwarded(self):
        """The same as above in plain words for the ones that matter, with a check on the stored copy as well:
        a stored body is echoed back to the class, so it must never grow secrets (secureValue is dropped)."""
        body = cg_body()
        body["properties"]["volumes"] = [{"name": "host", "hostPath": {"path": "/"}}]
        body["properties"]["containers"][0]["properties"].update(
            {"volumeMounts": [{"name": "host", "mountPath": "/host"}], "securityContext": {"privileged": True,
             "capabilities": {"add": ["SYS_ADMIN"]}}, "environmentVariables": [{"name": "TOKEN", "secureValue": "s3cret"}]})
        body["properties"]["ipAddress"]["type"] = "Private"
        resp = self.send_judged("PUT", self.cg_path(), body)
        self.assertLess(resp.status, 500, resp.body)
        if resp.status in (200, 201):
            self.assertEqual(len(self.daemon.creates), 1)
            spec = self.daemon.containers[self.daemon.creates[0]["name"]]
            self.assertEqual(spec_violations(spec), [])
            self.assertNotIn(b"s3cret", resp.body, "secureValue must not be echoed back")
        self.check_after()


# ================================================================================================
# 2. names: resource groups, container groups, subscriptions, in the URL path
# ================================================================================================
class NameFuzz(Stack):
    def test_names_in_every_path_position(self):
        for name in NAMES:
            for method, body in (("GET", None), ("PUT", RG_BODY), ("PATCH", {"tags": TAGS}), ("DELETE", None)):
                self.send_judged(method, self.rg_path(rg=name), body, label=f"{method} resource group named {shown(name, 80)}",
                                 size=len(name))
            for method, body in (("GET", None), ("PUT", cg_body()), ("PATCH", {"tags": TAGS}), ("DELETE", None)):
                self.send_judged(method, self.cg_path(cg=name), body, label=f"{method} container group named {shown(name, 80)}",
                                 size=len(name))
                self.send_judged(method, self.cg_path(rg=name), body, label=f"{method} container group in group {shown(name, 80)}",
                                 size=len(name))
            self.send_judged("GET", self.cg_path(cg=name, tail="/logs"), label=f"GET logs of {shown(name, 80)}", size=len(name))
        self.check_after()

    def test_names_that_are_valid_only_after_lower_casing_or_encoding(self):
        """A group created under one spelling must not be reachable, replaceable or deletable under a spelling that
        maps to somebody else's key, and every accepted spelling must give the executor a valid name and label."""
        for spelling in ("RG-FUZZ", "Rg-Fuzz", "rg-fuzz"):
            for cg in ("ci-fuzz", "CI-FUZZ", "Ci-Fuzz"):
                self.send_judged("PUT", self.cg_path(rg=spelling, cg=cg), cg_body(),
                                 label=f"PUT container group {spelling}/{cg}")
        self.check_after()

    def test_joined_names_cannot_collide_into_a_500(self):
        """container name = dojo-<user>-<rg>-<cg>, so (rg-ab, ci-b-ci-cc) and (rg-ab-ci-b, ci-cc) are the same container
        name, as are two names that only differ after the 120-character cut. The second create is refused by
        dockerd; the caller must get a 4xx that says so, not an InternalServerError."""
        pairs = [(("rg-ab", "ci-b-ci-cc"), ("rg-ab-ci-b", "ci-cc")),
                 (("rg-" + "a" * 56, "ci-" + "a" * 14 + "1"), ("rg-" + "a" * 56, "ci-" + "a" * 14 + "2")),
                 (("rg-" + "a" * 56, "ci-" + "a" * 56 + "x"), ("rg-" + "a" * 56, "ci-" + "a" * 56 + "y"))]
        for (rg1, cg1), (rg2, cg2) in pairs:
            self.reset()
            with self.state.lock:
                for rg in (rg1, rg2):
                    self.state.rgs[server.App.rg_key(SUB[A], rg)] = {"name": rg, "location": "canadacentral", "tags": dict(TAGS)}
            first = self.arm("PUT", self.cg_path(rg=rg1, cg=cg1), cg_body("label-one"))
            before, mark = self.snapshot(), len(self.lines)
            second = self.arm("PUT", self.cg_path(rg=rg2, cg=cg2), cg_body("label-two"))
            self.judge(second, f"second PUT {rg2}/{cg2} after {rg1}/{cg1} (first answered {first.status}): the two map to one container name",
                       before=before, mark=mark)
        self.check_after()

    def test_subscription_ids_in_the_path(self):
        good = SUB[A]
        variants = [good.upper(), good + "/", good + "%20", good.replace("-", ""), "{" + good + "}", "00000000-0000-0000-0000-000000000000",
                    "", ".", "..", "%2e%2e", good[:-1], good + "0", "student01", "*", "ｓｕｂ", good + "\x00", " " + good, good + "/../" + SUB[B]]
        for sub in variants:
            for method, tail, body in (("GET", "", None), ("GET", "/resourceGroups", None), ("PUT", f"/resourceGroups/{RG}", RG_BODY),
                                       ("DELETE", f"/resourceGroups/{RG}", None),
                                       ("GET", "/providers/Microsoft.ContainerInstance/containerGroups", None)):
                self.send_judged(method, f"/subscriptions/{sub}{tail}{ARM_QS}", body,
                                 label=f"{method} /subscriptions/{shown(sub, 60)}{tail}")
        self.check_after()

    def test_routes_and_odd_paths(self):
        paths = ["/", "//", "//subscriptions", "/subscriptions", "/subscriptions/", "/subscriptions//" + SUB[A], f"/subscriptions/{SUB[A]}//resourceGroups//{RG}",
                 f"/Subscriptions/{SUB[A]}/RESOURCEGROUPS/{RG}", f"/subscriptions/{SUB[A]}/resourceGroups/{RG}/providers",
                 f"/subscriptions/{SUB[A]}/resourceGroups/{RG}/providers/Microsoft.ContainerInstance",
                 f"/subscriptions/{SUB[A]}/resourceGroups/{RG}/providers/Microsoft.Storage/storageAccounts/x",
                 f"/subscriptions/{SUB[A]}/resourceGroups/{RG}/providers/Microsoft.ContainerInstance/containerGroups/{CG}/logs/extra",
                 f"/subscriptions/{SUB[A]}/resourceGroups/{RG}/providers/Microsoft.ContainerInstance/containerGroups/{CG}/exec",
                 f"/subscriptions/{SUB[A]}/providers/Microsoft.ContainerInstance/containerGroups",
                 f"/subscriptions/{SUB[A]}/resourceGroups/{RG};x=1", f"/subscriptions/{SUB[A]}/resourceGroups/{RG}?a=%zz&b",
                 "/metadata/endpoints", "/metadata/endpoints/x", "/healthz", "/readyz", "/readyz/", "/HEALTHZ", "/healthz/../subscriptions",
                 "/oauth2/v2.0/token", f"/{auth.TENANT_ID}/oauth2/v2.0/token", "/x/oauth2/token", "/.well-known/openid-configuration",
                 "/cloud", "/cloud/", "/cloud/static/app.js", "/cloud/static/../app.js", "/cloud/static/%2e%2e/app.js", "/cloud/static/app.js/",
                 "/cloud/static//app.js", "/cloud//static/app.js", "/cloud/api", "/cloud/api/", "/cloud/api/me/", "/cloud/api//me", "/cloud/API/ME",
                 "/cloud/api/containers", "/cloud/api/containers/x/y", "/cloud/site", "/cloud/site/", "/cloud/site/x", "/cloud/site/ab/",
                 "/cloud/site/hello-student01", "/cloud/site/hello-student01/", "/cloud/site/%68ello-student01/", "/cloud/site/HELLO-STUDENT01/",
                 "/etc/passwd", "/..", "/../..", "/%2e%2e/%2e%2e/etc/passwd", "/proc/self/environ", "/app/server.py", "/data/state.json",
                 "/secrets/signing.key", "/pki/ca.key", "/" + "a" * 70000, "/subscriptions/" + "a" * 60000]
        for path in paths:
            for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"):
                for headers in (self.bearer(A), self.gateway(A), []):
                    self.send_judged(method, path, b"{}" if method in ("POST", "PUT", "PATCH") else None, raw=True,
                                     headers=headers, json_reply=False,
                                     label=f"{method} {shown(path, 90)} with {'bearer' if headers is not None and headers and headers[0][0] == 'Authorization' else 'gateway headers' if headers else 'no credentials'}",
                                     size=len(path))
        self.check_after()


# ================================================================================================
# 3. identity: tokens, the token endpoint, gateway headers, other tenants
# ================================================================================================
class AuthFuzz(Stack):
    def b64(self, data):
        return auth._b64(data)

    def forged_tokens(self):
        head = self.b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        none_head = self.b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        now = int(time.time())

        def claims(user, **over):
            c = {"aud": "a", "iss": "i", "iat": now, "nbf": now, "exp": now + 3600, "tid": auth.TENANT_ID,
                 "oid": auth.app_id(user), "appid": auth.app_id(user), "sub": auth.app_id(user),
                 "preferred_username": user, "idtyp": "app"}
            c.update(over)
            return self.b64(json.dumps(c).encode())

        other = auth.Auth(b"z" * 32, USERS, FAC, "iss")
        good = self.tokens[A]
        h, b, s = good.split(".")
        forged = {
            "empty": "", "dot": ".", "two dots": "..", "garbage": "garbage", "a.b.c": "a.b.c", "a.b": "a.b", "4 parts": "a.b.c.d",
            "alg none, admin": f"{none_head}.{claims(FAC)}.", "alg none, student02": f"{none_head}.{claims(B)}.",
            "unsigned, admin": f"{head}.{claims(FAC)}.", "signature of A on B's claims": f"{h}.{claims(B)}.{s}",
            "signature of A on admin's claims": f"{h}.{claims(FAC)}.{s}", "other key, admin": other.issue_token(FAC, "a"),
            "other key, A": other.issue_token(A, "a"), "truncated signature": good[:-2], "extra char": good + "x",
            "swapped parts": f"{b}.{h}.{s}", "signature = body": f"{h}.{b}.{b}",
            "non-ascii signature": f"{h}.{b}.é", "non-ascii body": f"{h}.é.{s}",
            "very long": good + "A" * 60000, "NUL": good + "\x00", "inner space": good[:10] + " " + good[10:], "unknown user, right key": auth.Auth(KEY, ["mallory"], "mallory", "i").issue_token("mallory", "a"),
        }
        expired = auth.Auth(KEY, USERS, FAC, "i")
        real_time = time.time
        time.time = lambda: real_time() - 7200
        try:
            forged["expired, right key"] = expired.issue_token(A, "a")
        finally:
            time.time = real_time
        return forged

    def test_forged_and_broken_bearer_tokens_are_refused_everywhere(self):
        targets = [("GET", f"/subscriptions{ARM_QS}", None), ("GET", self.rg_path(), None), ("PUT", self.rg_path(), RG_BODY),
                   ("DELETE", self.rg_path(), None), ("PUT", self.cg_path(), cg_body()), ("DELETE", self.cg_path(), None),
                   ("PATCH", self.cg_path(), {"tags": TAGS}), ("GET", self.cg_path(tail="/logs"), None),
                   ("GET", f"/subscriptions/{SUB[FAC]}/resourceGroups{ARM_QS}", None)]
        for name, token in self.forged_tokens().items():
            for method, path, body in targets:
                resp = self.send_judged(method, path, body, headers=[("Authorization", "Bearer " + token)],
                                        label=f"{method} {path.split('?')[0]} with a {name} token")
                if resp.status is not None and resp.status < 500 and resp.status != 401:
                    self.problems.add(f"a {name} token was not refused with 401", f"{method} {path.split('?')[0]}", f"status {resp.status}")
        for value in ("", "Bearer", "Bearer ", "bearer x", "BEARER x", "Basic " + "QTpC", "Token x", "Bearer\tx", self.tokens[A],
                      "Bearer  " + self.tokens[A] + "  ", "Negotiate x", "Bearer " + "A" * 5000):
            resp = self.send_judged("GET", f"/subscriptions{ARM_QS}", headers=[("Authorization", value)],
                                    label=f"GET /subscriptions with Authorization: {shown(value, 60)}")
        for headers in ([], [("Authorization", "Bearer x"), ("Authorization", "Bearer " + self.tokens[A])],
                        [("Authorization", "Bearer " + self.tokens[A]), ("Authorization", "Bearer x")]):
            self.send_judged("GET", f"/subscriptions{ARM_QS}", headers=headers, label=f"GET /subscriptions with headers {headers!r}"[:200])
        self.check_after()

    def test_oversized_and_odd_credentials_in_the_token_endpoint(self):
        good_id, good_secret = auth.app_id(A), auth.client_secret(KEY, A)
        forms = [
            f"grant_type=client_credentials&client_id={good_id}&client_secret={good_secret}&scope=x/.default",
            f"client_id={good_id}&client_secret={good_secret}", f"client_id={good_id}", f"client_secret={good_secret}", "",
            f"client_id={good_id}&client_secret=", f"client_id={good_id}&client_secret=wrong", f"client_id={good_id}&client_secret=é",
            f"client_id={good_id}&client_secret=%C3%A9", f"client_id={good_id}&client_secret=%ff", f"client_id={good_id}&client_secret=中文",
            f"client_id={good_id}&client_secret={good_secret}é", f"client_id={good_id}&client_secret={good_secret}%00",
            f"client_id={good_id}&client_secret=" + "A" * 900_000, f"client_id={good_id}&client_secret={good_secret}&scope=" + "s" * 900_000,
            f"client_id={good_id}&client_id={auth.app_id(B)}&client_secret={good_secret}",
            f"client_id={auth.app_id(B)}&client_id={good_id}&client_secret={good_secret}",
            f"client_id={good_id}&client_secret={good_secret}&client_secret=wrong",
            f"client_id={good_id}&client_secret=wrong&client_secret={good_secret}",
            f"client_id={good_id.upper()}&client_secret={good_secret}", f"client_id={good_id}%00&client_secret={good_secret}",
            f"client_id={good_id}&client_secret={good_secret.upper()}", f"client_id[]={good_id}&client_secret[]={good_secret}",
            f"client_id={auth.app_id(FAC)}&client_secret={good_secret}", f"client_id={auth.app_id(B)}&client_secret={good_secret}",
            f"client_id=&client_secret=", "&&&&", "=", "%", "%zz", "client_id", "client_id=" + "A" * 900_000,
            f"client_id={good_id}&client_secret={good_secret}&scope=%ff%fe", f"client_id={good_id}&client_secret={good_secret}&resource=\x00",
            f"client_id={good_id}&client_secret={good_secret}&scope=https://management.dojo.cloud//.default",
        ]
        bodies = [f.encode("utf-8", "surrogatepass") for f in forms] + [b"\xff\xfe\x00", b"\x00" * 50, b"{}", b'{"client_id":"x"}']
        for paths in (f"/{auth.TENANT_ID}/oauth2/v2.0/token", "/x/oauth2/token"):
            for body in bodies:
                resp = self.send_judged("POST", paths, body, raw=True, headers=[("Content-Type", "application/x-www-form-urlencoded")],
                                        token_endpoint=True, label=f"POST {paths} form={shown(body, 120)}", size=len(body))
                fields = parse_qs(body.decode("utf-8", "replace"))
                right = (fields.get("client_id", [""])[0] == good_id and fields.get("client_secret", [""])[0] == good_secret)
                if resp.status == 200 and not right:
                    self.problems.add("the token endpoint issued a token for credentials that are not exactly a valid pair",
                                      f"form={shown(body, 200)}", "", len(body))
                if resp.status == 200:
                    token = (resp.json() or {}).get("access_token")
                    if self.app.auth.verify_token(token or "") not in (A,):
                        self.problems.add("the token issued does not belong to the client that authenticated", shown(body, 200), str(token)[:40], len(body))
        self.check_after()

    def test_gateway_headers_on_the_portal_api(self):
        """X-Auth-User counts only together with the exact X-Gateway-Token. Everything else is 401/403.
        (Spaces or tabs around a header value are not part of it in HTTP, so ' student01' IS student01.)"""
        users = [A, B, FAC, A.upper(), " " + A, A + " ", A + "\x00", "Student01", "root", "", "mallory", "student1", "*", "student0\uff11"]
        tokens = [TOKEN, TOKEN + " ", " " + TOKEN, TOKEN.upper(), TOKEN[:-1], TOKEN + "x", "", "null", "undefined", "\u00e9", TOKEN * 2, "\x00"]
        for user in users:
            for token in tokens:
                for header_order in (0, 1):
                    headers = [("X-Auth-User", user), ("X-Gateway-Token", token)]
                    headers = headers if header_order == 0 else headers[::-1]
                    resp = self.framed_get("/cloud/api/me", headers, f"GET /cloud/api/me as {shown(user, 30)!r} token {shown(token, 30)!r}")
                    if resp.status == 200:
                        who = (resp.json() or {}).get("user")
                        if token.strip(" \t") != TOKEN or user.strip(" \t") not in USERS:
                            self.problems.add("the portal answered 200 without the exact token and a roster user",
                                              f"user={shown(user, 40)!r} token={shown(token, 40)!r}", f"answered as {who!r}")
                        elif who != user.strip(" \t"):
                            self.problems.add("the portal answered as a different user than X-Auth-User", f"user={user!r}", f"answered as {who!r}")
        # duplicated headers: the first one wins in http.server; Caddy's header_up REPLACES both headers, and only
        # Caddy has the token, so this only has to never yield somebody the caller did not name
        for headers, named in (([("X-Auth-User", B), ("X-Auth-User", A), ("X-Gateway-Token", TOKEN)], {A, B}),
                               ([("X-Auth-User", A), ("X-Gateway-Token", "x"), ("X-Gateway-Token", TOKEN)], {A}),
                               ([("X-Auth-User", A), ("X-Gateway-Token", TOKEN), ("X-Gateway-Token", "x")], {A}),
                               ([("X-Auth-User", A + ", " + B), ("X-Gateway-Token", TOKEN)], set()),
                               ([("X-Auth-User", A), ("x-auth-user", B), ("X-Gateway-Token", TOKEN)], {A, B}),
                               ([("X-Auth-User", A), ("X-Gateway-Token", TOKEN), ("X-Forwarded-User", B), ("X-Cloud-User", B)], {A}),
                               ([("X-Auth-User", A), ("X-Gateway-Token", TOKEN + "\r\nX-Auth-User: " + B)], {A})):
            resp = self.framed_get("/cloud/api/me", headers, f"GET /cloud/api/me with headers {headers!r}"[:220])
            if resp.status == 200 and (resp.json() or {}).get("user") not in named:
                self.problems.add("duplicated identity headers made the portal answer as somebody they do not name", f"{headers!r}"[:200],
                                  str(resp.json())[:100])
        self.check_after()

    def framed_get(self, path, headers, label):
        self.reset()
        before, mark = self.snapshot(), len(self.lines)
        resp = talk(self.port, request_bytes("GET", path, headers))
        self.judge(resp, label, before=before, mark=mark)
        return resp

    def test_another_students_subscription_is_never_reachable_or_changed(self):
        """A holds a valid token for A and throws every method x path shape x spelling at B's subscription and B's
        real resources. Never a 2xx, never a change of B's records, never a call to the executor."""
        rng = self.rng
        self.reset()
        with self.state.lock:
            self.state.cgs[server.App.cg_key(SUB[B], RG, CG)] = {
                "name": CG, "rg": RG, "location": "canadacentral", "tags": dict(TAGS), "body": cg_body("hello-b"),
                "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125}, "port": 20500,
                "container": f"dojo-{B}-{RG}-{CG}", "dnsLabel": "hello-b", "owner": B}
        self.daemon.containers[f"dojo-{B}-{RG}-{CG}"] = docker_api.build_create_request("dojo/hello:1.0", [], 20500, .25, .125, {})
        secret_b = SUB[B]
        for i in range(max(1500, ITERATIONS)):
            sub = rng.choice([SUB[B], SUB[B].upper(), SUB[B] + "/", SUB[B] + ";x", SUB[B].replace("-", "-", 1)])
            rg = rng.choice([RG, RG.upper(), RG + "/", "rg-b", "%72g-fuzz"])
            cg = rng.choice([CG, CG.upper(), CG + "/", CG + ";x", "ci-x"])
            method = rng.choice(["GET", "PUT", "PATCH", "DELETE", "HEAD", "POST"])
            shape = rng.choice(["rg", "cg", "cglist", "rglist", "sub", "logs", "provider-cglist"])
            tail = {"rg": f"/resourceGroups/{rg}", "cg": f"/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/containerGroups/{cg}",
                    "cglist": f"/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/containerGroups",
                    "rglist": "/resourceGroups", "sub": "",
                    "logs": f"/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/containerGroups/{cg}/logs",
                    "provider-cglist": "/providers/Microsoft.ContainerInstance/containerGroups"}[shape]
            body = rng.choice([None, mutate(rng, cg_body("hello-x")), {"tags": TAGS}, RG_BODY])
            path = f"/subscriptions/{sub}{tail}{rng.choice(['', ARM_QS, '?x=1'])}"
            before, mark = self.snapshot(), len(self.lines)
            resp = self.arm(method, path, body, user=A)
            self.judge(resp, f"#{i} {method} {path.split('?')[0]} as {A} body={shown(body, 120)}", before=before, mark=mark,
                       size=len(path))
            if resp.status is not None and resp.status < 400 and method != "HEAD":
                self.problems.add("A got a success answer for B's subscription", f"{method} {path.split('?')[0]}", f"status {resp.status}", len(path))
            if resp.status is not None and resp.status not in (401, 403, 404, 405) and resp.status < 500:
                self.problems.add(f"unexpected status {resp.status} for A against B's subscription (want 403; 404/405 tolerated)",
                                  f"{method} {path.split('?')[0]}", resp.body[:120].decode("latin-1"), len(path))
            if secret_b.encode() in resp.body.replace(b'/subscriptions/' + secret_b.encode() + b"'", b"") and resp.status == 200:
                self.problems.add("B's data appeared in an answer to A", path.split("?")[0], "", len(path))
            if self.daemon.calls:
                self.problems.add("the executor was called for a request against another tenant", f"{method} {path.split('?')[0]}",
                                  str(self.daemon.calls), len(path))
                self.daemon.calls.clear()
            self.assertIn(server.App.cg_key(SUB[B], RG, CG), self.state.cgs, "B's container group was deleted")
        # what A's own lists show: nothing of B's
        for path in (f"/subscriptions/{SUB[A]}/resourceGroups{ARM_QS}",
                     f"/subscriptions/{SUB[A]}/providers/Microsoft.ContainerInstance/containerGroups{ARM_QS}"):
            resp = self.arm("GET", path)
            self.assertNotIn(SUB[B].encode(), resp.body, path)
            self.assertNotIn(b"hello-b", resp.body, path)
        self.check_after()

    def test_portal_api_keeps_tenants_apart_under_odd_spellings(self):
        rng = self.rng
        self.reset()
        with self.state.lock:
            self.state.cgs[server.App.cg_key(SUB[B], RG, CG)] = {
                "name": CG, "rg": RG, "location": "canadacentral", "tags": dict(TAGS), "body": cg_body("hello-b"),
                "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125}, "port": 20500,
                "container": f"dojo-{B}-{RG}-{CG}", "dnsLabel": "hello-b", "owner": B}
        self.daemon.containers[f"dojo-{B}-{RG}-{CG}"] = docker_api.build_create_request("dojo/hello:1.0", [], 20500, .25, .125, {})
        for i in range(max(600, ITERATIONS // 2)):
            sub = rng.choice([SUB[B], SUB[B].upper(), SUB[B].replace("-", "%2d"), "%2e%2e/" + SUB[B], SUB[B] + "%2f", SUB[A] + "%2f../" + SUB[B]])
            rg = rng.choice([RG, RG.upper(), "rg%2dfuzz", RG + "%2f" + CG])
            name = rng.choice([CG, CG.upper(), "ci%2dfuzz", "%2e%2e", CG + "%00"])
            method = rng.choice(["GET", "DELETE", "PATCH", "PUT", "POST"])
            suffix = rng.choice(["", "/logs", "/LOGS", "/logs/x"])
            path = f"/cloud/api/containers/{sub}/{rg}/{name}{suffix}"
            before, mark = self.snapshot(), len(self.lines)
            resp = talk(self.port, request_bytes(method, path, self.gateway(A), b'{"tags":{"owner":"a","env":"b"}}'))
            self.judge(resp, f"#{i} {method} {path} as {A} via the gateway headers", before=before, mark=mark, size=len(path))
            if resp.status == 200:
                self.problems.add("the portal answered 200 for A against B's container group", f"{method} {path}", resp.body[:100].decode("latin-1"))
            self.assertIn(server.App.cg_key(SUB[B], RG, CG), self.state.cgs, f"B's container group was removed by {method} {path}")
        # scope=class is documented (summaries of everyone); it must not carry ARM bodies, logs or secrets
        resp = talk(self.port, request_bytes("GET", "/cloud/api/overview?scope=class", self.gateway(A)))
        self.assertEqual(resp.status, 200)
        self.assertNotIn(b"properties", resp.body)
        self.assertNotIn(b"secureValue", resp.body)
        for path in ("/cloud/api/admin/progress", "/cloud/api/admin/settings", "/cloud/api/activity?scope=all"):
            self.assertEqual(talk(self.port, request_bytes("GET", path, self.gateway(A))).status, 403, path)
        self.assertEqual(talk(self.port, request_bytes("POST", "/cloud/api/admin/purge", self.gateway(A),
                                                        json_bytes({"subscriptionId": SUB[B]}))).status, 403)
        self.assertEqual(talk(self.port, request_bytes("PUT", "/cloud/api/admin/settings", self.gateway(A),
                                                        b'{"writeActions": false}')).status, 403)
        self.check_after()


# ================================================================================================
# 4. the portal API (bodies, parameters, admin routes)
# ================================================================================================
class PortalFuzz(Stack):
    def portal(self, method, path, body=None, user=A, **kw):
        payload = None if body is None else (body if isinstance(body, bytes) else json_bytes(body))
        self.reset(kw.pop("existing", LABEL))
        before, mark = self.snapshot(), len(self.lines)
        resp = talk(self.port, request_bytes(method, path, self.gateway(user), payload))
        request = f"{method} {path} as {user} body={shown(body, 200)}"
        self.judge(resp, request, before=before, mark=mark, size=len(str(body)) + len(path), **kw)
        return resp

    def test_patch_tag_bodies_and_other_bodies(self):
        url = f"/cloud/api/containers/{SUB[A]}/{RG}/{CG}"
        for value in NASTY + [HUGE]:
            for body in ({"tags": value}, {"tags": {"owner": value, "env": "dev"}}, {"tags": {"owner": "a", "env": value}},
                         {"tags": {value if isinstance(value, str) else "k": "v", "owner": "a", "env": "b"}}, value):
                self.portal("PATCH", url, body)
        for i in range(ITERATIONS // 2):
            self.portal("PATCH", url, random_json(self.rng))
        for raw in (b"", b"[", b"null", b"\xff", b"[" * 100_000, b'{"tags":' * 50_000):
            self.portal("PATCH", url, raw)
        self.check_after()

    def test_query_parameters_and_names(self):
        junk = ["", "0", "-1", "1", "500", "501", "1e3", "nan", "inf", "abc", "١٢٣", "9" * 5000, "%00", "%ff", "a b", "1&tail=2", "[]", "%0a", "-0"]
        for value in junk:
            for path in ("/cloud/api/containers/%s/%s/%s/logs?tail=" % (SUB[A], RG, CG), "/cloud/api/activity?limit=",
                         "/cloud/api/activity?scope=", "/cloud/api/overview?scope=", "/cloud/api/activity?scope=all&limit="):
                self.portal("GET", path + value, user=A)
                self.portal("GET", path + value, user=FAC)
        for name in NAMES:
            enc = name.replace("/", "%2f").replace("?", "%3f").replace("#", "%23").replace(" ", "%20") if "\x00" not in name else "x"
            for method in ("GET", "DELETE", "PATCH"):
                self.portal(method, f"/cloud/api/containers/{SUB[A]}/{enc}/{CG}", {"tags": TAGS}, user=A)
                self.portal(method, f"/cloud/api/containers/{SUB[A]}/{RG}/{enc}", {"tags": TAGS}, user=A)
                self.portal(method, f"/cloud/api/containers/{SUB[A]}/{enc}/{enc}/logs", {"tags": TAGS}, user=FAC)
        self.check_after()

    def test_admin_routes_with_hostile_bodies(self):
        for value in NASTY:
            self.portal("PUT", "/cloud/api/admin/settings", {"writeActions": value}, user=FAC)
            self.portal("PUT", "/cloud/api/admin/settings", value, user=FAC)
            self.portal("POST", "/cloud/api/admin/purge", {"subscriptionId": value}, user=FAC)
            self.portal("POST", "/cloud/api/admin/purge", value, user=FAC)
        for raw in (b"", b"null", b"[", b"\xff", b'{"subscriptionId":' + b"[" * 100_000):
            self.portal("POST", "/cloud/api/admin/purge", raw, user=FAC)
            self.portal("PUT", "/cloud/api/admin/settings", raw, user=FAC)
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            for path in ("/cloud/api/me", "/cloud/api/overview", "/cloud/api/activity", "/cloud/api/admin/progress",
                         "/cloud/api/admin/settings", "/cloud/api/admin/purge", "/cloud/api/admin/nope", "/cloud/api/admin",
                         "/cloud/static/app.js", "/cloud/"):
                for user in (A, FAC):
                    resp = self.portal(method, path, {}, user=user, json_reply=not path.startswith(("/cloud/static", "/cloud/")) or "api" in path)
        self.check_after()

    def test_facilitator_only_routes_refuse_students_for_every_method(self):
        for method in ("GET", "PUT", "POST", "PATCH", "DELETE"):
            for path in ("/cloud/api/admin/progress", "/cloud/api/admin/settings", "/cloud/api/admin/purge"):
                resp = self.portal(method, path, {"subscriptionId": SUB[B], "writeActions": False}, user=A)
                if resp.status is not None and resp.status not in (403, 405):
                    self.problems.add("a student got past a facilitator-only route", f"{method} {path}", f"status {resp.status}")
                self.assertIn(server.App.cg_key(SUB[A], RG, CG), self.state.cgs)
        self.check_after()


# ================================================================================================
# 5. the site ingress: only the label's own container, nothing else
# ================================================================================================
class SiteFuzz(Stack):
    class Upstream(BaseHTTPRequestHandler):
        seen = None

        def do_GET(self):
            self.server.seen.append(self.path)
            body = f"upstream {self.server.tag}".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_HEAD = do_GET

        def log_message(self, *a):
            pass

    def start_upstream(self, tag):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.Upstream)
        httpd.seen, httpd.tag, httpd.daemon_threads = [], tag, True
        threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True).start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))
        return httpd

    def setUp(self):
        super().setUp()
        self.one, self.two = self.start_upstream("one"), self.start_upstream("two")
        server.CLOUD_HOST = "127.0.0.1"
        self.addCleanup(lambda: setattr(server, "CLOUD_HOST", self.saved[2]))
        with self.state.lock:
            for user, label, up in ((A, "site-one", self.one), (B, "site-two", self.two)):
                self.state.cgs[server.App.cg_key(SUB[user], RG, CG)] = {
                    "name": CG, "rg": RG, "location": "canadacentral", "tags": dict(TAGS), "body": cg_body(label),
                    "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125}, "port": up.server_address[1],
                    "container": f"dojo-{user}-{RG}-{CG}", "dnsLabel": label, "owner": user}
                self.daemon.containers[f"dojo-{user}-{RG}-{CG}"] = docker_api.build_create_request("dojo/hello:1.0", [], 20000, .25, .125, {})

    def reset(self, existing=None):  # the two seeded sites must survive
        self.lines.clear(), self.unhandled.clear()

    def test_paths_under_a_site_reach_only_that_sites_container_exactly_once(self):
        tails = ["", "/", "/index.html", "/../site-two/", "/..%2fsite-two/", "/%2e%2e/site-two/", "/../../../etc/passwd", "//site-two/",
                 "//evil.example/x", "/http://evil.example/", "/?x=1", "/a?b=c#d", "/%00", "/%0d%0aX-Injected:%201", "/a b", "/a\tb",
                 "/\x7f", "/\x01", "/\x00", "/é", "/ａ", "/" + "a" * 50000, "/;x=1", "/.", "/..", "/./", "/a/./b/../c",
                 "/\\..\\", "/%5c..%5c", "/.git/config", "/proc/self/environ", "/@evil.example", ":80/", "/site-two", "/cloud/site/site-two/"]
        for label in ("site-one", "SITE-ONE", "site-one%2f", "site-one/../site-two", "site-two"):
            for tail in tails:
                for method in ("GET", "HEAD", "POST", "DELETE"):
                    self.one.seen.clear(), self.two.seen.clear()
                    mark = len(self.lines)
                    path = f"/cloud/site/{label}{tail}"
                    resp = talk(self.port, request_bytes(method, path))
                    self.judge(resp, f"{method} {shown(path, 120)}", json_reply=False, mark=mark, size=len(path))
                    if resp.status is not None and resp.status < 500:
                        # anything that reached an upstream must be exactly one request, to the label's own container
                        if label == "site-one" and (len(self.one.seen) > 1 or self.two.seen):
                            self.problems.add("a request under site-one reached another container or reached its own more than once",
                                              f"{method} {shown(path, 120)}", f"one={self.one.seen} two={self.two.seen}")
                        if label == "site-two" and (self.one.seen or len(self.two.seen) > 1):
                            self.problems.add("a request under site-two reached another container or reached its own more than once",
                                              f"{method} {shown(path, 120)}", f"one={self.one.seen} two={self.two.seen}")
                        if label != "site-one" and label != "site-two" and (self.one.seen and self.two.seen):
                            self.problems.add("one request reached both containers", f"{method} {shown(path, 120)}")
                        for seen in self.one.seen + self.two.seen:
                            if not seen.startswith("/") or "\r" in seen or "\n" in seen or " " in seen:
                                self.problems.add("the proxied request line is not a clean origin-form path", f"{method} {shown(path, 120)}", repr(seen))
        self.check_after()

    def test_a_site_reply_cannot_run_script_in_the_portal_origin(self):
        resp = talk(self.port, request_bytes("GET", "/cloud/site/site-one/"))
        self.assertEqual(resp.status, 200)
        csp = resp.headers.get("content-security-policy", [""])[0]
        self.assertIn("sandbox", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertEqual(resp.headers.get("x-content-type-options"), ["nosniff"])


# ================================================================================================
# 6. HTTP framing: what a raw socket can do that a client library will not
# ================================================================================================
class FramingFuzz(Stack):
    def framed(self, payload, label, *, first_only=True, patience=0.0, timeout=4.0, **kw):
        self.reset()
        before, mark = self.snapshot(), len(self.lines)
        resp = talk(self.port, payload, timeout=timeout, first_only=first_only, patience=patience)
        self.judge(resp, label, before=before, mark=mark, size=len(payload), **kw)
        return resp

    def put_headers(self):
        return self.bearer(A) + [("Content-Type", "application/json")]

    def test_content_length_variants(self):
        body = json_bytes(RG_BODY)
        # (a Content-Length LARGER than the body just makes any server wait for the rest, so those are not here)
        for value in ("abc", "", " ", "-1", "-5", "+5", "1e3", "0x10", "1_0", "１２", "5, 5", "5 5", str(len(body)) + "x",
                      "0", "1", str(len(body) - 1), "\t5"):
            payload = (b"PUT " + self.rg_path().encode() + b" HTTP/1.1\r\nHost: x\r\nConnection: close\r\n"
                       + b"".join(to_bytes(k) + b": " + to_bytes(v) + b"\r\n" for k, v in self.bearer(A))
                       + b"Content-Length: " + value.encode("utf-8") + b"\r\n\r\n" + body)
            self.framed(payload, f"PUT resource group with Content-Length: {value!r} and a {len(body)}-byte body", timeout=2.5)
        # no length at all, with a body
        self.framed(b"PUT " + self.rg_path().encode() + b" HTTP/1.1\r\nHost: x\r\nConnection: close\r\n" +
                    b"".join(to_bytes(k) + b": " + to_bytes(v) + b"\r\n" for k, v in self.bearer(A)) + b"\r\n" + body,
                    "PUT resource group with a body and no Content-Length", timeout=2.5)
        self.check_after()

    def test_duplicate_and_conflicting_framing_headers(self):
        body = json_bytes(RG_BODY)
        n = str(len(body)).encode()
        auth_lines = b"".join(to_bytes(k) + b": " + to_bytes(v) + b"\r\n" for k, v in self.bearer(A))
        head = b"PUT " + self.rg_path().encode() + b" HTTP/1.1\r\nHost: x\r\n" + auth_lines
        cases = {
            "two Content-Length (same)": b"Content-Length: " + n + b"\r\nContent-Length: " + n + b"\r\n",
            "two Content-Length (0 then n)": b"Content-Length: 0\r\nContent-Length: " + n + b"\r\n",
            "two Content-Length (n then 0)": b"Content-Length: " + n + b"\r\nContent-Length: 0\r\n",
            "Content-Length and Transfer-Encoding: chunked": b"Content-Length: " + n + b"\r\nTransfer-Encoding: chunked\r\n",
            "Transfer-Encoding: chunked only": b"Transfer-Encoding: chunked\r\n",
            "Transfer-Encoding: identity": b"Transfer-Encoding: identity\r\nContent-Length: " + n + b"\r\n",
            "obsolete line folding": b"Content-Length: " + n + b"\r\n X-Fold: 1\r\n",
            "space before the colon": b"Content-Length : " + n + b"\r\n",
            "Expect: 100-continue": b"Expect: 100-continue\r\nContent-Length: " + n + b"\r\n",
            "Content-Length with tab": b"Content-Length:\t" + n + b"\r\n",
            "header without a colon": b"NoColonHere\r\nContent-Length: " + n + b"\r\n",
            "NUL in a header value": b"X-Null: a\x00b\r\nContent-Length: " + n + b"\r\n",
            "bare LF line ends": b"Content-Length: " + n + b"\n",
            "non-ascii header name": b"X-\xc3\xa9: 1\r\nContent-Length: " + n + b"\r\n",
            "Host twice": b"Host: y\r\nContent-Length: " + n + b"\r\n",
            "Connection: keep-alive, close": b"Connection: keep-alive, close\r\nContent-Length: " + n + b"\r\n",
        }
        for name, lines in cases.items():
            self.framed(head + lines + b"\r\n" + body, f"PUT resource group with {name}", timeout=2.5, patience=0.4)
        self.check_after()

    def test_header_floods(self):
        auth_line = b"Authorization: Bearer " + to_bytes(self.tokens[A]) + b"\r\n"
        base = b"GET /subscriptions HTTP/1.1\r\nHost: x\r\nConnection: close\r\n" + auth_line
        for label, extra in (("one 70 kB header line", b"X-Big: " + b"a" * 70_000 + b"\r\n"),
                             ("150 headers", b"".join(b"X-H%d: v\r\n" % i for i in range(150))),
                             ("5000 headers", b"".join(b"X-H%d: v\r\n" % i for i in range(5000))),
                             ("a 70 kB request line", b""), ("a 200 kB cookie", b"Cookie: " + b"a=b; " * 50_000 + b"\r\n")):
            payload = base + extra + b"\r\n"
            if label.startswith("a 70 kB request line"):
                payload = b"GET /" + b"a" * 70_000 + b" HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
            self.framed(payload, label, timeout=3.0, json_reply=False)  # header-size refusals are http.server's own HTML pages
        self.check_after()

    def test_malformed_request_lines_get_an_answer_not_a_dead_socket(self):
        # A blank request line is not answered (RFC 9112 says to ignore it); the server must simply stay healthy.
        for line in (b"GET", b"GET / HTTP", b"GET / HTTP/9.9", b"GET / HTTP/1.1 extra", b"GET  /  HTTP/1.1",
                     b"GET /\x00 HTTP/1.1", b"\x00\x01\x02", b"GET / HTTP/1.1\x00",
                     b"GET http://evil.example/ HTTP/1.1", b"GET * HTTP/1.1", b"GET /\xff\xfe HTTP/1.1", b"GET / HTTP/1.1\r\n\r\n\r\n",
                     b"GET /subscriptions\xa0HTTP/1.1", b"GET /a\x85b HTTP/1.1", b"GET / HTTP/1.0", b"POST / HTTP/2.0",
                     b"PRI * HTTP/2.0"):
            payload = line + (b"\r\nHost: x\r\nConnection: close\r\n\r\n" if b"\r\n" not in line else b"")
            self.framed(payload, f"raw request line {shown(line, 80)}", timeout=2.5, json_reply=True,
                        allow_status=(505,))  # 505: an HTTP version we do not speak
        for blank in (b"", b"\r\n"):
            talk(self.port, blank + b"\r\nHost: x\r\nConnection: close\r\n\r\n", timeout=1.5)
        self.check_after()

    def test_unknown_methods_are_refused_without_side_effects(self):
        """http.server answers 501 itself for a method with no do_* handler; that is a refusal (RFC 9110), not a
        crash, so 405 and 501 are both accepted here, and only here. Nothing may change."""
        for method in ("OPTIONS", "TRACE", "CONNECT", "PROPFIND", "MKCOL", "COPY", "MOVE", "LOCK", "BREW", "LINK", "UNLINK", "PURGE", "get", "Put"):
            for path in (self.rg_path(), self.cg_path(), "/cloud/api/me", "/cloud/", "/healthz", "/metadata/endpoints", "/cloud/site/x-y/"):
                self.reset()
                before, mark = self.snapshot(), len(self.lines)
                resp = talk(self.port, request_bytes(method, path, self.bearer(A) + self.gateway(A), b"{}"), timeout=2.5)
                self.judge(resp, f"{method} {path}", json_reply=False, before=before, mark=mark, allow_status=(501,))
                if resp.status is not None and resp.status not in (400, 401, 403, 404, 405, 501):
                    self.problems.add("an unknown method was not refused", f"{method} {path}", f"status {resp.status}")
        # HEAD must not mutate and must not carry a body
        for path in (self.rg_path(), self.cg_path(), "/cloud/api/me"):
            self.reset()
            resp = talk(self.port, request_bytes("HEAD", path, self.bearer(A) + self.gateway(A)), timeout=2.5)
            self.judge(resp, f"HEAD {path}", json_reply=False)
        self.check_after()

    def test_oversized_body_is_refused_and_does_not_smuggle_a_second_request(self):
        """The body cap is 1 MB: server._body() reads min(Content-Length, 1 MB) and (as of this writing) leaves the
        rest on the socket. Caddy keeps its connection to cloud-api open between requests, so anything left unread is
        parsed as the NEXT request on that connection and its answer goes to whoever uses the connection next.
        The connection must be closed (or the body drained): exactly one response, and the smuggled request must
        not be executed."""
        smuggled = request_bytes("GET", "/healthz", keepalive=True)
        for over in (1, 1000, 2_000_000):
            body = b" " * 1_000_000 + smuggled + b"#" * over
            payload = request_bytes("PUT", self.rg_path(), self.bearer(A), body, keepalive=True)
            resp = self.framed(payload, f"PUT with a {len(body)}-byte body ({len(smuggled)}-byte GET /healthz after the 1 MB cap, keep-alive)",
                               first_only=True, patience=1.0, timeout=8.0)
            if resp.status is not None and resp.status < 400:
                self.problems.add("a body above the 1 MB cap was accepted", f"{len(body)} bytes", f"status {resp.status}")
        # exact-cap body in a valid JSON document is still fine
        pad = "x" * (1_000_000 - len(json_bytes({"location": "canadacentral", "tags": {"owner": "s", "env": "dev", "p": ""}})) - 4)
        body = json_bytes({"location": "canadacentral", "tags": {"owner": "s", "env": "dev", "p": pad}})
        self.framed(request_bytes("PUT", self.rg_path(), self.bearer(A), body), f"PUT with a {len(body)}-byte body just under the cap", timeout=8.0)
        self.check_after()

    def test_pipelined_requests_are_answered_one_for_one(self):
        two = request_bytes("GET", "/healthz", keepalive=True) + request_bytes("GET", "/readyz", keepalive=True)
        resp = self.framed(two, "two pipelined GETs", first_only=True, patience=0.6, timeout=4.0, responses=2)
        if not resp.error and [r[0] for r in resp.responses] != [200, 200]:
            self.problems.add("two pipelined requests did not get two 200 answers", "GET /healthz + GET /readyz",
                              str([r[0] for r in resp.responses]))
        self.check_after()

    def test_slow_and_stalled_clients_do_not_hang_the_next_request(self):
        """A client that sends half a request and stops holds one thread; other requests must still be answered."""
        stalled = []
        try:
            for _ in range(40):
                s = socket.create_connection(("127.0.0.1", self.port), timeout=2)
                s.sendall(b"PUT /subscriptions HTTP/1.1\r\nHost: x\r\nContent-Length: 500\r\n\r\n{")
                stalled.append(s)
            started = time.monotonic()
            resp = talk(self.port, request_bytes("GET", "/healthz"), timeout=3)
            self.judge(resp, "GET /healthz while 40 half-sent requests are open", json_reply=True)
            if time.monotonic() - started > 2:
                self.problems.add("the server was slow to answer while stalled clients were connected", "40 stalled clients", "")
        finally:
            for s in stalled:
                s.close()
        self.check_after()


# ================================================================================================
# 7. docker_api.build_create_request, directly
# ================================================================================================
class BuilderFuzz(unittest.TestCase):
    """The builder is "the ONE place a container spec is assembled". Whatever it is given, it must either
    refuse or produce a hardened request. Two things it leaves to its callers (the policy validates env names, the
    server fixes the label keys) are probed separately and marked as known defence-in-depth gaps."""

    FIXED = {"dojo.owner": A, "dojo.rg": RG, "dojo.name": CG}
    DEFAULTS = dict(image="dojo/hello:1.0", env_pairs=[("MESSAGE", "hi")], host_port=20001, cpu=0.25, memory_gb=0.125, labels=FIXED)

    def setUp(self):
        self.rng = random.Random(f"{SEED}:{self.id()}")

    def build(self, **over):
        args = copy.deepcopy(self.DEFAULTS)
        args.update(over)
        try:
            return args, docker_api.build_create_request(**args), None
        except (docker_api.DockerError, ValueError, TypeError, OverflowError, ArithmeticError, AttributeError) as exc:
            return args, None, exc   # refusing is a safe answer

    def check(self, problems, args, spec):
        problems.requests += 1
        if spec is None:
            return
        shown_args = {k: v for k, v in args.items() if v != self.DEFAULTS.get(k)}
        for problem in spec_violations(spec):
            problems.add(f"builder output: {problem}", shown(shown_args, 240))
        if spec["Image"] != args["image"]:
            problems.add("builder changed the image", shown(shown_args, 240))
        if spec["Labels"] != dict(args["labels"], **{docker_api.LABEL_MANAGED: "true"}):
            problems.add("builder changed or dropped a label", shown(shown_args, 240))

    def numbers(self):
        return [0, -1, -0.0, 1e-12, 1e-9, 1e-6, 0.001, 0.005, 0.009, 0.01, 0.0058, 0.006, 0.125, 0.25, 0.2500001, 0.26, 1, 2, 64, 1e308,
                float("nan"), float("inf"), float("-inf"), "0.25", "0.1", "1e-12", "abc", "", "nan", "inf", True, False, None, [0.25],
                {"a": 1}, 2 ** 70, -2 ** 70, b"0.1", "\u0660.\u0662", complex(1, 1)]

    def finish(self, problems):
        if problems.groups:
            self.fail("\n" + problems.report())

    def test_numbers_never_produce_an_unlimited_or_negative_cap(self):
        problems = Problems()
        for cpu in self.numbers():
            for mem in self.numbers():
                args, spec, _ = self.build(cpu=cpu, memory_gb=mem)
                self.check(problems, args, spec)
        self.finish(problems)

    def test_every_image_ref_is_refused_unless_allow_listed(self):
        problems = Problems()
        for image in IMAGES + [None, 1, [], {}, b"dojo/hello:1.0", ("dojo/hello:1.0",)]:
            _, spec, exc = self.build(image=image)
            problems.requests += 1
            if type(image) is str and image in policy.ALLOWED_IMAGES:
                if spec is None:
                    problems.add("an allow-listed image was refused", shown(image), repr(exc))
            elif spec is not None:
                problems.add("a non-allow-listed image produced a create request", shown(image), shown(spec, 200))
        self.finish(problems)

    def test_host_port_is_a_number_or_a_refusal(self):
        problems = Problems()
        for port in [20000, "20005", 20999, 0, 80, 65536, 2 ** 40, "80", " 5", "5\n", "\u0665", 1.5, True, "1; rm -rf /", "1:2", "",
                     None, [80], {"a": 1}, "0x10", float("nan"), float("inf"), "20000/tcp", "0.0.0.0:80", "20000\n80"]:
            args, spec, _ = self.build(host_port=port)
            self.check(problems, args, spec)
            try:
                int(port)
                numeric = True
            except (TypeError, ValueError, OverflowError):
                numeric = False
            if spec is not None and not numeric:
                problems.add("a value that is not a number produced a create request", shown(port))
            if spec is not None and numeric and spec["HostConfig"]["PortBindings"] != {"80/tcp": [{"HostPort": str(int(port))}]}:
                problems.add("the host port in the request is not the number that was given", shown(port))
        self.finish(problems)

    def test_label_values_and_env_values_cannot_add_keys_or_entries(self):
        problems = Problems()
        values = ["v", "", "a" * 100000, "\n", "\x00", "\u00e9", "\ud800", "x=y", "\n--privileged", "$(id)"]
        for owner in values:
            for rg in values[:6]:
                args, spec, _ = self.build(labels={"dojo.owner": owner, "dojo.rg": rg, "dojo.name": owner})
                self.check(problems, args, spec)
        for value in values:
            for name in ("MESSAGE", "OWNER"):
                args, spec, _ = self.build(env_pairs=[(name, value)])
                self.check(problems, args, spec)
                if spec is not None and spec["Env"] != [f"{name}={value}"]:
                    problems.add("an env value changed the number or shape of entries", shown((name, value)))
        self.finish(problems)

    def test_random_argument_tuples(self):
        problems = Problems()
        rng = self.rng
        for _ in range(ITERATIONS):
            args, spec, _ = self.build(
                image=rng.choice(IMAGES), env_pairs=[(rng.choice(["MESSAGE", "OWNER", "X"]), rng.choice(NASTY[23:60]))
                                                     for _ in range(rng.randrange(0, 12))],
                host_port=rng.choice([20000, 20999, 3, "3", None, 2 ** 20]), cpu=rng.choice(self.numbers()),
                memory_gb=rng.choice(self.numbers()),
                labels={k: rng.choice(["a", "b\n", "c" * 300]) for k in rng.sample(sorted(self.FIXED), rng.randrange(0, 4))})
            self.check(problems, args, spec)
        self.finish(problems)

    @unittest.expectedFailure
    def test_known_gap_builder_alone_accepts_any_label_key_and_env_name(self):
        """DEFENCE IN DEPTH, not reachable over the network: the server always passes the three fixed label keys and
        the policy has already validated env names, so the builder does not check either. If it ever did, this test
        would start to pass ("unexpected success") and the marker should go."""
        problems = Problems()
        for labels in ({"com.docker.compose.project": "x"}, {"traefik.enable": "true"}, {"x=y": "z"}, {"": "z"}):
            args, spec, _ = self.build(labels=labels)
            if spec is not None:
                problems.add("a label key outside the fixed set reached the create request", shown(labels))
        for name in ("A B", "A=B", "A\nB", "", "1A", "LD_PRELOAD", "PATH"):
            _, spec, _ = self.build(env_pairs=[(name, "v")])
            if spec is not None:
                problems.add("an unsafe env name reached the create request", shown(name))
        self.finish(problems)


if __name__ == "__main__":
    unittest.main()
