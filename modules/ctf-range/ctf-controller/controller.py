"""ctf-controller — the single, unprivileged client of the boxed ctf-host dind
(decision CTF-D21, spike S14). It is the only thing in the range that can start
or replace a target slot, and students can never reach it (it sits on the
internal `ctf_ops` network).

Two jobs:

  * Reconcile (CTF-5 model, §4 "Exception: CTF-5"): keep one always-on
    customer-portal slot running per student, created from the base image, each
    seeded for that student and handed that student's flag value (§5). A slot
    already running a patched image is left alone — reconcile never rolls a fix
    back.

  * Redeploy in place (the live tail of the S6 loop that defend-main.yml
    calls): on merge to main the pipeline pushes the student's rebuilt image to
    the in-lab registry and POSTs here; the controller pulls that tag and
    recreates the slot UNDER THE SAME NAME AND ADDRESS, so the attacker bot's
    next probe hits the patched app without anything being redirected. The
    wall-of-shame entry then flips LIVE → DISCONNECTED (§8.12).

The controller never builds an image and never sees a Dockerfile; its whole
reach into ctf-host is docker_api.Executor (pull / create / start / stop / rm).

A third job lives here too, in a separate class (AttackManager, below):
student-controlled start/stop/reset for the CTF-1 to CTF-4 attack ladder
(§4 "Student-controlled targets, one live per slot", decision CTF-D20). It
shares the executor and the ctf-host connection but nothing else with the
always-on CTF-5 model above — a different slot name, a different published-
port range, and (unlike reconcile()) nothing auto-creates a slot: it stays
"stopped" until a student asks for a target. See AttackManager's docstring.
"""
import hmac
import http.server
import json
import os
import re
import signal
import socket
import socketserver
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has
# copied it in (SHARED= in module.env) — the AttackManager HTTP paths below
# are gateway-identity-gated (X-Auth-User + X-Gateway-Token), unlike this
# file's existing Bearer-token paths, which dojo_http has nothing to do with.
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402

import docker_api
import flags

TICK = 10          # reconcile loop period, seconds
# Per-slot published port inside ctf-host: BASE + index. Overridable
# (CTF_HOST_PORT_BASE) because the web-terminal firewall hook
# (modules/ctf-range/terminal/start.d/50-ctf-range.sh) computes the same
# address from the same roster/index and must agree with this value - see
# that hook's header comment.
HOST_PORT_BASE = 15000
# AttackManager's own port range — deliberately a different base than the
# always-on CTF-5 slots above, so the two slot kinds can never collide on
# ctf-host even for the same student. terminal/start.d/50-ctf-range.sh's
# per-uid firewall rule must agree with this value, same pairing as
# CTF_HOST_PORT_BASE (that hook's header comment).
ATTACK_PORT_BASE = 16000
# How many ports every attack-ladder slot publishes to its student IP: the
# target's real app port plus a fixed block of decoy ports (plan §7.3's nmap
# primer — a student scans their box and finds more than the one port
# they'll actually use, same as a HackTheBox box). Nothing varies per
# target image here; one that doesn't bind every container port just leaves
# that slot silent (closed, not "open but refused" — same no-op-ACCEPT
# reasoning 50-ctf-range.sh's header comment gives for an idle range).
# DECOY_*_CONTAINER_PORT are the fixed internal ports a target's own decoy
# listener binds if it wants that slot (see targets/*/app.py's "decoy
# listeners"); nothing here cares whether a given image actually uses them.
ATTACK_PORT_BLOCK = 3
DECOY_SSH_CONTAINER_PORT = 2222
DECOY_FTP_CONTAINER_PORT = 2121

# HackTheBox-style per-target IPs (student request 2026-10-07). Each student
# gets one IP on ctf_net PER attack target in the pack's catalog, carved out
# of this base octet range. student01 (roster idx 0, 1st target idx 0) ->
# <subnet-prefix>.100 ; student01 2nd target -> .101 ; student02 1st -> .104
# with ATTACK_IPS_PER_STUDENT=4. ctf-host adds every one of these addresses
# to its eth1 at startup (modules/ctf-range/ctf-host/entrypoint.sh); the
# per-student terminal firewall accepts the student's own 4-IP range only.
# Only one target slot per student is live at a time (CTF-D20) — the other
# three IPs are reserved but silent until the student starts that target.
ATTACK_IP_BASE_OCTET = 100
ATTACK_IPS_PER_STUDENT = 4
ATTACK_IDLE_SECONDS = 20 * 60  # plan §4 "Limits": ~20 min with no traffic
ATTACK_MAX_CONCURRENT = 10     # plan §4 "Start queue": ~10 at once (tuned in S14)


def _mem_bytes(text, default=128 * 1024 ** 2):
    """Parse a compose-style size ('128m', '1g', '536870912') to bytes."""
    m = re.fullmatch(r"\s*(\d+)\s*([kmg]?)\s*", (text or "").lower())
    if not m:
        return default
    n = int(m.group(1))
    return n * {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}[m.group(2)]


def parse_targets(text):
    """CTF_ATTACK_TARGETS ('ctf-1=some/image:tag,ctf-2=...') -> {id: image},
    in order. Blank/unset -> {} — no targets wired yet (module.env default;
    the real target-1..4 images are CTF-S8, not built as of this module). The
    AttackManager below is fully generic over whatever this catalog holds, so
    wiring a real target is a config change here, never a code change."""
    out = {}
    for pair in (text or "").split(","):
        pair = pair.strip()
        if not pair:
            continue
        tid, _, image = pair.partition("=")
        tid, image = tid.strip(), image.strip()
        if tid and image:
            out[tid] = image
    return out


def roster(env):
    """The students who get an always-on slot. Matches the engine's padding
    exactly (allocator STUDENT_IDS, `{n:02d}`), as cloud-api's roster() does."""
    prefix = env.get("STUDENT_PREFIX", "student")
    try:
        count = int(env.get("STUDENT_COUNT", "0") or 0)
    except ValueError:
        count = 0
    return [f"{prefix}{n:02d}" for n in range(1, count + 1)]


def _ctf_host_addr():
    """ctf-host's address on ctf_net, for the landing-page Attack Range
    header. Read from /run/ctf/ctf-net-addr if ctf-host wrote it (that
    container's entrypoint picks the address of its own eth that falls
    inside CTF_NET_SUBNET; see modules/ctf-range/ctf-host/entrypoint.sh);
    the file is on the shared ctf_run volume mounted into both services.
    Falls back to gethostbyname("ctf-host") only as a last resort -- that
    returns our shared ctf_ops address, not the ctf_net one, which is
    wrong for a student view (caught live 2026-10-06: the status page
    showed 10.89.4.3 instead of 10.42.0.x). Empty => the header shows just
    the hostname + subnet with no numeric address."""
    try:
        with open("/run/ctf/ctf-net-addr") as f:
            addr = f.read().strip()
            if addr:
                return addr
    except OSError:
        pass
    try:
        return socket.gethostbyname("ctf-host")
    except OSError:
        return ""


class Config:
    def __init__(self, env=os.environ):
        self.socket = env.get("CTF_SOCKET", "/run/ctf/docker.sock")
        self.control_token = env.get("CTF_CONTROL_TOKEN", "")
        self.registry = env.get("CTF_REGISTRY", "").rstrip("/")
        self.base_image = env.get("CTF_BASE_IMAGE", "ctf-customer-portal:base")
        self.container_port = int(env.get("CTF_TARGET_PORT", "5000"))
        self.mem_bytes = _mem_bytes(env.get("CTF_TARGET_MEM_LIMIT", "128m"))
        self.pids = int(env.get("CTF_TARGET_PIDS_LIMIT", "256"))
        self.seed = env.get("STUDENT_PASSWORD_SEED", "")
        self.host_port_base = int(env.get("CTF_HOST_PORT_BASE", "") or HOST_PORT_BASE)
        self.users = roster(env)
        # Stable per-user index → container name and published port, so a
        # recreate keeps the same address (§4 "Stable slot address").
        self.index = {u: i for i, u in enumerate(self.users)}
        # -- AttackManager (CTF-D20): the student-toggled CTF-1..4 ladder --
        # the gateway's per-upstream token for this service's /attack/*
        # paths (render_extensions.py's upstream_tokens; compose passes it in
        # as GATEWAY_TOKEN, never the shared master).
        self.gateway_token = env.get("GATEWAY_TOKEN", "")
        self.facilitator = env.get("FACILITATOR_USERNAME", "")
        self.attack_targets = parse_targets(env.get("CTF_ATTACK_TARGETS", ""))
        self.attack_port_base = int(env.get("CTF_ATTACK_PORT_BASE", "") or ATTACK_PORT_BASE)
        self.attack_port_block = int(env.get("CTF_ATTACK_PORT_BLOCK", "") or ATTACK_PORT_BLOCK)
        self.attack_idle_seconds = int(env.get("CTF_ATTACK_IDLE_SECONDS", "") or ATTACK_IDLE_SECONDS)
        self.attack_max_concurrent = int(env.get("CTF_ATTACK_MAX_CONCURRENT", "") or ATTACK_MAX_CONCURRENT)
        # ctf_net scan range shown to the student on the landing-page Attack
        # Range header. The subnet is pinned in modules/ctf-range/compose.yml
        # (ctf_net.ipam) and read here through CTF_NET_SUBNET; the firewall
        # hook (terminal/start.d/50-ctf-range.sh) default-denies on the same
        # CIDR so the student's scan only ever surfaces ctf-host. ctf-host's
        # address inside the subnet is resolved at startup instead of pinned
        # (podman-compose does not honour ipv4_address pins -- live caught
        # 2026-10-06 as "requested ip 10.42.0.2 already allocated"); an empty
        # subnet or unresolvable name => the page falls back to just
        # "ctf-host" with no numeric hints.
        self.net_subnet = env.get("CTF_NET_SUBNET", "")
        self.net_host_addr = env.get("CTF_HOST_ADDR", "") or _ctf_host_addr()
        # Attack IP block: see ATTACK_IP_BASE_OCTET above. Both must stay in
        # step with ctf-host/entrypoint.sh and terminal/start.d/50-ctf-range.sh.
        self.attack_ip_base_octet = int(env.get("CTF_ATTACK_IP_BASE_OCTET", "") or ATTACK_IP_BASE_OCTET)
        self.attack_ips_per_student = int(env.get("CTF_ATTACK_IPS_PER_STUDENT", "") or ATTACK_IPS_PER_STUDENT)
        # Subnet prefix: "10.42.0.0/24" -> "10.42.0". Empty => per-target IPs
        # are disabled and attack_ports falls back to the pre-2026-10-07 port
        # block scheme (still used by CTF-5 reconcile).
        self.attack_subnet_prefix = ""
        if self.net_subnet:
            parts = self.net_subnet.split("/")[0].split(".")
            if len(parts) == 4:
                self.attack_subnet_prefix = ".".join(parts[:3])

    def slot_name(self, user):
        return f"ctf-{flags.CHALLENGE}-{user}"

    def host_port(self, user):
        return self.host_port_base + self.index.get(user, 0)

    def attack_slot_name(self, user):
        return f"ctf-attack-{user}"

    def attack_host_port(self, user):
        """The one port a student is told nothing about — the real app's
        port, offset 0 in that student's block (status()'s own comment:
        "a student finds their own port with nmap")."""
        return self.attack_port_base + self.index.get(user, 0) * self.attack_port_block

    def attack_target_ip(self, user, target_id):
        """IP this student's slot for `target_id` binds to on ctf_net
        (HackTheBox-style per-box IP, 2026-10-07). Blank if the subnet
        prefix isn't configured or the target isn't in this pack's catalog
        -- in which case attack_ports() falls back to the port-block
        binding on ctf-host's main IP."""
        if not self.attack_subnet_prefix or target_id not in self.attack_targets:
            return ""
        user_idx = self.index.get(user, 0)
        target_idx = list(self.attack_targets).index(target_id)
        octet = self.attack_ip_base_octet + user_idx * self.attack_ips_per_student + target_idx
        if octet > 254:
            return ""
        return f"{self.attack_subnet_prefix}.{octet}"

    def attack_target_ips(self, user):
        """{target_id: ip} for every target in this pack's catalog, in order.
        Used by /attack/status so the landing-page cards can show each
        target's reserved IP."""
        return {tid: self.attack_target_ip(user, tid) for tid in self.attack_targets}

    def attack_ports(self, user, target_id=None):
        """Port publish list for this student's attack slot.

        With a configured subnet prefix + known target, binds to the
        student's dedicated IP for that target with the target's own
        container ports (5000 app + 2222/2121 decoys). One IP per box,
        same ports -- "scan 10.42.0.100 and find your target" (student
        request 2026-10-07).

        Falls back to the old port-block binding on ctf-host's main IP
        if the prefix is unset or the target isn't in the catalog --
        keeps CTF-5 reconcile and any pack that hasn't opted in working.
        """
        host_ip = self.attack_target_ip(user, target_id) if target_id else ""
        if host_ip:
            return [
                (self.container_port, self.container_port, host_ip),
                (DECOY_SSH_CONTAINER_PORT, DECOY_SSH_CONTAINER_PORT, host_ip),
                (DECOY_FTP_CONTAINER_PORT, DECOY_FTP_CONTAINER_PORT, host_ip),
            ]
        base = self.attack_host_port(user)
        return [
            (self.container_port, base),
            (DECOY_SSH_CONTAINER_PORT, base + 1),
            (DECOY_FTP_CONTAINER_PORT, base + 2),
        ]


class Controller:
    def __init__(self, cfg, executor, clock=time.time):
        self.cfg = cfg
        self.ex = executor
        self.clock = clock
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.last_ok = 0
        self.error = ""
        self.snapshot = {"ready": False, "slots": [], "error": "starting", "updated": 0}

    # -- slot operations ---------------------------------------------------

    def _env_for(self, user):
        return [
            ("CTF_STUDENT", user),
            ("CTF_FLAG", flags.render(user, self.cfg.seed)),
            ("PORT", str(self.cfg.container_port)),
        ]

    def _create_slot(self, user, image):
        """Create (replacing any existing) one slot for `user` from `image`."""
        name = self.cfg.slot_name(user)
        self.ex.remove(name)
        self.ex.create(
            name=name,
            image=image,
            env_pairs=self._env_for(user),
            ports=[(self.cfg.container_port, self.cfg.host_port(user))],
            memory_bytes=self.cfg.mem_bytes,
            pids_limit=self.cfg.pids,
            labels={docker_api.LABEL_SLOT: user, docker_api.LABEL_USER: user},
        )

    def redeploy(self, user, image=None):
        """The S6 live tail. Pull (if a registry tag) and recreate the user's
        slot in place from `image` (default: the base image). Returns (ok, msg)."""
        if user not in self.cfg.index:
            return False, f"unknown slot {user!r}"
        image = image or self.cfg.base_image
        with self.lock:
            try:
                if image != self.cfg.base_image:
                    # A registry tag: pull it first (base is already imported).
                    self.ex.pull(image)
                elif not self.ex.image_present(image):
                    return False, f"base image {image!r} not present on ctf-host"
                self._create_slot(user, image)
            except docker_api.DockerError as exc:
                return False, str(exc)
        return True, f"redeployed {self.cfg.slot_name(user)} <- {image}"

    def reconcile(self):
        """Ensure every student has a running slot. A slot already running a
        (patched) image is left as-is — reconcile never downgrades a fix."""
        try:
            present = set(self.ex.list_managed())
        except docker_api.DockerError as exc:
            self.error = str(exc)
            return
        for user in self.cfg.users:
            name = self.cfg.slot_name(user)
            try:
                state = self.ex.state(name) if name in present else None
                if state is None:
                    self._create_slot(user, self.cfg.base_image)
                elif state != "running":
                    # Recreate from whatever image it already carries, so a
                    # patched slot that stopped comes back patched.
                    self._create_slot(user, self.ex.image_of(name) or self.cfg.base_image)
            except docker_api.DockerError as exc:
                self.error = f"{name}: {exc}"

    # -- state for callers / readiness -------------------------------------

    def ready(self):
        return self.ex.ping() and self.error == ""

    def healthy(self):
        return self.clock() - self.last_ok < 3 * TICK

    def _snapshot(self):
        rows = []
        try:
            for user in self.cfg.users:
                name = self.cfg.slot_name(user)
                rows.append({
                    "user": user, "name": name,
                    "state": self.ex.state(name) or "absent",
                    "image": self.ex.image_of(name) or "",
                    "port": self.cfg.host_port(user),
                })
        except docker_api.DockerError as exc:
            self.error = str(exc)
        with self.lock:
            self.snapshot = {
                "ready": self.ex.ping(),
                "slots": rows,
                "error": self.error,
                "updated": int(self.clock()),
            }

    def tick(self):
        if self.ex.ping():
            self.error = ""
            self.reconcile()
            self.last_ok = self.clock()
        else:
            self.error = "ctf-host unreachable"
        self._snapshot()

    def loop(self):
        while True:
            self.tick()
            self.wake.wait(TICK)
            self.wake.clear()


class AttackManager:
    """One toggle-able target per student (§4 "Student-controlled targets,
    one live per slot", CTF-1 to CTF-4 only, decision CTF-D20).

    Per-user state is one of:
        stopped   nothing running (the resting state; nothing to clean up)
        queued    a start/reset is waiting for a free worker slot
        starting  a worker is mid create() for this user right now
        live      running; `target`/`started_at` are set
        error     the last create() failed; `error` holds why

    Start and reset both go through ONE FIFO queue, drained by up to
    `cfg.attack_max_concurrent` jobs at a time (plan's "~10 at once, tuned in
    S14"), so a room that all clicks Start together doesn't spike ctf-host. A
    student has at most one request in the queue — a second start while
    already queued/starting is refused, not stacked. Stop always skips the
    queue (it only removes a container, and frees a worker slot for someone
    else). See process_one()/loop() for the worker side; tests call
    process_one() directly rather than spinning up threads.
    """

    def __init__(self, cfg, executor, clock=time.time):
        self.cfg = cfg
        self.ex = executor
        self.clock = clock
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.slots = {}   # user -> {target, state, queued_at, started_at, error}
        self.queue = []   # FIFO of usernames waiting for a worker
        self.running = 0  # jobs currently mid-create(), <= cfg.attack_max_concurrent

    def _slot(self, user):
        return self.slots.setdefault(
            user, {"target": None, "state": "stopped", "queued_at": 0, "started_at": 0, "error": ""})

    def catalog(self):
        return [{"id": tid} for tid in self.cfg.attack_targets]

    def status(self, user):
        """A JSON-safe snapshot for one student. Deliberately carries no port
        — the card shows only that a target is reachable at ctf-host; a
        student finds their own port with nmap (plan §4 "Card")."""
        with self.lock:
            slot = dict(self._slot(user))
            slot["queue_position"] = self.queue.index(user) + 1 if user in self.queue else None
        return slot

    def _env_for(self, user, target):
        return [
            ("CTF_STUDENT", user),
            ("CTF_TARGET", target),
            ("CTF_FLAG", flags.render(user, self.cfg.seed, challenge=target)),
            # A second, generic per-(user, target) secret, same derivation as
            # CTF_FLAG but its own challenge tag so the two can never collide.
            # Most targets ignore it; it exists for a target whose *foothold*
            # lives outside ctf_net entirely (git-secrets, target 8: the
            # credential sits in a Forgejo repo's history, not in this
            # container) and needs a value it can check a presented
            # credential against without ever holding STUDENT_PASSWORD_SEED
            # itself. The provisioning side (e.g. a start.d hook) computes the
            # identical value independently, same two-copies-not-shared-code
            # idiom as every other flag/token render in this range.
            ("CTF_TARGET_TOKEN", flags.render(user, self.cfg.seed, challenge=f"{target}-token")),
            ("PORT", str(self.cfg.container_port)),
        ]

    def start(self, user, target):
        if target not in self.cfg.attack_targets:
            return False, f"unknown target {target!r}"
        with self.lock:
            slot = self._slot(user)
            if slot["state"] in ("queued", "starting"):
                return False, f"already {slot['state']}"
            if slot["state"] == "live" and slot["target"] == target:
                return True, "already live"
            slot["target"], slot["state"], slot["error"] = target, "queued", ""
            slot["queued_at"] = self.clock()
            self.queue.append(user)
        self.wake.set()
        return True, "queued"

    def stop(self, user):
        """Skips the queue. Cancels a queued request outright; refuses while
        a worker is mid-create (it will be done in moments — a create() is
        too short-lived to need a cancellation path of its own)."""
        with self.lock:
            slot = self._slot(user)
            if slot["state"] == "stopped":
                return True, "already stopped"
            if slot["state"] == "starting":
                return False, "still starting, try again in a moment"
            if slot["state"] == "queued":
                if user in self.queue:
                    self.queue.remove(user)
                slot.update(target=None, state="stopped", error="")
                return True, "cancelled"
            name = self.cfg.attack_slot_name(user)
        try:
            self.ex.remove(name)
        except docker_api.DockerError as exc:
            with self.lock:
                slot["error"] = str(exc)
            return False, str(exc)
        with self.lock:
            slot.update(target=None, state="stopped", started_at=0, error="")
        return True, "stopped"

    def reset(self, user):
        """Re-queue the SAME target fresh — stop() then start() would also
        work, but would make a student's one pending-request slot briefly
        free between the two calls; this way reset is one atomic queue
        entry, exactly like a fresh start."""
        with self.lock:
            slot = self._slot(user)
            target = slot["target"]
            if not target:
                return False, "no target to reset"
            if slot["state"] in ("queued", "starting"):
                return False, f"already {slot['state']}"
            slot["state"], slot["error"] = "queued", ""
            slot["queued_at"] = self.clock()
            self.queue.append(user)
        self.wake.set()
        return True, "queued"

    # -- worker side ---------------------------------------------------

    def process_one(self):
        """Pop and run one queued job if a worker slot is free. Returns True
        if it did anything, so loop() can keep draining without sleeping."""
        with self.lock:
            if self.running >= self.cfg.attack_max_concurrent or not self.queue:
                return False
            user = self.queue.pop(0)
            slot = self._slot(user)
            if slot["state"] != "queued":  # cancelled while it was waiting
                return True
            target = slot["target"]
            slot["state"] = "starting"
            self.running += 1
        image = self.cfg.attack_targets.get(target)
        name = self.cfg.attack_slot_name(user)
        try:
            self.ex.remove(name)
            self.ex.create(
                name=name, image=image, env_pairs=self._env_for(user, target),
                ports=self.cfg.attack_ports(user, target),
                memory_bytes=self.cfg.mem_bytes, pids_limit=self.cfg.pids,
                labels={docker_api.LABEL_SLOT: user, docker_api.LABEL_USER: user,
                        docker_api.LABEL_TARGET: target},
            )
        except docker_api.DockerError as exc:
            with self.lock:
                self.running -= 1
                slot.update(state="error", error=str(exc))
            return True
        with self.lock:
            self.running -= 1
            slot.update(state="live", started_at=self.clock(), error="")
        return True

    def sweep_idle(self):
        """Auto-stop a live slot after cfg.attack_idle_seconds (plan §4
        "Limits"). Time-based, not real traffic: the controller sits off
        ctf-host's data path and has no visibility into a target's actual
        connections (docker_api.py's docstring on what it is allowed to
        reach) — a deliberate scoped-down simplification, same spirit as the
        wall of shame's minimal slice. Revisit if idle-but-untouched slots
        turn out to matter in a real class."""
        now = self.clock()
        with self.lock:
            stale = [u for u, s in self.slots.items()
                     if s["state"] == "live" and now - s["started_at"] > self.cfg.attack_idle_seconds]
        for user in stale:
            self.stop(user)

    def loop(self):
        while True:
            while self.process_one():
                pass
            self.sweep_idle()
            self.wake.wait(TICK)
            self.wake.clear()


# -- HTTP control API ------------------------------------------------------
# Reachable only by the allocator / the defend pipeline on ctf_ops. Mutating
# routes need the control token; /healthz is open for compose's healthcheck.
# AttackManager's /attack/* paths are a separate auth scheme entirely — see
# their own comment below.

def make_handler(ctl, atk):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-controller"
        sys_version = ""

        def log_message(self, fmt, *args):  # quiet
            pass

        def _json(self, status, doc):
            body = json.dumps(doc).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _static(self, body, ctype):
            dojo_http.send(self, 200, body, ctype)

        def _gw_user(self):
            """The gateway-vouched-for identity for the /attack/* paths — a
            wholly separate scheme from _authed()'s Bearer control token
            below (dojo_http.py, FIND-16: X-Auth-User only counts alongside
            this upstream's own X-Gateway-Token). None if either is missing
            or wrong."""
            return dojo_http.gateway_user(self.headers, ctl.cfg.gateway_token)

        def _authed(self):
            want = ctl.cfg.control_token
            if not want:
                return False  # fail closed: no token configured = no access
            given = self.headers.get("Authorization", "")
            if given.startswith("Bearer "):
                given = given[len("Bearer "):]
            return hmac.compare_digest(given.encode(), want.encode())

        def _path(self):
            return self.path.split("?", 1)[0] or "/"

        def do_GET(self):
            path = self._path()
            if path == "/healthz":
                self._json(200 if ctl.healthy() else 503,
                           {"ok": ctl.healthy(), "ready": ctl.ready(), "error": ctl.error})
                return
            # The attack-range card (static/): nothing secret in the page
            # shell itself, same as any other module's SPA. The gateway
            # route is identity-gated already, so anyone reaching this at
            # all is an authenticated account; the data the page fetches
            # (below) is what actually checks who.
            if path in ("/", "/index.html"):
                self._static(STATIC["index.html"], "text/html; charset=utf-8")
                return
            if path == "/app.js":
                self._static(STATIC["app.js"], "application/javascript; charset=utf-8")
                return
            if path == "/app.css":
                self._static(STATIC["app.css"], "text/css; charset=utf-8")
                return
            if path == "/attack-cards.js":
                self._static(STATIC["attack-cards.js"], "application/javascript; charset=utf-8")
                return
            if path == "/attack-cards.css":
                self._static(STATIC["attack-cards.css"], "text/css; charset=utf-8")
                return
            if path == "/attack/status":
                user = self._gw_user()
                if not user:
                    self._json(403, {"error": "gateway token required"})
                    return
                # Scan target shown on the landing page's Attack Range header
                # (static for the stack's lifetime) + per-target IPs so each
                # card shows the student their own IP for that specific box.
                net = {"host": "ctf-host", "subnet": ctl.cfg.net_subnet, "addr": ctl.cfg.net_host_addr}
                if user == ctl.cfg.facilitator:
                    self._json(200, {"ok": True, "facilitator": True,
                                     "targets": atk.catalog(), "slot": None, "net": net})
                    return
                target_ips = ctl.cfg.attack_target_ips(user)
                targets = [dict(t, addr=target_ips.get(t["id"], "")) for t in atk.catalog()]
                self._json(200, {"ok": True, "facilitator": False,
                                 "targets": targets, "slot": atk.status(user), "net": net})
                return
            if not self._authed():
                self._json(403, {"error": "control token required"})
                return
            if path == "/slots":
                self._json(200, ctl.snapshot)
                return
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def _audit(self, action, result):
            print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "event": "ctf-controller", "action": action, "result": result},
                             separators=(",", ":")), flush=True)

        def do_POST(self):
            path = self._path()
            is_attack = path.startswith("/attack/")
            user = None
            if is_attack:
                user = self._gw_user()
                if not user:
                    self._json(403, {"error": "gateway token required"})
                    return
            elif not self._authed():
                self._json(403, {"error": "control token required"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 2048:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "bad request"})
                return
            if is_attack:
                if user == ctl.cfg.facilitator:
                    self._json(403, {"error": "facilitator account has no attack slot"})
                    return
                if path == "/attack/start":
                    target = body.get("target")
                    if not isinstance(target, str):
                        self._json(400, {"error": "bad target"})
                        return
                    ok, msg = atk.start(user, target)
                    self._json(200 if ok else 409, {"ok": ok, "message": msg})
                    return
                if path == "/attack/stop":
                    ok, msg = atk.stop(user)
                    self._json(200 if ok else 409, {"ok": ok, "message": msg})
                    return
                if path == "/attack/reset":
                    ok, msg = atk.reset(user)
                    self._json(200 if ok else 409, {"ok": ok, "message": msg})
                    return
                self._json(404, {"error": "not found"})
                return
            if path == "/redeploy":
                user = str(body.get("user") or "")
                image = body.get("image")
                if image is not None and not isinstance(image, str):
                    self._json(400, {"error": "bad image"})
                    return
                ok, msg = ctl.redeploy(user, image)
                self._audit(f"redeploy {user} {image or '(base)'}", "ok" if ok else msg)
                self._json(200 if ok else 409, {"ok": ok, "message": msg})
                return
            if path == "/reconcile":
                ctl.wake.set()
                self._json(200, {"ok": True, "message": "reconcile scheduled"})
                return
            self._json(404, {"error": "not found"})

    return Handler


# The attack-range card's page shell (static/, allow-listed by name — fixed
# set, loaded once at start, same pattern as dns-ui's zone-viewer).
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(HERE, "static"))
STATIC = {}
for _name in ("index.html", "app.js", "app.css", "attack-cards.js", "attack-cards.css"):
    with open(os.path.join(STATIC_DIR, _name), "rb") as _f:
        STATIC[_name] = _f.read()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    cfg = Config()
    ex = docker_api.Executor(cfg.socket, registry_prefix=cfg.registry,
                             extra_images=set(cfg.attack_targets.values()))
    ctl = Controller(cfg, ex)
    atk = AttackManager(cfg, ex)
    threading.Thread(target=ctl.loop, daemon=True).start()
    threading.Thread(target=atk.loop, daemon=True).start()
    print(f"[ctf-controller] {len(cfg.users)} slot(s), base {cfg.base_image}, "
          f"registry {cfg.registry or '(none)'}, {len(cfg.attack_targets)} attack target(s)", flush=True)
    Server(("0.0.0.0", 9000), make_handler(ctl, atk)).serve_forever()


if __name__ == "__main__":
    main()
