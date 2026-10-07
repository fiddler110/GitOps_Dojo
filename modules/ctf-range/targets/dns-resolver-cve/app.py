"""dns-resolver-cve — CTF target 6 (plan docs/CTF-WORKSHOP-PLAN.md §7.3,
CTF-3 "Vulnerable and outdated components", ties `dns-as-code`). The real
flaw is CVE-2022-30295 in uClibc / uClibc-ng ≤ 1.0.40: the stub resolver
assigns monotonically increasing DNS transaction IDs, so an attacker who
observes one lookup can predict the next and land a single spoofed reply
that steers the agent to an address of their choosing. Confirmed empirically
on 2026-10-06 against the pinned Bootlin x86-64--uclibc--stable-2021.11-5
toolchain's uClibc-ng 1.0.39 (docs/CTF-SPIKES.md "Target 6" addendum): 20
getaddrinfo calls emitted TXIDs 2,3,4,...,21 — strictly +1 each query.
Source ports are kernel-ephemeral, not static as some writeups and the
earlier plan draft claimed — the lab exposes this honestly in /observations.

The agent is a real static ELF cross-compiled against that libc (see
agent.c and ctf-host/Dockerfile's dns-resolver-cve-agent-build stage); it
is NOT a Python simulation. Every DNS query the lab shows at /observations
was emitted by the actual uClibc stub.

Why the attack is modelled on loopback inside one container, instead of
across ctf_net to a sibling container as the earlier plan draft imagined:
the range's ctf-host runs every slot inside an inner dockerd with
--icc=false and a DOCKER-USER drop on NEW outbound (ctf-host/entrypoint.sh)
— a slot cannot reach another slot across the inner bridge at all, so a
cross-slot off-path attack is architecturally impossible here. The CVE
itself (predictable TXID, kernel-ephemeral source port) is real and
observable; the mechanical staging is local. The lesson doesn't change: a
service that trusts DNS to find its backend hands its credentials to
whoever controls resolution; the fix is to update the resolver pin past
uClibc-ng 1.0.41.

Three processes share this one container's address space (threads, not
subprocesses — no fork required and nothing writes to disk):

  * The uClibc agent (./agent, launched by this file) resolves
    `vault.svc.internal` every AGENT_PERIOD_SECONDS and POSTs its service
    token (CTF_TARGET_TOKEN, derived HMAC — see the module.env block that
    sets it) as `Authorization: Bearer <token>` to the resolved IP on
    port AGENT_VAULT_PORT (default 9000).

  * The DNS answerer (bound 127.0.0.1:5353 — unprivileged, since the slot
    runs with CapDrop ALL and no CAP_NET_BIND_SERVICE) accepts the agent's
    queries, logs each (iter, txid, src_port) pair into a bounded ring
    buffer the panel exposes at /observations, and ANSWERS one of two
    ways: normally with 127.0.0.1 (the real vault), or with 127.0.0.2 (the
    attacker's capture point) exactly when the current pending-spoof's
    predicted TXID matches the incoming query's TXID — i.e. the student
    predicted correctly. A wrong TXID gets the normal answer; the spoof
    stays pending until the next query lands with the right TXID (so a
    one-TXID-off guess doesn't permanently waste the slot).

  * The HTTP control panel (Flask, bound 0.0.0.0:5000) is what the student
    reaches over the gateway. Endpoints:
      GET  /                 index + instructions
      GET  /observations     recent (iter, txid, qname) emissions
      POST /spoof            {"predicted_txid": N} — arms one spoof
      GET  /spoof            the active spoof's state
      GET  /captured         after a successful spoof: the credential +
                             flag 1 (CTF_TARGET_TOKEN); 404 before
      POST /admin            Authorization: Bearer <captured token> ->
                             flag 2 (CTF_FLAG). Any other token -> 401.
      GET  /admin            describes the endpoint but gives nothing

  * Two in-process HTTP listeners stand in for the "real vault" and the
    "attacker's receiver": 127.0.0.1:9000 and 127.0.0.2:9000. (127/8 is
    all-local on lo and binds unprivileged, so no caps or extra setup are
    needed.) Both answer the same shape so the agent never knows which it
    reached; the attacker's receiver stores the delivered token in a
    module-level slot the /captured endpoint reads.

  * One decoy :2222 ssh-banner listener (plan §7.3's nmap primer, same
    shape every other target in this ladder uses — not a real sshd under
    this range's CapDrop ALL; see e.g. ping-tool/app.py's identical
    comment for the full why).

Env:
  CTF_FLAG                 flag 2 — admin endpoint reward (plan §5).
  CTF_TARGET_TOKEN         flag 1 — the service token the agent carries;
                           captured by the attacker's receiver on a
                           successful spoof.
  CTF_STUDENT              the student handle; logged only.
  PORT                     control panel listen port (default 5000).
  AGENT_PERIOD_SECONDS     how often the agent resolves + checks in (default 2).
"""
import os
import socket
import struct
import subprocess
import threading
import time
from collections import deque

from flask import Flask, jsonify, request

# --- flag / credential wiring -------------------------------------------------
# CTF_FLAG is handed up when a request bearing the captured token reaches /admin
# — the plan's "second flag on the same host" the spoof chain unlocks.
# CTF_TARGET_TOKEN is what the agent carries and what the attacker's receiver
# captures when a spoof lands; it is itself flag 1 (submittable to dojo-flag
# as challenge "dns-resolver-cve-token", a separate HMAC derivation from
# CTF_FLAG — ctf-controller/controller.py's AttackManager._env_for does both).
FLAG = os.environ.get("CTF_FLAG", "flag{dns-resolver-cve-dev0000000000}")
TOKEN = os.environ.get("CTF_TARGET_TOKEN", "flag{dns-resolver-cve-token-dev0000000000}")
STUDENT = os.environ.get("CTF_STUDENT", "studentNN")

# --- loopback plumbing --------------------------------------------------------
# 127.0.0.1 is the "real vault"; 127.0.0.2 is the on-box attacker's receiver.
# A spoofed DNS answer swaps the agent's resolve from the first to the second;
# the rest is plain TCP on port 9000, which both bind.
VAULT_ADDR = "127.0.0.1"
ATTACKER_ADDR = "127.0.0.2"
VAULT_PORT = 9000

# --- shared state the DNS answerer, the attacker receiver and the panel use --
_lock = threading.Lock()
_observations = deque(maxlen=64)        # [{iter, txid, src_port, qname, answered_with}]
_obs_counter = 0
_pending_spoof = {"predicted_txid": None, "set_at": 0.0, "fired_at": 0.0}
_captured = {}                          # {token, flag, source_addr, when}

# --- the DNS answerer ---------------------------------------------------------
# A tiny UDP server on 127.0.0.1:5353 (unprivileged). Reads one query at a
# time, records it, answers A record with the vault's address UNLESS a spoof
# is pending AND its predicted TXID matches the incoming query's TXID, in
# which case it answers with the attacker's address instead. One answer per
# query, no retries, no caching — a stub resolver doesn't cache, so this is
# per-lookup redirection: the next agent cycle after a successful spoof is
# the one that lands at the attacker.

def _parse_qname(data, offset=12):
    labels = []
    while True:
        length = data[offset]
        offset += 1
        if length == 0:
            break
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    return ".".join(labels), offset


def _build_a_reply(req, ip):
    # Mirror TXID + Question; set QR=1, RA=1, ANCOUNT=1.
    txid = req[:2]
    header = txid + struct.pack(">HHHHH", 0x8180, 1, 1, 0, 0)
    i = 12
    while req[i] != 0:
        i += 1 + req[i]
    end_q = i + 1 + 4
    question = req[12:end_q]
    rr = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 30, 4) + socket.inet_aton(ip)
    return header + question + rr


def _dns_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5353))
    global _obs_counter
    while True:
        data, addr = sock.recvfrom(4096)
        if len(data) < 12:
            continue
        txid = struct.unpack(">H", data[:2])[0]
        try:
            qname, _end = _parse_qname(data)
        except (IndexError, UnicodeDecodeError):
            continue
        with _lock:
            # Spoof check — a correct prediction redirects THIS reply only
            # and clears the pending spoof (recording when it fired).
            answered_with = VAULT_ADDR
            if _pending_spoof["predicted_txid"] == txid:
                answered_with = ATTACKER_ADDR
                _pending_spoof["fired_at"] = time.time()
                _pending_spoof["predicted_txid"] = None
            _obs_counter += 1
            _observations.append({
                "iter": _obs_counter,
                "txid": txid,
                "src_port": addr[1],
                "qname": qname,
                "answered_with": answered_with,
            })
        try:
            sock.sendto(_build_a_reply(data, answered_with), addr)
        except OSError:
            pass


# --- the "real vault" and the attacker's receiver -----------------------------
# Both are minimal HTTP/1.0 servers reading one request and sending back a
# 200. Only the attacker's receiver stores the delivered Bearer token.

def _read_request(conn):
    conn.settimeout(2.0)
    buf = b""
    try:
        while b"\r\n\r\n" not in buf and len(buf) < 4096:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
    except OSError:
        return b""
    return buf


def _extract_bearer(req):
    for line in req.split(b"\r\n"):
        if line.lower().startswith(b"authorization:"):
            value = line.split(b":", 1)[1].strip()
            if value.lower().startswith(b"bearer "):
                return value[7:].decode("ascii", "replace").strip()
    return ""


def _vault_handler(conn, remote):
    _ = _read_request(conn)
    try:
        conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nok\n")
    except OSError:
        pass
    finally:
        conn.close()


def _attacker_handler(conn, remote):
    req = _read_request(conn)
    tok = _extract_bearer(req)
    if tok:
        with _lock:
            _captured["token"] = tok
            _captured["flag"] = tok  # the token IS flag 1 (dns-resolver-cve-token)
            _captured["source_addr"] = remote[0] if remote else ""
            _captured["when"] = time.time()
    try:
        # Answer the same shape as the real vault so the agent never notices.
        conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nok\n")
    except OSError:
        pass
    finally:
        conn.close()


def _bind_tcp(addr, port, handler, label):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((addr, port))
    srv.listen(16)

    def _loop():
        while True:
            try:
                conn, remote = srv.accept()
            except OSError:
                continue
            threading.Thread(target=handler, args=(conn, remote), daemon=True).start()
    t = threading.Thread(target=_loop, daemon=True, name=label)
    t.start()


# --- the agent subprocess -----------------------------------------------------
# Launched once at startup; the Python app does not try to restart it on exit
# (a crashed agent means the slot is broken, which is a controller problem,
# not something to paper over here). Its stdout rides along in docker logs.

def _start_agent():
    env = {
        **os.environ,
        "AGENT_NS_ADDR": "127.0.0.1",
        "AGENT_NS_PORT": "5353",
        "AGENT_VAULT_NAME": "vault.svc.internal",
        "AGENT_VAULT_PORT": str(VAULT_PORT),
        "AGENT_PERIOD_SECONDS": os.environ.get("AGENT_PERIOD_SECONDS", "2"),
        "CTF_TARGET_TOKEN": TOKEN,
    }
    # Give the DNS answerer and the TCP listeners a moment to bind before the
    # first lookup fires; the agent itself retries on resolve failure anyway,
    # but a clean first-iteration keeps `docker logs` readable.
    time.sleep(0.3)
    subprocess.Popen(["/app/agent"], env=env, close_fds=True)


# --- Flask control panel ------------------------------------------------------
app = Flask(__name__)


INDEX_HTML = """\
<!doctype html>
<html lang=en><head><meta charset=utf-8><title>vault-gateway</title></head>
<body>
<h1>vault-gateway <small>— internal check-in bus</small></h1>
<p>An internal agent in this box resolves <code>vault.svc.internal</code>
every couple of seconds and checks in with its service token. The agent is
linked against <strong>uClibc-ng&nbsp;1.0.39</strong> — a build in the
<strong>CVE-2022-30295</strong> range (predictable DNS transaction IDs). The
resolver is a stub, so it does not cache; every cycle is its own fresh
lookup.</p>
<h2>Endpoints</h2>
<ul>
  <li><a href=/observations>GET /observations</a> — recent DNS queries the
     agent has emitted (iter, txid, qname, which answer was returned)</li>
  <li><code>POST /spoof</code> body <code>{"predicted_txid": N}</code> —
     arm one spoofed answer; fires on the next query whose TXID equals N</li>
  <li><a href=/spoof>GET /spoof</a> — current pending spoof state</li>
  <li><a href=/captured>GET /captured</a> — the service token the attacker's
     receiver captured if the spoof already landed</li>
  <li><a href=/admin>GET /admin</a> — describes the admin endpoint</li>
  <li><code>POST /admin</code> with <code>Authorization: Bearer &lt;token&gt;</code></li>
</ul>
<p><em>student:</em> <code>%s</code></p>
</body></html>
"""


@app.get("/")
def index():
    return INDEX_HTML % STUDENT, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/observations")
def observations():
    with _lock:
        rows = list(_observations)
    return jsonify({
        "count": len(rows),
        "observations": rows,
        "note": "txids are a monotonic +1 counter (CVE-2022-30295); the next txid will be the last one + 1",
    })


@app.route("/spoof", methods=["GET", "POST"])
def spoof():
    if request.method == "GET":
        with _lock:
            return jsonify(dict(_pending_spoof))
    body = request.get_json(silent=True) or {}
    try:
        predicted = int(body.get("predicted_txid"))
    except (TypeError, ValueError):
        return jsonify({"error": "predicted_txid (int) is required"}), 400
    if not (0 <= predicted <= 0xFFFF):
        return jsonify({"error": "predicted_txid must be a 16-bit DNS id"}), 400
    with _lock:
        _pending_spoof["predicted_txid"] = predicted
        _pending_spoof["set_at"] = time.time()
        _pending_spoof["fired_at"] = 0.0
    return jsonify({"status": "armed", "predicted_txid": predicted})


@app.get("/captured")
def captured():
    with _lock:
        if not _captured:
            return jsonify({"status": "nothing captured yet"}), 404
        return jsonify(dict(_captured))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        return (
            "<p>POST here with <code>Authorization: Bearer &lt;service token&gt;</code>. "
            "Only the agent's own service token is accepted — anything else returns 401.</p>",
            200, {"Content-Type": "text/html; charset=utf-8"},
        )
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return jsonify({"error": "missing Bearer credentials"}), 401
    presented = header.split(None, 1)[1].strip()
    # The real vault's auth check: constant-time compare against the agent's
    # own service token — the whole target reduces to possessing that token.
    import hmac as _hmac
    if not _hmac.compare_digest(presented, TOKEN):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"status": "authenticated", "flag": FLAG})


# --- decoy :2222 (plan §7.3's nmap primer, same shape as every other target) --
def _decoy_ssh_handler(conn, _remote):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
    except OSError:
        pass
    finally:
        conn.close()


# --- bring it up --------------------------------------------------------------
# Threads for every background listener, then the Flask app in the foreground.
# (The agent is launched after the listeners bind so its first lookup can
# resolve cleanly — see _start_agent's comment.)
threading.Thread(target=_dns_loop, daemon=True, name="dns-answerer").start()
_bind_tcp(VAULT_ADDR, VAULT_PORT, _vault_handler, "vault-receiver")
_bind_tcp(ATTACKER_ADDR, VAULT_PORT, _attacker_handler, "attacker-receiver")
_bind_tcp("0.0.0.0", 2222, _decoy_ssh_handler, "decoy-ssh")
threading.Thread(target=_start_agent, daemon=True, name="agent-launcher").start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
