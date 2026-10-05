# ping-tool — CTF target 4 (plan §7.3, CTF-2 "Server-side trust and APIs").
# See app.py's module docstring for the bug, the escalation stand-in, and
# why `host` (DNS lookup) replaces real `ping` here.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

RUN apt-get update && apt-get install -y --no-install-recommends dnsutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10019 --no-create-home --home-dir /app --shell /usr/sbin/nologin pingtool

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER pingtool
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
