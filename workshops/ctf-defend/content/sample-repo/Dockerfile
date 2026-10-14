# customer-portal — CTF target 14. A minimal Flask + plaintext SQLite app,
# built from original source in this repo (§6). BASE defaults to this
# project's own locally-built image (gitopsdojo/ prefix, no digest — it is
# never pulled from a registry, so check-pins.sh skips it as "this project's
# own image"), baked by ctf-host's `portal-deps` stage and imported into the
# inner dockerd at start. It already has Flask installed, so the default path
# has no `pip install` — this matters because ctf-builder rebuilds this exact
# Dockerfile inside ctf-host's inner, air-gapped dockerd (CTF-D24, no PyPI
# route at lab runtime). What has to stay in sync with this file's
# requirements.txt is NOT a digest here but ctf-host/Dockerfile's
# `portal-deps` stage — bump both together. See docs/CTF-SPIKES.md S6
# "Scoped" (2026-10-05).
#
# The `deps` stage below exists ONLY for modules/ctf-range/compose.yml's
# standalone dev-path `customer-portal` service, which builds this file on
# the OUTER host engine (real network at build time) instead of inside
# ctf-host's inner dockerd — so it has no local copy of the gitopsdojo/
# tag (that tag is only ever imported into the INNER dockerd, never pushed or
# built on the outer host). That service passes `--build-arg BASE=deps` to
# get Flask the normal way instead. buildah only builds a stage the selected
# FROM actually resolves to, so the default (offline) path never builds or
# touches `deps` at all — zero extra cost, same mechanism as the terminal
# images' `ARG BASE=...` / `FROM ${BASE}` convention elsewhere in this repo.
ARG BASE=gitopsdojo/ctf-customer-portal-base:pinned

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM ${BASE}

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
