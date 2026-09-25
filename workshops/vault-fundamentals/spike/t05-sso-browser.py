# P0 T0.5 spike: OpenBao UI sign-in through Forgejo OIDC, as a student and as the
# facilitator inside the /admin Vault tab. Run in mcr.microsoft.com/playwright/python:v1.55.0-noble
# with --network host and the scratch dir at /s. Args: <base url> <gateway user> <gateway pw>
# <facilitator user> <facilitator pw>. Prints what OpenBao says about each login.
import json, sys
from playwright.sync_api import sync_playwright
U, gu, gp, fu, fp = sys.argv[1:6]

def oidc_login(page, frame):
    """Click the UI's OIDC sign-in in `frame`, approve in Forgejo's popup, return OpenBao's auth block."""
    frame.locator("button#auth-submit, button[data-test-auth-submit]").first.wait_for(timeout=20000)
    page.wait_for_timeout(3000)  # the UI fetches auth_url before the button does anything
    with page.expect_response(lambda r: "/v1/auth/oidc/oidc/callback" in r.url, timeout=30000) as cb:
        with page.expect_popup(timeout=20000) as pop:
            frame.locator("button#auth-submit, button[data-test-auth-submit]").first.click()
        popup = pop.value
        popup.wait_for_load_state()
        print("  popup:", popup.url.split("?")[0])
        grant = popup.locator("#authorize-app, button:has-text('Authorize Application')")
        if grant.count():
            grant.first.click()
    body = cb.value.json()
    if "auth" not in body or not body["auth"]:
        return body
    a = body["auth"]
    return {k: a.get(k) for k in ("entity_id", "policies", "identity_policies", "token_policies")} | \
        {"display": (a.get("metadata") or {}).get("role"), "user": (a.get("metadata") or {})}

with sync_playwright() as p:
    b = p.chromium.launch()

    print("== student")
    ctx = b.new_context(http_credentials={"username": gu, "password": gp}, base_url=U)
    pg = ctx.new_page()
    pg.goto("/"); pg.fill("input[name=name]", "Spike Student"); pg.click("form button")
    pg.wait_for_load_state()
    who = pg.request.get("/whoami").text()
    print("  whoami:", who[:120])
    pg.goto("/forgejo-login")
    pg.goto("/ui/vault/auth?with=oidc"); pg.wait_for_load_state()
    print("  auth:", json.dumps(oidc_login(pg, pg.main_frame)))
    pg.wait_for_timeout(2000); print("  landed:", pg.url.replace(U, ""))
    pg.screenshot(path="/s/t05_student.png")
    ctx.close()

    print("== facilitator in /admin Vault tab")
    ctx = b.new_context(http_credentials={"username": fu, "password": fp}, base_url=U)
    pg = ctx.new_page()
    pg.goto("/forgejo-login")
    pg.goto("/admin"); pg.click("button.tab[data-tab=vault]")
    pg.wait_for_timeout(3000)
    fr = next(f for f in pg.frames if "/ui/" in f.url)
    print("  frame:", fr.url.replace(U, ""))
    if "with=oidc" not in fr.url:
        fr.goto(U + "/ui/vault/auth?with=oidc"); fr.wait_for_load_state()
    print("  auth:", json.dumps(oidc_login(pg, fr)))
    pg.wait_for_timeout(2000); print("  landed:", fr.url.replace(U, ""))
    pg.screenshot(path="/s/t05_facilitator.png")
    b.close()
