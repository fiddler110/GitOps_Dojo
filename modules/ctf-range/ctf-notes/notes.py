"""ctf-notes: a browser editor for the file ~/lab/notes.md in a student's terminal home.

The terminal and this page edit the same file, so a student can `cat`/`vim` it in the terminal or
type into the Notes page, whichever is handier. Identity is X-Auth-User alongside this service's own
X-Gateway-Token (dojo_http.gateway_user); a student only ever reaches their own home. The service
has the terminal_home volume and two capabilities (DAC_OVERRIDE, CHOWN), so the path is walked with
dir fds and O_NOFOLLOW and each step must be owned by the home's owner: a symlink or hard link a
student plants in their home cannot redirect a write to another file.

  GET  /api/notes                -> {"text": str, "mtime": int}
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402

HOME_ROOT = os.environ.get("NOTES_HOME", "/home")
_WRITE = threading.Lock()
TOKEN = os.environ.get("GATEWAY_TOKEN", "")
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


def open_notes(user, root=None):
    """The open (read/write) fd of USER's notes file, creating it for them if needed."""
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
        lab = _dir_fd(home, "lab", owner)
        fds.append(lab)
        if os.fstat(lab).st_uid != owner[0]:
            raise NotesError("lab directory is not yours")
        try:
            fd = os.open("notes.md", os.O_RDWR | os.O_NOFOLLOW, dir_fd=lab)
        except FileNotFoundError:
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


def read_notes(user, root=None):
    fd = open_notes(user, root)
    try:
        data = os.pread(fd, MAX_BYTES, 0)
        return data.decode("utf-8", "replace"), os.fstat(fd).st_mtime_ns
    finally:
        os.close(fd)


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
        now = os.fstat(fd).st_mtime_ns
        if base is not None and base != now:
            return False, now
        os.ftruncate(fd, 0)
        os.pwrite(fd, data, 0)
        os.fsync(fd)
        return True, os.fstat(fd).st_mtime_ns
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
            if path == "/api/notes":
                try:
                    text, mtime = read_notes(user)
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
