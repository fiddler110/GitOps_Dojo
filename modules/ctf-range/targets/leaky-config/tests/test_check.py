import importlib.util, os, sys, threading, unittest
try:
    import flask                            # noqa: F401 - app.py imports it; checked here so a
    from werkzeug.serving import make_server  # machine without it skips instead of erroring
except ImportError as exc:                  # this target's one dependency (requirements.txt)
    raise unittest.SkipTest("needs Flask (%s): pip install -r %s" % (
        exc.name, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "requirements.txt")))

T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CTF_FLAG"] = "flag{lc-test}"
        os.environ["CTF_METRICS_PASS"] = "pw123"
        cls.app = load("lc_app", os.path.join(T, "app.py"))
        cls.check = load("lc_check", os.path.join(T, "exploit", "check.py"))
        cls.srv = make_server("127.0.0.1", 0, cls.app.app)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_vulnerable(self):
        self.assertEqual(self.check.verdict(self.url)[0], "exploitable")
        self.assertEqual(self.check.main(["--url", self.url]), 0)

    def test_auth_on_logs_contains(self):
        files = dict(self.app._ADMIN_FILES)
        self.app._ADMIN_FILES.clear()  # emulate: log no longer served
        try:
            v = self.check.verdict(self.url, legit_key="metrics-agent:pw123")
        finally:
            self.app._ADMIN_FILES.update(files)
        self.assertEqual(v[0], "contained")

    def test_scrubbed_log_contains(self):
        files = dict(self.app._ADMIN_FILES)
        self.app._ADMIN_FILES["app.log"] = "2026 INFO nothing here\n"
        try:
            self.assertEqual(self.check.verdict(self.url)[0], "contained")
        finally:
            self.app._ADMIN_FILES.update(files)

    def test_broke_when_legit_key_wrong(self):
        files = dict(self.app._ADMIN_FILES)
        self.app._ADMIN_FILES["app.log"] = "clean\n"
        try:
            v = self.check.verdict(self.url, legit_key="metrics-agent:wrong")
        finally:
            self.app._ADMIN_FILES.update(files)
        self.assertEqual(v[0], "broke-normal-use")

    def test_unreachable(self):
        self.assertEqual(self.check.main(["--url", "http://127.0.0.1:1"]), 2)


if __name__ == "__main__":
    unittest.main()
