"""The HTTP request handler: plumbing, identity, and GET/POST routing to views and api.
"""
import hmac
import http.server
import json
import socket
import urllib.parse

from accounts import LOGIN_ASSETS, read_session, SESSION_COOKIE
from allocation import forgejo_login_request, local_path, slots, _state_lock, token_index
import allocation
from api import ApiMixin
from config import (
    COOKIE_NAME, COOKIE_SECURE, FACILITATOR_USERNAME, FORGEJO_ADMIN_PASSWORD, FORGEJO_ADMIN_USER, FORGEJO_ORG,
    FORGEJO_REPO, GATEWAY_TOKEN, _short,
)
import config
from dojo_secret import forgejo_password
from pages import ADMIN_ASSETS, CSP, NO_STORE_HEADERS, page, WORKSPACE_ASSETS
from views import ViewsMixin


class Handler(ViewsMixin, ApiMixin, http.server.BaseHTTPRequestHandler):
    server_version = "AllocatorHTTP/1.0"
    # Per-connection socket timeout. Each connection has its own thread
    # (AllocatorServer), so a client that connects and then sends slowly or
    # not at all only holds its own thread, for at most this long per read,
    # and never delays anyone else. 3 s is plenty for any legitimate request
    # (all local; control_request/forgejo_login_request have their own
    # CONTROL_TIMEOUT).
    timeout = 3

    def log_message(self, fmt, *args):
        pass  # keep container logs quiet; nothing sensitive is worth logging by default

    def handle_one_request(self):
        """An audit line for any handler that crashes (the traceback still
        goes to stderr), so a broken page shows up in the JSON log."""
        try:
            super().handle_one_request()
        except (ConnectionError, socket.timeout):
            raise
        except Exception as exc:
            config.audit("error", method=getattr(self, "command", None),
                  path=(getattr(self, "path", "") or "").split("?", 1)[0][:200],
                  exc=type(exc).__name__, detail=_short(str(exc)))
            raise

    # -- helpers ---------------------------------------------------------
    def send_html(self, body, status=200, headers=None):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def send_asset(self, content_type, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, data, status=200, headers=None):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        for k, v in (headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def gateway_authorized(self):
        """True only if this request carries the shared secret Caddy alone
        knows (see GATEWAY_TOKEN above) -- mirrors workspace-control.py's
        own authorized()/CONTROL_TOKEN check byte for byte. Checked first,
        in do_GET/do_POST, before any path parsing or resolve_identity()
        call: resolve_identity() trusts X-Auth-User, and this is the only
        thing standing between that trust and any other container on the
        shared workshop_lab network forging it."""
        token = self.headers.get("X-Gateway-Token", "")
        return hmac.compare_digest(token, GATEWAY_TOKEN)

    def get_cookie(self):
        cookie_header = self.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{COOKIE_NAME}="):
                return part[len(COOKIE_NAME) + 1:]
        return None

    def resolve_identity(self):
        """Return (username_for_control_plane, student_id_or_None) for the
        current request, or (None, None) if it isn't valid.

        Facilitator identity comes from X-Auth-User, set by
        gateway/Caddyfile's basic_auth + header_up on every request (this
        always overwrites any client-supplied value, so it can't be
        spoofed by a browser/curl -- only Caddy, on the internal-only
        network, can set it) to whichever account actually satisfied the
        shared or /admin basic_auth challenge. Caddy authenticates every
        request before it ever reaches this process, so this header is
        always present and correct -- typing the facilitator credential
        once, anywhere, is immediately enough; no cookie needed. A student
        identity, by contrast, only ever comes from the dojo_session
        cookie minted when they claim a slot via /assign.
        """
        if self.headers.get("X-Auth-User") == FACILITATOR_USERNAME:
            return FACILITATOR_USERNAME, None
        token = self.get_cookie()
        if token is None:
            return None, None
        with _state_lock:
            sid = token_index.get(token)
            if sid is not None and slots[sid]["token"] == token and slots[sid]["name"] is not None:
                return sid, sid
        return None, None

    def client_ip(self):
        # gateway/Caddyfile has no trusted_proxies configured, so Caddy's
        # reverse_proxy APPENDS the address it actually saw to whatever
        # X-Forwarded-For value the client already sent, rather than
        # replacing it -- the same header a curl/browser client is free to
        # set to anything. That means the FIRST entry can be attacker-
        # supplied, but the LAST entry is always the address Caddy itself
        # observed on the connection, since gateway is the sole public
        # entry point with nothing in front of it to have appended anything
        # earlier. Only that last hop is safe to trust (this is only ever
        # used for the facilitator roster display, not an auth decision).
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[-1].strip()
        return self.client_address[0]

    # Real form bodies here are tiny (a name, capped at 60 chars, is the
    # only field any form on this service ever submits) -- capping well
    # above that but far below "attacker-declared Content-Length" stops a
    # client from making this single-threaded process (see class docstring)
    # allocate or block on reading an enormous declared body.
    MAX_BODY_BYTES = 4096

    def read_body(self):
        """Read the request body, once, before do_POST routes or rejects anything.
        Every reply closes the connection (HTTP/1.0), and closing a socket with
        unread bytes in its receive buffer makes the kernel send RST instead of
        FIN, which can reach the client before it reads the reply: it gets
        ConnectionResetError, not the 403/404 it was sent. A body over the cap
        still leaves bytes behind; no real form comes near it."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        length = max(0, min(length, self.MAX_BODY_BYTES))
        return self.rfile.read(length) if length else b""

    def read_form_body(self):
        parsed = urllib.parse.parse_qs(self.body.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items()}

    # -- GET routes ----------------------------------------------------
    def do_GET(self):
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path == "/session-check":
            self.handle_session_check(parsed)
            return

        if path == "/gate-fail":
            self.handle_gate_fail()
            return

        if path == "/login":
            nxt = self.login_next(urllib.parse.parse_qs(parsed.query).get("next", [""])[0])
            if self.session_account():
                self.redirect(nxt)
            else:
                self.send_html(self.render_login(nxt=nxt), headers=NO_STORE_HEADERS)
            return

        if path.startswith("/login/assets/"):
            asset = LOGIN_ASSETS.get(path[len("/login/assets/"):])
            if asset is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", asset[0])
            self.send_header("Content-Length", str(len(asset[1])))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(asset[1])
            return

        if path == "/logout":
            self.redirect("/login", cookies=[self.session_cookie("", 0)])
            return

        if path == "/":
            username, sid = self.resolve_identity()
            if username == FACILITATOR_USERNAME:
                # /admin is the facilitator's one canonical page (own tool
                # links + roster) -- send them there instead of rendering
                # student-shaped content at "/".
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif sid is not None:
                self.send_html(self.render_confirmation(sid), headers=NO_STORE_HEADERS)
            else:
                self.send_html(self.render_name_form())
            return

        if path in WORKSPACE_ASSETS:
            self.send_asset(*WORKSPACE_ASSETS[path])
            return

        if path in ("/workspace", "/workspace/"):
            username, sid = self.resolve_identity()
            if username == FACILITATOR_USERNAME:
                # The facilitator's workspace is /admin.
                self.redirect("/admin")
            elif sid is None:
                self.redirect("/")
            else:
                self.send_html(self.render_workspace(sid), headers=NO_STORE_HEADERS)
            return

        if path == "/forgejo-login":
            # Deliberately NOT under /git/* -- Caddy's @git matcher is a
            # raw prefix match ("/git*"), so a path starting with "/git"
            # here would be routed straight to Forgejo instead of us.
            username, sid = self.resolve_identity()
            if username is None:
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if allocation.RESETS.fenced(username):
                self.send_html(page("Resetting", "<main><h1>Your environment is being reset</h1>"
                                    "<p>Reload this page in a few seconds.</p></main>"),
                               status=503, headers=NO_STORE_HEADERS)
                return
            if username == FACILITATOR_USERNAME:
                forgejo_user, password = FORGEJO_ADMIN_USER, FORGEJO_ADMIN_PASSWORD
            else:
                forgejo_user, password = sid, forgejo_password(sid)
            cookies = forgejo_login_request(forgejo_user, password)
            config.audit("forgejo-login", account=username, target=forgejo_user,
                  result="ok" if cookies else "failed")
            # ?next=<path>: signed in to Forgejo, go on to another page on
            # this site (a module's OIDC sign-in, say). Anything else: the repo.
            nxt = urllib.parse.parse_qs(parsed.query).get("next", [""])[0]
            self.send_response(303)
            self.send_header("Location", local_path(nxt) or f"/git/{FORGEJO_ORG}/{FORGEJO_REPO}")
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/whoami":
            # The browser's own student ID, for pages that personalise
            # themselves (the lab reader swaps it in for "studentXX").
            # null for the facilitator and for a browser holding no slot.
            _, sid = self.resolve_identity()
            self.send_json({"user": sid}, headers=NO_STORE_HEADERS)
            return

        if path == "/auth-check":
            self.handle_auth_check(parsed)
            return

        if path == "/auth-check-watch":
            self.handle_auth_check_watch(parsed)
            return

        if path in ("/admin", "/admin/"):
            # Reaching this route at all means Caddy's own facilitator-only
            # basic_auth (see gateway/Caddyfile's @admin block) already
            # passed -- no separate cookie/login step needed.
            self.send_html(self.render_facilitator_workspace())
            return

        if path in ADMIN_ASSETS:
            # The /admin page's own script and stylesheet (see ADMIN_JS):
            # same facilitator gate as /admin itself.
            self.send_asset(*ADMIN_ASSETS[path])
            return

        if path == "/admin/api/sessions":
            self.handle_sessions_api()
            return

        if path == "/admin/api/status":
            self.handle_status_api()
            return

        if path.startswith("/admin/api/forgejo-password/"):
            self.handle_forgejo_password(path[len("/admin/api/forgejo-password/"):])
            return

        self.send_response(404)
        self.end_headers()

    # -- POST routes -----------------------------------------------------
    def do_POST(self):
        self.body = self.read_body()  # before any reply, even a rejection: see read_body
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path == "/login":
            self.handle_login()
            return

        if path == "/assign":
            self.handle_assign()
            return

        if path.startswith("/admin/release/"):
            # HTTP Basic Auth (unlike a cookie) carries no SameSite
            # protection of its own -- a browser that's already satisfied
            # /admin's basic_auth reattaches those credentials to ANY
            # same-origin request, including one triggered by a hidden form
            # on a page a facilitator merely has open in another tab. A
            # plain cross-site <form method=post> can't set a custom
            # header, and a cross-site fetch() that tries to would first
            # need this server to answer its CORS preflight (it doesn't) --
            # so requiring this header on the actual roster JS's own fetch
            # call (see render_facilitator_workspace's releaseTile) blocks
            # both of those forgery paths while costing the real UI nothing.
            if self.headers.get("X-Requested-With") != "dojo-admin":
                self.send_response(403)
                self.end_headers()
                return
            sid = path[len("/admin/release/"):]
            self.handle_release(sid)
            return

        if path.startswith("/admin/reset/"):
            # Same forgery guard as Release, plus the typed id in the body.
            if self.headers.get("X-Requested-With") != "dojo-admin":
                self.send_response(403)
                self.end_headers()
                return
            self.handle_reset(path[len("/admin/reset/"):])
            return

        if path == "/admin/release-unused":
            if self.headers.get("X-Requested-With") != "dojo-admin":
                self.send_response(403)
                self.end_headers()
                return
            self.handle_release_unused()
            return

        self.send_response(404)
        self.end_headers()

    # -- front door (/login) ---------------------------------------------
    def session_cookie(self, value, max_age):
        cookie = f"{SESSION_COOKIE}={value}; HttpOnly; Path=/; SameSite=Lax; Max-Age={max_age}"
        return cookie + "; Secure" if COOKIE_SECURE else cookie

    def session_account(self):
        """The account the browser's login cookie was issued to, or None."""
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == SESSION_COOKIE:
                return read_session(value)
        return None

    @staticmethod
    def login_next(value):
        """Where to go after signing in: a path on this site, never the login
        page itself, else the front page."""
        value = local_path(value or "")
        return value if value and not value.startswith("/login") else "/"

    def redirect(self, location, cookies=()):
        self.send_response(303)
        self.send_header("Location", location)
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        for k, v in NO_STORE_HEADERS:
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()
