"""Unit tests for apphost.py that need no stack: JWT signing and checking,
the deploy claims, and what the app proxy passes on. Run:
    python3 -B -m unittest discover -s workshops/vault-fundamentals/compose/app-host/tests
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import apphost as P  # noqa: E402


def cfg(**env):
    base = {"STUDENT_COUNT": "3", "PUBLIC_BASE_URL": "http://localhost:8080", "GATEWAY_TOKEN": "t"}
    base.update(env)
    return P.Config(base)


def claims(**over):
    c = {"iss": "http://localhost:8080/git/api/actions", "aud": "app-host", "exp": time.time() + 300,
         "repository": "student01/vault-fundamentals", "ref": "refs/heads/main", "sha": "abc", "actor": "student01"}
    c.update(over)
    return c


class JWT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.key = os.path.join(cls.tmp.name, "key.pem")
        cls.other = os.path.join(cls.tmp.name, "other.pem")
        for k in (cls.key, cls.other):
            subprocess.run(["openssl", "genrsa", "-out", k, "2048"], check=True, capture_output=True)

    def test_round_trip(self):
        jwk = P.public_jwk(self.key)
        token = P.sign_jwt({"sub": "slot:student01"}, self.key, kid=jwk["kid"])
        self.assertEqual(P.verify_rs256(token, [jwk])["sub"], "slot:student01")

    def test_pem_matches_openssl(self):
        jwk = P.public_jwk(self.key)
        pem = P.rsa_public_pem(int.from_bytes(P.b64url_decode(jwk["n"]), "big"), 65537)
        want = subprocess.run(["openssl", "rsa", "-in", self.key, "-pubout"], capture_output=True, text=True).stdout
        self.assertEqual(pem, want)

    def test_other_key_refused(self):
        token = P.sign_jwt({"sub": "x"}, self.other)
        with self.assertRaisesRegex(ValueError, "bad signature"):
            P.verify_rs256(token, [P.public_jwk(self.key)])

    def test_tampered_claims_refused(self):
        jwk = P.public_jwk(self.key)
        h, _c, s = P.sign_jwt({"repository": "student01/vault-fundamentals"}, self.key).split(".")
        forged = P.b64url(json.dumps({"repository": "student02/vault-fundamentals"}).encode())
        with self.assertRaises(ValueError):
            P.verify_rs256(f"{h}.{forged}.{s}", [jwk])

    def test_alg_none_refused(self):
        h = P.b64url(json.dumps({"alg": "none"}).encode())
        c = P.b64url(json.dumps({"sub": "x"}).encode())
        with self.assertRaisesRegex(ValueError, "RS256"):
            P.verify_rs256(f"{h}.{c}.", [P.public_jwk(self.key)])

    def test_unknown_kid_refused(self):
        token = P.sign_jwt({"sub": "x"}, self.key, kid="nope")
        with self.assertRaisesRegex(ValueError, "kid"):
            P.verify_rs256(token, [P.public_jwk(self.key)])


class DeployClaims(unittest.TestCase):
    def test_main_of_own_repo(self):
        self.assertEqual(P.check_deploy_claims(claims(), cfg()), "student01")

    def test_audience_list(self):
        self.assertEqual(P.check_deploy_claims(claims(aud=["x", "app-host"]), cfg()), "student01")

    def refused(self, pattern, **over):
        with self.assertRaisesRegex(ValueError, pattern):
            P.check_deploy_claims(claims(**over), cfg())

    def test_branch(self):
        self.refused("only main", ref="refs/heads/try")

    def test_other_repo(self):
        self.refused("only student01/vault-fundamentals", repository="student01/other")

    def test_not_a_student(self):
        self.refused("no slot", repository="platform-team/vault-fundamentals")

    def test_wrong_audience(self):
        self.refused("audience", aud="openbao")

    def test_wrong_issuer(self):
        self.refused("issuer", iss="http://evil/git/api/actions")

    def test_expired(self):
        self.refused("expired", exp=time.time() - 120)


class Proxy(unittest.TestCase):
    def test_request_headers(self):
        kept = P.app_request_headers({"Cookie": "a", "Authorization": "Basic x", "X-Gateway-Token": "t",
                                      "X-Auth-User": "student01", "Accept": "text/html", "User-Agent": "u"})
        self.assertEqual(kept, {"Accept": "text/html", "User-Agent": "u"})

    def test_response_headers(self):
        out = P.app_response_headers([("Set-Cookie", "s=1"), ("Content-Security-Policy", "script-src *"),
                                      ("Content-Type", "text/html"), ("X-Frame-Options", "DENY")])
        names = [k.lower() for k, _ in out]
        self.assertNotIn("set-cookie", names)
        self.assertIn(("Content-Security-Policy", P.APP_CSP), out)
        self.assertEqual(names.count("content-security-policy"), 1)
        self.assertIn(("Content-Type", "text/html"), out)


if __name__ == "__main__":
    unittest.main()
