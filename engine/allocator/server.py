#!/usr/bin/env python3
"""Student self-service login + facilitator dashboard for the workshop engine.

Single-threaded on purpose (http.server.HTTPServer, not ThreadingHTTPServer):
the "find the first free studentNN slot and claim it" critical section below
is one plain synchronous function with no I/O in the middle, so two
concurrent /assign requests physically cannot claim the same slot -- the
single accept loop means they can't interleave. No lock, no DB transaction.

All state is in-memory and reset on container restart, matching this
project's ephemeral-by-design stack (see engine/docker-compose.yml).
"""
import hmac
import html
import http.client
import http.server
import json
import os
import re
import secrets
import socket
import time
import urllib.parse

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost")
# Marks the session cookie Secure whenever the public deployment actually
# terminates TLS (see gateway/README's Deployment scenarios) -- the browser
# then refuses to ever send it over a plain-HTTP connection, e.g. to a
# spoofed same-name host on an open network. No effect (and no downside)
# on the plain-HTTP localhost path, since that's never HTTPS to begin with.
COOKIE_SECURE = PUBLIC_BASE_URL.startswith("https://")

STUDENT_COUNT = int(os.environ.get("STUDENT_COUNT", "30"))
STUDENT_PREFIX = os.environ.get("STUDENT_PREFIX", "student")
# Demo/test bots (--test, see engine/run.sh and README.md's "Demo bots"
# section): unlike real students, these never go through /assign -- they're
# always shown in the roster (see handle_sessions_api) so a facilitator can
# watch/Release them without any browser having "joined" as them. 0 (the
# default) disables this feature entirely.
BOT_COUNT = int(os.environ.get("BOT_COUNT", "0"))
BOT_PREFIX = os.environ.get("BOT_PREFIX", "testuser")
WORKSHOP_NAME = os.environ.get("WORKSHOP_NAME", "Workshop Lab")
# Must match web-terminal's actual facilitator Linux account -- entrypoint.sh
# and docker-compose.yml both default this to "root", not "facilitator", so
# it has to come from the same env var, never be hardcoded here.
FACILITATOR_USERNAME = os.environ.get("FACILITATOR_USERNAME", "root")
# Deep-links the landing page's Forgejo button straight at the seeded
# workshop repo -- must match bootstrap.sh's FORGEJO_ORG/FORGEJO_REPO
# defaults (see docker-compose.yml's bootstrap service), not hardcoded here.
FORGEJO_ORG = os.environ.get("FORGEJO_ORG", "training")
FORGEJO_REPO = os.environ.get("FORGEJO_REPO", "sample-training-repo")
# SSO into Forgejo (see /forgejo-login below): must match the credentials
# bootstrap.sh actually created each account with, not hardcoded here.
STUDENT_PASSWORD = os.environ.get("STUDENT_PASSWORD", "student123")
FORGEJO_ADMIN_USER = os.environ["FORGEJO_ADMIN_USER"]
FORGEJO_ADMIN_PASSWORD = os.environ["FORGEJO_ADMIN_PASSWORD"]
# Shared secret sent on every call to web-terminal's control API (see
# control_request() below) -- proves these calls actually come from the
# allocator, not some other container on the internal workshop_lab network.
# Must match web-terminal's own CONTROL_TOKEN (workspace-control.py).
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
# Shared secret gateway/Caddyfile sends (via header_up X-Gateway-Token) on
# EVERY request it proxies to this process -- proves the request actually
# came through Caddy, not directly from some other container on the shared
# workshop_lab network (allocator must share that network with web-terminal
# and git-server for its own legitimate outbound calls -- see
# control_request()/forgejo_login_request() below -- and Docker/Podman
# bridge networks are not directional, so anything reachable BY allocator
# can equally reach allocator back). Without this check, resolve_identity()
# below trusting X-Auth-User would be forgeable by any process inside
# web-terminal (e.g. a student's own shell) simply by sending its own
# X-Auth-User: root header straight to http://allocator:8080/. Required, no
# default -- same fail-fast pattern as CONTROL_TOKEN above. Must match
# gateway's own GATEWAY_TOKEN (gateway/Caddyfile).
GATEWAY_TOKEN = os.environ["GATEWAY_TOKEN"]
DEMO_APP_ENABLED = os.environ.get("DEMO_APP_ENABLED", "0") == "1"
DEMO_APP_ZONE = os.environ.get("DEMO_APP_ZONE", "certs.dojo.test")

WEB_TERMINAL_HOST = "web-terminal"
CONTROL_PORT = 7682
CONTROL_TIMEOUT = 3.0

GIT_SERVER_HOST = "git-server"
GIT_SERVER_PORT = 3000

IDE_PORT_BASE = 9000
TERM_PORT_BASE = 9500
FACILITATOR_IDE_PORT = 9099
FACILITATOR_TERM_PORT = 9599
# Facilitator's read-only mirror of a student's term session -- must match
# WATCH_PORT_BASE in web-terminal/workspace-control.py, which actually
# spawns the ttyd process on this port.
WATCH_PORT_BASE = 9600
# Same, for demo bots -- must match BOT_WATCH_PORT_BASE in
# web-terminal/workspace-control.py.
BOT_WATCH_PORT_BASE = 9800
# Same collision fix as watch_port() below, mirrored here for ide_port()/
# term_port() -- must match BOT_IDE_PORT_BASE/BOT_TERM_PORT_BASE in
# web-terminal/workspace-control.py. Not currently reachable (resolve_identity()
# never returns a bot id as `username` -- only a real student id or the
# facilitator), but kept symmetric per this file's own "must match" comments.
BOT_IDE_PORT_BASE = 9700
BOT_TERM_PORT_BASE = 9750

COOKIE_NAME = "dojo_session"

STUDENT_IDS = [f"{STUDENT_PREFIX}{n:02d}" for n in range(1, STUDENT_COUNT + 1)]
BOT_IDS = [f"{BOT_PREFIX}{n}" for n in range(1, BOT_COUNT + 1)]

# studentId -> {name, ip, token, tool, assigned_at}
slots = {sid: {"name": None, "ip": None, "token": None, "tool": None, "assigned_at": None} for sid in STUDENT_IDS}
token_index = {}  # token -> studentId


def student_number(student_id):
    return int(student_id[len(STUDENT_PREFIX):])


def bot_number(bot_id):
    return int(bot_id[len(BOT_PREFIX):])


def ide_port(username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_IDE_PORT
    if username in BOT_IDS:
        return BOT_IDE_PORT_BASE + bot_number(username)
    return IDE_PORT_BASE + student_number(username)


def term_port(username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_TERM_PORT
    if username in BOT_IDS:
        return BOT_TERM_PORT_BASE + bot_number(username)
    return TERM_PORT_BASE + student_number(username)


def watch_port(sid):
    if sid in BOT_IDS:
        return BOT_WATCH_PORT_BASE + bot_number(sid)
    return WATCH_PORT_BASE + student_number(sid)


def find_free_slot():
    for sid in STUDENT_IDS:
        if slots[sid]["name"] is None:
            return sid
    return None


def control_request(method, path):
    """Best-effort call to workspace-control.py inside web-terminal. Never
    raises -- returns None on any failure so a flaky internal call degrades
    gracefully instead of blocking the single-threaded allocator."""
    try:
        conn = http.client.HTTPConnection(WEB_TERMINAL_HOST, CONTROL_PORT, timeout=CONTROL_TIMEOUT)
        conn.request(method, path, headers={"X-Control-Token": CONTROL_TOKEN})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        if resp.status != 200:
            return None
        return body
    except (OSError, socket.timeout, http.client.HTTPException):
        return None


def forgejo_login_request(username, password):
    """POST straight to Forgejo's own login form over the internal network
    and return the raw Set-Cookie header values from its response, in
    order, for /forgejo-login to relay verbatim onto the browser's
    response. Relaying them in the same order Forgejo sent them reproduces
    the exact session a real browser login would end up with (Forgejo's
    login POST needs no CSRF token -- verified against the running
    instance), without this process ever needing to hold a live session of
    its own. Best-effort: an empty list just means no cookies get set, so
    the browser lands on Forgejo's normal login page instead of an error."""
    try:
        conn = http.client.HTTPConnection(GIT_SERVER_HOST, GIT_SERVER_PORT, timeout=CONTROL_TIMEOUT)
        body = urllib.parse.urlencode({"user_name": username, "password": password, "remember": ""})
        conn.request("POST", "/user/login", body=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        cookies = resp.msg.get_all("Set-Cookie") or []
        resp.read()
        conn.close()
        return cookies
    except (OSError, socket.timeout, http.client.HTTPException):
        return []


# Inline, self-contained SVGs for the confirmation page's tool cards (see
# render_confirmation) -- feather-style, 24x24, stroke=currentColor so each
# one automatically picks up its card's icon color (including the primary
# card's white-on-blue) with no extra markup or external icon font/CDN
# request. This runs entirely inside a student's own browser, which this
# project makes no assumption has internet access beyond the workshop
# origin itself (see engine/README.md's Troubleshooting section on the
# terminal container's own lack of one) -- so nothing on this page ever
# depends on a third-party asset loading.
_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
ICON_CODE = _SVG.format('<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>')
ICON_TERMINAL = _SVG.format('<polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line>')
ICON_GIT = _SVG.format('<line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle>'
                        '<circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>')
ICON_SLIDES = _SVG.format('<rect x="2" y="4" width="20" height="14" rx="2"></rect>'
                           '<line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="18" x2="12" y2="21"></line>')
ICON_ROCKET = _SVG.format('<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>'
                           '<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>'
                           '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>'
                           '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>')
ICON_ARROW = '<svg class="card-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' \
             'stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"></line>' \
             '<polyline points="7 7 17 7 17 17"></polyline></svg>'


def page(title, body):
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 30rem; margin: 8vh auto; padding: 0 1.25rem; color: #1a1a1a; background: #fafafa; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #eee; background: #171717; }} }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .sub {{ opacity: 0.7; margin-bottom: 2rem; }}
  input[type=text] {{ width: 100%; padding: 0.6rem 0.8rem; font-size: 1rem; border-radius: 0.5rem;
          border: 1px solid #ccc; box-sizing: border-box; margin-bottom: 1rem; }}
  button, .btn {{ display: inline-block; padding: 0.6rem 1.2rem; font-size: 1rem; border-radius: 0.5rem;
          border: none; background: #2563eb; color: white; cursor: pointer; text-decoration: none;
          margin-right: 0.5rem; margin-bottom: 0.5rem; }}
  button:disabled {{ opacity: 0.6; cursor: default; }}
  .btn.secondary {{ background: #6b7280; }}
  .badge {{ display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.15rem 0.7rem; font-weight: 600; font-size: 0.9rem; }}
  @media (prefers-color-scheme: dark) {{ .badge {{ background: #1e2352; color: #c7d2fe; }} }}
</style></head>
<body>{body}</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AllocatorHTTP/1.0"
    # This server is single-threaded by design (see module docstring) --
    # every request blocks every other request/connection for its duration,
    # including the accept loop itself. Without a socket timeout, one client
    # that opens a connection and then sends bytes slowly (or not at all)
    # would stall the entire workshop's assignment/auth-check traffic
    # indefinitely. 10s is generous for any legitimate request this process
    # ever serves (all local, in-memory, no upstream I/O except the
    # best-effort control_request/forgejo_login_request calls, which have
    # their own shorter CONTROL_TIMEOUT).
    timeout = 10

    def log_message(self, fmt, *args):
        pass  # keep container logs quiet; nothing sensitive is worth logging by default

    # -- helpers ---------------------------------------------------------
    def send_html(self, body, status=200, headers=None):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for k, v in (headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, data, status=200):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
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

    def read_form_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        length = max(0, min(length, self.MAX_BODY_BYTES))
        raw = self.rfile.read(length) if length else b""
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items()}

    # -- pages -------------------------------------------------------------
    def render_name_form(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">Enter your name to get started.</p>
<form method="post" action="/assign" onsubmit="this.querySelector('button').disabled=true">
  <input type="text" name="name" placeholder="Your name" required autofocus maxlength="60">
  <button type="submit">Join workshop</button>
</form>"""
        return page(WORKSHOP_NAME, body)

    def render_full(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">All workshop seats are currently taken. Please ask your facilitator for help.</p>"""
        return page(WORKSHOP_NAME, body)

    def render_confirmation(self, sid):
        """The landing page a student sees on every visit after /assign has
        claimed them a slot (including refresh/back-button -- see
        handle_assign). Deliberately its own full HTML document, like
        render_facilitator_workspace, rather than page() -- page()'s
        narrow single-column layout is tuned for the two short forms
        (name entry, "lab full"), not a set of tool choices that benefits
        from room to show what each one actually does."""
        slot = slots[sid]
        tools = [
            {
                "href": "/ide/", "label": "VS Code", "icon": ICON_CODE, "primary": True,
                "desc": "Your editor, already open in your lab folder.",
            },
            {
                "href": "/term/", "label": "Terminal", "icon": ICON_TERMINAL,
                "desc": "A plain shell, same account, if you'd rather type.",
            },
            {
                "href": "/forgejo-login", "label": "Forgejo", "icon": ICON_GIT,
                "desc": "Your repo -- branches, commits, pull requests.",
            },
            {
                "href": "/slides/", "label": "Slides", "icon": ICON_SLIDES,
                "desc": "Today's material, for reference as you go.",
            },
        ]
        if DEMO_APP_ENABLED:
            tools.append({
                "href": "/demo/", "label": "Demo Site", "icon": ICON_ROCKET,
                "desc": "See your changes live once you've pushed them.",
            })

        cards = "\n".join(
            f"""<a class="card{' primary' if t.get('primary') else ''}" href="{t['href']}" target="_blank" rel="noopener">
  <span class="card-icon">{t['icon']}</span>
  <span class="card-text">
    <span class="card-title">{html.escape(t['label'])}</span>
    <span class="card-desc">{html.escape(t['desc'])}</span>
  </span>
  {ICON_ARROW}
</a>"""
            for t in tools
        )

        body = f"""
<div class="hero">
  <span class="hero-badge">{html.escape(sid)}</span>
  <h1>You're in, {html.escape(slot['name'])}</h1>
  <p class="sub">Pick a tool to get started -- each one opens in a new tab.</p>
</div>
<div class="cards">
{cards}
</div>
<p class="footnote">Reload this page any time -- it always brings you straight back here as <strong>{html.escape(sid)}</strong>, with nothing lost.</p>"""

        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 40rem; margin: 6vh auto; padding: 0 1.25rem 3rem; color: #1a1a1a; background: #fafafa; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #eee; background: #171717; }} }}
  .hero {{ text-align: center; margin-bottom: 2rem; }}
  .hero-badge {{ display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.2rem 0.85rem; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.02em;
          margin-bottom: 0.9rem; }}
  @media (prefers-color-scheme: dark) {{ .hero-badge {{ background: #1e2352; color: #c7d2fe; }} }}
  .hero h1 {{ font-size: 1.6rem; margin: 0 0 0.4rem; }}
  .hero .sub {{ opacity: 0.7; margin: 0; }}
  .cards {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }}
  @media (max-width: 30rem) {{ .cards {{ grid-template-columns: 1fr; }} }}
  .card {{ display: flex; align-items: center; gap: 0.85rem; padding: 0.9rem 1rem; border-radius: 0.75rem;
          border: 1px solid #e2e2e2; background: #fff; text-decoration: none; color: inherit;
          transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s; }}
  @media (prefers-color-scheme: dark) {{ .card {{ border-color: #333; background: #1f1f1f; }} }}
  .card:hover, .card:focus-visible {{ border-color: #2563eb; transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(37, 99, 235, 0.15); }}
  .card.primary {{ grid-column: 1 / -1; border-color: #2563eb; background: #eff6ff; }}
  @media (prefers-color-scheme: dark) {{ .card.primary {{ background: #172554; }} }}
  .card-icon {{ flex-shrink: 0; width: 2.25rem; height: 2.25rem; border-radius: 0.6rem; background: #eef2ff;
          color: #2563eb; display: flex; align-items: center; justify-content: center; }}
  @media (prefers-color-scheme: dark) {{ .card-icon {{ background: #1e2352; }} }}
  .card.primary .card-icon {{ background: #2563eb; color: #fff; }}
  .card-icon svg {{ width: 1.25rem; height: 1.25rem; }}
  .card-text {{ display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; flex: 1; }}
  .card-title {{ font-weight: 600; font-size: 0.98rem; }}
  .card-desc {{ font-size: 0.82rem; opacity: 0.65; line-height: 1.3; }}
  .card-arrow {{ flex-shrink: 0; opacity: 0.35; width: 1rem; height: 1rem; }}
  .card:hover .card-arrow, .card:focus-visible .card-arrow {{ opacity: 0.7; }}
  .footnote {{ margin-top: 1.75rem; text-align: center; font-size: 0.8rem; opacity: 0.55; }}
</style></head>
<body>{body}</body></html>"""

    def render_facilitator_workspace(self):
        """The facilitator's one-stop page at /admin: a roster of live
        terminal tiles (one per held slot -- account/name/IP/status/Release
        in the tile header, an iframe onto /admin/watch/<sid>/ underneath),
        plus their own VS Code/Terminal/Forgejo/Slides as further tabs, all
        on one wide page -- no dependency on the shared student gate either
        (see gateway/Caddyfile: /admin has its own basic_auth, which is
        also now accepted at the shared gate, so a facilitator never needs
        the student credential at all).

        Deliberately its own full HTML document rather than page() (which
        is tuned for the narrow single-column student flow) -- this page
        needs real width for the tool iframes and the roster grid.

        The VS Code/Terminal/Forgejo/Slides tabs are plain iframes onto the
        same /ide/, /term/, /forgejo-login, /slides/ routes the old
        separate-tab links used -- nothing new for Caddy or the allocator
        to authorize, since the facilitator's browser already carries
        whatever those routes need (the shared-gate basic_auth realm is
        reused automatically once /admin's has been satisfied -- see the
        Caddyfile comment above the shared block -- and neither ttyd nor
        code-server nor Forgejo send X-Frame-Options/frame-ancestors, the
        same fact that already makes the watch tiles embeddable). Each
        iframe's src is set lazily, on that tab's first click, so opening
        /admin doesn't eagerly spin up the facilitator's own VS
        Code/terminal/Forgejo session -- and once set it's never torn
        down, just hidden via CSS when another tab is active, so switching
        tabs doesn't lose editor/terminal state.

        The roster tab itself, unlike those, is the page's default (active)
        tab, so it builds its tiles -- and connects each one's watch
        websocket -- as soon as /admin loads, not lazily. It's kept in sync
        by polling /admin/api/sessions: client-side Set-diffing against the
        existing `tiles` object so a join/leave only ever adds/removes the
        one tile involved, never a wholesale replace (that would tear down
        and reconnect every iframe's websocket every poll). An existing
        tile's status dot does get refreshed in place on every poll, since
        "active" genuinely changes over a session -- just without touching
        that tile's iframe."""
        body = """
<div id="bar">
  <h1>Facilitator</h1>
  <p class="sub">Signed in as <span class="badge">FACILITATOR_USERNAME_PLACEHOLDER</span></p>
</div>
<div class="tabs">
  <button class="tab active" data-tab="roster">Roster</button>
  <button class="tab" data-tab="ide">VS Code</button>
  <button class="tab" data-tab="term">Terminal</button>
  <button class="tab" data-tab="forgejo">Forgejo</button>
  <button class="tab" data-tab="slides">Slides</button>
</div>

<div class="panel active" id="panel-roster">
  <p id="empty" class="sub">No students connected yet.</p>
  <div id="grid"></div>
</div>

<div class="panel" id="panel-ide"><iframe data-src="/ide/"></iframe></div>
<div class="panel" id="panel-term"><iframe data-src="/term/"></iframe></div>
<div class="panel" id="panel-forgejo"><iframe data-src="/forgejo-login"></iframe></div>
<div class="panel" id="panel-slides"><iframe data-src="/slides/"></iframe></div>

<script>
// -- tabs ---------------------------------------------------------------
const tabs = Array.from(document.querySelectorAll('.tab'));
const panels = {};
document.querySelectorAll('.panel').forEach(p => { panels[p.id.slice('panel-'.length)] = p; });

function activateTab(name) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  Object.entries(panels).forEach(([key, el]) => el.classList.toggle('active', key === name));
  const frame = panels[name] && panels[name].querySelector('iframe[data-src]');
  if (frame) { frame.src = frame.dataset.src; frame.removeAttribute('data-src'); }
}
tabs.forEach(t => t.onclick = () => activateTab(t.dataset.tab));

// -- roster grid ------------------------------------------------------
const grid = document.getElementById('grid');
const tiles = {};
let enlarged = null;

// The watch iframe is laid out at one fixed, generous pixel size -- not
// the tile's actual (usually much smaller) visible size -- then shrunk
// (or, enlarged, grown) to fit with a CSS transform (see updateScale).
// xterm.js inside sizes its terminal from that *unscaled* layout box, so
// tmux always sees a client at least as big as most real single-terminal
// panes; a client smaller than the real pane is what makes tmux clip to
// that corner instead of reflowing (see tmux.conf's window-size comment).
//
// This view is read-only and just for a facilitator's at-a-glance check,
// not a pixel-perfect mirror, so it deliberately does NOT track each
// student's actual pane size to match it exactly -- an earlier version
// did, but a session nobody else ever attaches to (every demo bot, always
// -- see tmux.conf) has nothing real to anchor that size against, so this
// page's own size guess fed back into itself every 5s poll and grew
// without bound. One fixed reference size, comfortably bigger than almost
// any single terminal pane, sidesteps that whole problem.
//
// A smaller per-tile-only reference (more legible text, less content
// visible) was tried and reverted -- shrinking a small tile's *content*,
// not just its text, isn't the tradeoff wanted here; a small tile should
// show as much of the real pane as an enlarged one does, just smaller.
const FRAME_W = 1120;
const FRAME_H = 800;

function initFrameSize(frame) {
  frame.dataset.w = FRAME_W;
  frame.dataset.h = FRAME_H;
  frame.style.width = FRAME_W + 'px';
  frame.style.height = FRAME_H + 'px';
}

// A floor on how far a tile will shrink the frame to fit -- without one,
// a tile still mid-layout (0 width/height for a tick after being added)
// or an unusually large real pane would render text at an illegibly tiny
// scale. Below this floor .tile-frame-wrap's overflow: hidden just crops
// to whatever corner fits, same as tmux would show a too-small client
// anyway (see above) -- a legible fraction beats all of it unreadable.
const MIN_SCALE = 0.3;

function updateScale(wrap) {
  const frame = wrap.querySelector('iframe');
  if (!frame || !frame.dataset.w) return;
  const rect = wrap.getBoundingClientRect();
  const scale = Math.min(rect.width / frame.dataset.w, rect.height / frame.dataset.h);
  frame.style.transform = `scale(${Math.max(scale, MIN_SCALE)})`;
}

const frameObserver = new ResizeObserver(entries => {
  for (const entry of entries) updateScale(entry.target);
});

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function statusHtml(active) {
  return active
    ? '<span style="color:#16a34a">&#9679; active</span>'
    : '<span style="color:#dc2626">&#9679; inactive</span>';
}

// Connects a tile's iframe to its watch endpoint the first time the
// student becomes watchable (see updateRoster) -- a no-op if already
// connected, so it's safe to call on every poll.
function activateWatch(tile, sid) {
  const frame = tile.querySelector('iframe');
  if (frame.src) return;
  frame.src = '/admin/watch/' + encodeURIComponent(sid) + '/';
  tile.classList.add('watching');
}

function reloadTile(sid) {
  const frame = tiles[sid].querySelector('iframe');
  if (!frame.src) return;  // not watchable yet -- nothing to reload
  const src = frame.src;
  frame.src = 'about:blank';
  frame.src = src;
}

function releaseTile(sid, btn) {
  btn.disabled = true;
  fetch('/admin/release/' + encodeURIComponent(sid), {
    method: 'POST',
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(refresh);
}

function toggleEnlarge(sid) {
  if (enlarged === sid) { closeEnlarge(); return; }
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  tiles[sid].classList.add('enlarged');
  grid.classList.add('has-enlarged');
  enlarged = sid;
}

function closeEnlarge() {
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  grid.classList.remove('has-enlarged');
  enlarged = null;
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeEnlarge(); });

function buildTile(r) {
  const tile = document.createElement('div');
  tile.className = 'tile';
  const head = document.createElement('div');
  head.className = 'tile-head';
  head.innerHTML = `
    <div class="tile-title">
      <span class="tile-label">${escapeHtml(r.studentId)} &mdash; ${escapeHtml(r.name)}</span>
      <button class="tile-reload" title="Reload (follow current terminal)">&#8635;</button>
    </div>
    <div class="tile-meta">
      <span class="tile-ip">${escapeHtml(r.ip)}</span>
      <span class="tile-status">${statusHtml(r.active)}</span>
      <button class="tile-release">Release</button>
    </div>`;
  head.querySelector('.tile-label').onclick = () => toggleEnlarge(r.studentId);
  head.querySelector('.tile-reload').onclick = (e) => { e.stopPropagation(); reloadTile(r.studentId); };
  head.querySelector('.tile-release').onclick = (e) => { e.stopPropagation(); releaseTile(r.studentId, e.currentTarget); };
  const wrap = document.createElement('div');
  wrap.className = 'tile-frame-wrap';
  const waiting = document.createElement('div');
  waiting.className = 'tile-waiting';
  waiting.textContent = 'Waiting for a terminal session to watch…';
  const frame = document.createElement('iframe');
  frame.loading = 'lazy';
  wrap.appendChild(waiting);
  wrap.appendChild(frame);
  initFrameSize(frame);
  tile.appendChild(head);
  tile.appendChild(wrap);
  frameObserver.observe(wrap);
  if (r.watchable) activateWatch(tile, r.studentId);
  return tile;
}

function updateRoster(rows) {
  const seen = new Set();
  for (const r of rows) {
    seen.add(r.studentId);
    if (tiles[r.studentId]) {
      tiles[r.studentId].querySelector('.tile-status').innerHTML = statusHtml(r.active);
      if (r.watchable) activateWatch(tiles[r.studentId], r.studentId);
      continue;
    }
    const tile = buildTile(r);
    grid.appendChild(tile);
    tiles[r.studentId] = tile;
  }
  for (const sid of Object.keys(tiles)) {
    if (seen.has(sid)) continue;
    frameObserver.unobserve(tiles[sid].querySelector('.tile-frame-wrap'));
    tiles[sid].remove();
    delete tiles[sid];
    if (enlarged === sid) enlarged = null;
  }
  document.getElementById('empty').style.display = rows.length ? 'none' : 'block';
}

async function refresh() {
  let rows;
  try {
    rows = await (await fetch('/admin/api/sessions')).json();
  } catch {
    return;  // transient fetch failure -- try again next poll, don't tear down tiles
  }
  updateRoster(rows);
}
refresh();
setInterval(refresh, 5000);
</script>"""
        body = body.replace("FACILITATOR_USERNAME_PLACEHOLDER", html.escape(FACILITATOR_USERNAME))
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)} — Facilitator</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 1400px; margin: 0 auto; padding: 1.25rem 1.5rem 2rem;
          color: #1a1a1a; background: #fafafa; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #eee; background: #171717; }} }}
  h1 {{ font-size: 1.4rem; margin: 0 0 0.15rem; }}
  .sub {{ opacity: 0.7; }}
  .badge {{ display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.15rem 0.7rem; font-weight: 600; font-size: 0.9rem; }}
  @media (prefers-color-scheme: dark) {{ .badge {{ background: #1e2352; color: #c7d2fe; }} }}
  button {{ font: inherit; }}
  .tabs {{ display: flex; gap: 0.25rem; flex-wrap: wrap; border-bottom: 2px solid #ddd; margin: 1.25rem 0 1.25rem; }}
  @media (prefers-color-scheme: dark) {{ .tabs {{ border-bottom-color: #333; }} }}
  .tab {{ padding: 0.55rem 1.1rem; font-size: 0.95rem; border: none; background: none; cursor: pointer;
          color: inherit; opacity: 0.6; border-bottom: 2px solid transparent; margin-bottom: -2px; }}
  .tab:hover {{ opacity: 0.85; }}
  .tab.active {{ opacity: 1; border-bottom-color: #2563eb; font-weight: 600; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .panel iframe {{ width: 100%; height: calc(100vh - 200px); min-height: 400px; border: 0; border-radius: 0.5rem; }}
  #grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 0.75rem; }}
  .tile {{ border: 1px solid #333; border-radius: 0.5rem; overflow: hidden; background: #000;
           display: flex; flex-direction: column; height: 280px; }}
  .tile-head {{ display: flex; flex-direction: column; gap: 0.2rem; padding: 0.3rem 0.6rem 0.4rem;
                font-size: 0.8rem; background: #111; color: #ccc; flex-shrink: 0; }}
  .tile-title {{ display: flex; align-items: center; justify-content: space-between; }}
  .tile-label {{ cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }}
  .tile-reload {{ background: none; border: none; color: #ccc; cursor: pointer; font-size: 0.95rem; padding: 0 0.2rem; flex-shrink: 0; }}
  .tile-reload:hover {{ color: #fff; }}
  .tile-meta {{ display: flex; align-items: center; gap: 0.6rem; font-size: 0.72rem; opacity: 0.85; }}
  .tile-ip {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .tile-status {{ white-space: nowrap; }}
  .tile-release {{ margin-left: auto; padding: 0.15rem 0.55rem; font-size: 0.72rem; border-radius: 0.35rem;
          border: none; background: #6b7280; color: white; cursor: pointer; flex-shrink: 0; }}
  .tile-release:hover {{ background: #7c8494; }}
  .tile-release:disabled {{ opacity: 0.6; cursor: default; }}
  /* The iframe is laid out at a fixed, generous pixel size (see
     FRAME_W/H below), then CSS-transformed to fill whatever size the
     tile wrapper actually is, enlarged or not -- see that comment and
     updateScale's for why. */
  .tile-frame-wrap {{ position: relative; flex: 1; overflow: hidden; background: #000; }}
  .tile-waiting {{ position: absolute; inset: 0; display: flex; align-items: center;
          justify-content: center; text-align: center; padding: 1rem;
          font-size: 0.78rem; color: #888; }}
  .tile.watching .tile-waiting {{ display: none; }}
  .tile iframe {{ position: absolute; top: 0; left: 0; border: 0; border-radius: 0;
          background: #000; transform-origin: top left; }}
  #grid.has-enlarged .tile {{ display: none; }}
  #grid.has-enlarged .tile.enlarged {{ display: flex; grid-column: 1 / -1; height: 80vh; }}
</style></head>
<body>{body}</body></html>"""

    # -- GET routes ----------------------------------------------------
    def do_GET(self):
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

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
                self.send_html(self.render_confirmation(sid))
            else:
                self.send_html(self.render_name_form())
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
            if username == FACILITATOR_USERNAME:
                forgejo_user, forgejo_password = FORGEJO_ADMIN_USER, FORGEJO_ADMIN_PASSWORD
            else:
                forgejo_user, forgejo_password = sid, STUDENT_PASSWORD
            cookies = forgejo_login_request(forgejo_user, forgejo_password)
            self.send_response(303)
            self.send_header("Location", f"/git/{FORGEJO_ORG}/{FORGEJO_REPO}")
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/auth-check":
            self.handle_auth_check(parsed)
            return

        if path == "/auth-check-watch":
            self.handle_auth_check_watch(parsed)
            return

        if path == "/admin":
            # Reaching this route at all means Caddy's own facilitator-only
            # basic_auth (see gateway/Caddyfile's @admin block) already
            # passed -- no separate cookie/login step needed.
            self.send_html(self.render_facilitator_workspace())
            return

        if path == "/admin/api/sessions":
            self.handle_sessions_api()
            return

        self.send_response(404)
        self.end_headers()

    def handle_auth_check(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        tool = (qs.get("tool") or [""])[0]
        if tool not in ("ide", "term", "demo"):
            self.send_response(400)
            self.end_headers()
            return

        username, _sid = self.resolve_identity()
        if username is None:
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if tool == "demo":
            if not DEMO_APP_ENABLED:
                self.send_response(404)
                self.end_headers()
                return
            student_id = username if username != FACILITATOR_USERNAME else None
            demo_host = f"{student_id or STUDENT_PREFIX + '01'}.{DEMO_APP_ZONE}"
            self.send_response(200)
            self.send_header("X-Demo-Host", demo_host)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        port = ide_port(username) if tool == "ide" else term_port(username)
        control_request("POST", f"/start/{tool}/{username}")

        self.send_response(200)
        self.send_header("X-Upstream-Port", str(port))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_auth_check_watch(self, parsed):
        """Gates /admin/watch/<studentId> (see gateway/Caddyfile). Reached
        only after Caddy's own facilitator-only basic_auth on /admin*, but
        re-checked here too -- this process shouldn't trust routing alone
        to keep a student out of another student's terminal."""
        username, _sid = self.resolve_identity()
        if username != FACILITATOR_USERNAME:
            self.send_response(403)
            self.end_headers()
            return

        sid = (urllib.parse.parse_qs(parsed.query).get("student") or [""])[0]
        # A demo bot has no "held slot" concept -- see BOT_IDS above -- it's
        # always watchable as long as --test provisioned it.
        if sid not in BOT_IDS and (sid not in slots or slots[sid]["name"] is None):
            self.send_response(404)  # not a currently held slot
            self.end_headers()
            return

        body = control_request("POST", f"/start/watch/{sid}")
        if body is None:
            self.send_response(409)  # student has no term session to watch yet
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("X-Upstream-Port", str(watch_port(sid)))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_sessions_api(self):
        held = [sid for sid in STUDENT_IDS if slots[sid]["name"] is not None]
        all_ids = held + BOT_IDS
        status = {}
        if all_ids:
            body = control_request("GET", "/status?users=" + ",".join(all_ids))
            if body:
                try:
                    status = json.loads(body)
                except json.JSONDecodeError:
                    status = {}
        rows = []
        for sid in held:
            slot = slots[sid]
            s = status.get(sid) or {}
            rows.append({
                "studentId": sid,
                "name": slot["name"],
                "ip": slot["ip"],
                "assignedAt": slot["assigned_at"],
                "active": bool(s.get("active", False)),
                # Whether this student has a terminal session to watch yet
                # -- see workspace-control.py's /status. The roster JS uses
                # this to connect a tile's watch iframe itself the moment
                # it turns true, instead of only on the next manual reload.
                "watchable": bool(s.get("watchable", False)),
            })
        # Demo bots are always listed (no /assign step -- see BOT_IDS above),
        # right after real students, so a facilitator can watch/Release them
        # the same way. bot-runner.sh's own narration prints which persona
        # (expert/intermediate/novice) each one is playing.
        for sid in BOT_IDS:
            s = status.get(sid) or {}
            rows.append({
                "studentId": sid,
                "name": f"Demo bot ({sid})",
                "ip": "bot",
                "assignedAt": None,
                "active": bool(s.get("active", False)),
                "watchable": bool(s.get("watchable", False)),
            })
        self.send_json(rows)

    # -- POST routes -----------------------------------------------------
    def do_POST(self):
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

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

        self.send_response(404)
        self.end_headers()

    def handle_assign(self):
        # Idempotent: a valid existing cookie just re-renders the confirmation
        # instead of claiming a second slot (handles refresh/back-button).
        # A facilitator identity in particular must never fall through to
        # the student-slot logic below -- that would silently demote them
        # to a random studentNN account (this is exactly how a facilitator
        # who typed admin:admin at "/" used to end up assigned student01).
        username, sid = self.resolve_identity()
        if username == FACILITATOR_USERNAME:
            self.read_form_body()  # drain body regardless
            self.send_html(self.render_facilitator_workspace())
            return
        if sid is not None:
            self.read_form_body()  # drain body regardless
            self.send_html(self.render_confirmation(sid))
            return

        form = self.read_form_body()
        name = (form.get("name") or "").strip()[:60]
        if not name:
            self.send_html(self.render_name_form(), status=400)
            return

        sid = find_free_slot()
        if sid is None:
            self.send_html(self.render_full())
            return

        token = secrets.token_urlsafe(32)
        slots[sid].update(name=name, ip=self.client_ip(), token=token, assigned_at=time.time())
        token_index[token] = sid

        cookie = f"{COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Lax"
        if COOKIE_SECURE:
            cookie += "; Secure"

        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_release(self, sid):
        if sid in BOT_IDS:
            # No slot bookkeeping for a bot -- it isn't "assigned" in the
            # first place (see BOT_IDS above). This just kills its process;
            # bot-supervisor.sh (in web-terminal) notices within its poll
            # interval and restarts it, and bot-runner.sh resumes from its
            # own persisted (round, step) state -- see engine/README.md's
            # "Demo bots (--test)" section.
            control_request("POST", f"/stop/{sid}")
            self.send_json({"released": sid})
            return
        if sid not in slots:
            self.send_response(404)
            self.end_headers()
            return
        control_request("POST", f"/stop/{sid}")
        old_token = slots[sid]["token"]
        if old_token in token_index:
            del token_index[old_token]
        slots[sid].update(name=None, ip=None, token=None, tool=None, assigned_at=None)
        self.send_json({"released": sid})


def main():
    server = http.server.HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
