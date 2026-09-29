"""CloudAPI's per-student token bucket. Run from this directory:
    python3 -B -m unittest test_ratelimit
"""
import unittest

import server


class RateLimitTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.lim = server.RateLimit(3, 1, clock=lambda: self.now)

    def test_burst_then_refused_with_retry_after(self):
        self.assertEqual([self.lim.take("user:a") for _ in range(3)], [0, 0, 0])
        self.assertGreaterEqual(self.lim.take("user:a"), 1)

    def test_identities_are_separate(self):
        for _ in range(3):
            self.lim.take("user:a")
        self.assertEqual(self.lim.take("user:b"), 0)

    def test_refills(self):
        for _ in range(3):
            self.lim.take("user:a")
        self.now += 2
        self.assertEqual(self.lim.take("user:a"), 0)

    def test_shared_identities_get_a_wider_bucket(self):
        self.assertEqual([self.lim.take("ci:x", 5) for _ in range(15)], [0] * 15)
        self.assertGreaterEqual(self.lim.take("ci:x", 5), 1)

    def test_zero_is_off(self):
        off = server.RateLimit(0, 0)
        self.assertEqual([off.take("user:a") for _ in range(1000)], [0] * 1000)


if __name__ == "__main__":    unittest.main()
