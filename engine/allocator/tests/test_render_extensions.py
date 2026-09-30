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
MASTER = "m" * 64


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

    def test_widget_fields(self):
        for item in ({"id": "w"}, {"id": "w", "src": "/a/", "height": "9999px"}):  # src required; no raw values
            with self.subTest(item=item), self.assertRaises(rx.ManifestError):
                self.load(manifest(widgets=[item]))

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
        for p in ("/admin", "/gitea", "/ide2", "/terminal", "/slides"):
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

    def test_workspace_path_is_reserved(self):
        for path in ("/workspace", "/workspace-x"):
            with self.subTest(path=path), self.assertRaises(rx.ManifestError):
                run_merge(manifest(routes=[route(path=path)]))

    def test_widget(self):
        merged, _ = run_merge(manifest(widgets=[{"id": "score", "src": "/achievements/widget/"}]))
        self.assertEqual(merged["widgets"], [{"source": "00-test.json", "id": "score",
                                              "src": "/achievements/widget/", "size": "small"}])
        merged, _ = run_merge(manifest(widgets=[{"id": "score", "src": "/a/", "size": "large"}]))
        self.assertEqual(merged["widgets"][0]["size"], "large")

    def test_widget_checks(self):
        bad = [
            {"id": "w", "src": "https://evil.example/"},   # not same-origin
            {"id": "w", "src": "//evil.example/"},         # scheme-relative
            {"id": "w", "src": "/a/", "size": "huge"},     # not a fixed size
            {"id": "Bad Id", "src": "/a/"},
        ]
        for w in bad:
            with self.subTest(w=w), self.assertRaises(rx.ManifestError):
                run_merge(manifest(widgets=[w]))

    def test_duplicate_widget_id(self):
        with self.assertRaises(rx.ManifestError):
            run_merge(manifest(widgets=[{"id": "w", "src": "/a/"}, {"id": "w", "src": "/b/"}]))

    def test_scripts(self):
        merged, _ = run_merge(manifest(scripts=[{"id": "toasts", "src": "/achievements/toast.js"}]))
        self.assertEqual(merged["scripts"], [{"source": "00-test.json", "id": "toasts", "src": "/achievements/toast.js"}])

    def test_script_checks(self):
        for bad in ({"id": "s", "src": "https://evil.example/x.js"}, {"id": "s", "src": "//evil.example/x.js"},
                    {"id": "S s", "src": "/a.js"}):
            with self.subTest(bad=bad), self.assertRaises(rx.ManifestError):
                run_merge(manifest(scripts=[bad]))
        with self.assertRaises(rx.ManifestError):
            run_merge(manifest(scripts=[{"id": "s", "src": "/a.js"}, {"id": "s", "src": "/b.js"}]))

    def test_status_checks(self):
        out, _ = run_merge(manifest(status_checks=[{"label": "Cloud", "url": "http://cloud-api:8080/readyz"}]))
        self.assertEqual(out["status_checks"][0]["url"], "http://cloud-api:8080/readyz")
        for u in ("http://nosuch:80/", "ftp://cloud-api/", "http://cloud-api:80/ x"):
            with self.assertRaises(rx.ManifestError):
                run_merge(manifest(status_checks=[{"label": "C", "url": u}]))


class CaddyTests(unittest.TestCase):
    def render(self, **over):
        out, _ = run_merge(manifest(routes=[route(**over)]))
        return rx.render_caddy(out["routes"], rx.upstream_tokens(out["routes"], MASTER))

    def test_identity_gate(self):
        c = self.render()
        self.assertIn("@ext_cloud_ui path /portal /portal/*", c)
        self.assertIn("uri /auth-check?route=cloud-ui", c)
        self.assertIn("header_up X-Auth-User {http.request.header.X-Dojo-User}", c)
        # forward_auth to the allocator keeps the shared token; the upstream gets its own
        self.assertEqual(c.count("header_up X-Gateway-Token {$GATEWAY_TOKEN}"), 1)
        self.assertLess(c.index("{$GATEWAY_TOKEN}"), c.index("reverse_proxy"))
        own = rx.upstream_tokens([{"upstream": "cloud-api:8080", "gate": "identity"}], MASTER)["cloud-api"]
        self.assertIn(f"header_up X-Gateway-Token {own}", c)
        self.assertNotIn(MASTER, c)
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
        body = body.replace("{http.request.header.X-Session-User}", "").replace("{$GATEWAY_TOKEN}", "")
        body = body.replace("{user}", "")
        self.assertEqual(body.count("{"), body.count("}"))

    def test_empty(self):
        self.assertIn("no extension routes", rx.render_caddy([]))


class TokenTests(unittest.TestCase):
    def routes(self, *pairs):
        return [{"id": f"r{i}", "upstream": u, "gate": g} for i, (u, g) in enumerate(pairs)]

    def test_one_token_per_identity_upstream(self):
        t = rx.upstream_tokens(self.routes(("cloud-api:8080", "identity"), ("app-host:8080", "facilitator"),
                                           ("zone-viewer:8080", "shared")), MASTER)
        self.assertEqual(set(t), {"cloud-api", "app-host"})
        self.assertNotEqual(t["cloud-api"], t["app-host"])
        for v in t.values():
            self.assertRegex(v, r"^[0-9a-f]{64}$")
            self.assertNotEqual(v, MASTER)

    def test_stable_and_bound_to_master(self):
        r = self.routes(("cloud-api:8080", "identity"))
        self.assertEqual(rx.upstream_tokens(r, MASTER), rx.upstream_tokens(r, MASTER))
        self.assertNotEqual(rx.upstream_tokens(r, MASTER), rx.upstream_tokens(r, "n" * 64))

    def test_needs_master_only_with_identity_routes(self):
        self.assertEqual(rx.upstream_tokens(self.routes(("demo-app:80", "shared")), ""), {})
        with self.assertRaises(rx.ManifestError):
            rx.upstream_tokens(self.routes(("demo-app:80", "identity")), "")

    def test_env_name_collision(self):
        with self.assertRaises(rx.ManifestError):
            rx.upstream_tokens(self.routes(("a-b:80", "identity"), ("a_b:80", "identity")), MASTER)

    def test_env_file(self):
        env = rx.render_tokens_env({"cloud-api": "ab" * 32})
        self.assertIn("GATEWAY_TOKEN_CLOUD_API=" + "ab" * 32 + "\n", env)

    def test_route_without_token_refused(self):
        out, _ = run_merge(manifest(routes=[route()]))
        with self.assertRaises(rx.ManifestError):
            rx.render_caddy(out["routes"])


class MainTests(unittest.TestCase):
    def setUp(self):
        old = os.environ.get("GATEWAY_TOKEN")
        os.environ["GATEWAY_TOKEN"] = MASTER
        self.addCleanup(lambda: os.environ.__setitem__("GATEWAY_TOKEN", old) if old is not None
                        else os.environ.pop("GATEWAY_TOKEN", None))

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
            env_path = os.path.join(d, "upstream-tokens.env")
            self.assertEqual(os.stat(env_path).st_mode & 0o777, 0o600)
            with open(env_path) as f:
                self.assertIn("GATEWAY_TOKEN_CLOUD_API=", f.read())

    def test_missing_master_writes_nothing(self):
        os.environ.pop("GATEWAY_TOKEN", None)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "in"))
            with open(os.path.join(d, "in", "01-workshop-x.json"), "w") as f:
                json.dump(manifest(routes=[route()]), f)
            rc = rx.main(["--in", os.path.join(d, "in"), "--out", d, "--services", " ".join(SERVICES)])
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(os.path.join(d, "gateway")))

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
