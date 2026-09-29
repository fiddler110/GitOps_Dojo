"""Unit tests for gate.py (host Python + the openssl CLI, no containers):
    cd modules/dns-gate/gate && python3 -B -m unittest test_gate
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import unittest

import gate

Z = "/api/v1/servers/localhost/zones"
SEED = "0f" * 32
ENV = {
    "PDNS_UPSTREAM_KEY": "up", "STUDENT_PASSWORD_SEED": SEED, "FACILITATOR_USERNAME": "facilitator",
    "DNS_GATE_USER_PARENTS": "dojo.test certs.dojo.test", "DNS_GATE_SHARED_ZONES": "certs.dojo.test",
    "DNS_GATE_CI_ZONES": "dojo.test", "DNS_GATE_CI_REPO": "dns-team/dns-as-code",
    "PUBLIC_BASE_URL": "http://localhost:8080/",
}
CFG = gate.Config(ENV)


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Signer:
    """An RSA key made with openssl, as a JWKS entry and a JWT signer."""

    def __init__(self, tmp, kid):
        self.path = os.path.join(tmp, kid + ".pem")
        subprocess.run(["openssl", "genrsa", "-out", self.path, "2048"], check=True, capture_output=True)
        out = subprocess.run(["openssl", "rsa", "-in", self.path, "-noout", "-modulus"],
                             check=True, capture_output=True, text=True).stdout
        n = int(out.strip().split("=", 1)[1], 16)
        self.jwk = {"kty": "RSA", "kid": kid, "n": b64url(n.to_bytes(256, "big")), "e": "AQAB"}

    def token(self, **over):
        claims = {"iss": "http://localhost:8080/git/api/actions", "aud": "dns-api",
                  "repository": "dns-team/dns-as-code", "ref": "refs/heads/main", "event_name": "push",
                  "exp": time.time() + 300}
        claims.update(over)
        claims = {k: v for k, v in claims.items() if v is not None}
        head = b64url(json.dumps({"alg": "RS256", "kid": self.jwk["kid"]}).encode())
        body = b64url(json.dumps(claims).encode())
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", self.path], input=f"{head}.{body}".encode(),
                             check=True, capture_output=True).stdout
        return f"{head}.{body}.{b64url(sig)}"


class Keys:
    def __init__(self, keys):
        self.keys = keys

    def get(self, kid):
        return self.keys


def user(name):
    return gate.identify(gate.dns_key(SEED, name), CFG, Keys([]))


def patch(*names):
    return json.dumps({"rrsets": [{"name": n, "type": "TXT", "changetype": "REPLACE", "records": []}
                                  for n in names]}).encode()


class IdentifyTest(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(gate.identify("workshop-not-a-secret", CFG, Keys([])).kind, "reader")
        c = user("student01")
        self.assertEqual((c.kind, c.name), ("user", "student01"))
        key = gate.dns_key(SEED, "student01")
        for bad in ("", "student01", "student02." + key.split(".")[1], key[:-1] + "A", key + "x",
                    gate.dns_key("other-seed", "student01")):
            with self.assertRaises(ValueError, msg=bad):
                gate.identify(bad, CFG, Keys([]))

    def test_no_seed_no_user_keys(self):
        cfg = gate.Config(dict(ENV, STUDENT_PASSWORD_SEED=""))
        with self.assertRaises(ValueError):
            gate.identify(gate.dns_key("", "student01"), cfg, Keys([]))


@unittest.skipUnless(subprocess.run(["sh", "-c", "command -v openssl"], capture_output=True).returncode == 0,
                     "needs the openssl CLI")
class CiTokenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.signer = Signer(cls.tmp.name, "k1")
        cls.other = Signer(cls.tmp.name, "k2")
        cls.keys = Keys([cls.signer.jwk])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ci(self, token):
        return gate.identify(token, CFG, self.keys)

    def test_main_push_writes_the_shared_zone(self):
        c = self.ci(self.signer.token())
        self.assertTrue(c.ci_writes)
        self.assertIsNone(gate.decide("PATCH", Z + "/dojo.test.", b"", c, CFG))
        self.assertIsNone(gate.decide("GET", Z + "/dojo.test.", b"", c, CFG))
        # ...and nothing else.
        self.assertIsNotNone(gate.decide("PATCH", Z + "/student01.dojo.test.", b"", c, CFG))
        self.assertIsNotNone(gate.decide("POST", "/api/v1/servers/localhost/tsigkeys", b"", c, CFG))

    def test_other_runs_only_read(self):
        for over in ({"repository": "student01/dns-as-code"}, {"ref": "refs/heads/feature"},
                     {"ref": "refs/pull/3/head"}, {"event_name": "pull_request"}, {"event_name": None}):
            c = self.ci(self.signer.token(**over))
            self.assertFalse(c.ci_writes, over)
            self.assertIsNotNone(gate.decide("PATCH", Z + "/dojo.test.", b"", c, CFG), over)
            self.assertIsNone(gate.decide("GET", Z + "/dojo.test.", b"", c, CFG), over)

    def test_bad_tokens_refused(self):
        good = self.signer.token()
        head, body, sig = good.split(".")
        forged = b64url(json.dumps(dict(json.loads(base64.urlsafe_b64decode(body + "==")),
                                        repository="x/y")).encode())
        for token in (self.other.token(),                      # unknown key
                      f"{head}.{forged}.{sig}",                 # claims changed after signing
                      f"{head}.{body}.{sig[:-4]}AAAA",          # signature changed
                      self.signer.token(aud="openbao"),
                      self.signer.token(iss="http://evil/git/api/actions"),
                      self.signer.token(exp=time.time() - 120)):
            with self.assertRaises(ValueError):
                self.ci(token)
        alg_none = b64url(json.dumps({"alg": "none"}).encode()) + "." + body + "."
        with self.assertRaises(ValueError):
            self.ci("eyJ" + alg_none[3:])


class DecideTest(unittest.TestCase):
    def test_reads_are_open(self):
        for c in (gate.Caller("reader", "read-key"), user("student01")):
            self.assertIsNone(gate.decide("GET", Z + "/dojo.test.", b"", c, CFG))
            self.assertIsNone(gate.decide("GET", Z, b"", c, CFG))

    def test_read_key_never_writes(self):
        c = gate.Caller("reader", "read-key")
        self.assertIsNotNone(gate.decide("PATCH", Z + "/student01.dojo.test.", b"", c, CFG))
        self.assertIsNotNone(gate.decide("PATCH", Z + "/certs.dojo.test.", patch("x.certs.dojo.test."), c, CFG))

    def test_shared_zone_refused_to_accounts(self):
        c = user("student01")
        for method in ("PATCH", "PUT", "DELETE"):
            for zid in ("dojo.test.", "dojo.test", "DOJO.TEST.", "dojo=2Etest.", "dojo%2Etest."):
                self.assertIsNotNone(gate.decide(method, f"{Z}/{zid}", b"", c, CFG), (method, zid))
        self.assertIsNotNone(gate.decide("POST", Z, b'{"name": "dojo.test."}', c, CFG))
        self.assertIsNotNone(gate.decide("PATCH", Z + "/dojo.test.", b"", user("facilitator"), CFG))

    def test_own_zone_only(self):
        c = user("student01")
        self.assertIsNone(gate.decide("PATCH", Z + "/student01.dojo.test.", b"", c, CFG))
        self.assertIsNone(gate.decide("PATCH", Z + "/STUDENT01.dojo=2Etest.", b"", c, CFG))
        self.assertIsNone(gate.decide("PUT", Z + "/student01.dojo.test./rectify", b"", c, CFG))
        self.assertIsNone(gate.decide("POST", Z, b'{"name": "student01.dojo.test."}', c, CFG))
        self.assertIsNone(gate.decide("POST", Z, b'{"name": "lab.student01.dojo.test."}', c, CFG))
        for zone in ("student02.dojo.test.", "xstudent01.dojo.test.", "student01.dojo.test.evil."):
            self.assertIsNotNone(gate.decide("PATCH", f"{Z}/{zone}", b"", c, CFG), zone)
            self.assertIsNotNone(gate.decide("POST", Z, json.dumps({"name": zone}).encode(), c, CFG), zone)

    def test_shared_records_zone(self):
        c = user("student01")
        z = Z + "/certs.dojo.test."
        self.assertIsNone(gate.decide("PATCH", z, patch("_acme-challenge.student01.certs.dojo.test."), c, CFG))
        self.assertIsNone(gate.decide("PATCH", z, patch("student01.certs.dojo.test"), c, CFG))
        for body in (patch("_acme-challenge.student02.certs.dojo.test."),
                     patch("student01.certs.dojo.test.", "student02.certs.dojo.test."),
                     patch("certs.dojo.test."), b"{}", b'{"rrsets": []}', b'{"rrsets": [{"type": "A"}]}',
                     b"not json"):
            self.assertIsNotNone(gate.decide("PATCH", z, body, c, CFG), body)
        for method in ("PUT", "DELETE"):
            self.assertIsNotNone(gate.decide(method, z, patch("student01.certs.dojo.test."), c, CFG))
        self.assertIsNotNone(gate.decide("PUT", z + "/rectify", b"", c, CFG))

    def test_facilitator_owns_every_account_name(self):
        f = user("facilitator")
        self.assertIsNone(gate.decide("PATCH", Z + "/student07.dojo.test.", b"", f, CFG))
        self.assertIsNone(gate.decide("PATCH", Z + "/certs.dojo.test.",
                                      patch("_acme-challenge.student07.certs.dojo.test."), f, CFG))
        self.assertIsNotNone(gate.decide("PATCH", Z + "/certs.dojo.test.", patch("certs.dojo.test."), f, CFG))

    def test_zones_outside_the_lab_refused(self):
        c = user("student01")
        for name in ("example.com.", "notdojo.test.", "test."):
            self.assertIsNotNone(gate.decide("POST", Z, ('{"name": "%s"}' % name).encode(), c, CFG))
            self.assertIsNotNone(gate.decide("PATCH", f"{Z}/{name}", b"", c, CFG))

    def test_non_zone_writes_refused(self):
        c = user("facilitator")
        for path in ("/api/v1/servers/localhost/config/x", "/api/v1/servers/localhost/tsigkeys", "/api/v1/servers"):
            self.assertIsNotNone(gate.decide("POST", path, b"", c, CFG))
        self.assertIsNotNone(gate.decide("POST", Z, b"not json", c, CFG))
        self.assertIsNotNone(gate.decide("POST", Z, b"[1]", c, CFG))


if __name__ == "__main__":
    unittest.main()
