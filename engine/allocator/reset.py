"""Student reset: put one student (or demo bot) back as they were at stack
start, while everyone else carries on (docs/archive/STUDENT-RESET-PLAN.md,
§4.2; decisions R2-R8, Q1-Q7).

The facilitator asks for it from the Roster (server.py, POST
/admin/reset/<sid>). One worker thread runs resets one at a time (R8), each
as a list of steps:

  stop               kill the student's VS Code and terminal processes
  <hook>-teardown    each service reset hook a module or workshop declares
                     (extensions.json `resets`), in manifest order, while the
                     Forgejo account still exists
  forgejo-teardown   in the org's repos: close the student's open pull
                     requests and delete the branches they made (Q5); then
                     delete the account with purge (its own repos and forks)
  forgejo-provision  recreate the account and its team membership, as
                     git-server/bootstrap.sh does (Q6)
  terminal           workspace-control.py's POST /reset/<user>: reset.d hooks,
                     home and temp files removed, the account provisioned
                     again, account.d hooks
  <hook>-provision   each service reset hook again, same order: set the
                     student's state up as at start

A step that fails stops the reset there; Retry runs the whole list again
(every step is idempotent, R5). While a reset is queued or running the
student is fenced: server.py serves the starting page (or 503) for their
routes instead of proxying. The seat is kept (R4).

Locking: `ResetManager.lock` guards `state` only, never held across a step.
"""
import base64
import hashlib
import hmac
import http.client
import json
import queue
import socket
import threading
import time
import urllib.parse

DETAIL_MAX = 200
TEAM_NAME = "students"
# render_extensions.py RESET_TOKEN_CONTEXT: each hook's service gets its own
# token, RESET_TOKEN_<SERVICE> in its compose fragment.
RESET_TOKEN_CONTEXT = "dojo-reset-token/v1/"


class ResetError(Exception):
    pass


def _short(text):
    text = " ".join(str(text).split())
    return text if len(text) <= DETAIL_MAX else text[:DETAIL_MAX - 1] + "…"


class Forgejo:
    """The few admin API calls a reset makes, as the Forgejo admin."""

    def __init__(self, host, port, user, password, timeout=10.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def call(self, method, path, body=None):
        """(status, parsed JSON or None). Raises ResetError when Forgejo
        can't be reached."""
        headers = {"Authorization": self.auth, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        try:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            conn.request(method, "/api/v1" + path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            raise ResetError(f"Forgejo unreachable: {exc}") from exc
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return resp.status, parsed

    def expect(self, method, path, ok, body=None):
        status, parsed = self.call(method, path, body)
        if status not in ok:
            message = parsed.get("message") if isinstance(parsed, dict) else ""
            raise ResetError(f"{method} {path.split('?')[0]}: HTTP {status} {message or ''}".strip())
        return status, parsed

    def pages(self, path):
        """Every item of a paged list endpoint."""
        sep = "&" if "?" in path else "?"
        page, items = 1, []
        while True:
            _, chunk = self.expect("GET", f"{path}{sep}limit=50&page={page}", (200,))
            chunk = chunk or []
            items += chunk
            if len(chunk) < 50:
                return items
            page += 1


def q(part):
    return urllib.parse.quote(part, safe="")


def _authored_by(branch, user):
    commit = branch.get("commit") or {}
    for who in (commit.get("author") or {}, commit.get("committer") or {}):
        if who.get("username") == user or (who.get("email") or "").lower() == f"{user}@example.com":
            return True
    return False


def clean_org_repo(fj, org, repo, user):
    """Close the user's open PRs in one org repo and delete the branches they
    made: the heads of their PRs and branches whose head commit is theirs.
    Never the default branch, a protected one, or one another user's open PR
    still uses. Returns (closed, deleted) counts."""
    full = f"{q(org)}/{q(repo['name'])}"
    pulls = fj.pages(f"/repos/{full}/pulls?state=open")
    in_repo = f"{org}/{repo['name']}"
    theirs, others = set(), set()
    closed = 0
    for pr in pulls:
        head = pr.get("head") or {}
        same_repo = ((head.get("repo") or {}).get("full_name") or "") == in_repo
        if (pr.get("user") or {}).get("login") == user:
            fj.expect("PATCH", f"/repos/{full}/pulls/{int(pr['number'])}", (200, 201), {"state": "closed"})
            closed += 1
            if same_repo and head.get("ref"):
                theirs.add(head["ref"])
        elif same_repo and head.get("ref"):
            others.add(head["ref"])
    deleted = 0
    for branch in fj.pages(f"/repos/{full}/branches"):
        name = branch.get("name") or ""
        if (not name or name == repo.get("default_branch") or branch.get("protected")
                or name in others):
            continue
        if name in theirs or _authored_by(branch, user):
            fj.expect("DELETE", f"/repos/{full}/branches/{urllib.parse.quote(name, safe='/')}", (204, 404))
            deleted += 1
    return closed, deleted


def forgejo_teardown(fj, org, user):
    closed = deleted = 0
    for repo in fj.pages(f"/orgs/{q(org)}/repos"):
        c, d = clean_org_repo(fj, org, repo, user)
        closed, deleted = closed + c, deleted + d
    status, _ = fj.expect("DELETE", f"/admin/users/{q(user)}?purge=true", (204, 404))
    gone = "account deleted" if status == 204 else "no account"
    return f"{closed} PR(s) closed, {deleted} branch(es) deleted, {gone}"


def forgejo_provision(fj, org, user, password):
    status, _ = fj.call("GET", f"/users/{q(user)}")
    if status == 404:
        fj.expect("POST", "/admin/users", (201,), {
            "username": user, "password": password, "email": f"{user}@example.com",
            "must_change_password": False})
        made = "account created"
    else:
        fj.expect("PATCH", f"/admin/users/{q(user)}", (200,), {
            "login_name": user, "source_id": 0, "password": password, "must_change_password": False})
        made = "account kept"
    team = next((t for t in fj.pages(f"/orgs/{q(org)}/teams") if t.get("name") == TEAM_NAME), None)
    if team is None:
        raise ResetError(f"no '{TEAM_NAME}' team in {org}")
    fj.expect("PUT", f"/teams/{int(team['id'])}/members/{q(user)}", (204,))
    return f"{made}, in team '{TEAM_NAME}'"


def hook_token(master, service):
    """The X-Dojo-Reset-Token a service's reset hook checks."""
    return hmac.new(master.encode(), (RESET_TOKEN_CONTEXT + service).encode(), hashlib.sha256).hexdigest()


def call_hook(hook, user, phase, master):
    """POST one service reset hook (render_extensions.py checked its
    upstream, path and timeout). The service answers 200 with
    {"ok": true, "detail": "..."}; anything else fails the step."""
    service, _, port = hook["upstream"].rpartition(":")
    path = hook["path"].replace("{user}", q(user)) + "?phase=" + phase
    try:
        conn = http.client.HTTPConnection(service, int(port), timeout=hook["timeout"])
        conn.request("POST", path, body=b"", headers={
            "X-Dojo-Reset-Token": hook_token(master, service), "Accept": "application/json",
            "Content-Length": "0"})
        resp = conn.getresponse()
        raw = resp.read(64 * 1024)
        conn.close()
    except (OSError, socket.timeout, http.client.HTTPException) as exc:
        raise ResetError(f"{service} unreachable: {exc}") from exc
    try:
        parsed = json.loads(raw) if raw else None
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        parsed = {}
    detail = parsed.get("detail") or parsed.get("error") or ""
    if resp.status != 200 or parsed.get("ok") is not True:
        raise ResetError(f"{service}: HTTP {resp.status} {detail}".strip())
    return str(detail) or "ok"


def hook_steps(hooks, user, phase, master):
    """[(id, label, fn)] for one phase of every service hook, in order."""
    word = {"teardown": "tear down", "provision": "set up again"}[phase]
    return [(f"{h['id']}-{phase}", f"{h['label']}: {word}",
             (lambda h=h: call_hook(h, user, phase, master))) for h in hooks]


class ResetManager:
    """Queued and running resets, and the last result for each account.

    `steps_for(sid)` returns [(id, label, fn)]; fn() returns a short detail
    string or raises. `audit(event, **fields)` logs each step."""

    def __init__(self, steps_for, audit, clock=time.time):
        self.steps_for, self.audit, self.clock = steps_for, audit, clock
        self.lock = threading.Lock()
        self.state = {}  # sid -> {"state", "steps": [{id, label, status, detail}], "started", "finished"}
        self.queue = queue.Queue()

    def request(self, sid):
        """Queue a reset. False when one is already queued or running."""
        with self.lock:
            if self._busy(sid):
                return False
            self.state[sid] = {
                "state": "queued", "started": None, "finished": None,
                "steps": [{"id": i, "label": label, "status": "pending", "detail": ""}
                          for i, label, _ in self.steps_for(sid)]}
        self.audit("reset-requested", target=sid)
        self.queue.put(sid)
        return True

    def _busy(self, sid):
        cur = self.state.get(sid)
        return cur is not None and cur["state"] in ("queued", "running")

    def fenced(self, sid):
        with self.lock:
            return self._busy(sid)

    def snapshot(self, sid):
        with self.lock:
            cur = self.state.get(sid)
            if cur is None:
                return None
            return dict(cur, steps=[dict(s) for s in cur["steps"]])

    def _set(self, sid, **fields):
        with self.lock:
            self.state[sid].update(fields)

    def _set_step(self, sid, n, **fields):
        with self.lock:
            self.state[sid]["steps"][n].update(fields)

    def run_one(self, sid):
        self._set(sid, state="running", started=self.clock())
        ok = True
        for n, (step_id, _label, fn) in enumerate(self.steps_for(sid)):
            self._set_step(sid, n, status="running")
            try:
                detail, step_ok = _short(fn() or ""), True
            except Exception as exc:  # noqa: BLE001 -- any failure is the step's result
                detail, step_ok = _short(exc), False
            self._set_step(sid, n, status="done" if step_ok else "failed", detail=detail)
            self.audit("reset-step", target=sid, step=step_id, ok=step_ok, detail=detail)
            if not step_ok:
                ok = False
                break
        self._set(sid, state="done" if ok else "failed", finished=self.clock())
        self.audit("reset", target=sid, result="done" if ok else "failed")

    def worker(self):
        while True:
            self.run_one(self.queue.get())

    def start(self):
        threading.Thread(target=self.worker, name="student-reset", daemon=True).start()
