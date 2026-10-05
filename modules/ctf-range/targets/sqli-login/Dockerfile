# sqli-login — CTF target 0 (plan §7.3, CTF-1 "Access and identity"). A
# single deliberately-vulnerable Flask app with no second stage — see
# app.py's module docstring for the bug and the flag.
#
# Unlike targets/customer-portal, this image has no ctf-host-side base-image
# dependency to stay in sync with: ctf-builder never rebuilds an attack-ladder
# target (students here don't patch and redeploy, they only attack it), so
# there's no offline-rebuild constraint (CTF-D24) to design around — a plain
# pinned base plus this image's own tiny requirements.txt is enough.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

# Fixed high uid, no home, no login — same convention as customer-portal,
# a different uid so the two never collide if ever run on the same host
# outside a container (they never are, but it costs nothing to keep distinct).
RUN useradd --uid 10015 --no-create-home --home-dir /app --shell /usr/sbin/nologin sqli

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000

USER sqli
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
