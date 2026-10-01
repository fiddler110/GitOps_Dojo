# PowerDNS API gate (see gate.py). Stdlib-only Python; it checks Forgejo's
# RS256 tokens itself, so no openssl or extra packages.
FROM docker.io/library/python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111
WORKDIR /app
COPY gate.py events.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER nobody
EXPOSE 8081
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8081/healthz || exit 1
CMD ["python3", "/app/gate.py"]
