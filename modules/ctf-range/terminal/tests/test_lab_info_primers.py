"""Lab Info primers must teach a tool on a made-up target, never with a lab's own values.

Run: python3 -B -m unittest discover -s modules/ctf-range/terminal/tests

Three mechanical checks, so no person has to read every primer for leaked payloads (plan 13.3):
  1. a payload-like string literal from any target's exploit/solve.py or check.py appears in a primer;
  2. a route that exists in exactly one target's app appears in a primer;
  3. a rendered flag (flag{name-hex}) appears in a primer.
A hit is either a lab defect (reword the primer with a made-up value) or generic vocabulary, which goes in
ALLOWED with the reason.
"""
import ast
import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RANGE = os.path.dirname(os.path.dirname(HERE))
PRIMERS = sorted(glob.glob(os.path.join(RANGE, "terminal", "content", "lab-info", "*.md")))
TARGETS = os.path.join(RANGE, "targets")

# Generic HTTP/web vocabulary a primer legitimately uses; each is common to many targets, not one lab's secret.
ALLOWED = {
    "/login": "every web app has one; primers use it as the example form",
    "/admin": "generic example path in the Authorization header primer",
    "Content-Type": "HTTP header name",
    "application/json": "media type",
}

PAYLOAD_SHAPE = re.compile(r"[/=%;|(){}$'\"\\0-9<>*-]")
PLAIN_WORDS = re.compile(r"[a-z]+(-[a-z]+)+")  # kebab names such as verdicts and target names
ROUTE = re.compile(r"""@\w+\.(?:route|get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _primers():
    return {os.path.basename(p): _read(p) for p in PRIMERS}


def _exploit_literals():
    """{literal: {target, ...}} for payload-like strings in every solve.py / check.py."""
    out = {}
    paths = glob.glob(os.path.join(TARGETS, "*", "exploit", "solve.py")) + \
        glob.glob(os.path.join(TARGETS, "*", "exploit", "check.py"))
    for path in paths:
        target = os.path.basename(os.path.dirname(os.path.dirname(path)))
        for node in ast.walk(ast.parse(_read(path))):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            s = node.value.strip()
            if len(s) >= 5 and " " not in s and PAYLOAD_SHAPE.search(s) and not PLAIN_WORDS.fullmatch(s):
                out.setdefault(s, set()).add(target)
    return out


def _single_target_routes():
    seen = {}
    for path in glob.glob(os.path.join(TARGETS, "*", "app.py")):
        target = os.path.basename(os.path.dirname(path))
        for route in ROUTE.findall(_read(path)):
            route = re.sub(r"<[^>]+>", "", route).rstrip("/")  # /users/<id> -> /users
            if len(route) > 1:
                seen.setdefault(route, set()).add(target)
    return {r: t for r, t in seen.items() if len(t) == 1}


class PrimerLeakTests(unittest.TestCase):
    def test_primers_found(self):
        self.assertGreaterEqual(len(PRIMERS), 10, "lab-info primers not found; path moved?")

    def test_no_exploit_literal_in_primers(self):
        primers, bad = _primers(), []
        for literal, targets in _exploit_literals().items():
            if literal in ALLOWED:
                continue
            for name, text in primers.items():
                if literal in text:
                    bad.append(f"{name}: {literal!r} (from {', '.join(sorted(targets))})")
        self.assertEqual(bad, [], "primer uses a lab's own payload/value; use a made-up one or add to ALLOWED")

    def test_no_single_target_route_in_primers(self):
        primers, bad = _primers(), []
        for route, targets in _single_target_routes().items():
            if route in ALLOWED:
                continue
            pat = re.compile(re.escape(route) + r"(?![\w-])")
            for name, text in primers.items():
                if pat.search(text):
                    bad.append(f"{name}: {route} (only in {next(iter(targets))})")
        self.assertEqual(bad, [], "primer names a route that belongs to one lab; use a made-up path")

    def test_no_rendered_flag_in_primers(self):
        rendered = re.compile(r"flag\{[a-z][a-z0-9-]*-[0-9a-f]{6,}\}")
        bad = [n for n, t in _primers().items() if rendered.search(t)]
        self.assertEqual(bad, [])

    def test_detector_catches_a_planted_leak(self):
        """Guard the guard: the literal extractor must see the known mass-assignment payload shape."""
        self.assertTrue(any("users/me" in k for k in _exploit_literals()), "extractor found no solve.py literals")


if __name__ == "__main__":
    unittest.main()
