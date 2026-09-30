# vault-fundamentals P4 in a real browser (T4.8): the My App card's page for a
# student, the /admin Apps tab for the facilitator (every slot), an app page
# through the gateway (sandboxed), labs 11-13 in the lab reader, and the Part 6
# slides, labs.md and the lab index within 16:9. Exits 1 on any failure.
#
# Run it in Playwright's image, with the stack up (from the repo root;
# screenshots go to $OUT):
#   set -a; . engine/.env; set +a
#   podman run --rm --network host -v "$PWD/workshops/vault-fundamentals/tests:/t:ro" -v "$OUT:/s" \
#     mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c \
#     'pip install -q --break-system-packages playwright==1.55.0 && python3 -B /t/p4_browser.py \
#      "$0" "$1" "$2" "$3" "$4"' "$PUBLIC_BASE_URL" "${TTYD_USERNAME:-student}" "$TTYD_PASSWORD" \
#      "$FACILITATOR_USERNAME" "$FACILITATOR_PASSWORD"
import sys
from playwright.sync_api import sync_playwright

U, gu, gp, fu, fp = sys.argv[1:6]
U = U.rstrip("/")
SLIDES = [("presentation.md", n) for n in range(37, 45)] + [("labs.md", 6), ("lab-index.md", 1)]
failed = []


def check(ok, what):
    print(("  ok:   " if ok else "  FAIL: ") + what)
    if not ok:
        failed.append(what)


def watch_console(page, errors):
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)


def login_ctx(b, user, password, **kw):
    """A browser context signed in through the class login form (the gateway no longer takes basic auth)."""
    ctx = b.new_context(**kw)
    r = ctx.request.post("/login", form={"username": user, "password": password, "next": "/"}, max_redirects=0)
    assert r.status == 303, f"login as {user} failed: {r.status}"
    return ctx


with sync_playwright() as p:
    b = p.chromium.launch()

    print("== student: the My App card")
    ctx = login_ctx(b, gu, gp, base_url=U,
                        viewport={"width": 390, "height": 800})
    pg = ctx.new_page()
    errors = []
    watch_console(pg, errors)
    pg.goto("/"); pg.fill("input[name=name]", "P4 Browser Student"); pg.click("form button")
    pg.wait_for_load_state()
    me = pg.request.get("/whoami").json().get("user")
    check(bool(me), f"got a student slot ({me})")
    check(pg.locator("a[href='/apps/']").count() > 0, "the landing page has the My App card")
    pg.goto("/apps/"); pg.wait_for_selector(".slot", timeout=15000)
    names = pg.locator(".slot .name").all_text_contents()
    check(names == [me], f"the page shows only my slot ({names})")
    check(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "no horizontal scroll at 390 px")
    check(not errors, f"no console errors ({errors[:2]})")
    pg.screenshot(path="/s/apps_student.png", full_page=True)
    r = pg.request.get("/apps/student03/")
    check(r.status in (200, 503) and "sandbox" in r.headers.get("content-security-policy", ""),
          f"an app page through the gateway is sandboxed ({r.status})")
    if r.status == 200:
        check("slot student03" in r.text(), "the app answers through the gateway")
    ctx.close()

    print("== facilitator: the /admin Apps tab")
    ctx = login_ctx(b, fu, fp, base_url=U,
                        viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    watch_console(pg, errors)
    pg.goto("/admin"); pg.click("button.tab[data-tab=apps]")
    pg.wait_for_timeout(3000)
    fr = next((f for f in pg.frames if f.url.endswith("/apps/")), None)
    check(fr is not None, "the tab frames /apps/")
    if fr:
        fr.wait_for_selector(".slot", timeout=15000)
        check(fr.locator("h1").inner_text() == "Apps", "the facilitator's title is Apps")
        check(fr.locator(".slot").count() >= 3, f"every slot is listed ({fr.locator('.slot').count()})")
    check(not [e for e in errors if "apps" in e.lower()], f"no console errors from the tab ({errors[:2]})")
    pg.screenshot(path="/s/apps_facilitator.png")

    print("== labs 11-13 in the lab reader")
    for n in (11, 12, 13):
        pg.goto(f"/slides/assets/lab-reader.html?file=lab{n}.md.txt"); pg.wait_for_timeout(1500)
        text = pg.locator("body").inner_text()
        check(f"Lab {n}" in text and "Check yourself" in text, f"lab {n} renders in full")
        pg.screenshot(path=f"/s/reader_lab{n}.png")

    print("== slides within 16:9")
    for deck, n in SLIDES:
        pg.goto(f"/slides/{deck}#{n}"); pg.wait_for_timeout(1500)
        out = pg.evaluate("""() => {
          const s = [...document.querySelectorAll('section')].find(x => x.offsetParent !== null
              && x.getBoundingClientRect().width > 100) || document.querySelector('section');
          if (!s) return ['no section'];
          const box = s.getBoundingClientRect();
          return [...s.querySelectorAll('p, li, pre, table, tr, h1, h2, h3')].filter(e => {
            const r = e.getBoundingClientRect();
            return r.height > 0 && (r.bottom > box.bottom + 2 || r.right > box.right + 2);
          }).map(e => e.tagName + ': ' + e.textContent.trim().slice(0, 40));
        }""")
        check(not out, f"{deck} #{n} fits ({out[:2]})")
        pg.screenshot(path=f"/s/slide_{deck.split('.')[0]}_{n}.png")
    ctx.close()
    b.close()

print("PASS" if not failed else f"FAIL: {len(failed)}")
sys.exit(1 if failed else 0)
