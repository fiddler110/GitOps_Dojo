"""idor-pcap — CTF target 1 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-1
"Access and identity"). A "support ticket archive" that serves numbered
packet captures with NO ownership check — any signed-in-feeling visitor can
download any `/data/<n>` regardless of whose ticket it is (classic IDOR,
"enumeration" teaching point). One of them is a real, parseable pcap file
holding a cleartext FTP control-channel login for a service account; that
account's password is reused on this box's `/admin` diagnostics endpoint
(credential reuse, same lesson row 5 `leaky-config` goes deeper on).

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).

**Scoped simplification, stated plainly (same spirit as other targets'
documented cuts):** the ladder row's escalation text is "a Python binary with
cap_setuid" — real Linux-capability privilege escalation, which needs an
actual local shell. This attack-ladder architecture (ctf-controller) gives a
student exactly one published TCP port per slot and no shell on the box, so
there is no channel to demonstrate a real capability-abuse privesc over the
network. `/admin` stands in for that step: it is gated by the exact same
FTP credentials leaked in the pcap (so the "second place this identity
unlocks" lesson still holds), and its response explains — and credits the
flag for — the capability abuse it represents. The Lab Info library covers
`getcap`/`cap_setuid` as a standalone concept; see
`../../terminal/content/lab-info/`.
"""
import base64
import os
import socket
import struct
import threading
import time

from flask import Flask, Response, abort, request

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{idor-pcap-dev0000000000}")

FTP_USER = "svc-backup"
FTP_PASS = "Backup!2024"
# Which numbered ticket holds the leaked capture. Not shown anywhere; a
# student finds it by enumerating 0..9 (the IDOR itself).
LEAK_INDEX = 7
TICKET_COUNT = 10


def _eth_ip_tcp(payload, sport=21, dport=51422):
    """A minimal, parseable (not cryptographically correct) Ethernet/IPv4/TCP
    frame carrying `payload` as the TCP segment data. Checksums are left as 0
    ("not computed" is common in real captures too) — every tool a student
    would reach for here (`strings`, `tshark -r`, Wireshark's "Follow TCP
    Stream") still shows the payload; nothing in this lab depends on the
    checksums validating.
    """
    eth = b"\x00" * 6 + b"\x00" * 6 + b"\x08\x00"  # dst, src, type=IPv4
    ip_total_len = 20 + 20 + len(payload)
    ip = struct.pack(
        "!BBHHHBBH4s4s",
        0x45, 0, ip_total_len, 0, 0x4000, 64, 6, 0,
        b"\x0a\x00\x00\x02", b"\x0a\x00\x00\x01",
    )
    tcp = struct.pack("!HHLLBBHHH", sport, dport, 1, 1, 0x50, 0x18, 0, 0, 0)
    return eth + ip + tcp + payload


def build_pcap(lines):
    """A libpcap (classic) file: one packet per line in `lines`."""
    global_header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    body = bytearray()
    ts = int(time.time())
    for i, line in enumerate(lines):
        frame = _eth_ip_tcp(line.encode())
        body += struct.pack("<IIII", ts + i, 0, len(frame), len(frame))
        body += frame
    return bytes(global_header) + bytes(body)


def ticket_pcap(n):
    if n == LEAK_INDEX:
        return build_pcap([
            "220 backup-ftp ready\r\n",
            f"USER {FTP_USER}\r\n",
            "331 password required\r\n",
            f"PASS {FTP_PASS}\r\n",
            "230 login OK\r\n",
        ])
    # Every other ticket: an unrelated, harmless capture (same shape, no
    # creds) so the leak isn't findable by content-sniffing the response
    # size alone.
    return build_pcap([f"ticket #{n}: nothing of interest\r\n"])


# -- Presentation only (no behavior): each target wears the look of its own
# scenario. The stylesheet is a separate route so `curl` output stays readable.
_CSS = """
:root{--bg:#fff8f0;--card:#fff;--ink:#3b2a1a;--mute:#8a6d52;--acc:#ea580c;--line:#f1dcc8}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--acc);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:var(--acc);font-weight:800;border-radius:50%;width:1.7rem;height:1.7rem;display:inline-grid;place-items:center}.brand{font-weight:600}
main{max-width:640px;margin:2rem auto;padding:0 1rem}h1{font-size:1.4rem;margin:0 0 1rem}
ul{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
li{padding:.7rem 1rem;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:.6rem}li:last-child{border:0}
li::before{content:"\1F3AB";filter:grayscale(.2)}a{color:var(--acc);text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
p{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1rem;word-break:break-word}
"""


@app.get("/assets/theme.css")
def theme_css():
    return Response(_CSS, mimetype="text/css")


def _page(title, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title} &middot; Helpdesk Support</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">H</span><span class="brand">Helpdesk Support</span></header>'
        f'<main>{body}</main></body></html>'
    )


@app.get("/")
def index():
    links = "".join(f'<li><a href="/data/{n}">ticket-{n}.pcap</a></li>' for n in range(TICKET_COUNT))
    return _page("Ticket archive", f"<h1>Support Ticket Archive</h1><ul>{links}</ul>")


@app.get("/data/<int:n>")
def data(n):
    # THE BUG: no check that `n` belongs to the caller — any ticket number
    # in range is served to anyone. The fix is an ownership check against
    # the caller's own session/account before returning any bytes.
    if n < 0 or n >= TICKET_COUNT:
        abort(404)
    return Response(ticket_pcap(n), mimetype="application/vnd.tcpdump.pcap")


def _basic_auth_ok():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return user == FTP_USER and password == FTP_PASS


@app.get("/admin")
def admin():
    if not _basic_auth_ok():
        return Response("auth required", 401, {"WWW-Authenticate": 'Basic realm="ops"'})
    return _page("Diagnostics", (
        "<h1>svc-backup diagnostics</h1>"
        "<p>This account's helper, /usr/local/bin/ctf-triage, carries the "
        "cap_setuid capability — any process it execs can call setuid(0). "
        f"Running it as svc-backup drops you to root. {FLAG}</p>"
    ))


# -- Decoy listeners (plan §7.3's nmap primer: a student scans their box
# and finds more than the one port they'll actually use, same as a
# HackTheBox box) -------------------------------------------------------
# NOT real services: every slot container drops every Linux capability and
# runs read-only as a non-root user (docker_api.py's build_create_request()),
# which makes a genuine sshd/vsftpd impossible here at all (host keys,
# privilege separation and setuid-per-connection all need root). Each
# speaks just enough of the real protocol's opening handshake to
# fingerprint correctly under `nmap -sV`, then always fails the next step.
# ctf-controller's AttackManager always reserves these two ports
# (DECOY_SSH_CONTAINER_PORT, DECOY_FTP_CONTAINER_PORT).
def _decoy_ssh_handler(conn):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
    except OSError:
        pass
    finally:
        conn.close()


def _decoy_ftp_handler(conn):
    # The irony is the point: USER/PASS here are read, but svc-backup's real
    # creds (the ones the pcap leaks) still don't work — this box's actual
    # foothold is the IDOR on /data/<n>, not a live FTP login, and a student
    # who tries the obvious thing first learns that the hard way.
    try:
        conn.sendall(b"220 (vsFTPd 3.0.5)\r\n")
        conn.settimeout(5)
        while True:
            data = conn.recv(256)
            if not data:
                break
            line = data.decode("utf-8", "replace").strip().upper()
            if line.startswith("USER"):
                conn.sendall(b"331 Please specify the password.\r\n")
            elif line.startswith("PASS"):
                conn.sendall(b"530 Login incorrect.\r\n")
            elif line.startswith("QUIT"):
                conn.sendall(b"221 Goodbye.\r\n")
                break
            else:
                conn.sendall(b"502 Command not implemented.\r\n")
    except OSError:
        pass
    finally:
        conn.close()


def _start_decoy(port, handler):
    def _accept_loop():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(16)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            threading.Thread(target=handler, args=(conn,), daemon=True).start()
    threading.Thread(target=_accept_loop, daemon=True).start()


_start_decoy(2222, _decoy_ssh_handler)
_start_decoy(2121, _decoy_ftp_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
