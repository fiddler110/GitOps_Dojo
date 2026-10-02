"""cert-autorenewal pack: each wired item fires on the command or event the labs produce, and not on
lookalikes; the challenge verbs read a faked demo-app handshake."""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402
from fake_forgejo import FakeForgejo  # noqa: E402

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "cert-autorenewal")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
PLUGIN = os.path.join(HERE, "..", "plugins", "certs")
FORGEJO = os.path.join(HERE, "..", "achievements")   # file_contains, history_absent, the repo seeds
_spec = importlib.util.spec_from_file_location("certcheck", os.path.join(PLUGIN, "certcheck.py"))
certcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(certcheck)


def ids(ev):
    c = catalog.load(PACK, SHARED)[0]
    return mt.Matcher(lg.Ledger(c, lg.Config()).index).match(ev)


def sh(cmd, exit=0, **kw):
    return ids(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class CertsShell(unittest.TestCase):
    def test_lab1(self):
        self.assertIn("c1-root", sh("step certificate inspect /opt/step-ca-root/root_ca.crt --short"))
        self.assertNotIn("c1-root", sh("step certificate inspect /tmp/other.crt"))
        self.assertIn("c1-fingerprint", sh("step certificate fingerprint /opt/step-ca-root/root_ca.crt"))
        self.assertIn("c1-fingerprint", sh("openssl x509 -in a.crt -noout -fingerprint"))
        self.assertNotIn("c1-fingerprint", sh("openssl x509 -in a.crt -noout -dates"))
        self.assertIn("c1-trust", sh("step ca bootstrap --ca-url https://step-ca:9443 --fingerprint abc"))
        self.assertNotIn("c1-trust", sh("step ca bootstrap --ca-url x", 1))

    def test_lab2_3(self):
        self.assertIn("c2-vhost", sh('curl --resolve "amy.certs.dojo.test:80:10.0.0.5" "http://amy.certs.dojo.test/"'))
        self.assertNotIn("c2-vhost", sh('curl --resolve "amy.certs.dojo.test:443:10.0.0.5" "https://amy.certs.dojo.test/"'))
        self.assertIn("c2-issue", sh("certbot certonly --webroot -w /srv/webroot/amy/html -d amy.certs.dojo.test"))
        self.assertNotIn("c2-issue", sh("certbot certonly --webroot -d x", 1))
        self.assertNotIn("c2-issue", sh("certbot renew"))
        self.assertIn("c2-verify", sh("openssl s_client -connect demo-app:443 -servername amy.certs.dojo.test"))
        self.assertIn("c2-verify", sh('curl --resolve "amy.certs.dojo.test:443:10.0.0.5" --cacert r.crt "https://amy.certs.dojo.test/" -v'))
        self.assertIn("c3-issue", sh("acme.sh --issue --webroot /srv/webroot/amy/html -d amy.certs.dojo.test"))
        self.assertNotIn("c3-issue", sh("acme.sh --issue -d x", 2))
        self.assertIn("c3-read", sh("acme.sh --list"))
        self.assertIn("c3-read", sh("acme.sh --info -d x"))

    def test_lab4_5(self):
        self.assertIn("c4-script", sh("~/renew-and-reload.sh"))
        self.assertNotIn("c4-script", sh("./renew-and-reload.sh", 1))
        self.assertIn("c4-cron", sh("crontab -e"))
        self.assertIn("c4-cron", sh("crontab -l"))
        self.assertNotIn("c4-cron", sh("crontab -e", 1))
        self.assertIn("c5-start", sh("certbot certonly --manual --preferred-challenges dns-01 -d amy.certs.dojo.test", 1))
        self.assertNotIn("c5-start", sh("certbot certonly --webroot -d amy.certs.dojo.test"))
        self.assertIn("c5-done", sh("certbot certonly --manual --preferred-challenges dns-01 -d x"))
        self.assertNotIn("c5-done", sh("certbot certonly --manual --preferred-challenges dns-01 -d x", 1))

    def test_funny(self):
        self.assertIn("f-untrusted", sh("curl https://step-ca:9443/health", 60))
        self.assertNotIn("f-untrusted", sh("curl https://step-ca:9443/health", 0))
        self.assertIn("f-staging", sh("certbot certonly --dry-run -d x", 1))
        self.assertIn("f-staging", sh("certbot certonly --staging -d x"))
        self.assertNotIn("f-staging", sh("certbot certonly -d x"))
        self.assertIn("f-selfsigned", sh("openssl req -x509 -newkey rsa:2048 -nodes -keyout k -out c"))
        self.assertNotIn("f-selfsigned", sh("openssl req -new -key k -out c.csr"))

    def test_c1_tools_needs_certbot_first(self):
        ev = mt.shell_event(dict(cmd="acme.sh --issue --ca-bundle /opt/step-ca-root/root_ca.crt -d x", exit=0))
        c = catalog.load(PACK, SHARED)[0]
        m = mt.Matcher(lg.Ledger(c, lg.Config()).index)
        self.assertNotIn("c1-tools", m.match(ev))
        self.assertIn("c1-tools", m.match(ev, have=("c2-issue",)))
        ev = mt.shell_event(dict(cmd="acme.sh --issue -d x", exit=0))
        self.assertNotIn("c1-tools", m.match(ev, have=("c2-issue",)))

    def test_state_milestones(self):
        c = catalog.load(PACK, SHARED)[0]
        m = mt.Matcher(lg.Ledger(c, lg.Config()).index)
        pend = lambda have: {i for i, _ in m.pending_state(set(have))}   # noqa: E731
        self.assertEqual(pend(()), set())
        self.assertEqual(pend(("c2-issue",)), {"c2-install"})
        self.assertEqual(pend(("c2-install",)), {"c4-installs", "f-expired", "c2-https-only"})
        self.assertIn("c4-watch", pend(("c2-install", "c4-cron")))

    def test_dns_txt(self):
        ev = dict(source="dns", event="zone_patch", user="amy", zone="certs.dojo.test", first=False, created=1,
                  changed=0, deleted=0, min_ttl=60)
        self.assertIn("c5-txt", ids(mt.dns_event(ev)))
        self.assertNotIn("c5-txt", ids(mt.dns_event(dict(ev, zone="amy.dojo.test"))))
        self.assertNotIn("c5-txt", ids(mt.dns_event(dict(ev, event="api_refused"))))


def cert(serial, sans=("amy.certs.dojo.test",)):
    return {"serialNumber": serial, "subjectAltName": tuple(("DNS", s) for s in sans)}


KEY = "-----BEGIN PRIVATE KEY-----\nMIIEvQ...\n-----END PRIVATE KEY-----\n"
TLS = "\nserver {\n    listen 443 ssl;\n    server_name %s;\n}\n"
CRON = "* * * * * sh /home/amy/lab/cert-fuse/renew-and-reload.sh >> /home/amy/renew.log 2>&1\n"


class HttpBehaviour(unittest.TestCase):
    """served_redirect and served_hsts against real local servers: plain HTTP, and TLS with a throwaway CA."""
    @classmethod
    def setUpClass(cls):
        import http.server
        import ssl
        import subprocess
        import threading
        cls.tmp = tempfile.mkdtemp()
        key, crt = os.path.join(cls.tmp, "k.pem"), os.path.join(cls.tmp, "c.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt,
                        "-days", "1", "-subj", "/CN=www.amy.certs.dojo.test",
                        "-addext", "subjectAltName=DNS:www.amy.certs.dojo.test,DNS:api.amy.certs.dojo.test,"
                                  "DNS:members.amy.certs.dojo.test"],
                       check=True, capture_output=True)
        answers = cls.answers = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                tls = isinstance(self.connection, ssl.SSLSocket)
                if self.headers["Host"].startswith("members.") and tls:
                    # mTLS like nginx's `ssl_verify_client on`: 400 unless a verified client certificate came.
                    self.send_response(200 if self.connection.getpeercert() else 400)
                    self.end_headers()
                    return
                status, headers = answers[(self.headers["Host"], tls)]
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()

            def log_message(self, *a):
                pass
        cls.servers = []
        for tls in (False, True):
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
            if tls:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(crt, key)
                ctx.verify_mode = ssl.CERT_OPTIONAL      # a client certificate is asked for, not required
                ctx.load_verify_locations(crt)
                srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            cls.servers.append(srv)
        cls.env = {"CERTS_HTTP_ADDR": f"127.0.0.1:{cls.servers[0].server_port}",
                   "CERTS_TLS_ADDR": f"127.0.0.1:{cls.servers[1].server_port}", "CERTS_CA_ROOT": crt,
                   "CERTS_CLIENT_CERT": crt, "CERTS_CLIENT_KEY": key}

    @classmethod
    def tearDownClass(cls):
        for srv in cls.servers:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(cls.tmp)

    def setUp(self):
        from unittest import mock
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.answers.clear()

    def test_redirect_and_hsts_over_the_wire(self):
        w, a, ctx = "www.amy.certs.dojo.test", "api.amy.certs.dojo.test", {"user": "amy"}
        for h in (w, a):
            self.answers[(h, False)] = (301, {"Location": f"https://{h}/"})
            self.answers[(h, True)] = (200, {"Strict-Transport-Security": "max-age=86400"})
        self.assertEqual(certcheck.served_redirect(None, {"hosts": [w, a]}, ctx), (True, "ok"))
        self.assertEqual(certcheck.served_hsts(None, {"hosts": [w, a]}, ctx), (True, "ok"))
        self.answers[(a, False)] = (200, {})
        self.assertIn("answers 200", certcheck.served_redirect(None, {"hosts": [w, a]}, ctx)[1])
        self.answers[(a, True)] = (200, {})
        self.assertIn("no Strict-Transport-Security", certcheck.served_hsts(None, {"hosts": [a]}, ctx)[1])
        self.assertFalse(certcheck.served_hsts(None, {"hosts": ["www.bob.certs.dojo.test"]}, ctx)[0])

    def test_header_and_mtls_over_the_wire(self):
        a, m, ctx = "api.amy.certs.dojo.test", "members.amy.certs.dojo.test", {"user": "amy"}
        self.answers[(a, True)] = (200, {"X-Content-Type-Options": "nosniff"})
        args = {"hosts": [a], "name": "X-Content-Type-Options", "regex": "^nosniff$"}
        self.assertEqual(certcheck.served_header(None, args, ctx), (True, "ok"))
        self.assertIn("sends no", certcheck.served_header(None, dict(args, name="Content-Security-Policy"), ctx)[1])
        self.assertEqual(certcheck.served_mtls(None, {"host": m}, ctx), (True, "ok"))
        from unittest import mock
        with mock.patch.dict(os.environ, {"CERTS_CLIENT_CERT": ""}):
            with self.assertRaises(certcheck.Unavailable):
                certcheck.served_mtls(None, {"host": m}, ctx)
        self.answers[(a, True)] = (200, {})          # a site that lets anyone in
        self.assertIn("without a client certificate", certcheck.served_mtls(None, {"host": a}, ctx)[1])

    def test_untrusted_certificate(self):
        from unittest import mock
        other = os.path.join(self.tmp, "other.pem")
        import subprocess
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout",
                        os.path.join(self.tmp, "ok.pem"), "-out", other, "-days", "1", "-subj", "/CN=x"],
                       check=True, capture_output=True)
        self.answers[("www.amy.certs.dojo.test", True)] = (200, {"Strict-Transport-Security": "max-age=86400"})
        with mock.patch.dict(os.environ, {"CERTS_CA_ROOT": other}):
            ok, msg = certcheck.served_hsts(None, {"hosts": ["www.amy.certs.dojo.test"]}, {"user": "amy"})
        self.assertFalse(ok)
        self.assertIn("doesn't verify", msg)


class CertsChallenges(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(PACK, SHARED)[0]
        self.fj = FakeForgejo(["amy"])
        self.runner = challenges.Runner(challenges.load_plugins([PLUGIN, FORGEJO]),
                                        os.path.join(PACK, "achievements", "seeds"), self.fj, lambda: 0)
        self.mod = self.runner.verbs["served_cert"][1]
        self.orig, self.orig_head = self.mod._fetch, self.mod._head
        # Every site redirects permanently and sends HSTS, nosniff and a CSP unless a test says otherwise;
        # (host, tls, True) answers a request that presents the checker's client certificate.
        self.heads = {}
        self.mod._head = lambda host, tls, client=None: (
            self.heads.get((host, tls, True)) if client else None) or self.heads.get((host, tls)) or (
            (200, {"strict-transport-security": "max-age=86400", "x-content-type-options": "nosniff",
                   "content-security-policy": "default-src 'none'"}) if tls
            else (301, {"location": f"https://{host}/"}))

    def item(self, cid):
        return next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == cid)

    def seed(self, cid, files=None):
        """Start the challenge's repo for amy, then push `files` ({path: text, None deletes}) on main."""
        repo = self.runner.seed(self.item(cid), "amy")["repo"]
        if files:
            self.fj.commit(repo, "main", files, "amy")
        return repo

    def text(self, repo, path):
        return self.fj.file(repo, "main", path)

    def tearDown(self):
        self.mod._fetch = self.orig
        self.mod._head = self.orig_head

    def check(self, cid, served):
        ch = self.item(cid)

        def fetch(host):
            if isinstance(served.get(host), Exception):
                raise served[host]
            return served[host]
        self.mod._fetch = fetch
        return self.runner.verify(ch, "amy")

    def test_no_unknown_verbs(self):
        self.assertEqual(self.runner.unknown_verbs(self.cat), [])

    def test_c1(self):
        h, s = "amy.certs.dojo.test", "shop.amy.certs.dojo.test"
        repo = self.seed("c1")
        good = {h: cert("01"), s: cert("02", (s,))}
        res = self.check("c1", good)                       # served right, but the starter vhost has no TLS
        self.assertFalse(res["passed"])
        self.assertIn("shop.conf", res["message"])
        self.fj.commit(repo, "main", {"shop.conf": self.text(repo, "shop.conf") + TLS % s}, "amy")
        self.assertTrue(self.check("c1", good)["passed"])
        self.assertFalse(self.check("c1", {h: cert("01"), s: cert("01")})["passed"])
        self.assertFalse(self.check("c1", {h: cert("01"), s: certcheck.ssl.SSLCertVerificationError()})["passed"])

    def test_capstone(self):
        w, a = "www.amy.certs.dojo.test", "api.amy.certs.dojo.test"
        wild = cert("07", ("*.amy.certs.dojo.test",))
        repo = self.seed("capstone")
        self.assertIn("www.conf", self.check("capstone", {w: wild, a: wild})["message"])
        self.fj.commit(repo, "main", {"www.conf": self.text(repo, "www.conf") + TLS % w,
                                      "api.conf": self.text(repo, "api.conf") + TLS % a}, "amy")
        # The starter's certificate lines are still TODO (in the commented block); an uncommented TODO fails too.
        self.assertIn("www.conf", self.check("capstone", {w: wild, a: wild})["message"])
        todo = "\nserver {\n    listen 443 ssl;\n    ssl_certificate     TODO;\n}\n"
        self.fj.commit(repo, "main", {"www.conf": self.text(repo, "www.conf") + todo}, "amy")
        self.assertIn("www.conf", self.check("capstone", {w: wild, a: wild})["message"])
        real = "\n    ssl_certificate     /srv/webroot/amy/certs/wild/fullchain.pem;\n"
        self.fj.commit(repo, "main", {"www.conf": self.text(repo, "www.conf") + real,
                                      "api.conf": self.text(repo, "api.conf") + real}, "amy")
        self.assertIn("renew.cron", self.check("capstone", {w: wild, a: wild})["message"])
        self.fj.commit(repo, "main", {"renew.cron": self.text(repo, "renew.cron") + "* * * * * certbot renew -q\n"},
                       "amy")
        self.assertTrue(self.check("capstone", {w: wild, a: wild})["passed"])
        # The site's HTTP behaviour, each way it can be wrong.
        for bad, why in [(((a, False), (200, {})), "plain HTTP"),
                         (((a, False), (302, {"location": f"https://{a}/"})), "temporary"),
                         (((a, False), (301, {"location": f"https://{w}/"})), "not to https"),
                         (((w, True), (200, {})), "no Strict-Transport-Security"),
                         (((w, True), (200, {"strict-transport-security": "max-age=300"})), "under 86400"),
                         (((a, True), (200, {"strict-transport-security": "max-age=86400"})),
                          "no X-Content-Type-Options"),
                         (((a, True), (200, {"strict-transport-security": "max-age=86400",
                                             "x-content-type-options": "nosniff, nosniff"})), "isn't what"),
                         (((a, True), (200, {"strict-transport-security": "max-age=86400",
                                             "x-content-type-options": "nosniff"})), "no Content-Security-Policy")]:
            self.heads = dict([bad])
            self.assertIn(why, self.check("capstone", {w: wild, a: wild})["message"])
        self.heads = {(a, False): (308, {"location": f"https://{a}/x"}),
                      (w, True): (200, {"strict-transport-security": 'max-age="31536000"; includeSubDomains'})}
        self.assertTrue(self.check("capstone", {w: wild, a: wild})["passed"])
        self.assertFalse(self.check("capstone", {w: wild, a: cert("08", ("*.amy.certs.dojo.test",))})["passed"])
        self.assertFalse(self.check("capstone", {w: cert("07"), a: cert("07")})["passed"])

    def test_c3_members_only(self):
        m = "members.amy.certs.dojo.test"
        repo = self.seed("c3")
        self.mod._client_cert = lambda: ("client.crt", "client.key")
        self.addCleanup(lambda: delattr(self.mod, "_client_cert"))
        good = {m: cert("09", (m,))}
        self.heads = {(m, True): (200, {})}
        self.assertIn("without a client certificate", self.check("c3", good)["message"])
        self.heads = {(m, True): (400, {}), (m, True, True): (400, {})}
        self.assertIn("with a client certificate", self.check("c3", good)["message"])
        self.heads = {(m, True): (400, {}), (m, True, True): (200, {})}
        self.assertIn("members.conf", self.check("c3", good)["message"])    # the starter is all TODO
        self.fj.commit(repo, "main", {"members.conf": self.text(repo, "members.conf") +
                                      "server {\n    ssl_verify_client on;\n}\n"}, "amy")
        self.assertTrue(self.check("c3", good)["passed"])
        self.fj.commit(repo, "main", {"key.pem": KEY}, "amy")
        self.assertIn("private key", self.check("c3", good)["message"])

    def test_renewal_is_seen_as_serials_change(self):
        self.mod._fetch = lambda host: cert(self.serial)
        ctx = {"user": "amy"}
        args = {"host": "amy.certs.dojo.test", "key": "t"}
        self.serial = "01"
        self.assertFalse(self.mod.served_changed(None, args, ctx)[0])      # baseline
        self.assertFalse(self.mod.served_changed(None, args, ctx)[0])      # same
        self.serial = "02"
        self.assertTrue(self.mod.served_changed(None, args, ctx)[0])
        self.assertFalse(self.mod.served_changed(None, dict(args, times=3), ctx)[0])
        self.assertFalse(self.mod.served_changed(None, dict(args, key="other"), ctx)[0])   # own baseline
        self.assertFalse(self.mod.served_changed(None, args, {"user": "ben"})[0])           # not amy's host
        self.mod._seen.clear()

    def test_renews_watches_for_the_whole_window(self):
        self.serial, now = "01", [0]
        self.mod._fetch = lambda host: (_ for _ in ()).throw(self.serial) if isinstance(self.serial, Exception) \
            else cert(self.serial)
        args = {"host": "amy.certs.dojo.test", "minutes": 20, "renewals": 2}

        def look(after=0, user="amy"):
            now[0] += after
            return self.mod.served_renews(None, args, {"user": user, "now": now[0]})[0]
        self.assertFalse(look())                    # starts the watch
        self.serial = "02"
        self.assertFalse(look(8 * 60))
        self.serial = "03"
        self.assertFalse(look(8 * 60))              # renewed twice, but only 16 minutes
        self.assertTrue(look(4 * 60))
        self.serial = self.mod.ssl.SSLCertVerificationError()
        self.assertFalse(look(60))                  # lapsed: the watch starts again
        self.serial = "04"
        self.assertFalse(look(21 * 60))
        self.assertFalse(look(0, user="ben"))       # not ben's host
        self.mod._watch.clear()

    def test_c2_clears_itself_in_the_sweep(self):
        import store
        clock, d = Clock(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        calls = []

        def api(method, path, body=None, raw=False):
            calls.append(path)
            return self.fj(method, path, body, raw)

        def make_runner():
            return challenges.Runner(challenges.load_plugins([PLUGIN, FORGEJO]),
                                     os.path.join(PACK, "achievements", "seeds"), api, clock)
        runner = make_runner()
        repo = runner.seed(self.item("c2"), "amy")["repo"]
        st = store.Store(self.cat, lg.Config(), d, "secret", facilitator="boss", clock=clock)
        mod = runner.verbs["served_renews"][1]      # this runner's own copy of the plug-in
        self.serial = "01"
        mod._fetch = lambda host: cert(self.serial)
        calls.clear()
        self.assertFalse(st.check("amy", "c2", runner)["passed"])       # starts the watch
        self.assertEqual(st.watching, {"amy": ["c2"]})
        for serial in ("02", "03"):
            clock.t += 8 * 60
            self.serial = serial
            st.sweep_state(runner, gap=0)
        self.assertNotIn("c2", st.ledger.unlocked_ids("amy"))
        self.assertEqual(calls, [])     # watching reads the site only, never Forgejo
        # a restart: the service keeps the watch list, the plug-in's watch starts again
        st = store.Store(self.cat, lg.Config(), d, "secret", facilitator="boss", clock=clock)
        runner = make_runner()
        runner.verbs["served_renews"][1]._fetch = lambda host: cert(self.serial)
        self.assertEqual(st.watching, {"amy": ["c2"]})
        clock.t += 60
        self.assertEqual(st.sweep_state(runner, gap=0), 0)
        for serial in ("04", "05"):
            clock.t += 10 * 60
            self.serial = serial
            st.sweep_state(runner, gap=0)
        # The watch passed, but renew.cron on main is still only comments: not cleared, still watched.
        self.assertNotIn("c2", st.ledger.unlocked_ids("amy"))
        self.assertEqual(st.watching, {"amy": ["c2"]})
        self.assertTrue(calls)
        self.fj.commit(repo, "main", {"renew.cron": self.fj.file(repo, "main", "renew.cron") + CRON}, "amy")
        clock.t += 60
        self.serial = "06"
        st.sweep_state(runner, gap=0)
        self.assertIn("c2", st.ledger.unlocked_ids("amy"))
        self.assertEqual(st.watching, {"amy": []})
        self.assertTrue(st.checks[-1]["watched"])

    def test_no_key_anywhere_in_the_history(self):
        h, s = "amy.certs.dojo.test", "shop.amy.certs.dojo.test"
        good = {h: cert("01"), s: cert("02", (s,))}
        repo = self.seed("c1")
        self.fj.commit(repo, "main", {"shop.conf": self.text(repo, "shop.conf") + TLS % s}, "amy")
        self.assertTrue(self.check("c1", good)["passed"])
        self.fj.commit(repo, "main", {"certs/privkey.pem": KEY}, "amy")
        res = self.check("c1", good)
        self.assertFalse(res["passed"])
        self.assertIn("certs/privkey.pem", res["message"])
        self.fj.commit(repo, "main", {"certs/privkey.pem": None}, "amy")    # deleted: still in the history
        self.assertIn("history", self.check("c1", good)["message"])
        self.runner.seed(self.item("c1"), "amy", reset=True)                # reset rebuilds it clean
        self.fj.commit(repo, "main", {"shop.conf": self.text(repo, "shop.conf") + TLS % s}, "amy")
        self.assertTrue(self.check("c1", good)["passed"])
        # a key pasted into a file on another branch counts too (an EC key, any BEGIN ... PRIVATE KEY)
        self.fj.commit(repo, "try", {"notes.txt": "-----BEGIN EC PRIVATE KEY-----\nabc\n"}, "amy", start="main")
        self.assertFalse(self.check("c1", good)["passed"])

    def test_expired_cert(self):
        err = self.mod.ssl.SSLCertVerificationError()
        err.verify_message = "certificate has expired"
        host = "amy.certs.dojo.test"
        self.mod._fetch = lambda h: (_ for _ in ()).throw(err)
        self.assertTrue(self.mod.served_expired(None, {"host": host}, {"user": "amy"})[0])
        err.verify_message = "self-signed certificate"
        self.assertFalse(self.mod.served_expired(None, {"host": host}, {"user": "amy"})[0])
        self.mod._fetch = lambda h: cert("01")
        self.assertFalse(self.mod.served_expired(None, {"host": host}, {"user": "amy"})[0])
        self.assertFalse(self.mod.served_expired(None, {"host": "ben.certs.dojo.test"}, {"user": "amy"})[0])

    def test_unreachable_is_unavailable(self):
        self.mod._fetch = lambda host: (_ for _ in ()).throw(certcheck.Unavailable("down"))
        ch = next(c for c in self.cat["challenges"] if c["id"] == "c1")
        with self.assertRaises(Exception):
            self.runner.verify(ch, "amy")

    def test_a_check_never_reads_another_students_host(self):
        for host in ("ben.certs.dojo.test", "amy.ben.certs.dojo.test", "amy.certs.dojo.test.evil.test"):
            ok, _ = certcheck.served_cert(None, {"host": host}, {"user": "amy"})
            self.assertFalse(ok, host)
        ok, _ = certcheck.served_same(None, {"hosts": ["ben.certs.dojo.test"]}, {"user": "amy"})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
