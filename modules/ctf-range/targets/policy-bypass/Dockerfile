# policy-bypass — CTF target 9 (plan §7.3, CTF-4 "Trusting the wrong thing").
# See app.py's module docstring for the flaw; policy_engine.py is vendored
# verbatim from modules/dojo-cloud/cloud-api/policy_engine.py (its own header
# says why that's a copy, not a reimplementation, for this one file).
#
# BASE is this project's own locally-built Flask 3.0.3 image (the same one
# customer-portal uses, imported into ctf-host's inner dockerd at start): ctf-builder
# rebuilds this Dockerfile inside an air-gapped dockerd, so there is no `pip install`
# on the default path.
ARG BASE=topiary/ctf-customer-portal-base:pinned
FROM ${BASE}

COPY requirements.txt /app/requirements.txt

COPY policy_engine.py /app/policy_engine.py
COPY app.py /app/app.py
COPY proxy.py entrypoint.sh /app/

RUN useradd --uid 10025 --no-create-home --home-dir /app --shell /usr/sbin/nologin policybypass

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER policybypass
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
