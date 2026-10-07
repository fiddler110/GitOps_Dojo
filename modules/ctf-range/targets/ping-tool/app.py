"""ping-tool — CTF target 4 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-2
"Server-side trust and APIs"). A "network diagnostics" page that shells out
with the submitted host pasted straight into the command line — classic OS
command injection, foothold = arbitrary code execution as the app's own
user.

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).

**Two scoped simplifications, stated plainly (same spirit as idor-pcap's
and cert-trust-bypass's):**

1. The ladder row calls this a "ping" tool. Real `ping` needs CAP_NET_RAW
   (raw ICMP sockets), and docker_api.py's build_create_request() drops
   EVERY capability from EVERY slot container, attack-ladder targets
   included — so a real `ping` binary would fail with "Operation not
   permitted" before an attacker ever got the chance to inject anything.
   `host` (a DNS lookup) is the stand-in diagnostics command: no special
   capability needed, same "paste user input into a shell command" bug,
   same lesson.
2. The row's escalation is "`sudo -l` shows a passwordless GTFOBins
   binary." That same global CapDrop (plus `no-new-privileges`) strips
   CAP_SETUID/CAP_DAC_OVERRIDE from every container, so there is no real
   uid-0-vs-non-root boundary inside a slot to escalate across — a real
   `sudo` would simply fail to elevate here, in any target. `/escalate`
   stands in for the audit-and-GTFOBins step: the command-injection RCE is
   used to read a note (written at startup into the one writable path,
   `/tmp` — there is no real sudoers file to discover) that describes
   exactly the rule a `sudo -l` would show in a real deployment, and
   redeeming its token is the "used the GTFOBins binary" step.
"""
import os
import secrets
import socket
import subprocess
import threading

from flask import Flask, render_template_string, request

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{ping-tool-dev0000000000}")

# Written once at startup into /tmp (the one writable, tmpfs-backed path —
# see docker_api.py). Stands in for what `sudo -l` would show in a real
# deployment; see the module docstring for why real sudo can't run here.
_ESCALATION_TOKEN = secrets.token_hex(8)
_NOTE_PATH = "/tmp/sudo-note.txt"
with open(_NOTE_PATH, "w") as _f:
    _f.write(
        "ops-diag is NOPASSWD for /usr/local/bin/netcheck (GTFOBins-style "
        "binary -- it can read any file as the invoking user).\n"
        f"Escalation token: {_ESCALATION_TOKEN}\n"
    )

PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Network Diagnostics</title></head>
<body>
<h1>Network Diagnostics</h1>
<form method="post" action="/diagnostics">
  <label>Host to look up <input name="host" value="example.com"></label>
  <button type="submit">Look up</button>
</form>
{% if output %}<pre>{{ output }}</pre>{% endif %}
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE, output=None)


@app.post("/diagnostics")
def diagnostics():
    host = request.form.get("host", "example.com")
    # THE BUG: pasted straight into a shell command line. The fix is one
    # line: subprocess.run(["host", host], ...) with shell=False, so shell
    # metacharacters in `host` never reach a shell at all.
    cmd = f"host {host}"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        output = "(timed out)"
    return render_template_string(PAGE, output=output)


@app.post("/escalate")
def escalate():
    token = request.form.get("token", "")
    if token == _ESCALATION_TOKEN:
        return f"<p>netcheck invoked via sudo. {FLAG}</p>"
    return "<p>Invalid token.</p>", 403


# -- Decoy listener (plan §7.3's nmap primer: a student scans their box and
# finds more than the one port they'll actually use, same as a HackTheBox
# box) -----------------------------------------------------------------
# NOT a real sshd: every slot container drops every Linux capability and
# runs read-only as a non-root user (docker_api.py's build_create_request()),
# which makes a genuine sshd impossible here at all (host keys, privilege
# separation and setuid-per-connection all need root — the same reasoning
# that rules out a real `sudo`, above). This speaks just enough of the real
# SSH-2.0 handshake to fingerprint correctly under `nmap -sV`, then closes —
# there is no key exchange and no account behind it. ctf-controller's
# AttackManager always reserves this port (DECOY_SSH_CONTAINER_PORT).
def _decoy_ssh_handler(conn):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
