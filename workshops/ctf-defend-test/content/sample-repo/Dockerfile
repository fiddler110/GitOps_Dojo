# customer-portal — CTF target 14. A minimal Flask + plaintext SQLite app,
# built from original source in this repo (§6). This is the harness's own
# seeded copy of modules/ctf-range/targets/customer-portal/Dockerfile — kept
# in manual sync by convention (see that file's header), not generated. The
# base is this project's own locally-built image (gitopsdojo/ prefix, no
# digest — never pulled from a registry, so check-pins.sh skips it), baked by
# ctf-host's `portal-deps` stage and imported into the inner dockerd at start.
# It already has Flask installed, so there is no `pip install` here — this
# matters because ctf-builder rebuilds THIS exact Dockerfile (cloned from
# this repo) inside ctf-host's inner, air-gapped dockerd (CTF-D24, no PyPI
# route at lab runtime). What has to stay in sync with this file's
# requirements.txt is NOT a digest here but ctf-host/Dockerfile's
# `portal-deps` stage — bump both together. See docs/CTF-SPIKES.md S6
# "Scoped" (2026-10-05).
FROM gitopsdojo/ctf-customer-portal-base:pinned

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
