# ssrf-fetcher — CTF target 7 (plan §7.3, CTF-2 "Server-side trust and
# APIs"). Runs two Flask apps in one process (public + loopback-only
# internal) — see app.py's module docstring for why that's how this
# target's internal admin service is modeled under the one-published-port
# architecture.
FROM docker.io/library/python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10020 --no-create-home --home-dir /app --shell /usr/sbin/nologin ssrffetcher

ENV PORT=5000 \
    INTERNAL_PORT=5001 \
    PYTHONUNBUFFERED=1
# 5001 (loopback-only, never published — see app.py) isn't exposed here on
# purpose. 2222 is the decoy SSH listener app.py starts alongside the
# public app (plan §7.3's nmap primer) — not a real sshd.
EXPOSE 5000 2222

USER ssrffetcher
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
