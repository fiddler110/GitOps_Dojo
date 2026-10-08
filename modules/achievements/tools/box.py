# Usage (from the host, repo root mounted at /w):
#   podman run --rm --network host -v "$PWD":/w:Z -e TTYD_USERNAME -e TTYD_PASSWORD \
#     mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c \
#     "pip install -q --break-system-packages playwright==1.55.0; python3 /w/modules/achievements/tools/box.py lab1.md.txt /w/box.png"
# (export TTYD_USERNAME/TTYD_PASSWORD from .env first). Prints how many challenge-box elements the lab page shows.
import os, sys
from playwright.sync_api import sync_playwright
lab = sys.argv[1]; out = sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto("http://localhost:8080/login")
    pg.fill("input[name=username]", os.environ["TTYD_USERNAME"]); pg.fill("input[name=password]", os.environ["TTYD_PASSWORD"])
    pg.click("button[type=submit], input[type=submit]"); pg.wait_for_load_state("networkidle")
    pg.goto("http://localhost:8080/"); pg.wait_for_load_state("networkidle")
    inp = pg.query_selector("input[name=name]")
    if inp:
        inp.fill("Box Tester"); pg.keyboard.press("Enter"); pg.wait_for_timeout(3000)
    print("portal:", pg.url, pg.title())
    pg.goto(f"http://localhost:8080/slides/assets/lab-reader.html?file={lab}"); pg.wait_for_timeout(4000)
    boxes = pg.query_selector_all("[class*=challenge]")
    print("challenge elements:", len(boxes))
    for x in boxes[:2]: print("  ", x.inner_text()[:300].replace("\n", " | "))
    el = boxes[0] if boxes else None
    if el: el.scroll_into_view_if_needed()
    pg.screenshot(path=out)
    b.close()
