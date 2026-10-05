# ctf-host — the boxed Docker-in-Docker daemon the CTF range runs its target
# slots inside (decision CTF-D21, spike S14). It is the `cloud-host` pattern
# from dojo-cloud: privileged is acceptable ONLY because it sits on an
# `internal: true` network with no route to the internet, to students, to the
# gateway or to Forgejo; it publishes nothing to the host; and its only client
# is ctf-controller, over a unix socket in a shared volume. Students never
# speak Docker.
#
# The target image is built INTO this image at build time (network is available
# then) and imported into the inner daemon at start (offline, nothing pulled at
# lab time) — exactly how cloud-host handles dojo/hello. The build context is
# the module root (modules/ctf-range) so this can COPY the target's source; see
# the overlay's `build.context`.
#
# A rebuilt customer-portal image (ctf-builder, after a student's merged fix)
# still has a `FROM python:3.12-slim@sha256:...` of its own, and that build
# runs with pull=0 (CTF-D24 offline posture — no network at lab runtime). So
# the base image itself, not just the target's flattened rootfs below, has to
# already be sitting in the inner dockerd's image store before ctf-builder
# ever runs. The `base-image-fetch` stage below fetches it as a real,
# multi-layer, digest-addressable archive — at THIS image's build time, same
# as the `pip install` in the `portal` stage, i.e. with network available and
# nothing pulled at lab time — and entrypoint.sh loads that archive into the
# inner daemon at start.

# --- the target's filesystem: a ready-to-run customer-portal rootfs ----------
# Mirrors targets/customer-portal/Dockerfile (same deps, same non-root user) so
# the imported image behaves like the standalone one.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS portal
COPY targets/customer-portal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/customer-portal/app.py targets/customer-portal/seed.py targets/customer-portal/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh \
    && useradd --uid 10014 --no-create-home --home-dir /app --shell /usr/sbin/nologin portal \
    && mkdir -p /data \
    && chown portal:portal /data

# --- the target's one dependency, vendored for ctf-builder's offline rebuild -
# ctf-builder rebuilds the student's merged customer-portal fix inside THIS
# image's inner dockerd, which sits on ctf_ops (internal: true, CTF-D24) — no
# route to PyPI at lab runtime. So `pip install -r requirements.txt` has to
# already be satisfied before that rebuild's `RUN pip install` ever runs. This
# stage vendors Flask at THIS image's build time (network available then,
# same trade as the `portal` stage's own `pip install` above) into a rootfs
# that gets imported into the inner daemon at start as
# gitopsdojo/ctf-customer-portal-base:pinned, which
# targets/customer-portal/Dockerfile now FROMs instead of installing Flask
# itself — see docs/CTF-SPIKES.md S6 "Scoped" (2026-10-05).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS portal-deps
COPY targets/customer-portal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# --- the base image, as a loadable archive, for ctf-builder's rebuilds ------
# skopeo pinned by digest (quay.io/skopeo/stable). The digest copied below
# MUST stay in sync with targets/customer-portal/Dockerfile's `FROM` line (and
# the `portal` stage above) by hand — this is not yet wired into RV25's
# check-tool-pins.sh; that's a follow-up, out of scope here.
#
# Two things proven live (2026-10-05), neither obvious from the docs:
#   * `docker://name:tag@digest` is rejected by skopeo ("both a tag and a
#     digest") — the source reference must drop the tag and keep only the
#     digest.
#   * The digest here (like most Hub pins) is a multi-arch INDEX digest, not
#     a single-platform manifest digest. `docker-archive` can only ever hold
#     one flattened platform image, so it comes out with a DIFFERENT content
#     digest than the pin — `FROM image@sha256:<index-digest>` then can't
#     resolve locally no matter what name/tag it is loaded under (confirmed
#     live: `ctr images tag` and `docker tag` aliases do NOT satisfy it;
#     resolution needs a blob whose own sha256 IS that digest). `oci-archive`
#     with `--multi-arch all` keeps the real index bytes (and so the real
#     index digest) alongside every platform's manifest+layers, and giving
#     the destination an explicit `:docker.io/library/python:3.12-slim` name
#     makes `docker image load` register that NAME at the index digest
#     (proven: `docker image inspect python:3.12-slim` then reports image ID
#     `02108f5d...`, and a `FROM ...@sha256:02108f5d...` build resolves with
#     no network at all).
#
#   * `--multi-arch all` fetches all 16 platforms' blobs (~370MB) even though
#     only amd64 (the one platform this stack ever runs) is ever used — dead
#     weight re-loaded into the inner dockerd on every ctf-host start. Live-
#     verified (2026-10-05) hand-built fix: `skopeo copy --multi-arch
#     index-only` on its own gets the REAL multi-arch index.json (same bytes,
#     same index digest `02108f5d...`) with NO blob data at all; a second
#     `skopeo copy --multi-arch system` gets just the amd64 manifest + its
#     layer/config blobs (flattened, into its own OCI layout). Merging the
#     first's `index.json`/`oci-layout` with the second's `blobs/sha256/*`
#     (plus the index-only copy's one blob, the manifest-list itself) yields
#     an OCI layout that lists all 16 platforms by digest but only actually
#     contains blob data for amd64. `docker image load` accepts this
#     perfectly well — it never needs to resolve blobs for platforms it isn't
#     asked to run — and the loaded image's ID/RepoDigest is the exact same
#     `sha256:02108f5d...` index digest (confirmed with `docker image
#     inspect`), and an offline `docker build --network=none` with `FROM
#     python:3.12-slim@sha256:02108f5d...` still resolves with zero network
#     calls. Archive shrinks from 384MB to 46MB, and in a standalone
#     docker:29.8.1-dind timing (same engine version this stage's image
#     runs), `docker image load` dropped from ~58s to ~6-17s for this one
#     image — the fetch below only ever touches amd64 bytes, so the
#     student-facing ~3min startup cost shrinks accordingly.
FROM quay.io/skopeo/stable@sha256:dcb473551681437c514d5eabd9d01f7f69d5be1218d36b9be3ad1a40e5add9e4 AS base-image-fetch
RUN set -eux; \
    mkdir -p /tmp/idx-only /tmp/amd64-only /out/merged/blobs/sha256; \
    skopeo copy --multi-arch index-only \
      docker://docker.io/library/python@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d \
      oci:/tmp/idx-only:docker.io/library/python:3.12-slim; \
    skopeo copy --multi-arch system \
      docker://docker.io/library/python@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d \
      oci:/tmp/amd64-only:docker.io/library/python:3.12-slim; \
    cp /tmp/idx-only/index.json /tmp/idx-only/oci-layout /out/merged/; \
    cp /tmp/idx-only/blobs/sha256/* /tmp/amd64-only/blobs/sha256/* /out/merged/blobs/sha256/; \
    tar -C /out/merged -cf /out/python-3.12-slim.tar .

# --- the range host itself ----------------------------------------------------
FROM docker.io/library/docker:29.8.1-dind@sha256:3f3c01aaaebf7cce837356b688b7c059a4749f10bd7660dec7c58fc454a283f0

# docker:dind's entrypoint also opens an UNAUTHENTICATED tcp://0.0.0.0:2375
# listener when TLS is off. We only ever want the unix socket (shared with
# ctf-controller), so remove it and fail the build if the upstream script
# changes shape and the removal stops working (identical guard to cloud-host).
RUN sed -i '/--host=tcp:\/\/0.0.0.0:2375/d' /usr/local/bin/dockerd-entrypoint.sh \
    && ! grep -q -- '--host=tcp://0.0.0.0:2375' /usr/local/bin/dockerd-entrypoint.sh \
    && grep -q -- '--host="$dockerSocket"' /usr/local/bin/dockerd-entrypoint.sh

COPY --from=portal / /opt/portal-rootfs/
COPY --from=portal-deps / /opt/portal-deps-rootfs/
COPY --from=base-image-fetch /out/python-3.12-slim.tar /opt/base-images/python-3.12-slim.tar
COPY ctf-host/entrypoint.sh /usr/local/bin/ctf-host-entrypoint
RUN chmod 0755 /usr/local/bin/ctf-host-entrypoint

# Socket dir shared with ctf-controller (a named volume in the overlay).
ENV DOCKER_HOST=unix:///run/ctf/docker.sock \
    DOCKER_TLS_CERTDIR=
ENTRYPOINT ["ctf-host-entrypoint"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect ctf-customer-portal:base >/dev/null 2>&1 || exit 1
