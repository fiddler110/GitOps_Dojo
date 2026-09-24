"""Unit tests for gate.py's decision rules (host Python, no containers):
    cd workshops/dns-as-code/compose/dns-api && python3 -B -m unittest test_gate
"""
import os
import unittest

os.environ.setdefault("PDNS_UPSTREAM_KEY", "test-upstream")
import gate  # noqa: E402

Z = "/api/v1/servers/localhost/zones"


class DecideTest(unittest.TestCase):
    def test_reads_are_open(self):
        self.assertIsNone(gate.decide("GET", Z + "/dojo.test.", b"", False))
        self.assertIsNone(gate.decide("GET", Z, b"", False))

    def test_shared_zone_only_from_ci(self):
        for method in ("PATCH", "PUT", "DELETE"):
            for zid in ("dojo.test.", "dojo.test", "DOJO.TEST.", "dojo=2Etest.", "dojo%2Etest."):
                self.assertIsNotNone(gate.decide(method, f"{Z}/{zid}", b"", False), (method, zid))
                self.assertIsNone(gate.decide(method, f"{Z}/{zid}", b"", True), (method, zid))
        self.assertIsNotNone(gate.decide("PUT", Z + "/dojo.test./rectify", b"", False))
        self.assertIsNotNone(gate.decide("POST", Z, b'{"name": "dojo.test."}', False))
        self.assertIsNone(gate.decide("POST", Z, b'{"name": "dojo.test."}', True))

    def test_own_zone_open_to_students(self):
        self.assertIsNone(gate.decide("PATCH", Z + "/student07.dojo.test.", b"", False))
        self.assertIsNone(gate.decide("POST", Z, b'{"name": "student07.dojo.test."}', False))

    def test_zones_outside_the_lab_refused(self):
        for name in ("example.com.", "notdojo.test.", "test."):
            self.assertIsNotNone(gate.decide("POST", Z, ('{"name": "%s"}' % name).encode(), False))
            self.assertIsNotNone(gate.decide("PATCH", f"{Z}/{name}", b"", True))

    def test_non_zone_writes_refused_even_for_ci(self):
        for path in ("/api/v1/servers/localhost/config/x", "/api/v1/servers/localhost/tsigkeys", "/api/v1/servers"):
            self.assertIsNotNone(gate.decide("POST", path, b"", True))
        self.assertIsNotNone(gate.decide("POST", Z, b"not json", False))
        self.assertIsNotNone(gate.decide("POST", Z, b"[1]", False))


if __name__ == "__main__":
    unittest.main()
