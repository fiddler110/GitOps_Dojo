"""adapter_client: signed, queued, best-effort posts to the achievements adapter."""
import hashlib
import hmac
import json
import threading
import unittest

from adapter_client import AdapterClient


class Posting(unittest.TestCase):
    def client(self, url="http://x", secret="s", **kw):
        sent = []
        kw.setdefault("send", lambda raw, sig: sent.append((raw, sig)))
        return AdapterClient(url, secret, "test", **kw), sent

    def test_signed_compact_body_with_its_source(self):
        c, sent = self.client()
        self.assertTrue(c.post({"event": "e", "user": "amy"}))
        c.flush()
        raw, sig = sent[0]
        self.assertEqual(raw, b'{"event":"e","user":"amy","source":"test"}')
        self.assertEqual(sig, hmac.new(b"s", raw, hashlib.sha256).hexdigest())

    def test_off_without_url_or_secret(self):
        for url, secret in (("", "s"), ("http://x", "")):
            c, sent = self.client(url, secret)
            self.assertFalse(c.enabled)
            self.assertFalse(c.post({"event": "e"}))
            c.flush()
            self.assertEqual(sent, [])
            self.assertIsNone(c._worker)

    def test_one_worker_for_every_event_in_order(self):
        c, sent = self.client()
        before = threading.active_count()
        for n in range(50):
            c.post({"n": n})
        c.flush()
        self.assertEqual([json.loads(raw)["n"] for raw, _ in sent], list(range(50)))
        self.assertLessEqual(threading.active_count(), before + 1)

    def test_a_failing_send_never_raises(self):
        def boom(raw, sig):
            raise OSError("down")
        c, _ = self.client(send=boom)
        c.post({"event": "e"})
        c.post({"event": "e"})
        c.flush()

    def test_a_full_queue_drops_without_blocking(self):
        gate, got = threading.Event(), []
        c, _ = self.client(send=lambda raw, sig: (gate.wait(5), got.append(raw)), size=2)
        results = [c.post({"n": n}) for n in range(6)]   # one in the worker's hands, two queued, the rest drop
        gate.set()
        c.flush()
        self.assertEqual(results.count(False), len(results) - len(got))
        self.assertIn(len(got), (2, 3))

    def test_a_doc_that_is_not_json_is_dropped(self):
        c, sent = self.client()
        self.assertFalse(c.post({"bad": object()}))
        c.flush()
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
