#!/bin/sh
# Entrypoint of the dojo/hello container image: renders a tiny page from the
# environment the "cloud" hands it, then serves it with busybox httpd.
#   MESSAGE        text to show (default below)
#   OWNER          who deployed it
#   HELLO_VERSION  baked into the image (1.0 / 2.0) — 2.0 looks different so a
#                  version bump is visible in the browser
set -eu

# Everything below comes from a student's Terraform: escape it before it
# lands in HTML.
esc() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'; }

message="$(esc "${MESSAGE:-Hello from Dojo Cloud!}")"
owner="$(esc "${OWNER:-unknown}")"
version="$(esc "${HELLO_VERSION:-1.0}")"

case "$version" in
  2.*) bg="#0b3d2e"; fg="#d6fff0"; accent="#38d9a9" ;;
  *)   bg="#10243d"; fg="#e6f0ff"; accent="#4dabf7" ;;
esac

mkdir -p /www
cat > /www/index.html <<HTML
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${message}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:${bg};color:${fg};
       font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  main{text-align:center;padding:2rem}
  h1{font-size:clamp(1.6rem,5vw,3rem);margin:0 0 .5rem}
  .pill{display:inline-block;border:1px solid ${accent};color:${accent};border-radius:99px;padding:.15rem .8rem;margin:.2rem;font-size:.9rem}
</style></head>
<body><main>
  <h1>${message}</h1>
  <p><span class="pill">owner: ${owner}</span><span class="pill">image: dojo/hello:${version}</span></p>
  <p style="opacity:.6">Running on Dojo Cloud &middot; a training environment</p>
</main></body></html>
HTML

# The portal's Logs tab shows this container's stdout/stderr, so say something:
# a startup line, then one line per request (httpd -v logs to stderr).
echo "dojo/hello:${version} starting for owner '${OWNER:-unknown}' - listening on :80"
# This script is PID 1 of the container, and PID 1 ignores SIGTERM unless it has a handler. Without one, stopping the
# cloud host waits out Docker's 10 s stop timeout for every running site, then kills it. So keep httpd as a child
# and exit when told to.
httpd -f -v -p 80 -h /www &
httpd_pid=$!
trap 'kill "$httpd_pid" 2>/dev/null; exit 0' TERM INT
wait "$httpd_pid"
