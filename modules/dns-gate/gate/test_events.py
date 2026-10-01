import hashlib
import hmac
import json
import unittest

import events


def patch(*rrsets):
    return json.dumps({"rrsets": list(rrsets)}).encode()


def rr(name, ip, ttl=300, change="REPLACE"):
    return {"name": name, "type": "A", "ttl": ttl, "changetype": change, "records": [{"content": ip}]}


class Summarise(unittest.TestCase):
    def test_first_push_then_add_change_remove(self):
        st = {}
        z = "amy.dojo.test."
        a = events.summarise(st, z, patch(rr("www." + z, "1.1.1.1"), rr(z, "1.1.1.1")))
        self.assertEqual((a["first"], a["created"], a["changed"], a["deleted"]), (True, 2, 0, 0))
        b = events.summarise(st, z, patch(rr("mail." + z, "2.2.2.2")))
        self.assertEqual((b["first"], b["created"]), (False, 1))
        c = events.summarise(st, z, patch(rr("www." + z, "9.9.9.9")))
        self.assertEqual((c["created"], c["changed"]), (0, 1))
        d = events.summarise(st, z, patch(rr("mail." + z, "2.2.2.2")))       # same again: nothing
        self.assertEqual((d["created"], d["changed"], d["deleted"]), (0, 0, 0))
        e = events.summarise(st, z, patch(rr("mail." + z, "", change="DELETE")))
        self.assertEqual(e["deleted"], 1)

    def test_min_ttl_and_garbage(self):
        st = {}
        s = events.summarise(st, "z.", patch(rr("a.z.", "1.1.1.1", ttl=30), rr("b.z.", "1.1.1.2", ttl=300)))
        self.assertEqual(s["min_ttl"], 30)
        self.assertIsNone(events.summarise(st, "z.", b"not json"))
        self.assertIsNone(events.summarise(st, "z.", b'{"rrsets": 3}'))


class Reporting(unittest.TestCase):
    def test_signed_post_and_off_switch(self):
        sent = []
        r = events.Reporter("http://x", "secret", send=lambda raw, sig: sent.append((raw, sig)))
        r.patched("amy", "amy.dojo.test", patch(rr("www.amy.dojo.test.", "1.1.1.1")), wait=True)
        r.refused("amy", "dojo.test.", wait=True)
        self.assertEqual(len(sent), 2)
        raw, sig = sent[0]
        self.assertEqual(sig, hmac.new(b"secret", raw, hashlib.sha256).hexdigest())
        doc = json.loads(raw)
        self.assertEqual((doc["source"], doc["event"], doc["user"], doc["zone"], doc["first"]),
                         ("dns", "zone_patch", "amy", "amy.dojo.test", True))
        self.assertEqual(json.loads(sent[1][0])["zone"], "dojo.test")
        off = events.Reporter("", "", send=lambda *a: sent.append(a))
        off.patched("amy", "z", patch(), wait=True)
        self.assertEqual(len(sent), 2)

    def test_a_failing_send_is_swallowed(self):
        def boom(raw, sig):
            raise OSError("down")
        events.Reporter("http://x", "s", send=boom).refused("amy", "z", wait=True)


if __name__ == "__main__":
    unittest.main()
