# P0 T0.4 spike: run in mcr.microsoft.com/playwright/python:v1.55.0-noble with --network host,
# the scratch dir (holding init.json from init-bao.sh) mounted at /s. Args: <gateway user> <password>.
import json, os, sys
from playwright.sync_api import sync_playwright
U = "http://localhost:8080"
tok = json.load(open("/s/init.json"))["root_token"]
user, pw = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(http_credentials={"username": user, "password": pw})
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    # 1) UI direct: token login -> dashboard
    pg.goto(U + "/ui/vault/auth?with=token", wait_until="networkidle")
    pg.fill("input[name=token]", tok)
    pg.get_by_role("button", name="Sign in").click()
    pg.wait_for_url("**/ui/vault/secrets**", timeout=20000)
    pg.screenshot(path="/s/t04_direct.png")
    print("direct: logged in ->", pg.url)
    # 2) framed from same origin (like /admin does)
    pg.route(U + "/spike-frame-test", lambda r: r.fulfill(status=200, content_type="text/html",
        body='<html><body style="margin:0"><iframe id=f src="/ui/vault/secrets" style="width:100vw;height:100vh;border:0"></iframe></body></html>'))
    pg.goto(U + "/spike-frame-test", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    fr = pg.frame_locator("#f")
    txt = fr.locator("body").inner_text(timeout=15000)
    print("framed: body has 'Secrets engines' =", "Secrets engines" in txt or "secrets" in txt.lower())
    pg.screenshot(path="/s/t04_framed.png")
    print("console errors:", [e[:160] for e in errs][:5])
    b.close()
