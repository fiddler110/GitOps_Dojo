"""Unit tests for student resets in OpenBao (no stack needed):

    python3 -B -m unittest discover -s modules/openbao/tests -p 'test_*.py'

- openbao-reset (reset/reset.py): the token checks, and a job relayed to a
  stand-in worker and back over real HTTP.
- setup.sh's reset_one with vault-fundamentals' openbao-setup.d hooks in
  one-user mode, against a stub `bao` that records each call: only that
  student's part runs, with the reset token, teardown in reverse order.
"""
import http.client
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..")
REPO = os.path.join(MODULE, "..", "..")
HOOKS = os.path.join(REPO, "workshops", "vault-fundamentals", "compose", "openbao-setup.d")
sys.path.insert(0, os.path.join(MODULE, "reset"))
import reset as r  # noqa: E402

TOKEN = "hook-token"


class Service(unittest.TestCase):
    def setUp(self):
        self.relay = r.Relay()
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), r.make_handler(self.relay, TOKEN, job_timeout=2, poll_wait=1))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, method, path, token=TOKEN, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        conn.request(method, path, body=body, headers={} if token is None else {"X-Dojo-Reset-Token": token})
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, raw.decode()

    def test_token_required(self):
        for token in (None, "", "wrong"):
            for method, path in (("POST", "/_dojo/reset/student01?phase=teardown"), ("GET", "/_dojo/work"),
                                 ("POST", "/_dojo/work/abc")):
                self.assertEqual(self.call(method, path, token)[0], 403, (token, path))
        self.assertEqual(list(self.relay.pending), [])

    def test_empty_token_refuses_everything(self):
        self.server.RequestHandlerClass = r.make_handler(self.relay, "")
        self.assertEqual(self.call("POST", "/_dojo/reset/student01?phase=teardown", "")[0], 403)
        self.assertEqual(self.call("GET", "/_dojo/work", "")[0], 403)
        self.assertEqual(self.call("GET", "/healthz", None), (200, {"ok": True, "armed": False}))

    def test_bad_requests(self):
        self.assertEqual(self.call("POST", "/_dojo/reset/student01?phase=wipe")[0], 404)
        self.assertEqual(self.call("POST", "/_dojo/reset/..%2Fsys?phase=teardown")[0], 400)
        self.assertEqual(self.call("POST", "/_dojo/reset/Student01?phase=teardown")[0], 400)
        self.assertEqual(self.call("POST", "/_dojo/other/student01?phase=teardown")[0], 404)

    def test_a_job_goes_to_the_worker_and_back(self):
        seen = []

        def worker():
            line = self.call("GET", "/_dojo/work")[1]
            seen.append(line)
            self.call("POST", "/_dojo/work/" + line.split()[0], body=b"ok\nopenbao-setup: tenancy: deleted\nteardown done\n")
        threading.Thread(target=worker, daemon=True).start()
        code, doc = self.call("POST", "/_dojo/reset/student01?phase=teardown")
        self.assertEqual((code, doc), (200, {"ok": True, "detail": "openbao-setup: tenancy: deleted teardown done"}))
        self.assertRegex(seen[0], r"^[0-9a-f]{16} teardown student01\n$")

    def test_failure_and_no_worker(self):
        def worker():
            line = self.call("GET", "/_dojo/work")[1]
            self.call("POST", "/_dojo/work/" + line.split()[0], body=b"fail\nhook 10-tenancy.sh failed")
        threading.Thread(target=worker, daemon=True).start()
        self.assertEqual(self.call("POST", "/_dojo/reset/student01?phase=provision"),
                         (502, {"ok": False, "detail": "hook 10-tenancy.sh failed"}))
        started = time.monotonic()
        code, doc = self.call("POST", "/_dojo/reset/student01?phase=provision")
        self.assertEqual(code, 502)
        self.assertIn("not running", doc["detail"])
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(self.call("GET", "/_dojo/work"), (200, ""))  # the timed-out job was withdrawn
        self.assertEqual(self.call("POST", "/_dojo/work/deadbeef", body=b"ok\n")[0], 404)

    def test_relay_reports_a_taken_job_that_never_finishes(self):
        relay = r.Relay()
        threading.Thread(target=lambda: relay.take(2), daemon=True).start()
        ok, detail = relay.run("teardown", "student01", 0.5)
        self.assertFalse(ok)
        self.assertIn("did not finish", detail)


# A stand-in for the bao CLI: records "<namespace>|<token>|<args>" and keeps
# namespaces as files, enough for the hooks' one-user paths.
BAO_STUB = r"""#!/bin/sh
st="$STUB_STATE"
echo "${BAO_NAMESPACE:-}|${BAO_TOKEN:-}|$*" >> "$st/calls"
case "$*" in
  "namespace lookup "*) [ -e "$st/ns-${BAO_NAMESPACE:-}-$3" ] ;;
  "namespace create "*) touch "$st/ns-${BAO_NAMESPACE:-}-$3" ;;
  "namespace delete "*) rm -f "$st/ns-${BAO_NAMESPACE:-}-$3" ;;
  "list -format=json secret/metadata/students/student01/")
    printf '[\n  "app/",\n  "welcome"\n]\n' ;;
  "list -format=json secret/metadata/students/student01/app/")
    printf '[\n  "db"\n]\n' ;;
  "list -format=json "*) echo "No value found at $3" >&2; exit 2 ;;
  "read database/config/app-db") exit 2 ;;
  *" -") cat > /dev/null ;;
esac
"""


def shell_function(text, name):
    m = re.search(r"^" + name + r"\(\) \{\n.*?^\}\n", text, re.S | re.M)
    assert m, name
    return m.group(0)


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class ResetOne(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        t = self.tmp
        for d in ("bin", "state", "hooks", "run", "app-db"):
            os.makedirs(os.path.join(t, d))
        with open(os.path.join(t, "bin", "bao"), "w") as f:
            f.write(BAO_STUB)
        os.chmod(os.path.join(t, "bin", "bao"), 0o755)
        for name in os.listdir(HOOKS):
            with open(os.path.join(HOOKS, name)) as f:
                text = f.read().replace("/app-db/", t + "/app-db/").replace("/etc/openbao-setup.d", t + "/hooks")
            with open(os.path.join(t, "hooks", name), "w") as f:
                f.write(text)
        with open(os.path.join(t, "app-db", "student01"), "w") as f:
            f.write("first-password")
        with open(os.path.join(t, "run", "reset-token"), "w") as f:
            f.write("the-reset-token\n")
        with open(os.path.join(MODULE, "setup", "setup.sh")) as f:
            setup = f.read()
        funcs = "".join(shell_function(setup, n) for n in ("class_users", "par_each", "enable_once", "reset_one"))
        self.harness = os.path.join(t, "harness.sh")
        with open(self.harness, "w") as f:
            f.write("set -eu\n"
                    f"run={t}/run; hooks={t}/hooks\n"
                    'log() { echo "openbao-setup: $*"; }\n'
                    # No waiting in tests: one try each.
                    'retry() { shift; "$@"; }\n'
                    + funcs + 'reset_one "$1" "$2"\n')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def reset(self, phase, user="student01"):
        env = dict(os.environ, PATH=os.path.join(self.tmp, "bin") + ":" + os.environ["PATH"],
                   STUB_STATE=os.path.join(self.tmp, "state"), STUDENT_COUNT="2", STUDENT_PREFIX="student",
                   BOT_COUNT="1", BOT_PREFIX="testuser", BAO_CHECK_TOKEN="check", PUBLIC_BASE_URL="http://x",
                   BAO_TOKEN="the-provisioner-must-not-be-used")
        out = subprocess.run(["sh", self.harness, phase, user], capture_output=True, text=True, env=env, timeout=60)
        try:
            with open(os.path.join(self.tmp, "state", "calls")) as f:
                calls = f.read().splitlines()
            os.unlink(os.path.join(self.tmp, "state", "calls"))
        except FileNotFoundError:
            calls = []
        return out, calls

    def assert_only_student01(self, calls):
        self.assertTrue(calls)
        for c in calls:
            ns, token, args = c.split("|", 2)
            self.assertEqual(token, "the-reset-token", c)
            self.assertNotIn("student02", c)
            self.assertNotIn("testuser1", c)
            # The class-wide parts: the root namespace's mounts and policies, students/, the check token.
            if not ns:
                for class_wide in ("secrets enable", "policy write", "namespace create students"):
                    self.assertFalse(args.startswith(class_wide), c)
            self.assertNotIn("auth/token/create", args)

    def test_teardown(self):
        open(os.path.join(self.tmp, "state", "ns-students-student01"), "w").close()
        out, calls = self.reset("teardown")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assert_only_student01(calls)
        self.assertIn("students|the-reset-token|namespace delete student01", calls)
        self.assertIn("|the-reset-token|delete secret/metadata/students/student01/welcome", calls)
        self.assertIn("|the-reset-token|delete secret/metadata/students/student01/app/db", calls)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "state", "ns-students-student01")))
        self.assertNotIn("auth enable", "\n".join(calls))  # 20/30 do nothing on teardown
        self.assertIn("teardown of student01 done", out.stdout)
        # Again, with the namespace already gone: still fine.
        out, calls = self.reset("teardown")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("students|the-reset-token|namespace delete student01", calls)

    def test_provision(self):
        out, calls = self.reset("provision")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assert_only_student01(calls)
        joined = "\n".join(calls)
        self.assertIn("students|the-reset-token|namespace create student01", calls)
        self.assertIn("|the-reset-token|write sys/quotas/rate-limit/students-student01", joined)
        self.assertIn("|the-reset-token|write secret/data/students/student01/welcome -", calls)
        self.assertIn("students/student01|the-reset-token|auth enable -path=jwt-ci", joined)
        self.assertIn("students/student01|the-reset-token|auth enable -path=jwt-platform", joined)
        self.assertIn(f"password=@{self.tmp}/app-db/student01", joined)
        self.assertIn("students/student01|the-reset-token|write -f database/rotate-root/app-db", calls)
        # Name order on provision: tenancy before ci before platform.
        first = [next(i for i, c in enumerate(calls) if key in c)
                 for key in ("namespace create", "-path=jwt-ci", "-path=jwt-platform")]
        self.assertEqual(first, sorted(first))

    def test_refusals(self):
        out, calls = self.reset("teardown", "student09")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not an account of this class", out.stdout)
        self.assertEqual(calls, [])
        os.unlink(os.path.join(self.tmp, "run", "reset-token"))
        out, calls = self.reset("teardown")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("no reset token", out.stdout)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
