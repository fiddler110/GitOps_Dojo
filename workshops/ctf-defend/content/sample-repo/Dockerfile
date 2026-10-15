# customer-portal — CTF target 14. A minimal Flask + plaintext SQLite app,
# built from original source in this repo (§6). BASE defaults to this
# project's own locally-built image (gitopsdojo/ prefix, no digest — it is
# never pulled from a registry, so check-pins.sh skips it as "this project's
# own image"), baked by ctf-host's `portal-deps` stage and imported into the
# inner dockerd at start. It already has Flask installed, so this file never
# needs `pip install` — this matters because ctf-builder rebuilds this exact
# Dockerfile inside ctf-host's inner, air-gapped dockerd (CTF-D24, no PyPI
# route at lab runtime). What has to stay in sync with this file's
# requirements.txt is NOT a digest here but ctf-host/Dockerfile's
# `portal-deps` stage — bump both together. See docs/CTF-SPIKES.md S6
# "Scoped" (2026-10-05).
#
# ONE stage only, deliberately (found live 2026-10-15, CTF-D27): ctf-host's
# inner dockerd uses the classic (non-BuildKit) Engine API builder, which
# builds every FROM stage physically present in the Dockerfile, in file
# order, whether or not the final image's FROM ever resolves to it --
# unlike BuildKit/buildah, it does NOT prune stages the result doesn't
# depend on. An earlier version of this file kept a second `deps` stage
# (`FROM python:3.12-slim` + `pip install`) for Dockerfile.dev's benefit,
# reasoning that it would never be built offline since the default FROM
# never points at it; that reasoning was wrong for this builder. The
# `pip install` ran every time regardless, failed offline (no PyPI route),
# and failed ctf-builder's very first rebuild for every student. The dev-only
# path now lives entirely in `Dockerfile.dev`, built only on the OUTER host
# engine by modules/ctf-range/compose.yml's standalone `customer-portal`
# service; this file never contains a network-reaching stage at all.
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
