# PowerDNS API gate (see gate.py). Stdlib-only Python; it checks Forgejo's
# RS256 tokens itself, so no openssl or extra packages.
FROM docker.io/library/python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72
WORKDIR /app
COPY gate.py events.py reset.py /app/
COPY _shared/ /app/_shared/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER nobody
EXPOSE 8081
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8081/healthz || exit 1
CMD ["python3", "/app/gate.py"]
