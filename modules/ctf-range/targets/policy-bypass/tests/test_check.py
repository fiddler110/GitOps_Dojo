import importlib.util, json, os, sys, threading, unittest, urllib.request
from werkzeug.serving import make_server

T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY, TOKEN = "sec-key", "tok-123"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CTF_FLAG"] = "flag{pb-test}"
        os.environ["CTF_PROXY_TOKEN"] = TOKEN
        sys.path.insert(0, T)
        cls.app = load("pb_app", os.path.join(T, "app.py"))
        cls.check = load("pb_check", os.path.join(T, "exploit", "check.py"))
        cls.proxy = load("pb_proxy", os.path.join(T, "proxy.py"))
        cls.srv = make_server("127.0.0.1", 0, cls.app.app)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.psrv = cls.proxy.serve(port=0, upstream_port=cls.srv.server_port, key=KEY, token=TOKEN)
        cls.url = f"http://127.0.0.1:{cls.psrv.server_address[1]}"
        threading.Thread(target=cls.psrv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.psrv.shutdown()
        cls.srv.shutdown()

    def _fix(self):
        """Emulate the student fix: the rule's tag comes from the proxy-provided role."""
        orig = self.app.engine.resource_view
        app = self.app

        def rv(kind, name, loc, tags, props, sub, rg):
            tags = dict(tags)
            tags["provisioned-by"] = app._caller_role()
            return orig(kind, name, loc, tags, props, sub, rg)
        self.app.engine.resource_view = rv
        return lambda: setattr(self.app.engine, "resource_view", orig)

    def test_vulnerable_exploitable(self):
        self.assertEqual(self.check.verdict(self.url, KEY)[0], "exploitable")
        self.assertEqual(self.check.main(["--url", self.url]), 0)

    def test_fixed_contained(self):
        undo = self._fix()
        try:
            self.assertEqual(self.check.verdict(self.url, KEY)[0], "contained")
            self.assertEqual(self.check.main(["--url", self.url, "--legit-key", KEY]), 1)
        finally:
            undo()

    def test_fixed_but_wrong_key_breaks(self):
        undo = self._fix()
        try:
            self.assertEqual(self.check.verdict(self.url, "other")[0], "broke-normal-use")
        finally:
            undo()

    def test_proxy_strips_client_headers(self):
        seen = {}
        orig = self.app._caller_role

        def spy():
            seen["role"] = orig()
            return seen["role"]
        self.app._caller_role = spy
        try:
            req = urllib.request.Request(self.url + "/api/provision", method="POST",
                                         data=json.dumps({"name": "n", "resourceGroup": "rg-sandbox"}).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "X-Caller-Role": "security-team", "X-Gateway-Token": "x"})
            urllib.request.urlopen(req).read()
        finally:
            self.app._caller_role = orig
        self.assertEqual(seen["role"], "developer")

    def test_app_ignores_role_without_token(self):
        c = self.app.app.test_client()
        r = c.post("/api/provision", json={"name": "n", "resourceGroup": "rg-sandbox"},
                   headers={"X-Caller-Role": "security-team"})
        self.assertEqual(r.status_code, 201)
        with self.app.app.test_request_context(headers={"X-Caller-Role": "security-team"}):
            self.assertEqual(self.app._caller_role(), "unknown")
        with self.app.app.test_request_context(headers={"X-Caller-Role": "security-team",
                                                        "X-Gateway-Token": TOKEN}):
            self.assertEqual(self.app._caller_role(), "security-team")

    def test_unreachable(self):
        self.assertEqual(self.check.main(["--url", "http://127.0.0.1:1"]), 2)


if __name__ == "__main__":
    unittest.main()
