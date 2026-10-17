FROM docker.io/library/python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111

# Stdlib only -- no pip installs, matches this repo's minimal-deps convention.
COPY server.py /usr/local/bin/allocator-server.py
# The rest of the allocator, imported by server.py (RV22 split it into modules).
COPY config.py accounts.py allocation.py probes.py pages.py views.py api.py handler.py /usr/local/bin/
# The CSS and JS of the allocator pages (pages.py's STATIC_DIR).
COPY static/ /usr/local/bin/static/
# Per-student Forgejo passwords (remediation D13); imported by the server.
COPY dojo_secret.py /usr/local/bin/dojo_secret.py
# Student reset: Forgejo steps and the worker thread; imported by the server.
COPY reset.py /usr/local/bin/reset.py
# The /login page and its logo, styles and script (accounts.py's LOGIN_DIR).
COPY login/ /usr/local/bin/login/

EXPOSE 8080
# Must send X-Gateway-Token -- the allocator rejects every request
# (including this one) that lacks it (see handler.py's gateway_authorized()),
# same pattern as web-terminal/Dockerfile's own HEALTHCHECK sending
# X-Control-Token to workspace-control.py.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null --header="X-Gateway-Token: ${GATEWAY_TOKEN}" http://127.0.0.1:8080/ || exit 1

# Not root: the allocator holds the Forgejo admin password, the student
# password seed and both control-plane tokens, and needs no privilege at all.
# The state directory is created here, owned by that user, so a fresh named
# volume mounted on it (allocator_state) starts with the same owner. Compose
# also drops every capability and makes the root filesystem read-only.
# (sensei builds FROM this image but runs as 0:0 with no capabilities.)
RUN adduser -D -H -u 10001 allocator \
    && mkdir -p /var/lib/dojo-allocator \
    && chown allocator:allocator /var/lib/dojo-allocator
USER 10001:10001
CMD ["python3", "-B", "/usr/local/bin/allocator-server.py"]
