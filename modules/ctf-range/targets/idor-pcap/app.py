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
import struct
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


@app.get("/")
def index():
    links = "".join(f'<li><a href="/data/{n}">ticket-{n}.pcap</a></li>' for n in range(TICKET_COUNT))
    return f"<h1>Support Ticket Archive</h1><ul>{links}</ul>"


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
    return (
        "<h1>svc-backup diagnostics</h1>"
        "<p>This account's helper, /usr/local/bin/ctf-triage, carries the "
        "cap_setuid capability — any process it execs can call setuid(0). "
        f"Running it as svc-backup drops you to root. {FLAG}</p>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
