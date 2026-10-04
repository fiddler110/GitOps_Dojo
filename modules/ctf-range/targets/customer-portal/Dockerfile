# customer-portal — CTF target 14. A minimal Flask + plaintext SQLite app,
# built from original source in this repo (§6). The base is pinned by digest
# like every other external image here (check-pins.sh); ctf-host's `portal`
# stage mirrors this file, so bump both digests together.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

# Flask only; sqlite3 is stdlib. --no-cache-dir keeps the layer small, and the
# image does no network at run time (§6) — only here at build.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py seed.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# The DB lives on a named volume so teardown removes it. Create it owned by the
# unprivileged run user, since the container runs read-only except for /data.
# A fixed high uid (no home, no login) so the app never runs as root. Not
# --system: a system account caps the uid at 999 and would warn.
RUN useradd --uid 10014 --no-create-home --home-dir /app --shell /usr/sbin/nologin portal \
    && mkdir -p /data \
    && chown portal:portal /data
VOLUME /data

ENV CTF_DB_PATH=/data/portal.db \
    PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000

USER portal
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
