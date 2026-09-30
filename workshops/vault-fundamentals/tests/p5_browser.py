# vault-fundamentals P5 in a real browser (T5.6): the facilitator's /admin
# Audit tab (rows, the student filter, following an accessor, no console errors,
# no horizontal scroll at 390 px), a student refused at /vault-audit/, the
# facilitator's roster listing the demo bots when --test is on, and the
# wrap-up slides within 16:9. Exits 1 on any failure.
#
# Run it in Playwright's image, with the stack up (from the repo root;
# screenshots go to $OUT):
#   set -a; . engine/.env; set +a
#   podman run --rm --network host -v "$PWD/workshops/vault-fundamentals/tests:/t:ro" -v "$OUT:/s" \
#     mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c \
#     'pip install -q --break-system-packages playwright==1.55.0 && python3 -B /t/p5_browser.py \
#      "$0" "$1" "$2" "$3" "$4"' "$PUBLIC_BASE_URL" "${TTYD_USERNAME:-student}" "$TTYD_PASSWORD" \
#      "$FACILITATOR_USERNAME" "$FACILITATOR_PASSWORD"
import sys
from playwright.sync_api import sync_playwright

U, gu, gp, fu, fp = sys.argv[1:6]
U = U.rstrip("/")
failed = []


def check(ok, what):
    print(("  ok:   " if ok else "  FAIL: ") + what)
    if not ok:
        failed.append(what)


def watch_console(page, errors):
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)


def audit_frame(pg):
    return next((f for f in pg.frames if "/vault-audit/" in f.url), None)


def login_ctx(b, user, password, **kw):
    """A browser context signed in through the class login form (the gateway no longer takes basic auth)."""
    ctx = b.new_context(**kw)
    r = ctx.request.post("/login", form={"username": user, "password": password, "next": "/"}, max_redirects=0)
    assert r.status == 303, f"login as {user} failed: {r.status}"
    return ctx


with sync_playwright() as p:
    b = p.chromium.launch()

    print("== student: no way into the Audit tab")
    ctx = login_ctx(b, gu, gp, base_url=U)
    # The gateway sends someone without the facilitator's login back to the landing page (303).
    r = ctx.request.get("/vault-audit/api/entries", max_redirects=0)
    check(r.status in (303, 401, 403), f"a student gets {r.status} from /vault-audit/, not the entries")
    ctx.close()

    for width in (1400, 390):
        print(f"== facilitator: the /admin Audit tab at {width} px")
        ctx = login_ctx(b, fu, fp, base_url=U,
                            viewport={"width": width, "height": 900})
        pg = ctx.new_page()
        errors = []
        watch_console(pg, errors)
        pg.goto("/admin")
        pg.click("button.tab[data-tab=audit]")
        pg.wait_for_timeout(3000)
        fr = audit_frame(pg)
        check(fr is not None, "the tab frames /vault-audit/")
        if fr:
            fr.wait_for_selector("#rows tr", timeout=15000)
            rows = fr.locator("#rows tr").count()
            check(rows > 0, f"entries are listed ({rows})")
            opts = fr.locator("#student option").all_text_contents()
            check(len(opts) > 1, f"the student filter lists students ({len(opts) - 1})")
            if len(opts) > 1:
                who = opts[1]
                fr.select_option("#student", who)
                fr.wait_for_timeout(1500)
                nss = set(fr.locator("#rows td.ns").all_text_contents())
                check(nss <= {f"students/{who}", "(root)"}, f"filtered to {who} ({sorted(nss)[:3]})")
                fr.select_option("#student", "*")
                fr.wait_for_timeout(1500)
            acc = fr.locator("#rows button.acc").first
            if acc.count():
                value = acc.inner_text()
                acc.click()
                fr.wait_for_timeout(1500)
                shown = set(fr.locator("#rows button.acc").all_text_contents())
                check(value in shown and fr.locator("#accessor").input_value() == value,
                      f"clicking an accessor follows that token ({len(shown)} accessors shown)")
            check(fr.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),
                  "no horizontal page scroll (the table scrolls inside its box)")
            pg.screenshot(path=f"/s/audit_{width}.png")
        check(not errors, f"no console errors ({errors[:2]})")
        if width == 1400:
            pg.goto("/admin")
            pg.wait_for_timeout(3000)
            text = pg.locator("body").inner_text()
            check("testuser1" in text or "Roster" in text, "the roster renders (bots show as testuserN with --test)")
            pg.screenshot(path="/s/admin_roster.png")
        ctx.close()

    print("== the wrap-up slides within 16:9")
    ctx = login_ctx(b, fu, fp, base_url=U,
                        viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto("/slides/presentation.md#1")
    pg.wait_for_timeout(2000)
    total = pg.evaluate("document.querySelectorAll('section').length")
    for n in range(max(1, total - 4), total + 1):
        pg.goto(f"/slides/presentation.md#{n}")
        pg.wait_for_timeout(1500)
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
        check(not out, f"presentation.md #{n} of {total} fits ({out[:2]})")
        pg.screenshot(path=f"/s/slide_presentation_{n}.png")
    ctx.close()
    b.close()

print("PASS" if not failed else f"FAIL: {len(failed)}")
sys.exit(1 if failed else 0)
