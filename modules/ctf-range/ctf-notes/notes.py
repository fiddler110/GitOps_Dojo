"""ctf-notes: a browser editor for the file ~/lab/notes.md in a student's terminal home.

The terminal and this page edit the same file, so a student can `cat`/`vim` it in the terminal or
type into the Notes page, whichever is handier. Identity is X-Auth-User alongside this service's own
X-Gateway-Token (dojo_http.gateway_user); a student only ever reaches their own home. The service
has the terminal_home volume and two capabilities (DAC_OVERRIDE, CHOWN), so the path is walked with
dir fds and O_NOFOLLOW and each step must be owned by the home's owner: a symlink or hard link a
student plants in their home cannot redirect a write to another file.

  GET  /api/notes                -> {"text": str, "mtime": int}
  GET  /api/notes?user=NAME      -> the same for a student, read-only; the facilitator only
  GET  /api/students             -> {"students": [name, ...]}; the facilitator only (403 otherwise)
  PUT  /api/notes {"text", "base"} -> {"ok": true, "mtime": int} | 409 {"conflict": true}
       "base" is the mtime the editor last saw; a different mtime means the terminal changed the
       file meanwhile. base=null overwrites regardless.
"""
import http.server
import json
import os
import re
import signal
import stat
import sys
import threading
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402

HOME_ROOT = os.environ.get("NOTES_HOME", "/home")
_WRITE = threading.Lock()
TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "")
MAX_BYTES = 256 * 1024
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/notes.js": ("notes.js", "text/javascript"),
          "/notes.css": ("notes.css", "text/css")}

# Keep in step with terminal/start.d/56-ctf-notes.sh, which creates the same file at login.
TEMPLATE = """# Lab notes

## Targets
- box / IP / ports:

## nmap results

## Credentials found
- user / password / where:

## Flags and ideas
"""


class NotesError(Exception):
    pass


def _dir_fd(parent_fd, name, owner=None):
    """Open directory NAME under PARENT_FD without following symlinks. With OWNER=(uid, gid) a
    missing directory is created for them. The result must be owned by the expected uid."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if owner is None:
            raise NotesError("no home directory for this account")
    except OSError:
        raise NotesError(f"{name} is not a plain directory")
    os.mkdir(name, 0o755, dir_fd=parent_fd)
    os.chown(name, owner[0], owner[1], dir_fd=parent_fd, follow_symlinks=False)
    return os.open(name, flags, dir_fd=parent_fd)


def open_notes(user, root=None, create=True):
    """The open (read/write) fd of USER's notes file, creating it for them if needed.
    create=False (the facilitator reading a student's) opens read-only and creates nothing."""
    if not USER_RE.match(user or ""):
        raise NotesError("bad account name")
    root_fd = os.open(root or HOME_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    fds = [root_fd]
    try:
        home = _dir_fd(root_fd, user)
        fds.append(home)
        st = os.fstat(home)
        if st.st_uid == 0:
            raise NotesError("refusing a root-owned home")
        owner = (st.st_uid, st.st_gid)
        try:
            lab = _dir_fd(home, "lab", owner if create else None)
        except NotesError:
            if create:
                raise
            raise NotesError("no notes yet")
        fds.append(lab)
        if os.fstat(lab).st_uid != owner[0]:
            raise NotesError("lab directory is not yours")
        try:
            fd = os.open("notes.md", (os.O_RDWR if create else os.O_RDONLY) | os.O_NOFOLLOW, dir_fd=lab)
        except FileNotFoundError:
            if not create:
                raise NotesError("no notes yet")
            fd = os.open("notes.md", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=lab)
            os.write(fd, TEMPLATE.encode())
            os.fchown(fd, owner[0], owner[1])
        except OSError:
            raise NotesError("notes.md is not a plain file")
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode) or fst.st_uid != owner[0] or fst.st_nlink != 1:
            os.close(fd)
            raise NotesError("notes.md is not a plain file you own")
        return fd
    finally:
        for f in fds:
            os.close(f)


def _mtime(fd):
    """Modification time in microseconds: nanoseconds overflow a JavaScript number's exact range."""
    return os.fstat(fd).st_mtime_ns // 1000


def read_notes(user, root=None, create=True):
    fd = open_notes(user, root, create)
    try:
        data = os.pread(fd, MAX_BYTES, 0)
        return data.decode("utf-8", "replace"), _mtime(fd)
    finally:
        os.close(fd)


def list_students(root=None, facilitator=None):
    """Every account with a home (not root's, not a symlink), for the facilitator's picker."""
    root = root or HOME_ROOT
    facilitator = FACILITATOR if facilitator is None else facilitator
    out = []
    for name in os.listdir(root):
        if name == facilitator or not USER_RE.match(name):
            continue
        try:
            st = os.lstat(os.path.join(root, name))
        except OSError:
            continue
        if stat.S_ISDIR(st.st_mode) and st.st_uid != 0:
            out.append(name)
    return sorted(out)


def write_notes(user, text, base, root=None):
    """Save TEXT. Returns (ok, mtime): not ok means the file changed since BASE."""
    data = text.encode()
    if len(data) > MAX_BYTES:
        raise NotesError("notes are too large")
    with _WRITE:
        return _write(user, data, base, root)


def _write(user, data, base, root):
    fd = open_notes(user, root)
    try:
        now = _mtime(fd)
        if base is not None and base != now:
            return False, now
        os.ftruncate(fd, 0)
        os.pwrite(fd, data, 0)
        os.fsync(fd)
        return True, _mtime(fd)
    finally:
        os.close(fd)


def make_handler():
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-notes"
        sys_version = ""

        def log_message(self, fmt, *args):
            pass

        def _path(self):
            return self.path.split("?", 1)[0]

        def do_GET(self):
            path = self._path()
            if path == "/healthz":
                return dojo_http.send(self, 200, b"ok\n", "text/plain")
            user = dojo_http.gateway_user(self.headers, TOKEN)
            if not user:
                return dojo_http.send_json(self, 403, {"error": "gateway token required"})
            if path in STATIC:
                name, ctype = STATIC[path]
                with open(os.path.join(HERE, "static", name), "rb") as f:
                    return dojo_http.send(self, 200, f.read(), ctype)
            is_facilitator = bool(FACILITATOR) and user == FACILITATOR
            if path == "/api/students":
                if not is_facilitator:
                    return dojo_http.send_json(self, 403, {"error": "facilitator only"})
                return dojo_http.send_json(self, 200, {"students": list_students()})
            if path == "/api/notes":
                who = (parse_qs(urlsplit(self.path).query).get("user") or [user])[0]
                if who != user and not is_facilitator:
                    return dojo_http.send_json(self, 403, {"error": "you can only read your own notes"})
                try:
                    text, mtime = read_notes(who, create=(who == user))
                except NotesError as exc:
                    return dojo_http.send_json(self, 409, {"error": str(exc)})
                return dojo_http.send_json(self, 200, {"text": text, "mtime": mtime})
            dojo_http.send_json(self, 404, {"error": "not found"})

        def do_PUT(self):
            user = dojo_http.gateway_user(self.headers, TOKEN)
            if not user:
                return dojo_http.send_json(self, 403, {"error": "gateway token required"})
            if self._path() != "/api/notes":
                return dojo_http.send_json(self, 404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BYTES + 4096:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                text, base = body.get("text"), body.get("base")
                if not isinstance(text, str) or not (base is None or isinstance(base, int)):
                    raise ValueError
            except (ValueError, AttributeError):
                return dojo_http.send_json(self, 400, {"error": "bad request"})
            try:
                ok, mtime = write_notes(user, text, base)
            except NotesError as exc:
                return dojo_http.send_json(self, 409, {"error": str(exc)})
            if not ok:
                return dojo_http.send_json(self, 409, {"conflict": True, "mtime": mtime})
            dojo_http.send_json(self, 200, {"ok": True, "mtime": mtime})
    return Handler


def main():
    port = int(os.environ.get("PORT", "9300"))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    print(f"[ctf-notes] listening on {port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
