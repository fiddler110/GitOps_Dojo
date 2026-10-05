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
import allocation  # noqa: E402
import config  # noqa: E402
import handler  # noqa: E402
import views  # noqa: E402
import pages  # noqa: E402

CARD = {"id": "demo", "label": "Demo Site", "desc": "Your site.", "href": "/demo/", "icon": "cloud"}
WIDGET = {"id": "score", "src": "/achievements/widget/", "size": "medium"}


def ext(**over):
    base = {"cards": [], "admin_tabs": [], "widgets": [], "scripts": [], "routes": [], "status_checks": []}
    base.update(over)
    return base


def workspace(extensions=None, sid="student01"):
    with mock.patch.dict(config.EXTENSIONS, extensions or ext(), clear=True):
        return handler.Handler.render_workspace(None, sid)


def landing(extensions=None, sid="student01", name="Ada"):
    slot = {"name": name, "ip": None, "token": None, "tool": None, "assigned_at": None}
    with mock.patch.dict(config.EXTENSIONS, extensions or ext(), clear=True), \
            mock.patch.dict(allocation.slots, {sid: slot}):
        return handler.Handler.render_confirmation(None, sid)


class WorkspacePage(unittest.TestCase):
    def test_engine_tabs_in_order(self):
        page = workspace()
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page), ["ide", "term", "forgejo", "slides", "labs"])
        for label in ("VS Code", "Terminal", "Forgejo", "Slides", "Labs"):
            self.assertIn(f">{label}</button>", page)

    def test_card_tabs_follow_the_engine_tabs(self):
        page = workspace(ext(cards=[CARD]))
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page)[-1], "demo")
        self.assertIn('data-src="/demo/"', page)
        self.assertIn(">Demo Site</button>", page)

    def test_labs_sit_under_slides_and_widgets_get_a_tab_before_cards(self):
        page = workspace(ext(cards=[CARD], widgets=[WIDGET]))
        self.assertIn('class="tab indent" data-tab="labs"', page)
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page),
                         ["ide", "term", "forgejo", "slides", "labs", "achievements", "demo"][:5] + [WIDGET["id"], "demo"])
        self.assertIn(f'data-src="{WIDGET["src"]}"', page)

    def test_first_tab_is_active_and_frames_load_lazily(self):
        page = workspace()
        self.assertEqual(len(re.findall(r'class="tab active"', page)), 1)
        self.assertEqual(len(re.findall(r'class="panel active"', page)), 1)
        self.assertIn('class="tab active" data-tab="ide"', page)
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
        self.assertIn('href="/?split"', page)

    def test_labels_and_ids_are_escaped(self):
        page = workspace(ext(cards=[dict(CARD, label='<img src=x onerror=alert(1)>')]))
        self.assertNotIn("<img", page)
        self.assertIn("&lt;img", page)

    def test_scripts_and_styles_are_served(self):
        self.assertEqual(set(pages.WORKSPACE_ASSETS), {"/workspace/workspace.css", "/workspace/workspace.js",
                                                        "/workspace/mode.js", "/workspace/extra.js"})
        page = workspace()
        for path in pages.WORKSPACE_ASSETS:
            if not path.endswith("workspace.css"):
                self.assertIn(f'src="{path}"', page)
        self.assertIn('href="/workspace/workspace.css"', page)


class SharedShell(unittest.TestCase):
    """/admin and /workspace share one layout and tab script; splitting them lost nothing."""

    def test_admin_keeps_its_roster_rules(self):
        self.assertTrue(pages.ADMIN_CSS.startswith(pages.SHELL_CSS))
        for rule in (".tile", "#grid", "#roster-bar", ".tab.active", ".panel iframe"):
            self.assertIn(rule, pages.ADMIN_CSS)
        self.assertTrue(pages.ADMIN_JS.startswith(pages.TABS_JS))
        self.assertIn("roster grid", pages.ADMIN_JS)

    def test_workspace_gets_only_the_shell(self):
        for rule in (".tab.active", ".panel iframe", "#side"):
            self.assertIn(rule, pages.WORKSPACE_CSS)
        for rule in (".tile", "#grid", "#roster-bar"):
            self.assertNotIn(rule, pages.WORKSPACE_CSS)
        self.assertNotIn("roster", pages.WORKSPACE_JS)
        self.assertIn("activateTab(tabs[0]", pages.WORKSPACE_JS)


class ModeScript(unittest.TestCase):
    def test_remembers_the_choice_per_browser(self):
        js = pages.WORKSPACE_MODE_JS
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

    def test_widget_is_a_framed_same_origin_page_below_the_cards(self):
        page = landing(ext(widgets=[WIDGET]))
        self.assertIn('<iframe class="widget widget-medium" src="/achievements/widget/" title="score"></iframe>', page)
        self.assertGreater(page.index("<iframe"), page.index('class="cards"'))

    def test_widget_sizes_have_css_classes(self):
        for size in ("small", "medium", "large"):
            self.assertIn(f".widget-{size} {{", pages.CONFIRM_CSS)

    def test_student_name_is_escaped(self):
        page = landing(name="<b>x</b>")
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)

    def test_csp_covers_the_landing_stylesheet(self):
        # The page's one inline <style> is allowed by hash; if CONFIRM_CSS changes the hash follows.
        self.assertIn(pages._style_hash(pages.CONFIRM_CSS), pages.CSP)
        self.assertIn("script-src 'self'", pages.CSP)
        self.assertIn("frame-ancestors 'self'", pages.CSP)


class LoadExtensions(unittest.TestCase):
    def test_widgets_key_defaults_to_empty(self):
        self.assertEqual(config.load_extensions(os.path.join(HERE, "no-such-file.json"))["widgets"], [])

    def test_widgets_are_read_from_the_rendered_manifest(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"version": 1, "widgets": [WIDGET]}, f)
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(config.load_extensions(f.name)["widgets"], [WIDGET])


class ExtraScripts(unittest.TestCase):
    def test_pages_include_the_loader_with_their_surface(self):
        self.assertIn('<script src="/workspace/extra.js" data-surface="portal"></script>', landing())
        self.assertIn('<script src="/workspace/extra.js" data-surface="workspace"></script>', workspace())

    def test_loader_lists_only_the_manifest_scripts(self):
        self.assertIn("[].forEach", pages.build_extra_js([]))
        js = pages.build_extra_js([{"src": "/achievements/toast.js"}, {"src": "/x/y.js"}])
        self.assertIn('["/achievements/toast.js", "/x/y.js"].forEach', js)

    def test_loader_passes_the_surface_on(self):
        self.assertIn("setAttribute('data-surface', surface)", pages.build_extra_js([]))

    def test_loader_is_served(self):
        ctype, body = pages.WORKSPACE_ASSETS["/workspace/extra.js"]
        self.assertTrue(ctype.startswith("text/javascript"))
        self.assertIn("document.currentScript", body)

    def test_default_is_no_scripts(self):
        self.assertEqual(config.load_extensions(os.path.join(HERE, "nope.json"))["scripts"], [])


class ZellijFlavor(unittest.TestCase):
    """TERMINAL_FLAVOR=zellij (config.HAS_IDE false): no IDE anywhere a student or facilitator looks."""

    def test_student_workspace_has_no_vscode_tab(self):
        with mock.patch.object(views, "HAS_IDE", False):
            page = workspace()
        self.assertEqual(re.findall(r'data-tab="([a-z0-9-]+)"', page), ["term", "forgejo", "slides", "labs"])
        self.assertNotIn("VS Code", page)
        self.assertEqual(len(re.findall(r'class="tab active"', page)), 1)

    def test_landing_page_leads_with_the_terminal(self):
        with mock.patch.object(views, "HAS_IDE", False):
            page = landing()
        self.assertNotIn("VS Code", page)
        self.assertNotIn('href="/ide/"', page)
        self.assertIn('href="/term/"', page)

    def test_facilitator_page_drops_its_ide_tab_and_panel(self):
        with mock.patch.dict(config.EXTENSIONS, ext(), clear=True):
            on = handler.Handler.render_facilitator_workspace(None)
            with mock.patch.object(views, "HAS_IDE", False):
                off = handler.Handler.render_facilitator_workspace(None)
        self.assertIn('data-tab="ide"', on)
        self.assertNotIn('data-tab="ide"', off)
        self.assertNotIn('panel-ide', off)
        self.assertIn('data-tab="term"', off)

    def test_default_flavor_keeps_the_ide(self):
        self.assertTrue(config.HAS_IDE)
        self.assertIn('data-tab="ide"', workspace())


if __name__ == "__main__":
    unittest.main()

