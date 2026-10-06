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

# --- the attack-ladder targets' filesystems (CTF-1/CTF-2, plan §7.3) --------
# Unlike customer-portal above, none of these is ever rebuilt by ctf-builder
# (students attack them, they don't patch and redeploy them — see each
# target's own Dockerfile comment), so there is no offline-rebuild dependency
# to vendor for them: a flattened rootfs import is the whole story, same base
# image digest as portal/portal-deps above (already proven droppable into
# `docker import`, no FROM resolution needed at import time). Each stage
# mirrors its targets/<name>/Dockerfile exactly (same deps, same uid, same
# EXPOSE set including the decoy ports — see controller.py's Config.attack_ports
# and each app.py's decoy-listener comment).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS sqli-login
COPY targets/sqli-login/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/sqli-login/app.py /app/app.py
RUN useradd --uid 10015 --no-create-home --home-dir /app --shell /usr/sbin/nologin sqli

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS idor-pcap
COPY targets/idor-pcap/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/idor-pcap/app.py /app/app.py
RUN useradd --uid 10016 --no-create-home --home-dir /app --shell /usr/sbin/nologin idor

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS weak-auth-portal
COPY targets/weak-auth-portal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/weak-auth-portal/app.py /app/app.py
RUN useradd --uid 10017 --no-create-home --home-dir /app --shell /usr/sbin/nologin weakauth

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS cert-trust-bypass
COPY targets/cert-trust-bypass/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/cert-trust-bypass/app.py /app/app.py
RUN useradd --uid 10018 --no-create-home --home-dir /app --shell /usr/sbin/nologin certbypass

# ping-tool alone needs `host` (dnsutils) on PATH — see its app.py docstring
# for why a DNS lookup stands in for real `ping` under this range's global
# CapDrop (no raw ICMP socket is possible here regardless).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS ping-tool
RUN apt-get update && apt-get install -y --no-install-recommends dnsutils \
    && rm -rf /var/lib/apt/lists/*
COPY targets/ping-tool/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/ping-tool/app.py /app/app.py
RUN useradd --uid 10019 --no-create-home --home-dir /app --shell /usr/sbin/nologin pingtool

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS ssrf-fetcher
COPY targets/ssrf-fetcher/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/ssrf-fetcher/app.py /app/app.py
RUN useradd --uid 10020 --no-create-home --home-dir /app --shell /usr/sbin/nologin ssrffetcher

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS api-mass-assignment
COPY targets/api-mass-assignment/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/api-mass-assignment/app.py /app/app.py
RUN useradd --uid 10021 --no-create-home --home-dir /app --shell /usr/sbin/nologin massassign

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS api-bfla
COPY targets/api-bfla/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/api-bfla/app.py /app/app.py
RUN useradd --uid 10022 --no-create-home --home-dir /app --shell /usr/sbin/nologin apibfla

# leaky-config — CTF-3 "Secrets and misconfiguration" (plan §7.3 row 5), not
# yet in a real session pack (CTF-3/CTF-4 stay on the shared full-catalog
# stage below until that pack work happens — see CTF-D26).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS leaky-config
COPY targets/leaky-config/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/leaky-config/app.py /app/app.py
RUN useradd --uid 10023 --no-create-home --home-dir /app --shell /usr/sbin/nologin leakyconfig

# git-secrets — CTF-3, ties git-fundamentals (plan §7.3 row 8). No bug in
# this image at all; the foothold is in Forgejo's git history
# (terminal/start.d/55-git-secrets.sh), not here — see app.py's docstring.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS git-secrets
COPY targets/git-secrets/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/git-secrets/app.py /app/app.py
RUN useradd --uid 10024 --no-create-home --home-dir /app --shell /usr/sbin/nologin gitsecrets

# policy-bypass — CTF-4 "Trusting the wrong thing" (plan §7.3 row 9), ties
# cloud-policy-as-code. No bug in how the rule is evaluated
# (policy_engine.py is vendored verbatim from modules/dojo-cloud/cloud-api/)
# — the deployed rule itself is wrong. See app.py's docstring.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS policy-bypass
COPY targets/policy-bypass/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/policy-bypass/policy_engine.py targets/policy-bypass/app.py /app/
RUN useradd --uid 10025 --no-create-home --home-dir /app --shell /usr/sbin/nologin policybypass

# dns-resolver-cve agent build (target 6, CTF-3 "Vulnerable and outdated
# components", ties dns-as-code; plan §7.3 row 6). CVE-2022-30295: uClibc /
# uClibc-ng ≤ 1.0.40's stub resolver assigns monotonically-increasing DNS
# transaction IDs — settled empirically on 2026-10-06 against the pinned
# toolchain below (docs/CTF-SPIKES.md "Target 6" addendum; TXIDs ran
# 2,3,4,...,21 strictly +1 across 20 getaddrinfo calls; source ports were
# kernel-ephemeral, not static as earlier writeups claimed).
#
# The agent is a tiny static ELF cross-compiled against that libc so the real
# CVE lives in the one process the lab resolves through — not a Python
# simulation. The 125 MB Bootlin tarball is pulled, verified, used ONCE for
# this one gcc invocation, and the whole build stage is discarded; only the
# ~150 KB /agent binary is copied into the runtime stage below. The project's
# "pin by digest" rule applies at the tarball level here (sha256 of
# toolchain.tar.bz2); the toolchain itself bundles buildroot-pinned uClibc-ng
# 1.0.39 (summary.csv in the tarball).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS dns-resolver-cve-agent-build
ARG TOOLCHAIN_URL=https://toolchains.bootlin.com/downloads/releases/toolchains/x86-64/tarballs/x86-64--uclibc--stable-2021.11-5.tar.bz2
ARG TOOLCHAIN_SHA256=e68fd1b23f4a5c5132f2122e4012c17eb24e5179b2ff45bb793a27ac30dd454f
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates bzip2 \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    cd /opt; \
    curl -sfL -o tc.tar.bz2 "$TOOLCHAIN_URL"; \
    echo "$TOOLCHAIN_SHA256  tc.tar.bz2" | sha256sum -c -; \
    tar xjf tc.tar.bz2; \
    rm tc.tar.bz2; \
    grep -q 'uclibc.*1\.0\.39' /opt/x86-64--uclibc--stable-2021.11-5/summary.csv
COPY targets/dns-resolver-cve/agent.c /tmp/agent.c
RUN set -eux; \
    /opt/x86-64--uclibc--stable-2021.11-5/bin/x86_64-buildroot-linux-uclibc-gcc \
      -static -O2 -s -o /agent /tmp/agent.c; \
    test -s /agent && head -c 4 /agent | od -An -tx1 | grep -q '7f 45 4c 46'

# dns-resolver-cve runtime rootfs: python:3.12-slim + Flask + the static
# agent above + the on-box lab plumbing (see targets/dns-resolver-cve/app.py's
# module docstring for why the attacker's observe-and-spoof is modelled on
# loopback inside this one container, not across ctf_net — the inner dockerd's
# --icc=false topology forbids a real cross-slot off-path attack).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS dns-resolver-cve
COPY targets/dns-resolver-cve/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/dns-resolver-cve/app.py /app/app.py
COPY --from=dns-resolver-cve-agent-build /agent /app/agent
RUN chmod 0755 /app/agent \
    && useradd --uid 10026 --no-create-home --home-dir /app --shell /usr/sbin/nologin dnsresolver

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
# range-base: everything every pack's ctf-host image needs regardless of
# which attack-ladder targets it bakes in (CTF-D26). A final stage below
# FROMs this and COPYs in only its own pack's target rootfses — BuildKit
# then never even builds the stages a pack doesn't reference (not "baked but
# skipped at import", genuinely absent: zero extra build time, zero extra
# image bytes for a scoped pack).
FROM docker.io/library/docker:29.8.1-dind@sha256:3f3c01aaaebf7cce837356b688b7c059a4749f10bd7660dec7c58fc454a283f0 AS range-base

# dnsmasq, for entrypoint.sh's fake-DNS stub (see its own comment): a fast,
# local, always-reachable DNS responder for the inner dockerd's embedded
# per-container resolver to forward to, since ctf_ops/ctf_net are both
# `internal: true` (CTF-D24) and so have no real resolver to reach at all.
# apk at THIS image's build time, same offline-at-lab-time trade as every
# other network-needing step above.
RUN apk add --no-cache dnsmasq

# docker:dind's entrypoint also opens an UNAUTHENTICATED tcp://0.0.0.0:2375
# listener when TLS is off. We only ever want the unix socket (shared with
# ctf-controller), so remove it and fail the build if the upstream script
# changes shape and the removal stops working (identical guard to cloud-host).
RUN sed -i '/--host=tcp:\/\/0.0.0.0:2375/d' /usr/local/bin/dockerd-entrypoint.sh \
    && ! grep -q -- '--host=tcp://0.0.0.0:2375' /usr/local/bin/dockerd-entrypoint.sh \
    && grep -q -- '--host="$dockerSocket"' /usr/local/bin/dockerd-entrypoint.sh

COPY ctf-host/entrypoint.sh /usr/local/bin/ctf-host-entrypoint
RUN chmod 0755 /usr/local/bin/ctf-host-entrypoint

# Socket dir shared with ctf-controller (a named volume in the overlay).
ENV DOCKER_HOST=unix:///run/ctf/docker.sock \
    DOCKER_TLS_CERTDIR=
ENTRYPOINT ["ctf-host-entrypoint"]

# --- ctf-host: the full catalog (default `docker build` target, no --target
# needed) — used by the shared workshops/ctf-defend-test harness, which
# deliberately wants every target in one image (module.env's comment on
# CTF_ATTACK_TARGETS). entrypoint.sh's import_* functions each guard on
# their own rootfs directory existing, so this is the only stage where every
# guard actually fires.
FROM range-base AS ctf-host
COPY --from=portal / /opt/portal-rootfs/
COPY --from=portal-deps / /opt/portal-deps-rootfs/
COPY --from=base-image-fetch /out/python-3.12-slim.tar /opt/base-images/python-3.12-slim.tar
COPY --from=sqli-login / /opt/sqli-login-rootfs/
COPY --from=idor-pcap / /opt/idor-pcap-rootfs/
COPY --from=weak-auth-portal / /opt/weak-auth-portal-rootfs/
COPY --from=cert-trust-bypass / /opt/cert-trust-bypass-rootfs/
COPY --from=ping-tool / /opt/ping-tool-rootfs/
COPY --from=ssrf-fetcher / /opt/ssrf-fetcher-rootfs/
COPY --from=api-mass-assignment / /opt/api-mass-assignment-rootfs/
COPY --from=api-bfla / /opt/api-bfla-rootfs/
COPY --from=leaky-config / /opt/leaky-config-rootfs/
COPY --from=git-secrets / /opt/git-secrets-rootfs/
COPY --from=policy-bypass / /opt/policy-bypass-rootfs/
COPY --from=dns-resolver-cve / /opt/dns-resolver-cve-rootfs/
# The compose service's own healthcheck (modules/ctf-range/compose.yml) uses
# CTF_HOST_EXPECTED_IMAGES and checks every baked tag; this one is a fallback
# for a standalone `docker run` of this image alone.
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect ctf-customer-portal:base >/dev/null 2>&1 || exit 1

# --- ctf-host-ctf1: CTF-1 "Access and identity" only (targets 0,1,2,3 —
# sqli-login, idor-pcap, weak-auth-portal, cert-trust-bypass). None of these
# is ever rebuilt (students attack, never patch, them), so this pack needs no
# customer-portal/ctf-builder plumbing at all — scoped to exactly its own 4
# rootfses, nothing else. `docker build --target ctf-host-ctf1`.
FROM range-base AS ctf-host-ctf1
COPY --from=sqli-login / /opt/sqli-login-rootfs/
COPY --from=idor-pcap / /opt/idor-pcap-rootfs/
COPY --from=weak-auth-portal / /opt/weak-auth-portal-rootfs/
COPY --from=cert-trust-bypass / /opt/cert-trust-bypass-rootfs/
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect ctf-sqli-login:base >/dev/null 2>&1 || exit 1

# --- ctf-host-ctf2: CTF-2 "Server-side trust and APIs" only (targets 4,7,12,
# 13 — ping-tool, ssrf-fetcher, api-mass-assignment, api-bfla). Same shape as
# ctf-host-ctf1 above. `docker build --target ctf-host-ctf2`.
FROM range-base AS ctf-host-ctf2
COPY --from=ping-tool / /opt/ping-tool-rootfs/
COPY --from=ssrf-fetcher / /opt/ssrf-fetcher-rootfs/
COPY --from=api-mass-assignment / /opt/api-mass-assignment-rootfs/
COPY --from=api-bfla / /opt/api-bfla-rootfs/
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect ctf-ping-tool:base >/dev/null 2>&1 || exit 1
