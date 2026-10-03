"""HTML pages rendered by the request handler (mixed into handler.Handler).
"""
import html

from accounts import LOGIN_HTML
from allocation import slot_snapshot
from config import EXTENSIONS, FACILITATOR_USERNAME, WORKSHOP_DESCRIPTION, WORKSHOP_NAME
from dojo_secret import forgejo_password
from pages import (
    CONFIRM_CSS, ICON_ARROW, ICON_CODE, ICON_GIT, ICON_LAYOUT, ICON_SLIDES, ICON_TERMINAL, ICONS_BY_NAME, page,
)
class ViewsMixin:
    """HTML pages rendered by the request handler (mixed into handler.Handler)."""

    # -- pages -------------------------------------------------------------
    def render_name_form(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">Enter your name to get started.</p>
<form method="post" action="/assign">
  <input type="text" name="name" placeholder="Your name" required autofocus maxlength="60">
  <button type="submit">Join workshop</button>
</form>"""
        return page(WORKSHOP_NAME, body)

    def render_full(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">All workshop seats are currently taken. Please ask your facilitator for help.</p>"""
        return page(WORKSHOP_NAME, body)

    def render_busy(self, wait):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">A lot of people are joining at once. Please try again in {int(wait)} seconds.</p>
<p><a href="/">Try again</a></p>"""
        return page(WORKSHOP_NAME, body)

    def render_confirmation(self, sid):
        """The landing page a student sees on every visit after /assign has
        claimed them a slot (including refresh/back-button -- see
        handle_assign). Deliberately its own full HTML document, like
        render_facilitator_workspace, rather than page() -- page()'s
        narrow single-column layout is tuned for the two short forms
        (name entry, "lab full"), not a set of tool choices that benefits
        from room to show what each one actually does."""
        slot = slot_snapshot(sid)
        tools = [
            {
                "href": "/ide/", "label": "VS Code", "icon": ICON_CODE, "primary": True,
                "desc": "Your editor, already open in your lab folder.",
            },
            {
                "href": "/term/", "label": "Terminal", "icon": ICON_TERMINAL,
                "desc": "A plain shell, same account, if you'd rather type.",
            },
            {
                "href": "/forgejo-login", "label": "Forgejo", "icon": ICON_GIT,
                "desc": "Your repo -- branches, commits, pull requests.",
            },
            {
                "href": "/slides/", "label": "Slides", "icon": ICON_SLIDES,
                "desc": "Today's material, for reference as you go.",
            },
        ]
        for card in EXTENSIONS["cards"]:
            tools.append({
                "href": card["href"], "label": card["label"], "desc": card["desc"],
                "icon": ICONS_BY_NAME.get(card["icon"], ICON_ARROW),
            })

        workspace_card = f"""<a class="card wide" href="/workspace" data-mode="workspace">
  <span class="card-icon">{ICON_LAYOUT}</span>
  <span class="card-text">
    <span class="card-title">Open workspace</span>
    <span class="card-desc">Everything on one page: the labs, VS Code, terminal, Forgejo and slides as tabs.</span>
  </span>
  {ICON_ARROW}
</a>"""
        widgets = "\n".join(
            f'<iframe class="widget widget-{html.escape(w["size"])}" src="{html.escape(w["src"])}" '
            f'title="{html.escape(w["id"])}"></iframe>'
            for w in EXTENSIONS["widgets"]
        )
        if widgets:
            widgets = f'<div class="widgets">\n{widgets}\n</div>'

        cards = "\n".join(
            f"""<a class="card{' primary' if t.get('primary') else ''}" href="{t['href']}" target="_blank" rel="noopener">
  <span class="card-icon">{t['icon']}</span>
  <span class="card-text">
    <span class="card-title">{html.escape(t['label'])}</span>
    <span class="card-desc">{html.escape(t['desc'])}</span>
  </span>
  {ICON_ARROW}
</a>"""
            for t in tools
        )

        body = f"""
<a class="signout" href="/logout">Sign out</a>
<div class="hero">
  <span class="hero-badge">{html.escape(sid)}</span>
  <h1>You're in, {html.escape(slot['name'])}</h1>
  <p class="sub">Pick a tool to get started -- each opens in a new tab -- or open the workspace to keep everything on one page.</p>
</div>
<div class="secret">
  <span class="secret-label">Your Forgejo account</span>
  <table class="secret-table">
    <tr><th scope="row">Username</th><td><code class="secret-value">{html.escape(sid)}</code></td></tr>
    <tr><th scope="row">Password</th><td><code class="secret-value">{html.escape(forgejo_password(sid))}</code></td></tr>
  </table>
  <span class="secret-hint">Yours alone, for signing in to Forgejo by hand. Git in your terminal and VS Code is already signed in (a token in <code>~/.git-credentials</code>), and the Forgejo card signs you in to the web page.</span>
</div>
<div class="cards">
{workspace_card}
{cards}
</div>
{widgets}
<p class="footnote">Reload this page any time -- it always brings you straight back here as <strong>{html.escape(sid)}</strong>, with nothing lost.</p>
"""

        return f"""<!doctype html>
<html data-page="landing"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)}</title>
<script src="/workspace/mode.js"></script>
<script src="/workspace/extra.js" data-surface="portal"></script>
<style>{CONFIRM_CSS}</style></head>
<body>{body}</body></html>"""

    def render_workspace(self, sid):
        """The student's tabbed workspace at /workspace: the lab reader, VS
        Code, terminal, Forgejo and slides, plus a tab for each landing card
        a workshop or module declares, all as iframes on one page (the
        student's counterpart of /admin, sharing its layout and tab code).
        Nothing new for Caddy to authorize: each iframe is the same
        session-gated route the landing page's cards open in a new tab, and
        it is set lazily on that tab's first click so opening the workspace
        doesn't start a VS Code or terminal the student may not use.

        Split mode (the landing page and its separate tabs) stays as it is:
        the "Split mode" link and the landing page's "Open workspace" card
        each remember the choice in this browser (see WORKSPACE_MODE_JS)."""
        # VS Code, Terminal, Forgejo, Slides (the labs sit under it), then a tab per
        # widget (its full page) and per card. The first tab opens at load.
        tabs = [
            ("ide", "VS Code", "/ide/", False),
            ("term", "Terminal", "/term/", False),
            ("forgejo", "Forgejo", "/forgejo-login", False),
            ("slides", "Slides", "/slides/", False),
            ("labs", "Labs", "/slides/labs.md", True),
        ] + [(w["id"], w["id"].replace("-", " ").title(), w["src"], False) for w in EXTENSIONS["widgets"]] \
          + [(c["id"], c["label"], c["href"], False) for c in EXTENSIONS["cards"]]
        buttons = "".join(
            f'  <button class="tab{" indent" if sub else ""}{" active" if i == 0 else ""}" data-tab="{html.escape(tid)}">{html.escape(label)}</button>\n'
            for i, (tid, label, _, sub) in enumerate(tabs))
        panels = "".join(
            f'<div class="panel{" active" if i == 0 else ""}" id="panel-{html.escape(tid)}">'
            f'<iframe data-src="{html.escape(src)}" title="{html.escape(label)}"></iframe></div>\n'
            for i, (tid, label, src, _) in enumerate(tabs))
        return f"""<!doctype html>
<html data-page="workspace"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)}</title>
<script src="/workspace/mode.js"></script>
<script src="/workspace/extra.js" data-surface="workspace"></script>
<link rel="stylesheet" href="/workspace/workspace.css">
</head>
<body>
<nav id="side">
  <div id="bar">
    <h1>Workspace</h1>
    <p class="sub"><span class="badge">{html.escape(sid)}</span></p>
    <p class="sub"><a href="/" data-mode="split" target="_top">Split mode</a></p>
  </div>
  <div class="tabs" role="tablist" aria-orientation="vertical">
{buttons}  </div>
</nav>
<div id="content">
<div id="topbar">
  <span class="who">{html.escape(sid)}</span>
  <a href="/?split" target="_top">Home</a>
  <a href="/logout" target="_top">Sign out</a>
</div>
<main id="main">
{panels}</main>
</div>
<script src="/workspace/workspace.js"></script>
</body></html>"""

    def render_facilitator_workspace(self):
        """The facilitator's one-stop page at /admin: a roster of live
        terminal tiles (one per held slot -- account/name/IP/status/Release
        in the tile header, an iframe onto /admin/watch/<sid>/ underneath),
        plus their own VS Code/Terminal/Forgejo/Slides as further tabs, all
        on one wide page -- no dependency on the shared student gate either
        (see gateway/Caddyfile: /admin has its own basic_auth, which is
        also now accepted at the shared gate, so a facilitator never needs
        the student credential at all).

        Deliberately its own full HTML document rather than page() (which
        is tuned for the narrow single-column student flow) -- this page
        needs real width for the tool iframes and the roster grid.

        The VS Code/Terminal/Forgejo/Slides tabs are plain iframes onto the
        same /ide/, /term/, /forgejo-login, /slides/ routes the old
        separate-tab links used -- nothing new for Caddy or the allocator
        to authorize, since the facilitator's browser already carries
        whatever those routes need (the shared-gate basic_auth realm is
        reused automatically once /admin's has been satisfied -- see the
        Caddyfile comment above the shared block -- and neither ttyd nor
        code-server nor Forgejo send X-Frame-Options/frame-ancestors, the
        same fact that already makes the watch tiles embeddable). Each
        iframe's src is set lazily, on that tab's first click, so opening
        /admin doesn't eagerly spin up the facilitator's own VS
        Code/terminal/Forgejo session -- and once set it's never torn
        down, just hidden via CSS when another tab is active, so switching
        tabs doesn't lose editor/terminal state.

        The roster tab itself, unlike those, is the page's default (active)
        tab, so it builds its tiles -- and connects each one's watch
        websocket -- as soon as /admin loads, not lazily. It's kept in sync
        by polling /admin/api/sessions: client-side Set-diffing against the
        existing `tiles` object so a join/leave only ever adds/removes the
        one tile involved, never a wholesale replace (that would tear down
        and reconnect every iframe's websocket every poll). An existing
        tile's status dot does get refreshed in place on every poll, since
        "active" genuinely changes over a session -- just without touching
        that tile's iframe."""
        body = """
<nav id="side">
  <div id="bar">
    <h1>Facilitator</h1>
    <p class="sub">Signed in as <span class="badge">FACILITATOR_USERNAME_PLACEHOLDER</span></p>
    <p class="sub"><a href="/logout" target="_top">Sign out</a></p>
  </div>
  <div class="tabs" role="tablist" aria-orientation="vertical">
  <button class="tab active" data-tab="roster">Roster</button>
  <button class="tab" data-tab="ide">VS Code</button>
  <button class="tab" data-tab="term">Terminal</button>
  <button class="tab" data-tab="forgejo">Forgejo</button>
  <button class="tab" data-tab="slides">Slides</button>
EXT_TABS_PLACEHOLDER  </div>
  <div id="status" role="group" aria-label="Service status"></div>
</nav>

<main id="main">
<div class="panel active" id="panel-roster">
  <div id="roster-bar">
    <button id="release-unused" type="button" title="Frees every slot taken over 2 minutes ago with no VS Code or terminal running">Release unused</button>
    <span id="release-unused-out" class="sub"></span>
  </div>
  <p id="empty" class="sub">No students connected yet.</p>
  <div id="grid"></div>
</div>

<div class="panel" id="panel-ide"><iframe data-src="/ide/"></iframe></div>
<div class="panel" id="panel-term"><iframe data-src="/term/"></iframe></div>
<div class="panel" id="panel-forgejo"><iframe data-src="/forgejo-login"></iframe></div>
<div class="panel" id="panel-slides"><iframe data-src="/slides/"></iframe></div>
EXT_PANELS_PLACEHOLDER</main>
<script src="/admin/admin.js"></script>"""
        body = body.replace("FACILITATOR_USERNAME_PLACEHOLDER", html.escape(FACILITATOR_USERNAME))
        # The facilitator gets every tool a student has: every tab a workshop
        # or module declares next to its cards (extensions.json).
        # Ids are [a-z0-9-] and src a checked same-origin path; escaped anyway.
        body = body.replace(
            "EXT_TABS_PLACEHOLDER",
            "".join(f'  <button class="tab" data-tab="{html.escape(t["id"])}">{html.escape(t["label"])}</button>\n'
                    for t in EXTENSIONS["admin_tabs"]),
        ).replace(
            "EXT_PANELS_PLACEHOLDER",
            "".join(f'<div class="panel" id="panel-{html.escape(t["id"])}">'
                    f'<iframe data-src="{html.escape(t["src"])}"></iframe></div>\n'
                    for t in EXTENSIONS["admin_tabs"]),
        )
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)} — Facilitator</title>
<link rel="stylesheet" href="/admin/admin.css">
</head>
<body>{body}</body></html>"""

    def render_login(self, error=None, username="", nxt="/"):
        esc = html.escape
        alert = ""
        if error:
            alert = ('<p class="alert" role="alert"><svg viewBox="0 0 24 24" aria-hidden="true">'
                     '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>'
                     f'{esc(error)}</p>')
        lede = esc(WORKSHOP_DESCRIPTION) if WORKSHOP_DESCRIPTION else "Sign in with the class login to reach your lab."
        return (LOGIN_HTML.replace("{{WORKSHOP}}", esc(WORKSHOP_NAME))
                .replace("{{LEDE}}", lede)
                .replace("{{ERROR}}", alert)
                .replace("{{CARD_CLASS}}", " shake" if error else "")
                .replace("{{USERNAME}}", esc(username, quote=True))
                .replace("{{NEXT}}", esc(nxt, quote=True)))
