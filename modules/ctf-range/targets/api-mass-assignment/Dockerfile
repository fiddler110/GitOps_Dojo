# api-mass-assignment — CTF target 12 (plan §7.3, CTF-2, API-only). See
# app.py's module docstring for the bug.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10021 --no-create-home --home-dir /app --shell /usr/sbin/nologin massassign

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER massassign
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
