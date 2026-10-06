# policy-bypass — CTF target 9 (plan §7.3, CTF-4 "Trusting the wrong thing").
# See app.py's module docstring for the flaw; policy_engine.py is vendored
# verbatim from modules/dojo-cloud/cloud-api/policy_engine.py (its own header
# says why that's a copy, not a reimplementation, for this one file).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY policy_engine.py /app/policy_engine.py
COPY app.py /app/app.py

RUN useradd --uid 10025 --no-create-home --home-dir /app --shell /usr/sbin/nologin policybypass

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER policybypass
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
