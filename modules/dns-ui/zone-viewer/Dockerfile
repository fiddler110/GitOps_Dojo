# Read-only zone viewer for the workshop's PowerDNS. Stdlib-only Python.
FROM docker.io/library/python:3.12-alpine
WORKDIR /app
COPY server.py /app/
COPY static/ /app/static/
# Unit tests ride along so `podman exec ... python -m unittest` works in the image.
COPY test_server.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Holds nothing secret (the PowerDNS key is the workshop's shared one, also in
# the sample repo's creds.json), but there's no reason to run as root.
USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080${PATH_PREFIX}/healthz || exit 1
CMD ["python3", "/app/server.py"]
