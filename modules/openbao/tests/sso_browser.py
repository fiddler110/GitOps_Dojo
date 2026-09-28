# The openbao module's single sign-on, in a real browser: a student opens the
# Vault card and the facilitator the /admin Vault tab (both go through
# /forgejo-login?next=), sign in with OIDC through Forgejo, and get their own
# entity and policy. Exits 1 on any failure.
#
# No browser on the dev machine, so run it in Playwright's image, with the
# stack up (from the repo root; screenshots go to $OUT):
#   set -a; . engine/.env; [ -z "${DOJO_ENV:-}" ] || . "engine/.env.$DOJO_ENV"; set +a
#   podman run --rm --network host -v "$PWD/modules/openbao/tests:/t:ro" -v "$OUT:/s" \
#     mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c \
#     'pip install -q --break-system-packages playwright==1.55.0 && python3 -B /t/sso_browser.py \
#      "$0" "$1" "$2" "$3" "$4"' "$PUBLIC_BASE_URL" "${TTYD_USERNAME:-student}" "$TTYD_PASSWORD" \
#      "$FACILITATOR_USERNAME" "$FACILITATOR_PASSWORD"
# Args: <base url> <student gateway user> <password> <facilitator gateway user> <password>.
import json, sys
from playwright.sync_api import sync_playwright

U, gu, gp, fu, fp = sys.argv[1:6]
U = U.rstrip("/")
VAULT = "/forgejo-login?next=/ui/vault/auth?with=oidc"
failed = []


def check(ok, what):
    print(("  ok:   " if ok else "  FAIL: ") + what)
    if not ok:
        failed.append(what)


def oidc_login(page, frame):
    """Click the UI's OIDC sign-in in `frame`, approve in Forgejo's popup if
    it asks, return (OpenBao's auth block, whether Forgejo asked)."""
    button = frame.locator("button#auth-submit, button[data-test-auth-submit]").first
    button.wait_for(timeout=20000)
    page.wait_for_timeout(3000)  # the UI fetches auth_url before the button does anything
    asked = False
    with page.expect_response(lambda r: "/v1/auth/oidc/oidc/callback" in r.url, timeout=30000) as cb:
        with page.expect_popup(timeout=20000) as pop:
            button.click()
        popup = pop.value
        popup.wait_for_load_state()
        if "/user/login" in popup.url:
            print("  popup landed on Forgejo's login page (no Forgejo session)")
        grant = popup.locator("#authorize-app, button:has-text('Authorize Application')")
        if grant.count():
            asked = True
            grant.first.click()
    return (cb.value.json().get("auth") or {}), asked


def report(auth, asked, policy):
    print("  auth:", json.dumps({k: auth.get(k) for k in ("entity_id", "identity_policies", "token_policies")}))
    check(bool(auth.get("client_token")), "OpenBao issued a token")
    check(policy in (auth.get("identity_policies") or []), f"the entity has the {policy} policy")
    print("  Forgejo's Authorize page:", "shown" if asked else "skipped")


with sync_playwright() as p:
    b = p.chromium.launch()

    print("== student: the Vault card")
    ctx = b.new_context(http_credentials={"username": gu, "password": gp}, base_url=U)
    pg = ctx.new_page()
    pg.goto("/"); pg.fill("input[name=name]", "SSO Test Student"); pg.click("form button")
    pg.wait_for_load_state()
    sid = pg.request.get("/whoami").json().get("user")
    check(bool(sid), f"got a student slot ({sid})")
    pg.goto(VAULT); pg.wait_for_load_state()
    check("/ui/vault/auth" in pg.url, "the card lands on the OIDC sign-in")
    auth, asked = oidc_login(pg, pg.main_frame)
    report(auth, asked, "student")
    check((auth.get("metadata") or {}).get("role") == "forgejo", "signed in with the forgejo role")
    pg.wait_for_timeout(2000)
    print("  landed:", pg.url.replace(U, ""))
    pg.screenshot(path="/s/sso_student.png")
    ctx.close()

    print("== facilitator: the /admin Vault tab")
    ctx = b.new_context(http_credentials={"username": fu, "password": fp}, base_url=U)
    pg = ctx.new_page()
    pg.goto("/admin"); pg.click("button.tab[data-tab=vault]")
    pg.wait_for_timeout(3000)
    fr = next((f for f in pg.frames if "/ui/" in f.url), None)
    check(fr is not None, "the tab frames the OpenBao UI")
    if fr:
        auth, asked = oidc_login(pg, fr)
        report(auth, asked, "facilitator")
        pg.wait_for_timeout(2000)
        print("  landed:", fr.url.replace(U, ""))
    pg.screenshot(path="/s/sso_facilitator.png")

    print("== /forgejo-login?next= refuses other sites")
    r = pg.request.get("/forgejo-login?next=//example.com/", max_redirects=0)
    check(r.status == 303 and r.headers.get("location", "").startswith("/git/"),
          f"//example.com goes to the repo instead ({r.status} {r.headers.get('location')})")
    b.close()

print("PASS" if not failed else f"FAILED: {len(failed)}")
sys.exit(1 if failed else 0)
