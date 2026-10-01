import base64
import unittest

import seed

TEXT = 'A("www", "1"),\n\tA("mail", "2"),\n'
CFG = {"repo": "o/r", "file": "dnsconfig.js", "before": '\tA("mail", "2"),', "line": '\tA("status", "3"),',
       "title": "T", "body": "B"}


class Fake:
    def __init__(self, text=TEXT):
        self.text, self.calls = text, []

    def __call__(self, method, path, body=None, raw=False):
        self.calls.append((method, path.split("?")[0], body))
        if method == "GET":
            return 200, {"content": base64.b64encode(self.text.encode()).decode(), "sha": "abc"}
        if path.endswith("/branches"):
            return 201, {}
        if "/contents/" in path:
            return 200, {}
        return 201, {"number": 7}


class SeedTests(unittest.TestCase):
    def test_opens_once_with_one_line_added(self):
        api = Fake()
        s = seed.Seeder(CFG, api)
        self.assertTrue(s.seed())
        put = [c for c in api.calls if c[0] == "PUT"][0][2]
        self.assertEqual(base64.b64decode(put["content"]).decode(), 'A("www", "1"),\n\tA("status", "3"),\n\tA("mail", "2"),\n')
        self.assertEqual(put["branch"], "dns-bot/add-status")
        n = len(api.calls)
        self.assertFalse(s.seed())
        self.assertEqual(len(api.calls), n)

    def test_never_reopens_after_restart(self):
        import os, tempfile
        path = os.path.join(tempfile.mkdtemp(), "seed.json")
        self.assertTrue(seed.Seeder(CFG, Fake(), path).seed())
        api = Fake()
        self.assertFalse(seed.Seeder(CFG, api, path).seed())
        self.assertEqual(api.calls, [])

    def test_unexpected_file_is_left_alone(self):
        api = Fake("something else\n")
        self.assertFalse(seed.Seeder(CFG, api).seed())
        self.assertEqual([c for c in api.calls if c[0] != "GET"], [])


if __name__ == "__main__":
    unittest.main()
