"""A small SSH server with an emulated shell, for the sqli-login box.

A real sshd can't run here: the slot container drops every capability and runs
read-only as a non-root user, and sshd needs root to switch users. So this is a
genuine SSH-2 server (asyncssh) that students reach with their normal `ssh`
client, but the shell behind the login is a handful of built-in commands over a
fake filesystem. There is no real shell, no real filesystem access and nothing
to escape to: the commands only read the dict below.

One account (the service account that leaks in the portal's logs). The flag sits
in its home directory as flag.txt.
"""
import asyncio
import hashlib
import hmac
import posixpath
import threading

import asyncssh
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HOSTNAME = "print01"
BANNER = "OpenSSH_9.7p1 Debian-7"


def _fs(user, flag):
    home = f"/home/{user}"
    files = {
        f"{home}/flag.txt": flag + "\n",
        f"{home}/README": "Meridian print server. Queue logs are in /var/log/cups.\n"
                          "Questions: it-helpdesk@meridiancorp.example\n",
        "/etc/hostname": HOSTNAME + "\n",
        "/etc/os-release": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"\n',
        "/etc/passwd": ("root:x:0:0:root:/root:/bin/bash\n"
                        "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
                        f"{user}:x:1001:1001:Print service:{home}:/bin/bash\n"),
        "/var/log/cups/error_log": "E [18/Oct/2026:09:12:41 +0000] Unable to open print file: Permission denied\n",
    }
    dirs = {"/", "/home", home, "/etc", "/var", "/var/log", "/var/log/cups", "/tmp", "/root"}
    return files, dirs


class Shell:
    def __init__(self, user, flag):
        self.user = user
        self.home = f"/home/{user}"
        self.cwd = self.home
        self.files, self.dirs = _fs(user, flag)

    def path(self, p):
        if p.startswith("~"):
            p = self.home + p[1:]
        return posixpath.normpath(p if p.startswith("/") else posixpath.join(self.cwd, p))

    def prompt(self):
        shown = "~" if self.cwd == self.home else self.cwd
        return f"{self.user}@{HOSTNAME}:{shown}$ "

    def _denied(self, p):
        return p == "/root" or p.startswith("/root/")

    def ls(self, args):
        long = any(a.startswith("-") and "l" in a for a in args)
        show_all = any(a.startswith("-") and "a" in a for a in args)
        targets = [a for a in args if not a.startswith("-")] or ["."]
        out = []
        for t in targets:
            p = self.path(t)
            if self._denied(p):
                out.append(f"ls: cannot open directory '{t}': Permission denied")
                continue
            if p in self.files:
                names = [posixpath.basename(p)]
            elif p in self.dirs:
                names = sorted({posixpath.basename(x) for x in list(self.files) + list(self.dirs)
                                if x != p and posixpath.dirname(x) == p and posixpath.basename(x)})
            else:
                out.append(f"ls: cannot access '{t}': No such file or directory")
                continue
            if not show_all:
                names = [n for n in names if not n.startswith(".")]
            if len(targets) > 1:
                out.append(f"{t}:")
            if long:
                for n in names:
                    full = posixpath.join(p, n) if p in self.dirs else p
                    kind, size = ("d", 4096) if full in self.dirs else ("-", len(self.files.get(full, "")))
                    out.append(f"{kind}rw-r--r-- 1 {self.user} {self.user} {size:>5} Oct 18 09:12 {n}")
            elif names:
                out.append("  ".join(names))
        return "\n".join(out)

    def cat(self, args):
        if not args:
            return ""
        out = []
        for a in args:
            p = self.path(a)
            if self._denied(p):
                out.append(f"cat: {a}: Permission denied")
            elif p in self.files:
                out.append(self.files[p].rstrip("\n"))
            elif p in self.dirs:
                out.append(f"cat: {a}: Is a directory")
            else:
                out.append(f"cat: {a}: No such file or directory")
        return "\n".join(out)

    def cd(self, args):
        p = self.path(args[0]) if args else self.home
        if self._denied(p):
            return f"bash: cd: {args[0]}: Permission denied"
        if p in self.files:
            return f"bash: cd: {args[0]}: Not a directory"
        if p not in self.dirs:
            return f"bash: cd: {args[0]}: No such file or directory"
        self.cwd = p
        return ""

    def run(self, line):
        """Returns (output, exit?)."""
        line = line.strip()
        if not line:
            return "", False
        parts = line.split()
        cmd, args = parts[0], parts[1:]
        if cmd in ("exit", "logout"):
            return "logout", True
        if cmd == "ls":
            return self.ls(args), False
        if cmd == "cat":
            return self.cat(args), False
        if cmd == "cd":
            return self.cd(args), False
        if cmd == "pwd":
            return self.cwd, False
        if cmd == "whoami":
            return self.user, False
        if cmd == "id":
            return f"uid=1001({self.user}) gid=1001({self.user}) groups=1001({self.user})", False
        if cmd == "hostname":
            return HOSTNAME, False
        if cmd == "uname":
            return ("Linux print01 6.1.0-18-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.76-1 x86_64 GNU/Linux"
                    if "-a" in args else "Linux"), False
        if cmd == "echo":
            return " ".join(args), False
        if cmd == "clear":
            return "\x1b[2J\x1b[H", False
        if cmd == "sudo":
            return f"Sorry, user {self.user} may not run sudo on {HOSTNAME}.", False
        if cmd == "help":
            return "Available here: ls, cat, cd, pwd, whoami, id, hostname, uname, echo, clear, exit", False
        return f"bash: {cmd}: command not found", False


class _Server(asyncssh.SSHServer):
    def __init__(self, user, password):
        self._user, self._password = user, password

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        ok_user = hmac.compare_digest(username.encode(), self._user.encode())
        ok_pw = hmac.compare_digest(password.encode(), self._password.encode())
        return ok_user and ok_pw


def _host_key(seed):
    """A stable host key per box, so Reset/restart doesn't trip the student's known_hosts."""
    raw = hashlib.sha256(b"sqli-login-hostkey:" + seed.encode()).digest()
    pem = Ed25519PrivateKey.from_private_bytes(raw).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption())
    return asyncssh.import_private_key(pem)


def start(port, user, password, flag, key_seed):
    key = _host_key(key_seed)

    async def handle(process):
        sh = Shell(user, flag)
        out = process.stdout
        if process.command:  # ssh host 'cat flag.txt'
            text, _ = sh.run(process.command)
            if text:
                out.write(text + "\n")
            process.exit(0)
            return
        out.write(f"Welcome to {HOSTNAME} (Meridian Corp print server)\n"
                  "Type 'help' for the commands available here.\n\n")
        while True:
            out.write(sh.prompt())
            try:
                line = await process.stdin.readline()
            except asyncssh.BreakReceived:
                continue
            except asyncssh.TerminalSizeChanged:
                continue
            if not line:
                break
            text, done = sh.run(line)
            if text:
                out.write(text + "\n")
            if done:
                break
        process.exit(0)

    def serve():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncssh.listen(
            "0.0.0.0", port,
            server_factory=lambda: _Server(user, password),
            server_host_keys=[key], process_factory=handle,
            server_version=BANNER, encoding="utf-8",
            line_editor=True))
        loop.run_forever()

    threading.Thread(target=serve, daemon=True).start()
