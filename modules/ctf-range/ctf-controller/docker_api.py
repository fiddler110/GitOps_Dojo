"""The executor: turns a slot request into a container inside ctf-host through
the Docker Engine API on the shared unix socket.

The controller's ENTIRE capability over ctf-host is here, and it is deliberately
narrow (spike S6/S14): pull an allow-listed image by name, then create / start /
stop / remove a slot container built from a fixed template. No build, no
Dockerfile, no bind mounts, no privileged, no host networking, no added
capabilities — nothing a controller compromise could turn into host control.
The create body is assembled HERE from a template; the only slot-influenced
inputs are an allow-listed image tag, a validated env list and a clamped port.
See tests/test_executor.py.
"""
import http.client
import json
import socket
from urllib.parse import quote

LABEL_MANAGED = "ctf.managed"
LABEL_SLOT = "ctf.slot"
LABEL_USER = "ctf.user"
LABEL_IMAGE = "ctf.image"
# Which catalog entry an attack slot (controller.py's AttackManager, CTF-D20)
# is currently running; the always-on CTF-5 slots above never set this.
LABEL_TARGET = "ctf.target"


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


def allowed_image(image, registry_prefix, extra=()):
    """A slot may only ever run the base target image, a tag the in-lab
    registry serves under the approved prefix (what defend-main.yml pushes),
    or one of EXTRA — the attack-range catalog (controller.py's
    CTF_ATTACK_TARGETS, CTF-D20), a short, config-supplied allow-list of exact
    image tags, never a pattern. Anything else — a Hub image, a latest tag, a
    different name — is refused before it reaches the daemon."""
    if image == "ctf-customer-portal:base":
        return True
    if registry_prefix and image.startswith(registry_prefix + "/"):
        return True
    return image in extra


def build_create_request(image, env_pairs, ports,
                         memory_bytes, pids_limit, labels):
    """The ONE place a slot spec is assembled. Pure function (tested).

    `ports` is a list of (container_port, host_port) or (container_port,
    host_port, host_ip) tuples. The 3-tuple form binds the publish to a
    specific IP on the ctf-host host namespace (controller.py's
    AttackManager uses this to give each student their own IP on ctf_net
    with the target's native ports — one IP per attack box in the student's
    private block, see "HackTheBox-style" in controller.py). The 2-tuple
    form keeps the pre-change behaviour: publish on 0.0.0.0 of ctf-host,
    one host port per student (CTF-5 reconcile still does this).

    Hardening matches targets/customer-portal's compose service: read-only root,
    tmpfs for the only writable paths, all capabilities dropped, no new privs.
    """
    exposed = {}
    bindings = {}
    for item in ports:
        if len(item) == 3:
            container_port, host_port, host_ip = item
        else:
            container_port, host_port = item
            host_ip = ""
        port_key = f"{int(container_port)}/tcp"
        exposed[port_key] = {}
        binding = {"HostPort": str(int(host_port))}
        if host_ip:
            binding["HostIp"] = str(host_ip)
        bindings[port_key] = [binding]
    return {
        "Image": image,
        "Env": [f"{name}={value}" for name, value in env_pairs],
        "Labels": dict(labels, **{LABEL_MANAGED: "true", LABEL_IMAGE: image}),
        "ExposedPorts": exposed,
        "HostConfig": {
            "PortBindings": bindings,
            "Memory": int(memory_bytes),
            "MemorySwap": int(memory_bytes),  # no swap beyond the limit
            "PidsLimit": int(pids_limit),
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "ReadonlyRootfs": True,
            # The only writable paths the app needs; both ephemeral, so a
            # recreate reseeds a clean DB (the fix lives in the image, not here).
            # A tmpfs mounts root-owned by default, but the app runs as the
            # image's non-root user (uid 10014), so /data is given that uid/gid
            # or the read-only-root app cannot create its SQLite file.
            "Tmpfs": {
                "/tmp": "rw,nosuid,nodev,mode=1777",
                "/data": "rw,nosuid,nodev,size=16m,uid=10014,gid=10014,mode=0700",
            },
            # dockerd brings slots back if ctf-host restarts; nothing stops a
            # slot except remove(), which deletes it.
            "RestartPolicy": {"Name": "unless-stopped"},
            "Privileged": False,
        },
    }


class Executor:
    def __init__(self, socket_path, registry_prefix="", extra_images=()):
        self.socket_path = socket_path
        self.registry_prefix = registry_prefix
        self.extra_images = frozenset(extra_images)

    def _call(self, method, path, body=None, timeout=30):
        conn = _UnixConnection(self.socket_path, timeout=timeout)
        try:
            payload = json.dumps(body).encode() if body is not None else None
            hdrs = {"Content-Type": "application/json"} if payload else {}
            conn.request(method, path, body=payload, headers=hdrs)
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

    def image_present(self, image):
        status, _ = self._call("GET", f"/images/{quote(image, safe='')}/json")
        if status not in (200, 404):
            raise DockerError(f"image inspect failed ({status})")
        return status == 200

    def pull(self, image):
        """Pull an allow-listed image from the in-lab registry. Offline posture:
        the registry is internal (CTF-D24); this never reaches the internet."""
        if not allowed_image(image, self.registry_prefix, self.extra_images):
            raise DockerError(f"image {image!r} is not allowed")
        status, data = self._call("POST", f"/images/create?fromImage={quote(image, safe='')}",
                                  timeout=120)
        if status != 200:
            raise DockerError(f"pull failed ({status}): {data[:200]!r}")

    def create(self, name, image, env_pairs, ports,
               memory_bytes, pids_limit, labels):
        if not allowed_image(image, self.registry_prefix, self.extra_images):
            raise DockerError(f"image {image!r} is not allowed")
        spec = build_create_request(image, env_pairs, ports,
                                    memory_bytes, pids_limit, labels)
        status, data = self._call("POST", f"/containers/create?name={quote(name)}", spec)
        if status != 201:
            raise DockerError(f"create failed ({status}): {data[:200]!r}")
        status, data = self._call("POST", f"/containers/{quote(name)}/start")
        if status not in (204, 304):
            self.remove(name)
            raise DockerError(f"start failed ({status}): {data[:200]!r}")

    def remove(self, name):
        status, _ = self._call("DELETE", f"/containers/{quote(name)}?force=true&v=true")
        return status in (204, 404)

    def inspect(self, name):
        status, data = self._call("GET", f"/containers/{quote(name)}/json")
        return json.loads(data) if status == 200 else None

    def state(self, name):
        info = self.inspect(name)
        if info is None:
            return None
        return "running" if info["State"].get("Running") else "stopped"

    def image_of(self, name):
        """The image tag a running slot was created from (from its label), or None."""
        info = self.inspect(name)
        if info is None:
            return None
        return (info.get("Config", {}).get("Labels") or {}).get(LABEL_IMAGE)

    def list_managed(self):
        filters = {"label": [f"{LABEL_MANAGED}=true"]}
        status, data = self._call(
            "GET", f"/containers/json?all=true&filters={quote(json.dumps(filters))}")
        if status != 200:
            raise DockerError(f"list failed ({status})")
        return [c["Names"][0].lstrip("/") for c in json.loads(data)]
