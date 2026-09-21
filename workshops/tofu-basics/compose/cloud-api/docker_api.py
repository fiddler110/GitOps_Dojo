"""The executor: turns an approved container-group request into a container on
cloud-host through the Docker Engine API on a unix socket.

Students never speak Docker. The create request is built HERE from a fixed
template; the only student-influenced inputs are an allow-listed image, a
validated env list, and numbers we clamp — nothing else can reach the daemon
(no mounts, no privileged, no host networking, no added capabilities). See
test_executor.py.
"""
import http.client
import json
import socket
import struct
from urllib.parse import quote

import policy

LABEL_MANAGED = "dojo.managed"


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


def build_create_request(image, env_pairs, host_port, cpu, memory_gb, labels):
    """The ONE place a container spec is assembled. Pure function (tested)."""
    if image not in policy.ALLOWED_IMAGES:
        raise DockerError(f"image {image!r} is not allowed")
    cpu = min(float(cpu), policy.MAX_CPU)
    memory_gb = min(float(memory_gb), policy.MAX_MEMORY_GB)
    return {
        "Image": image,
        "Env": [f"{name}={value}" for name, value in env_pairs],
        "Labels": dict(labels, **{LABEL_MANAGED: "true"}),
        "ExposedPorts": {"80/tcp": {}},
        "HostConfig": {
            "PortBindings": {"80/tcp": [{"HostPort": str(int(host_port))}]},
            "Memory": int(memory_gb * 1024 ** 3),
            "MemorySwap": int(memory_gb * 1024 ** 3),
            "NanoCpus": int(cpu * 1e9),
            "PidsLimit": 64,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            # dockerd (cloud-host) brings student containers back when cloud-host itself restarts. Otherwise
            # they stay Exited, the site 502s, and `plan` says "No changes" (T8.9). unless-stopped, not
            # always: nothing here ever stops a container except remove(), which deletes it.
            "RestartPolicy": {"Name": "unless-stopped"},
            "Privileged": False,
            "ReadonlyRootfs": False,  # the hello entrypoint writes /www
        },
    }


class Executor:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    def _call(self, method, path, body=None):
        conn = _UnixConnection(self.socket_path)
        try:
            payload = json.dumps(body).encode() if body is not None else None
            headers = {"Content-Type": "application/json"} if payload else {}
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        except OSError as exc:
            raise DockerError(f"cloud-host unreachable: {exc}") from exc
        finally:
            conn.close()

    def ping(self):
        try:
            return self._call("GET", "/_ping")[0] == 200
        except DockerError:
            return False

    def image_present(self, image):
        """True if cloud-host has this image. Only allow-listed images can be asked about, so
        the request path stays a fixed template like everything else here. Raises DockerError
        if cloud-host cannot be asked (an unknown answer is not "missing")."""
        if image not in policy.ALLOWED_IMAGES:
            raise DockerError(f"image {image!r} is not allowed")
        status, _ = self._call("GET", f"/images/{quote(image)}/json")
        if status not in (200, 404):
            raise DockerError(f"image inspect failed ({status})")
        return status == 200

    def create(self, name, image, env_pairs, host_port, cpu, memory_gb, labels):
        spec = build_create_request(image, env_pairs, host_port, cpu, memory_gb, labels)
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
        return "Running" if info["State"].get("Running") else "Terminated"

    def _list_names(self, all_states, extra_filters=None):
        filters = dict(extra_filters or {}, label=[f"{LABEL_MANAGED}=true"])
        status, data = self._call(
            "GET", f"/containers/json?all={'true' if all_states else 'false'}"
                   f"&filters={quote(json.dumps(filters))}")
        if status != 200:
            raise DockerError(f"list failed ({status})")
        return [c["Names"][0].lstrip("/") for c in json.loads(data)]

    def list_managed(self):
        return self._list_names(True)

    def list_running(self):
        """Names of running managed containers: ONE call for the portal's status column
        (never one inspect per container)."""
        return set(self._list_names(False, {"status": ["running"]}))

    def logs(self, name, tail=200):
        status, data = self._call(
            "GET", f"/containers/{quote(name)}/logs?stdout=1&stderr=1&tail={int(tail)}")
        if status != 200:
            return None
        out, i = [], 0
        while i + 8 <= len(data):  # multiplexed stream: 8-byte header per frame
            size = struct.unpack(">I", data[i + 4:i + 8])[0]
            out.append(data[i + 8:i + 8 + size].decode(errors="replace"))
            i += 8 + size
        return "".join(out)
