# P0 T0.4 spike: run in mcr.microsoft.com/playwright/python:v1.55.0-noble with --network host,
# the scratch dir (holding init.json from init-bao.sh) mounted at /s. Args: <gateway user> <password>.
import json, sys
from playwright.sync_api import sync_playwright
U="http://localhost:8080"; tok=json.load(open("/s/init.json"))["root_token"]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(http_credentials={"username":sys.argv[1],"password":sys.argv[2]}); pg=ctx.new_page()
    pg.route(U+"/spike-frame-test", lambda r: r.fulfill(status=200, content_type="text/html",
        body='<html><body style="margin:0"><iframe id=f src="/ui/vault/auth?with=token" style="width:100vw;height:100vh;border:0"></iframe></body></html>'))
    pg.goto(U+"/spike-frame-test", wait_until="networkidle")
    f=pg.frame_locator("#f"); f.locator("input[name=token]").fill(tok); f.get_by_role("button", name="Sign in").click()
    f.get_by_text("Secrets engines").first.wait_for(timeout=20000)
    print("framed login ok; frame url:", [fr.url for fr in pg.frames][1])
    # storage used by the UI
    print("storage:", pg.frames[1].evaluate("()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})"))
    pg.screenshot(path="/s/t04_framed_in.png"); b.close()
