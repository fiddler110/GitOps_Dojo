# dns-resolver-cve — CTF target 6 (plan §7.3 row 6, CTF-3 "Vulnerable and
# outdated components", ties dns-as-code). See app.py's module docstring for
# the flaw (CVE-2022-30295 in uClibc / uClibc-ng ≤ 1.0.40). The ctf-host
# image bakes a flattened rootfs of this image's final stage into
# /opt/dns-resolver-cve-rootfs (ctf-host/Dockerfile), so this standalone
# Dockerfile is dev-only — a straight `docker build .` to exercise the target
# image on its own, mirroring targets/policy-bypass/Dockerfile et al.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS agent-build
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
    rm tc.tar.bz2
COPY agent.c /tmp/agent.c
RUN set -eux; \
    /opt/x86-64--uclibc--stable-2021.11-5/bin/x86_64-buildroot-linux-uclibc-gcc \
      -static -O2 -s -o /agent /tmp/agent.c; \
    test -s /agent && head -c 4 /agent | od -An -tx1 | grep -q '7f 45 4c 46'

FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY --from=agent-build /agent /app/agent
RUN chmod 0755 /app/agent \
    && useradd --uid 10026 --no-create-home --home-dir /app --shell /usr/sbin/nologin dnsresolver

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER dnsresolver
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
