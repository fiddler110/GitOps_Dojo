"""OpenTofu http state backend (tfstate.py) against a real server. python3 -B -m unittest test_tfstate"""
import base64
import http.client
import json
import unittest

import auth
import portal_api
import tfstate
from test_policy_api import A, B, FAC, SUB, Base


class TfState(Base):
    def basic(self, user):
        cid, sec = auth.app_id(user), auth.client_secret(self.app.auth.key, user)
        return "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode()

    def tf(self, method, name, body=b"", user=A, query="", auth_header=None):
        h = {"Authorization": auth_header if auth_header is not None else self.basic(user)} if (user or auth_header) else {}
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request(method, f"{tfstate.PREFIX}{name}{query}", body=body, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, data, r

    def test_auth_failures(self):
        for kw in ({"user": None}, {"auth_header": "Basic " + base64.b64encode(b"x:y").decode()},
                   {"auth_header": "Basic !!!"}, {"auth_header": "Bearer abc"}):
            s, _, r = self.tf("GET", "s", **kw)
            self.assertEqual(s, 401)
            self.assertEqual(r.getheader("WWW-Authenticate"), 'Basic realm="dojo-tfstate"')
        bad = "Basic " + base64.b64encode(f"{auth.app_id(A)}:wrong".encode()).decode()
        self.assertEqual(self.tf("POST", "s", b"{}", auth_header=bad)[0], 401)

    def test_bad_name(self):
        self.assertEqual(self.tf("GET", "Bad_Name")[0], 400)
        self.assertEqual(self.tf("GET", "a" * 41)[0], 400)

    def test_get_post_delete(self):
        self.assertEqual(self.tf("GET", "infra")[0], 404)
        self.assertEqual(self.tf("POST", "infra", b'{"v":1}')[0], 200)
        self.assertEqual(self.tf("GET", "infra")[:2], (200, b'{"v":1}'))
        self.assertEqual(self.tf("POST", "infra", b'{"v":2}')[0], 200)
        self.assertEqual(self.tf("GET", "infra")[1], b'{"v":2}')
        self.assertEqual(self.tf("DELETE", "infra")[0], 200)
        self.assertEqual(self.tf("GET", "infra")[0], 404)
        log = json.dumps(self.st.data["activity"])
        self.assertIn("Save state infra", log)
        self.assertIn("Delete state infra", log)
        self.assertNotIn('"v"', log)

    def test_lock_cycle(self):
        info = json.dumps({"ID": "L1", "Who": "me"}).encode()
        self.assertEqual(self.tf("LOCK", "infra", info)[0], 200)
        s, body, _ = self.tf("LOCK", "infra", json.dumps({"ID": "L2"}).encode())
        self.assertEqual((s, json.loads(body)["ID"]), (423, "L1"))
        self.assertEqual(self.tf("POST", "infra", b"{}")[0], 409)  # no ID
        self.assertEqual(self.tf("POST", "infra", b"{}", query="?ID=nope")[0], 409)
        self.assertEqual(self.tf("DELETE", "infra")[0], 409)
        self.assertEqual(self.tf("POST", "infra", b'{"ok":1}', query="?ID=L1")[0], 200)
        self.assertEqual(self.tf("UNLOCK", "infra", json.dumps({"ID": "L2"}).encode())[0], 409)
        self.assertEqual(self.tf("UNLOCK", "infra", info)[0], 200)
        self.assertEqual(self.tf("LOCK", "infra", info)[0], 200)

    def test_force_unlock(self):
        self.tf("LOCK", "infra", b'{"ID":"L1"}')
        self.assertEqual(self.tf("UNLOCK", "infra")[0], 200)
        self.assertEqual(self.tf("LOCK", "infra", b'{"ID":"L3"}')[0], 200)
        self.assertEqual(self.tf("UNLOCK", "infra", b'{"ID":"L3"}')[0], 200)
        self.assertEqual(self.tf("UNLOCK", "infra")[0], 200)  # nothing held

    def test_isolation(self):
        self.tf("POST", "infra", b'{"a":1}', user=A)
        self.assertEqual(self.tf("GET", "infra", user=B)[0], 404)
        self.tf("LOCK", "infra", b'{"ID":"L1"}', user=A)
        self.assertEqual(self.tf("LOCK", "infra", b'{"ID":"Lb"}', user=B)[0], 200)
        # a student cannot ask for another subscription
        self.assertEqual(self.tf("GET", "infra", user=B, query=f"?subscription={SUB[A]}")[0], 403)

    def test_facilitator_read(self):
        self.tf("POST", "infra", b'{"a":1}', user=A)
        self.assertEqual(self.tf("GET", "infra", user=FAC, query=f"?subscription={SUB[A]}")[:2], (200, b'{"a":1}'))
        self.assertEqual(self.tf("GET", "infra", user=FAC)[0], 404)
        self.assertEqual(self.tf("POST", "infra", b"{}", user=FAC, query=f"?subscription={SUB[A]}")[0], 403)

    def test_limits(self):
        self.assertEqual(self.tf("POST", "big", b"x" * (tfstate.MAX_BYTES + 1))[0], 413)
        self.assertEqual(self.tf("POST", "big", b"x" * tfstate.MAX_BYTES)[0], 200)
        for i in range(tfstate.MAX_STATES - 1):
            self.assertEqual(self.tf("POST", f"s{i}", b"{}")[0], 200)
        self.assertEqual(self.tf("POST", "extra", b"{}")[0], 507)
        self.assertEqual(self.tf("POST", "s0", b"{}")[0], 200)  # overwrite still fine
        self.assertEqual(self.tf("POST", "other", b"{}", user=B)[0], 200)

    def test_purge_and_reset(self):
        self.tf("POST", "infra", b"{}")
        self.tf("LOCK", "infra", b'{"ID":"L1"}')
        status, _h, raw = self.portal._purge("t", SUB[A])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["removed"].get("tfStates"), 1)
        self.assertEqual(self.tf("GET", "infra")[0], 404)
        self.assertEqual(self.tf("LOCK", "infra", b'{"ID":"L2"}')[0], 200)
        self.tf("POST", "infra", b"{}")
        self.portal.student_reset(A, "teardown")
        self.assertEqual(self.tf("GET", "infra")[0], 404)

    def test_other_routes_unaffected(self):
        self.assertEqual(self.arm("GET", "/subscriptions?api-version=2020-01-01")[0], 200)
        resp, _ = self.raw("POST", "/_dojo/reset/student01?phase=teardown", user=None)
        self.assertEqual(resp.status, 403)


if __name__ == "__main__":
    unittest.main()
