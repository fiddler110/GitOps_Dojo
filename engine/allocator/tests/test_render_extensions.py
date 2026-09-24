"""Tests for render_extensions.py. Run in the allocator image (no host Python needed):

  podman run --rm --network none -v ./engine/allocator:/src:ro -w /src \
    gitopsdojo/allocator:local python3 -B -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import render_extensions as rx  # noqa: E402

SERVICES = {"allocator", "gateway", "cloud-api", "demo-app"}


def manifest(**kinds):
    return dict(version=1, **kinds)


def route(**over):
    r = {"id": "cloud-ui", "path": "/portal", "upstream": "cloud-api:8080", "gate": "identity"}
    r.update(over)
    return r


def run_merge(*datas):
    return rx.merge([(f"{i:02d}-test.json", d) for i, d in enumerate(datas)], SERVICES)


class LoadTests(unittest.TestCase):
    def load(self, data, raw=None):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(raw if raw is not None else json.dumps(data))
        self.addCleanup(os.unlink, f.name)
        return rx.load_manifest(f.name)

    def test_bad_json(self):
        with self.assertRaisesRegex(rx.ManifestError, "not valid JSON"):
            self.load(None, raw="{nope")

    def test_version_required(self):
        with self.assertRaisesRegex(rx.ManifestError, "version"):
            self.load({"cards": []})

    def test_unknown_top_level_key(self):
        with self.assertRaisesRegex(rx.ManifestError, "unknown keys"):
            self.load(manifest(caddy="respond 200"))

    def test_unknown_field(self):
        with self.assertRaisesRegex(rx.ManifestError, "unknown fields"):
            self.load(manifest(routes=[route(extra_caddy="x")]))

    def test_missing_field(self):
        with self.assertRaisesRegex(rx.ManifestError, "missing"):
            self.load(manifest(routes=[{"id": "x", "path": "/x", "gate": "shared"}]))

    def test_env_expansion(self):
        os.environ["RX_ZONE"] = "certs.dojo.test"
        self.addCleanup(os.environ.pop, "RX_ZONE")
        _, data = self.load(manifest(routes=[route(host="{user}.${RX_ZONE}")]))
        self.assertEqual(data["routes"][0]["host"], "{user}.certs.dojo.test")

    def test_env_unset_is_error(self):
        with self.assertRaisesRegex(rx.ManifestError, "RX_UNSET_VAR"):
            self.load(manifest(routes=[route(host="{user}.${RX_UNSET_VAR}")]))


class RouteRuleTests(unittest.TestCase):
    def bad(self, pattern, **over):
        with self.assertRaisesRegex(rx.ManifestError, pattern):
            run_merge(manifest(routes=[route(**over)]))

    def test_good_route(self):
        out, warnings = run_merge(manifest(routes=[route()]))
        self.assertEqual(out["routes"][0]["upstream"], "cloud-api:8080")
        self.assertEqual(warnings, [])

    def test_engine_prefix_collisions(self):
        for p in ("/admin", "/gitea", "/ide2", "/terminal", "/slides", "/demo"):
            self.bad("collides", path=p)

    def test_allocator_paths(self):
        self.bad("allocator", path="/assign")
        self.bad("allocator", path="/forgejo-login")

    def test_path_shape(self):
        for p in ("portal", "/Portal", "/por tal", "/a/b", "/x{y}", "//evil", "/"):
            self.bad("path must match", path=p)

    def test_overlap_between_manifests(self):
        with self.assertRaisesRegex(rx.ManifestError, "id 'cloud-ui' already used"):
            run_merge(manifest(routes=[route()]), manifest(routes=[route()]))
        with self.assertRaisesRegex(rx.ManifestError, "overlaps"):
            run_merge(manifest(routes=[route()]), manifest(routes=[route(id="other")]))

    def test_upstream(self):
        self.bad("not in this stack", upstream="nosuch:80")
        for u in ("cloud-api", "cloud-api:0", "cloud-api:70000", "cloud-api:80 {", "http://cloud-api:80"):
            self.bad("upstream must be", upstream=u)

    def test_gate(self):
        self.bad("gate must be", gate="none")

    def test_strip_prefix_bool(self):
        self.bad("strip_prefix", strip_prefix="yes")

    def test_host(self):
        self.bad("host needs", gate="shared", host="a.example.test")
        for h in ("{user}", "x{user}.test", "evil.test }", "{uid}.test", "UP.test"):
            self.bad("host must be", host=h)
        out, _ = run_merge(manifest(routes=[route(host="{user}.certs.dojo.test")]))
        self.assertEqual(out["routes"][0]["host"], "{user}.certs.dojo.test")

    def test_id_shape(self):
        for i in ("Cloud", "1cloud", "cloud_ui", "c" * 40):
            self.bad("id must match", id=i)


class CardTabStatusTests(unittest.TestCase):
    def card(self, **over):
        c = {"id": "cloud", "label": "Dojo Cloud", "href": "/cloud/", "icon": "cloud"}
        c.update(over)
        return c

    def test_card_href_must_be_local(self):
        for h in ("https://evil.test/", "//evil.test/", "javascript:alert(1)", "/a b", '/"x', "/\\x"):
            with self.assertRaisesRegex(rx.ManifestError, "same-origin"):
                run_merge(manifest(cards=[self.card(href=h)]))

    def test_card_icon_fixed_set(self):
        with self.assertRaisesRegex(rx.ManifestError, "icon"):
            run_merge(manifest(cards=[self.card(icon="<svg onload=x>")]))

    def test_text_limits(self):
        with self.assertRaisesRegex(rx.ManifestError, "longer"):
            run_merge(manifest(cards=[self.card(label="x" * 41)]))
        with self.assertRaisesRegex(rx.ManifestError, "control"):
            run_merge(manifest(cards=[self.card(label="a\nb")]))

    def test_builtin_tab_ids(self):
        for t in rx.ENGINE_TAB_IDS:
            with self.assertRaisesRegex(rx.ManifestError, "built-in"):
                run_merge(manifest(admin_tabs=[{"id": t, "label": "x", "src": "/x/"}]))

    def test_card_without_tab_warns(self):
        _, warnings = run_merge(manifest(cards=[self.card()]))
        self.assertEqual(len(warnings), 1)
        _, warnings = run_merge(manifest(cards=[self.card()],
                                         admin_tabs=[{"id": "cloud", "label": "Dojo Cloud", "src": "/cloud/#/p"}]))
        self.assertEqual(warnings, [])

    def test_status_checks(self):
        out, _ = run_merge(manifest(status_checks=[{"label": "Cloud", "url": "http://cloud-api:8080/readyz"}]))
        self.assertEqual(out["status_checks"][0]["url"], "http://cloud-api:8080/readyz")
        for u in ("http://nosuch:80/", "ftp://cloud-api/", "http://cloud-api:80/ x"):
            with self.assertRaises(rx.ManifestError):
                run_merge(manifest(status_checks=[{"label": "C", "url": u}]))


class CaddyTests(unittest.TestCase):
    def render(self, **over):
        out, _ = run_merge(manifest(routes=[route(**over)]))
        return rx.render_caddy(out["routes"])

    def test_identity_gate(self):
        c = self.render()
        self.assertIn("@ext_cloud_ui path /portal /portal/*", c)
        self.assertIn("uri /auth-check?route=cloud-ui", c)
        self.assertIn("header_up X-Auth-User {http.request.header.X-Dojo-User}", c)
        self.assertIn("header_up X-Gateway-Token {$GATEWAY_TOKEN}", c)
        self.assertIn("request_header -X-Dojo-User", c)
        self.assertIn("header_up -Authorization", c)
        self.assertNotIn("strip_prefix", c)
        self.assertNotIn("header_up Host", c)
        # client-supplied gate headers are removed before forward_auth copies them in
        self.assertLess(c.index("request_header -X-Dojo-User"), c.index("forward_auth"))

    def test_shared_gate_forwards_no_identity(self):
        c = self.render(gate="shared")
        self.assertNotIn("forward_auth", c)
        self.assertIn("header_up -X-Auth-User", c)
        self.assertIn("header_up -X-Gateway-Token", c)

    def test_strip_and_host(self):
        c = self.render(strip_prefix=True, host="{user}.certs.dojo.test")
        self.assertIn("uri strip_prefix /portal", c)
        self.assertIn("header_up Host {http.request.header.X-Dojo-Host}", c)
        self.assertNotIn("certs.dojo.test", c)  # the template stays in the allocator

    def test_braces_balanced(self):
        c = self.render(strip_prefix=True, host="{user}.certs.dojo.test")
        body = c.replace("{http.request.header.X-Dojo-User}", "").replace("{http.request.header.X-Dojo-Host}", "")
        body = body.replace("{http.auth.user.id}", "").replace("{$GATEWAY_TOKEN}", "")
        self.assertEqual(body.count("{"), body.count("}"))

    def test_empty(self):
        self.assertIn("no extension routes", rx.render_caddy([]))


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "in"))
            with open(os.path.join(d, "in", "01-workshop-x.json"), "w") as f:
                json.dump(manifest(routes=[route()]), f)
            rc = rx.main(["--in", os.path.join(d, "in"), "--out", d, "--services", " ".join(SERVICES)])
            self.assertEqual(rc, 0)
            with open(os.path.join(d, "allocator", "extensions.json")) as f:
                self.assertEqual(json.load(f)["routes"][0]["id"], "cloud-ui")
            self.assertTrue(os.path.exists(os.path.join(d, "gateway", "extensions.caddy")))

    def test_error_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "in"))
            with open(os.path.join(d, "in", "01-bad.json"), "w") as f:
                json.dump(manifest(routes=[route(path="/admin")]), f)
            rc = rx.main(["--in", os.path.join(d, "in"), "--out", d, "--services", "cloud-api"])
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(os.path.join(d, "gateway")))

    def test_no_manifests(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "in"))
            self.assertEqual(rx.main(["--in", os.path.join(d, "in"), "--out", d, "--services", "x"]), 0)


if __name__ == "__main__":
    unittest.main()
