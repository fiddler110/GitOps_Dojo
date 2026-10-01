"""cert-autorenewal pack: each wired item fires on the command or event the labs produce, and not on
lookalikes; the challenge verbs read a faked demo-app handshake."""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "cert-autorenewal")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
PLUGIN = os.path.join(HERE, "..", "plugins", "certs")
_spec = importlib.util.spec_from_file_location("certcheck", os.path.join(PLUGIN, "certcheck.py"))
certcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(certcheck)


def ids(ev):
    c = catalog.load(PACK, SHARED)[0]
    return mt.Matcher(lg.Ledger(c, lg.Config()).index).match(ev)


def sh(cmd, exit=0, **kw):
    return ids(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)))


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
        self.assertEqual(pend(("c2-install",)), {"c4-installs", "f-expired"})
        self.assertIn("c4-watch", pend(("c2-install", "c4-cron")))

    def test_dns_txt(self):
        ev = dict(source="dns", event="zone_patch", user="amy", zone="certs.dojo.test", first=False, created=1,
                  changed=0, deleted=0, min_ttl=60)
        self.assertIn("c5-txt", ids(mt.dns_event(ev)))
        self.assertNotIn("c5-txt", ids(mt.dns_event(dict(ev, zone="amy.dojo.test"))))
        self.assertNotIn("c5-txt", ids(mt.dns_event(dict(ev, event="api_refused"))))


def cert(serial, sans=("amy.certs.dojo.test",)):
    return {"serialNumber": serial, "subjectAltName": tuple(("DNS", s) for s in sans)}


class CertsChallenges(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(PACK, SHARED)[0]
        self.runner = challenges.Runner(challenges.load_plugins([PLUGIN]), os.path.join(PACK, "achievements", "seeds"),
                                        None, lambda: 0)
        self.mod = self.runner.verbs["served_cert"][1]
        self.orig = self.mod._fetch

    def tearDown(self):
        self.mod._fetch = self.orig

    def check(self, cid, served):
        ch = next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == cid)

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
        self.assertTrue(self.check("c1", {h: cert("01"), s: cert("02", (s,))})["passed"])
        self.assertFalse(self.check("c1", {h: cert("01"), s: cert("01")})["passed"])
        self.assertFalse(self.check("c1", {h: cert("01"), s: certcheck.ssl.SSLCertVerificationError()})["passed"])

    def test_capstone(self):
        w, a = "www.amy.certs.dojo.test", "api.amy.certs.dojo.test"
        wild = cert("07", ("*.amy.certs.dojo.test",))
        self.assertTrue(self.check("capstone", {w: wild, a: wild})["passed"])
        self.assertFalse(self.check("capstone", {w: wild, a: cert("08", ("*.amy.certs.dojo.test",))})["passed"])
        self.assertFalse(self.check("capstone", {w: cert("07"), a: cert("07")})["passed"])

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
