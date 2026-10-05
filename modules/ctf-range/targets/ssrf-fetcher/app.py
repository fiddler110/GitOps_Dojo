"""ssrf-fetcher — CTF target 7 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-2
"Server-side trust and APIs"). A "preview this URL" feature fetches
server-side with no allow-list at all, so it can be pointed at an
internal-only admin endpoint instead of the public internet — classic SSRF.

The ladder row calls for "an internal-only admin endpoint on another
service in the same target, not another student's target." This image runs
BOTH: the public preview app on 0.0.0.0:$PORT (the app's own port — the
slot's block also carries a decoy SSH port, see the bottom of this file, but
that's unrelated to this bug) and a second, internal-only Flask app bound to
127.0.0.1 only, in a background thread. Nothing outside this container can
ever reach the internal app directly — it is never published and isn't
bound to a routable address — but the preview app's own outbound fetch runs
*inside* the same container, so it can reach 127.0.0.1 fine. That gap
between "not published" and "not reachable from this process" is the whole
vulnerability.

Env:
  CTF_FLAG         this slot's flag value (plan §5).
  PORT             public listen port (default 5000).
  INTERNAL_PORT    internal-only listen port (default 5001, loopback only).
"""
import os
import socket
import threading
import urllib.error
import urllib.request

from flask import Flask, render_template_string, request

FLAG = os.environ.get("CTF_FLAG", "flag{ssrf-fetcher-dev0000000000}")
INTERNAL_PORT = int(os.environ.get("INTERNAL_PORT", "5001"))

internal_app = Flask("internal")


@internal_app.get("/internal/admin/status")
def internal_status():
    return "<p>internal admin: ok (flavor only, no auth — see module docstring)</p>"


@internal_app.get("/internal/admin/flag")
def internal_flag():
    # Never reachable from outside this container (see module docstring) —
    # reaching it at all over the network IS the exploit, so the lack of an
    # auth check here is the point, not an oversight.
    return f"<p>{FLAG}</p>"


app = Flask("public")

PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>URL Preview</title></head>
<body>
<h1>URL Preview</h1>
<form method="post" action="/preview">
  <label>URL to preview <input name="url" size="60" value="https://example.com"></label>
  <button type="submit">Preview</button>
</form>
{% if body %}<pre>{{ body }}</pre>{% endif %}
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE, body=None)


@app.post("/preview")
def preview():
    url = request.form.get("url", "")
    # THE BUG: no allow-list at all. The fix is to resolve the host first,
    # reject anything that isn't a known-public address (and reject the
    # scheme unless it's exactly http/https), before ever calling urlopen.
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read(2000).decode("utf-8", "replace")
    except (urllib.error.URLError, ValueError) as exc:
        body = f"(fetch failed: {exc})"
    return render_template_string(PAGE, body=body)


def _run_internal():
    internal_app.run(host="127.0.0.1", port=INTERNAL_PORT, threaded=True)


threading.Thread(target=_run_internal, daemon=True).start()


# -- Decoy listener (plan §7.3's nmap primer: a student scans their box and
# finds more than the one port they'll actually use, same as a HackTheBox
# box) -----------------------------------------------------------------
# NOT a real sshd: every slot container drops every Linux capability and
# runs read-only as a non-root user (docker_api.py's build_create_request()),
# which makes a genuine sshd impossible here at all (host keys, privilege
# separation and setuid-per-connection all need root). This speaks just
# enough of the real SSH-2.0 handshake to fingerprint correctly under
# `nmap -sV`, then closes — there is no key exchange and no account behind
# it, and it has nothing to do with the internal Flask app above, which
# stays loopback-only regardless. ctf-controller's AttackManager always
# reserves this port (DECOY_SSH_CONTAINER_PORT).
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
