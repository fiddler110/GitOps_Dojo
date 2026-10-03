"""Icons, the CSP and the page shells for the allocator's HTML pages; the CSS and JS are in static/."""
import base64
import hashlib
import html
import json
import os

from config import EXTENSIONS


# Inline, self-contained SVGs for the confirmation page's tool cards (see
# render_confirmation) -- feather-style, 24x24, stroke=currentColor so each
# one automatically picks up its card's icon color (including the primary
# card's white-on-blue) with no extra markup or external icon font/CDN
# request. This runs entirely inside a student's own browser, which this
# project makes no assumption has internet access beyond the workshop
# origin itself (see engine/README.md's Troubleshooting section on the
# terminal container's own lack of one) -- so nothing on this page ever
# depends on a third-party asset loading.
_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
ICON_CODE = _SVG.format('<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>')
ICON_TERMINAL = _SVG.format('<polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line>')
ICON_GIT = _SVG.format('<line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle>'
                        '<circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>')
ICON_SLIDES = _SVG.format('<rect x="2" y="4" width="20" height="14" rx="2"></rect>'
                           '<line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="18" x2="12" y2="21"></line>')
ICON_ROCKET = _SVG.format('<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>'
                           '<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>'
                           '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>'
                           '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>')
ICON_CLOUD = _SVG.format('<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>')
ICON_KEY = _SVG.format('<circle cx="7.5" cy="15.5" r="5.5"></circle><path d="M21 2l-9.6 9.6"></path>'
                        '<path d="M15.5 7.5l3 3L22 7l-3-3"></path>')
ICON_DNS = _SVG.format('<circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line>'
                        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>')
# Names an extensions.json card may use (render_extensions.py ICONS).
ICON_LAYOUT = _SVG.format('<rect x="3" y="3" width="18" height="18" rx="2"></rect>'
                         '<line x1="9" y1="3" x2="9" y2="21"></line><line x1="9" y1="9" x2="21" y2="9"></line>')
ICONS_BY_NAME = {"code": ICON_CODE, "terminal": ICON_TERMINAL, "git": ICON_GIT, "slides": ICON_SLIDES,
                 "rocket": ICON_ROCKET, "cloud": ICON_CLOUD, "key": ICON_KEY, "dns": ICON_DNS}
ICON_ARROW ='<svg class="card-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' \
             'stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"></line>' \
             '<polyline points="7 7 17 7 17 17"></polyline></svg>'


# -- page assets (remediation T4.2, FIND-14) ------------------------------
# Every allocator page is served under a strict Content-Security-Policy (see
# CSP below): no inline script, no style attributes. The facilitator page's
# script and stylesheet are served from memory at /admin/admin.js and
# /admin/admin.css (behind the same facilitator gate as /admin). The student
# pages keep one inline <style> each, allowed by its sha256 hash, computed
# here from the exact text so the header can't drift from the page.
# The CSS and JS are files in static/ (STATIC_DIR), read once at start-up.
STATIC_DIR = os.environ.get("STATIC_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _static(name):
    with open(os.path.join(STATIC_DIR, name), encoding="utf-8") as f:
        return f.read()


LANDING_CSS = _static("landing.css")
CONFIRM_CSS = _static("confirm.css")
SHELL_CSS = _static("shell.css")
ADMIN_CSS = SHELL_CSS + _static("admin.css")
TABS_JS = _static("tabs.js")
ADMIN_JS = TABS_JS + _static("admin.js")


def _style_hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


CSP = ("default-src 'self'; script-src 'self'; "
       f"style-src 'self' {_style_hash(LANDING_CSS)} {_style_hash(CONFIRM_CSS)}; "
       "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'self'")

# Student workspace (/workspace): the same shell CSS and tab code as /admin,
# plus a small script that remembers split or workspace mode in this browser.
# Served behind the ordinary session gate (any login), like the pages.
WORKSPACE_CSS = SHELL_CSS + _static("workspace.css")
WORKSPACE_JS = TABS_JS + _static("workspace.js")
WORKSPACE_MODE_JS = _static("workspace-mode.js")


# Manifest `scripts`: one loader every student page includes (landing, /workspace, slides, lab
# reader) as <script src="/workspace/extra.js" data-surface="NAME">. It adds each same-origin
# script the run's modules asked for, passing the surface name along. Empty when there are none.
def build_extra_js(scripts):
    return """(function () {
  var me = document.currentScript, surface = me && me.getAttribute('data-surface');
  %s.forEach(function (src) {
    var s = document.createElement('script');
    s.src = src;
    if (surface) { s.setAttribute('data-surface', surface); }
    document.head.appendChild(s);
  });
})();
""" % json.dumps([x["src"] for x in scripts])


EXTRA_JS = build_extra_js(EXTENSIONS["scripts"])
WORKSPACE_ASSETS = {
    "/workspace/extra.js": ("text/javascript; charset=utf-8", EXTRA_JS),
    "/workspace/workspace.css": ("text/css; charset=utf-8", WORKSPACE_CSS),
    "/workspace/workspace.js": ("text/javascript; charset=utf-8", WORKSPACE_JS),
    "/workspace/mode.js": ("text/javascript; charset=utf-8", WORKSPACE_MODE_JS),
}

ADMIN_ASSETS = {
    # Reset hook labels passed render_extensions.py's check_text; json.dumps keeps them data.
    "/admin/admin.js": ("text/javascript; charset=utf-8", ADMIN_JS.replace(
        "__RESET_HOOK_LABELS__", json.dumps([h["label"] for h in EXTENSIONS["resets"] if not h.get("optional")])).replace(
        "__RESET_HOOK_OPTIONAL__", json.dumps([{"id": h["id"], "label": h["label"]}
                                               for h in EXTENSIONS["resets"] if h.get("optional")]))),
    "/admin/admin.css": ("text/css; charset=utf-8", ADMIN_CSS),
}


def page(title, body):
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{LANDING_CSS}</style></head>
<body>{body}</body></html>"""


# The landing page shows the student's Forgejo password, so nothing between
# here and the browser (or the browser's own back/forward cache) may keep a copy.
NO_STORE_HEADERS = [("Cache-Control", "no-store"), ("Pragma", "no-cache")]
