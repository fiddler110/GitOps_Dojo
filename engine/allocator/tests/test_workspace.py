"""The student workspace (/workspace) and the landing page's widgets and workspace card.
Run from engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
for _k, _v in {"FORGEJO_ADMIN_USER": "admin", "FORGEJO_ADMIN_PASSWORD": "x",
               "CONTROL_TOKEN": "control-test", "GATEWAY_TOKEN": "gateway-test",
               "EXTENSIONS_FILE": os.path.join(HERE, "no-such-file.json")}.items():
    os.environ.setdefault(_k, _v)
import server  # noqa: E402

CARD = {"id": "demo", "label": "Demo Site", "desc": "Your site.", "href": "/demo/", "icon": "cloud"}
WIDGET = {"id": "score", "src": "/achievements/widget/", "size": "medium"}


def ext(**over):
    base = {"cards": [], "admin_tabs": [], "widgets": [], "scripts": [], "routes": [], "status_checks": []}
    base.update(over)
    return base


def workspace(extensions=None, sid="student01"):
    with mock.patch.dict(server.EXTENSIONS, extensions or ext(), clear=True):
        return server.Handler.render_workspace(None, sid)


def landing(extensions=None, sid="student01", name="Ada"):
    slot = {"name": name, "ip": None, "token": None, "tool": None, "assigned_at": None}
    with mock.patch.dict(server.EXTENSIONS, extensions or ext(), clear=True), \
            mock.patch.dict(server.slots, {sid: slot}):
        return server.Handler.render_confirmation(None, sid)


class WorkspacePage(unittest.TestCase):
    def test_engine_tabs_in_order(self):
        page = workspace()
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page), ["labs", "ide", "term", "forgejo", "slides"])
        for label in ("Labs", "VS Code", "Terminal", "Forgejo", "Slides"):
            self.assertIn(f">{label}</button>", page)

    def test_card_tabs_follow_the_engine_tabs(self):
        page = workspace(ext(cards=[CARD]))
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page)[-1], "demo")
        self.assertIn('data-src="/demo/"', page)
        self.assertIn(">Demo Site</button>", page)

    def test_first_tab_is_active_and_frames_load_lazily(self):
        page = workspace()
        self.assertEqual(len(re.findall(r'class="tab active"', page)), 1)
        self.assertEqual(len(re.findall(r'class="panel active"', page)), 1)
        self.assertIn('class="tab active" data-tab="labs"', page)
        # Every iframe waits for its tab's first click: none has a live src.
        self.assertNotRegex(page, r"<iframe[^>]* src=")
        self.assertEqual(page.count("<iframe"), page.count("data-src="))

    def test_labs_tab_is_the_lab_index(self):
        self.assertIn('data-src="/slides/labs.md"', workspace())

    def test_no_inline_script_or_style(self):
        # The strict CSP (script-src 'self', styles by hash only) allows neither.
        page = workspace(ext(cards=[CARD]))
        self.assertNotRegex(page, r"<script(?![^>]* src=)")
        self.assertNotIn("<style", page)
        self.assertNotRegex(page, r'\sstyle=')
        self.assertNotRegex(page, r'\son[a-z]+=')

    def test_shows_who_and_links_back(self):
        page = workspace(sid="student07")
        self.assertIn(">student07<", page)
        self.assertIn('href="/" data-mode="split"', page)
        self.assertIn('href="/logout"', page)

    def test_labels_and_ids_are_escaped(self):
        page = workspace(ext(cards=[dict(CARD, label='<img src=x onerror=alert(1)>')]))
        self.assertNotIn("<img", page)
        self.assertIn("&lt;img", page)

    def test_scripts_and_styles_are_served(self):
        self.assertEqual(set(server.WORKSPACE_ASSETS), {"/workspace/workspace.css", "/workspace/workspace.js",
                                                        "/workspace/mode.js", "/workspace/extra.js"})
        page = workspace()
        for path in server.WORKSPACE_ASSETS:
            if not path.endswith("workspace.css"):
                self.assertIn(f'src="{path}"', page)
        self.assertIn('href="/workspace/workspace.css"', page)


class SharedShell(unittest.TestCase):
    """/admin and /workspace share one layout and tab script; splitting them lost nothing."""

    def test_admin_keeps_its_roster_rules(self):
        self.assertTrue(server.ADMIN_CSS.startswith(server.SHELL_CSS))
        for rule in (".tile", "#grid", "#roster-bar", ".tab.active", ".panel iframe"):
            self.assertIn(rule, server.ADMIN_CSS)
        self.assertTrue(server.ADMIN_JS.startswith(server.TABS_JS))
        self.assertIn("roster grid", server.ADMIN_JS)

    def test_workspace_gets_only_the_shell(self):
        for rule in (".tab.active", ".panel iframe", "#side"):
            self.assertIn(rule, server.WORKSPACE_CSS)
        for rule in (".tile", "#grid", "#roster-bar"):
            self.assertNotIn(rule, server.WORKSPACE_CSS)
        self.assertNotIn("roster", server.WORKSPACE_JS)
        self.assertIn("activateTab(tabs[0]", server.WORKSPACE_JS)


class ModeScript(unittest.TestCase):
    def test_remembers_the_choice_per_browser(self):
        js = server.WORKSPACE_MODE_JS
        self.assertIn("localStorage", js)
        self.assertIn("'dojo-mode'", js)
        # Storage can be blocked (private window): every access is guarded.
        self.assertEqual(js.count("localStorage"), js.count("try {"))
        # Going back to split mode on purpose must not bounce straight back.
        self.assertIn("split", js)
        self.assertIn("location.replace('/workspace')", js)


class LandingPage(unittest.TestCase):
    def test_workspace_card_is_first_and_opens_in_the_same_tab(self):
        page = landing(ext(cards=[CARD]))
        card = re.search(r'<a class="card wide" href="/workspace"[^>]*>', page)
        self.assertTrue(card, "no Open workspace card")
        self.assertIn('data-mode="workspace"', card.group(0))
        self.assertNotIn("_blank", card.group(0))
        self.assertLess(page.index('href="/workspace"'), page.index('href="/ide/"'))

    def test_tools_still_open_in_a_new_tab(self):
        page = landing(ext(cards=[CARD]))
        for href in ("/ide/", "/term/", "/forgejo-login", "/slides/", "/demo/"):
            self.assertRegex(page, rf'<a class="card[^"]*" href="{re.escape(href)}" target="_blank"')

    def test_mode_script_and_page_marker(self):
        page = landing()
        self.assertIn('<html data-page="landing">', page)
        self.assertIn('<script src="/workspace/mode.js"></script>', page)
        self.assertNotRegex(page, r"<script(?![^>]* src=)")

    def test_no_widgets_no_widget_markup(self):
        self.assertNotIn('class="widgets"', landing())
        self.assertNotIn("<iframe", landing())

    def test_widget_is_a_framed_same_origin_page_above_the_cards(self):
        page = landing(ext(widgets=[WIDGET]))
        self.assertIn('<iframe class="widget widget-medium" src="/achievements/widget/" title="score"></iframe>', page)
        self.assertLess(page.index("<iframe"), page.index('class="cards"'))

    def test_widget_sizes_have_css_classes(self):
        for size in ("small", "medium", "large"):
            self.assertIn(f".widget-{size} {{", server.CONFIRM_CSS)

    def test_student_name_is_escaped(self):
        page = landing(name="<b>x</b>")
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)

    def test_csp_covers_the_landing_stylesheet(self):
        # The page's one inline <style> is allowed by hash; if CONFIRM_CSS changes the hash follows.
        self.assertIn(server._style_hash(server.CONFIRM_CSS), server.CSP)
        self.assertIn("script-src 'self'", server.CSP)
        self.assertIn("frame-ancestors 'self'", server.CSP)


class LoadExtensions(unittest.TestCase):
    def test_widgets_key_defaults_to_empty(self):
        self.assertEqual(server.load_extensions(os.path.join(HERE, "no-such-file.json"))["widgets"], [])

    def test_widgets_are_read_from_the_rendered_manifest(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"version": 1, "widgets": [WIDGET]}, f)
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(server.load_extensions(f.name)["widgets"], [WIDGET])


class ExtraScripts(unittest.TestCase):
    def test_pages_include_the_loader_with_their_surface(self):
        self.assertIn('<script src="/workspace/extra.js" data-surface="portal"></script>', landing())
        self.assertIn('<script src="/workspace/extra.js" data-surface="workspace"></script>', workspace())

    def test_loader_lists_only_the_manifest_scripts(self):
        self.assertIn("[].forEach", server.build_extra_js([]))
        js = server.build_extra_js([{"src": "/achievements/toast.js"}, {"src": "/x/y.js"}])
        self.assertIn('["/achievements/toast.js", "/x/y.js"].forEach', js)

    def test_loader_passes_the_surface_on(self):
        self.assertIn("setAttribute('data-surface', surface)", server.build_extra_js([]))

    def test_loader_is_served(self):
        ctype, body = server.WORKSPACE_ASSETS["/workspace/extra.js"]
        self.assertTrue(ctype.startswith("text/javascript"))
        self.assertIn("document.currentScript", body)

    def test_default_is_no_scripts(self):
        self.assertEqual(server.load_extensions(os.path.join(HERE, "nope.json"))["scripts"], [])


if __name__ == "__main__":
    unittest.main()

