#!/bin/sh
# Check a running workshop's Marp pages for content past the 16:9 slide or into its footer. Run from the repo root,
# on a stack that is already up:
#   workshops/assets/slide-overflow.sh <workshop> [page.md ...] [--base URL]
# Pages default to every Marp file in workshops/<workshop>/content/slides/ (presentation, cheat sheet, labs index).
# Logs in at /login as the facilitator (engine/.env), opens /slides/<page>, and for every slide compares each
# h1-h3/p/li/pre/table/img/blockquote box with the slide, or with its footer's top; anything more than 2 px past
# prints as a FAIL with the page, slide number and the start of its text. No browser on this machine, so it runs
# Playwright in mcr.microsoft.com/playwright/python (host network). Exit 0 when every page is clean.
set -u
. workshops/assets/test-lib.sh

ws="" base="http://localhost:8080" pages=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) base="$2"; shift ;;
    -*) echo "slide-overflow: unknown option $1" >&2; exit 2 ;;
    *) if [ -z "$ws" ]; then ws="$1"; else pages="$pages $1"; fi ;;
  esac
  shift
done
dir="workshops/$ws/content/slides"
[ -n "$ws" ] && [ -d "$dir" ] || {
  echo "usage: workshops/assets/slide-overflow.sh <workshop> [page.md ...] [--base URL]" >&2; exit 2; }
if [ -z "$pages" ]; then
  for f in "$dir"/*.md; do
    head -5 "$f" | rg -q '^marp: true' && pages="$pages $(basename "$f")"
  done
fi
[ -n "$pages" ] || { echo "slide-overflow: no Marp pages in $dir" >&2; exit 2; }
load_env

podman run --rm --network host -i \
  -e BASE="$base" -e PAGES="$pages" \
  -e LOGIN_USER="$FACILITATOR_USERNAME" -e LOGIN_PASSWORD="$FACILITATOR_PASSWORD" \
  mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c '
pip install -q --break-system-packages playwright==1.55.0 >/dev/null 2>&1 || { echo "pip install failed"; exit 2; }
python3 -B - <<"EOF"
import os, sys
from playwright.sync_api import sync_playwright

base, pages = os.environ["BASE"], os.environ["PAGES"].split()
CHECK = """() => {
  const out = [];
  document.querySelectorAll("section").forEach((s, i) => {
    const box = s.getBoundingClientRect();
    if (!box.width) return;
    const foot = s.querySelector("footer");
    const bottom = foot ? Math.min(box.bottom, foot.getBoundingClientRect().top) : box.bottom;
    s.querySelectorAll("h1,h2,h3,p,li,pre,table,img,blockquote").forEach(el => {
      if (el.closest("footer, header")) return;
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) return;
      const past = Math.max(r.right - box.right, r.bottom - bottom, box.left - r.left, box.top - r.top);
      if (past > 2) out.push([i + 1, Math.round(past), el.tagName.toLowerCase(),
                              (el.textContent || el.getAttribute("src") || "").trim().slice(0, 60)]);
    });
  });
  return [document.querySelectorAll("section").length, out];
}"""
bad = 0
with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1280, "height": 720})
    page.goto(base + "/login")
    page.fill("input[name=username]", os.environ["LOGIN_USER"])
    page.fill("input[name=password]", os.environ["LOGIN_PASSWORD"])
    # Not "networkidle": the portal polls every few seconds, so it never goes idle.
    with page.expect_navigation():
        page.press("input[name=password]", "Enter")
    for name in pages:
        resp = page.goto(f"{base}/slides/{name}")
        page.wait_for_load_state("load")
        page.wait_for_timeout(1500)  # Marp lays out and highlight.js colours after load
        if not resp or resp.status != 200 or "/login" in page.url:
            print(f"  FAIL: {name}: not served (status {resp.status if resp else None}, {page.url})"); bad += 1; continue
        count, out = page.evaluate(CHECK)
        if not count:
            print(f"  FAIL: {name}: no slides rendered"); bad += 1; continue
        for n, px, tag, text in out:
            print(f"  FAIL: {name} slide {n}: <{tag}> {px} px past: {text}")
        bad += bool(out)
        if not out:
            print(f"  ok:   {name}: {count} slides, nothing past 16:9 or the footer")
sys.exit(1 if bad else 0)
EOF'
