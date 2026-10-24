# leaky-config — CTF target 5 (plan §7.3, CTF-3 "Secrets and misconfiguration").
# See app.py's module docstring for the flaw.
#
# BASE is this project's own locally-built Flask 3.0.3 image (the same one
# customer-portal uses, imported into ctf-host's inner dockerd at start): ctf-builder
# rebuilds this Dockerfile inside an air-gapped dockerd, so there is no `pip install`
# on the default path.
ARG BASE=topiary/ctf-customer-portal-base:pinned
FROM ${BASE}

COPY requirements.txt /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10023 --no-create-home --home-dir /app --shell /usr/sbin/nologin leakyconfig

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER leakyconfig
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
