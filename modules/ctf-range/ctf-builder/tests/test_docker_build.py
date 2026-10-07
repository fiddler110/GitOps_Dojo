"""Unit tests for docker_build's pure request-shape functions:

    python3 -B -m unittest discover -s modules/ctf-range/ctf-builder/tests -p 'test_*.py'

No daemon needed, same scope as ../ctf-controller/tests/test_executor.py:
image_tag_for / build_query / push_query / stream_had_error are pure.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import docker_build as d  # noqa: E402


class TestTagging(unittest.TestCase):
    def test_repo_ref(self):
        self.assertEqual(d.repo_ref("registry:5000"),
                         "registry:5000/ctf-customer-portal")

    def test_image_tag_for_ties_user_to_tag(self):
        tag = d.image_tag_for("student01", "registry:5000")
        self.assertEqual(tag, "registry:5000/ctf-customer-portal:student01")

    def test_matches_controller_allowed_image_prefix(self):
        # ctf-controller's docker_api.allowed_image checks
        # `image.startswith(registry_prefix + "/")` — confirm our tag does.
        prefix = "registry:5000"
        tag = d.image_tag_for("student02", prefix)
        self.assertTrue(tag.startswith(prefix + "/"))


class TestQueries(unittest.TestCase):
    def test_build_query_has_tag_and_no_pull(self):
        q = d.build_query("registry:5000/ctf-customer-portal:student01")
        self.assertIn("t=registry%3A5000%2Fctf-customer-portal%3Astudent01", q)
        self.assertIn("pull=0", q)
        self.assertIn("rm=1", q)
        self.assertIn("forcerm=1", q)

    def test_push_query_is_just_the_tag(self):
        self.assertEqual(d.push_query("student01"), "tag=student01")


class TestStreamHadError(unittest.TestCase):
    def test_clean_stream_is_ok(self):
        raw = b'{"stream":"Step 1/5 : FROM python:3.12-slim\\n"}\n{"stream":"Successfully built abc123\\n"}\n'
        self.assertFalse(d.stream_had_error(raw))

    def test_error_key_detected(self):
        raw = b'{"stream":"Step 1/5\\n"}\n{"errorDetail":{"message":"no such file"},"error":"no such file"}\n'
        self.assertTrue(d.stream_had_error(raw))

    def test_error_detail_only_detected(self):
        raw = b'{"errorDetail":{"message":"boom"}}\n'
        self.assertTrue(d.stream_had_error(raw))

    def test_blank_and_garbage_lines_ignored(self):
        raw = b'\n   \nnot json at all\n{"stream":"ok\\n"}\n'
        self.assertFalse(d.stream_had_error(raw))

    def test_empty_body_is_ok(self):
        self.assertFalse(d.stream_had_error(b""))


if __name__ == "__main__":
    unittest.main()
