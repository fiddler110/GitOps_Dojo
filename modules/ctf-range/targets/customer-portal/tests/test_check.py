import importlib.util, os, sys, tempfile, threading, unittest
from werkzeug.serving import make_server

T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["CTF_DB_PATH"] = os.path.join(cls.tmp, "p.db")
        os.environ["CTF_FLAG"] = "flag{cp-test}"
        sys.path.insert(0, T)
        seed = load("cp_seed", os.path.join(T, "seed.py"))
        seed.seed(os.environ["CTF_DB_PATH"])
        cls.app = load("cp_app", os.path.join(T, "app.py"))
        cls.check = load("cp_check", os.path.join(T, "exploit", "check.py"))
        cls.srv = make_server("127.0.0.1", 0, cls.app.app)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_vulnerable_is_exploitable(self):
        self.assertEqual(self.check.verdict(self.url)[0], "exploitable")
        self.assertEqual(self.check.main(["--url", self.url]), 0)

    def test_fixed_is_contained(self):
        orig = self.app._connect

        class Conn:
            def __init__(s, c): s.c = c
            def execute(s, sql, params=()):
                if "LIKE '%" in sql:  # the string-built query: emulate the fix
                    q = sql.split("LIKE '%", 1)[1].rsplit("%'", 1)[0]
                    return s.c.execute("SELECT id, name, email, password, account_id, tier FROM customers "
                                       "WHERE name LIKE ?", (f"%{q}%",))
                return s.c.execute(sql, params)
            def close(s): s.c.close()
        self.app._connect = lambda: Conn(orig())
        try:
            self.assertEqual(self.check.verdict(self.url)[0], "contained")
        finally:
            self.app._connect = orig

    def test_broken_and_unreachable(self):
        orig = self.app._connect
        self.app._connect = lambda: (_ for _ in ()).throw(RuntimeError("x"))
        try:
            self.assertEqual(self.check.verdict(self.url)[0], "broke-normal-use")
        finally:
            self.app._connect = orig
        self.assertEqual(self.check.verdict("http://127.0.0.1:1")[0], "unreachable")
        self.assertEqual(self.check.main(["--url", "http://127.0.0.1:1"]), 2)


if __name__ == "__main__":
    unittest.main()
