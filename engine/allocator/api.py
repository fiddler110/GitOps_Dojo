"""JSON and auth endpoints of the request handler: /auth-check, the admin APIs, assign,
release and reset (mixed into handler.Handler).
"""
import json
import time
import urllib.parse

from accounts import check_login, is_bot_id, LOGIN_GUARD, make_session, SESSION_SECONDS
from allocation import (
    claim_slot, held_slots, ide_port, local_path, release_slot, slot_snapshot, slots, term_port,
    UNUSED_AFTER_SECONDS, watch_port,
)
import allocation
from config import (
    audit_check, COOKIE_NAME, COOKIE_SECURE, DNS_LABEL_RE, EXT_ROUTES, EXTENSIONS, FACILITATOR_USERNAME, STUDENT_IDS,
)
import config
from dojo_secret import forgejo_password
from pages import NO_STORE_HEADERS, page
import probes
class ApiMixin:
    """JSON and auth endpoints of the request handler: /auth-check, the admin APIs, assign,"""

    def handle_auth_check(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        if "route" in qs:
            self.handle_route_check((qs.get("route") or [""])[0])
            return
        tool = (qs.get("tool") or [""])[0]
        if tool not in ("ide", "term"):
            self.send_response(400)
            self.end_headers()
            return
        if tool == "ide" and not config.HAS_IDE:
            self.send_response(404)  # the Zellij flavor has no IDE (web-terminal refuses it too)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # The page or asset the browser asked for (gateway/Caddyfile sends
        # it), without the query string, to tell a page load from an asset.
        uri = self.headers.get("X-Forwarded-Uri", "").split("?", 1)[0][:200]
        username, _sid = self.resolve_identity()
        if username is None:
            audit_check("auth-check", None, tool, 303, uri=uri)
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if allocation.RESETS.fenced(username):
            # Being reset: the self-refreshing starting page, as for a
            # workspace that isn't up yet; it comes back once the reset ends.
            audit_check("auth-check", username, tool, 202, uri=uri, reset=True)
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        port = ide_port(username) if tool == "ide" else term_port(username)
        started = time.monotonic()
        ready = allocation.READY_CACHE.get((tool, username)) is not None
        if not ready:
            resp = allocation.control_request("POST", f"/start/{tool}/{username}")
            if resp is not None:
                try:
                    ready = bool(json.loads(resp).get("ready"))
                except (ValueError, AttributeError):
                    ready = False
            if ready:
                allocation.READY_CACHE.put((tool, username), True)
        audit_check("auth-check", username, tool, 200 if ready else 202, uri=uri,
                    ms=round((time.monotonic() - started) * 1000))

        if ready:
            self.send_response(200)
            self.send_header("X-Upstream-Port", str(port))
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            # code-server/ttyd was just spawned (or web-terminal itself is
            # briefly unreachable) and isn't listening yet -- 202 tells
            # Caddy (see gateway/Caddyfile's @ide/@term handle_response) to
            # serve the self-refreshing starting page instead of proxying
            # to a port nothing is listening on yet.
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def handle_route_check(self, route_id):
        """forward_auth for an extension route's identity/facilitator gate
        (render_extensions.py's Caddy template). 200 hands Caddy the caller's
        name as X-Dojo-User, and X-Dojo-Host when the route has a host
        template; Caddy strips any client-sent copies first and passes them
        upstream next to X-Gateway-Token. No session: 303 to "/" like the
        other tools. Unknown or shared route: 404, so nothing reaches an
        upstream this workshop didn't declare."""
        route = EXT_ROUTES.get(route_id)
        username, _sid = self.resolve_identity()
        if username is None and is_bot_id(self.session_account()):
            username = self.session_account()  # a demo bot signed in as itself (check_login)
        denied = None
        if route is None or route["gate"] not in ("identity", "facilitator"):
            denied = 404
        elif username is None:
            denied = 303
        elif route["gate"] == "facilitator" and username != FACILITATOR_USERNAME:
            denied = 403
        elif "host" in route and not DNS_LABEL_RE.match(username.lower()):
            denied = 403
        elif allocation.RESETS.fenced(username):
            denied = 503
        audit_check("route-check", username, route_id, denied or 200)
        if denied == 503:
            self.send_response(503)
            self.send_header("Retry-After", "5")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if route is None or route["gate"] not in ("identity", "facilitator"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if username is None:
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if route["gate"] == "facilitator" and username != FACILITATOR_USERNAME:
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        host = None
        if "host" in route:
            label = username.lower()
            if not DNS_LABEL_RE.match(label):
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            host = route["host"].replace("{user}", label)
        self.send_response(200)
        self.send_header("X-Dojo-User", username)
        if host is not None:
            self.send_header("X-Dojo-Host", host)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_auth_check_watch(self, parsed):
        """Gates /admin/watch/<studentId> (see gateway/Caddyfile). Reached
        only after Caddy's own facilitator-only basic_auth on /admin*, but
        re-checked here too -- this process shouldn't trust routing alone
        to keep a student out of another student's terminal."""
        username, _sid = self.resolve_identity()
        sid = (urllib.parse.parse_qs(parsed.query).get("student") or [""])[0][:40]
        if username != FACILITATOR_USERNAME:
            audit_check("watch", username, sid, 403)
            self.send_response(403)
            self.end_headers()
            return

        # A demo bot has no "held slot" concept -- see BOT_IDS above -- it's
        # always watchable as long as --test provisioned it.
        if sid not in config.BOT_IDS and (sid not in slots or slot_snapshot(sid)["name"] is None):
            audit_check("watch", username, sid, 404)
            self.send_response(404)  # not a currently held slot
            self.end_headers()
            return

        body = None if allocation.RESETS.fenced(sid) else allocation.control_request("POST", f"/start/watch/{sid}")
        audit_check("watch", username, sid, 409 if body is None else 200)
        if body is None:
            self.send_response(409)  # student has no term session to watch yet
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("X-Upstream-Port", str(watch_port(sid)))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_status_api(self):
        """Facilitator service status: authorised exactly like
        /admin/api/sessions (do_GET's gateway_authorized() ran first; Caddy's
        /admin* basic_auth is the facilitator gate). Reads the snapshot the
        probe thread publishes -- no upstream I/O here."""
        self.send_json(probes._status_snapshot)

    def handle_forgejo_password(self, sid):
        """The Roster's "Password" button (remediation T2.1d): one student's
        own Forgejo password, for when the facilitator helps at a desk.
        Behind /admin's facilitator gate like the other /admin/api routes;
        also needs the roster JS's X-Requested-With header, as Release does,
        so no other page can have a browser fetch it. Logged."""
        if self.headers.get("X-Requested-With") != "dojo-admin":
            self.send_response(403)
            self.end_headers()
            return
        if sid not in STUDENT_IDS:
            self.send_response(404)
            self.end_headers()
            return
        config.audit("forgejo-password-shown", target=sid)
        self.send_json({"studentId": sid, "password": forgejo_password(sid)}, headers=NO_STORE_HEADERS)

    def handle_sessions_api(self):
        held = held_slots()  # copies; the status call below runs without the lock
        all_ids = list(held) + config.BOT_IDS
        status = {}
        if all_ids:
            query = "/status?users=" + ",".join(all_ids)
            body = allocation.STATUS_CACHE.get(query)
            if body is None:
                body = allocation.control_request("GET", query)
                if body:
                    allocation.STATUS_CACHE.put(query, body)
            if body:
                try:
                    status = json.loads(body)
                except json.JSONDecodeError:
                    status = {}
        rows = []
        for sid, slot in held.items():
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
                "reset": allocation.RESETS.snapshot(sid),
            })
        # Demo bots are always listed (no /assign step -- see BOT_IDS above),
        # right after real students, so a facilitator can watch/Release them
        # the same way. bot-runner.sh's own narration prints which persona
        # (expert/intermediate/novice) each one is playing.
        for sid in config.BOT_IDS:
            s = status.get(sid) or {}
            rows.append({
                "studentId": sid,
                "name": f"Demo bot ({sid})",
                "ip": "bot",
                "assignedAt": None,
                "active": bool(s.get("active", False)),
                "watchable": bool(s.get("watchable", False)),
                "reset": allocation.RESETS.snapshot(sid),
            })
        self.send_json(rows)

    def handle_session_check(self, parsed):
        """Caddy's forward_auth target for every gated request. 200 plus
        X-Session-User (Caddy copies it to X-Auth-User upstream) when the
        cookie is a live session; otherwise a browser page load is sent to
        /login and anything else (a poll, an API call) gets 401. ?role=
        facilitator is /admin: the class login is refused there."""
        account = self.session_account()
        role = urllib.parse.parse_qs(parsed.query).get("role", [""])[0]
        if account is None:
            wants_page = (self.headers.get("X-Forwarded-Method", "GET") == "GET"
                          and "text/html" in self.headers.get("Accept", ""))
            if wants_page:
                target = local_path(self.headers.get("X-Forwarded-Uri", ""))
                self.redirect("/login" if not target or target == "/"
                              else "/login?next=" + urllib.parse.quote(target, safe=""))
            else:
                self.send_response(401)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
            return
        if role == "facilitator" and account != FACILITATOR_USERNAME:
            self.send_html(page("Facilitator only", (
                "<h1>Facilitator only</h1><p>This page is for the facilitator's login.</p>"
                '<p><a href="/logout">Sign in as someone else</a></p>')), status=403,
                headers=NO_STORE_HEADERS)
            return
        self.send_response(200)
        self.send_header("X-Session-User", account)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_login(self):
        form = self.read_form_body()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
        nxt = self.login_next(form.get("next"))
        ip = self.client_ip()
        account = check_login(username, password)
        if account is None:
            # A right password still gets in during someone else's guessing
            # spree from the same address (a class behind one NAT).
            if LOGIN_GUARD.blocked(ip):
                config.audit("login", ip=ip, result="rate-limited")
                self.send_html(self.render_login("Too many wrong guesses. Wait a minute and try again.",
                                                 username, nxt),
                               status=429, headers=[("Retry-After", "60")] + NO_STORE_HEADERS)
                return
            LOGIN_GUARD.fail(ip)
            config.audit("login", ip=ip, result="failed")
            self.send_html(self.render_login("That username and password don't match. Try again.",
                                             username, nxt),
                           status=401, headers=NO_STORE_HEADERS)
            return
        config.audit("login", account=account, ip=ip, result="ok")
        self.redirect(nxt, cookies=[self.session_cookie(make_session(account), SESSION_SECONDS)])

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
        if sid is None and is_bot_id(self.session_account()):
            self.read_form_body()  # a demo bot's own login never takes a student slot
            self.send_html(page("Not for bots", "<h1>Bots don't take a student slot</h1>"), status=403,
                           headers=NO_STORE_HEADERS)
            return
        if sid is not None:
            self.read_form_body()  # drain body regardless
            self.send_html(self.render_confirmation(sid), headers=NO_STORE_HEADERS)
            return

        form = self.read_form_body()
        name = (form.get("name") or "").strip()[:60]
        if not name:
            self.send_html(self.render_name_form(), status=400)
            return

        wait = allocation.ASSIGN_LIMIT.take()
        if wait:
            config.audit("assign", name=name, ip=self.client_ip(), result="rate-limited")
            self.send_html(self.render_busy(wait), status=429,
                           headers=[("Retry-After", str(wait))] + NO_STORE_HEADERS)
            return

        sid, token = claim_slot(name, self.client_ip())
        if sid is None:
            config.audit("assign", name=name, ip=self.client_ip(), result="full")
            self.send_html(self.render_full())
            return

        config.audit("assign", account=sid, name=name, ip=self.client_ip(), result="assigned")

        cookie = f"{COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Lax"
        if COOKIE_SECURE:
            cookie += "; Secure"

        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_release(self, sid):
        if sid in config.BOT_IDS:
            # No slot bookkeeping for a bot -- it isn't "assigned" in the
            # first place (see BOT_IDS above). This just kills its process;
            # bot-supervisor.sh (in web-terminal) notices within its poll
            # interval and restarts it, and bot-runner.sh resumes from its
            # own persisted (round, step) state -- see engine/README.md's
            # "Demo bots (--test)" section.
            allocation.control_request("POST", f"/stop/{sid}")
            config.audit("release", target=sid, result="bot-restarted")
            self.send_json({"released": sid})
            return
        if sid not in slots:
            self.send_response(404)
            self.end_headers()
            return
        release_slot(sid)
        self.send_json({"released": sid})

    def handle_reset(self, sid):
        """The Roster's Reset (reset.py): puts one student or bot back as at
        stack start. The facilitator types the id (form field `confirm`);
        the reset runs on the worker thread and its progress shows in
        /admin/api/sessions. Never the facilitator's own account."""
        if self.resolve_identity()[0] != FACILITATOR_USERNAME:
            # Caddy's /admin* basic_auth already decided; checked again here,
            # as /auth-check-watch does, since a reset deletes data.
            self.send_response(403)
            self.end_headers()
            return
        if sid not in STUDENT_IDS and sid not in config.BOT_IDS:
            self.send_response(404)
            self.end_headers()
            return
        form = self.read_form_body()
        if form.get("confirm") != sid:
            self.send_json({"error": "type the student id to confirm"}, status=400)
            return
        chosen = {o for o in form.get("optional", "").split(",") if o}
        if chosen - {h["id"] for h in EXTENSIONS["resets"] if h.get("optional")}:
            self.send_json({"error": "unknown optional reset step"}, status=400)
            return
        if not allocation.RESETS.request(sid, chosen):
            self.send_json({"error": "a reset of this account is already running"}, status=409)
            return
        self.send_json({"reset": sid, "state": "queued"}, status=202)

    def handle_release_unused(self):
        """The Roster's "Release unused" (remediation T3.4): frees every slot
        taken at least UNUSED_AFTER_SECONDS ago with no IDE or terminal
        running, e.g. slots a script grabbed. One status call for all."""
        now = time.time()
        # sid -> the token holding it now: a slot released and re-claimed
        # while the status call below runs is left alone (release_slot).
        held = {sid: slot["token"] for sid, slot in held_slots().items()
                if now - (slot["assigned_at"] or now) >= UNUSED_AFTER_SECONDS}
        status = {}
        if held:
            body = allocation.control_request("GET", "/status?users=" + ",".join(held))
            if not body:
                self.send_json({"error": "workspace status unavailable"}, status=503)
                return
            try:
                status = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "workspace status unavailable"}, status=503)
                return
        released = []
        for sid, token in held.items():
            s = status.get(sid) or {}
            if not s.get("active") and not s.get("watchable"):
                if release_slot(sid, result="released-unused", token=token) is not None:
                    released.append(sid)
        self.send_json({"released": released})
