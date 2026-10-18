# sqli-login — CTF target 0 (plan §7.3, CTF-1 "Access and identity"). A
# single deliberately-vulnerable Flask app with no second stage — see
# app.py's module docstring for the bug and the flag.
#
# Unlike targets/customer-portal, this image has no ctf-host-side base-image
# dependency to stay in sync with: ctf-builder never rebuilds an attack-ladder
# target (students here don't patch and redeploy, they only attack it), so
# there's no offline-rebuild constraint (CTF-D24) to design around — a plain
# pinned base plus this image's own tiny requirements.txt is enough.
FROM docker.io/library/python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY assets/ /app/assets/

# Fixed high uid, no home, no login — same convention as customer-portal,
# a different uid so the two never collide if ever run on the same host
# outside a container (they never are, but it costs nothing to keep distinct).
RUN useradd --uid 10015 --no-create-home --home-dir /app --shell /usr/sbin/nologin sqli

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222 2121 8081

USER sqli
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
