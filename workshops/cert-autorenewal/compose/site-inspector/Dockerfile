# Site Inspector for the cert-autorenewal workshop: a browser's view of a student's site on demo-app (see
# server.py). Stdlib-only Python.
FROM docker.io/library/python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111
WORKDIR /app
COPY server.py /app/
COPY static/ /app/static/
# Unit tests ride along so `podman exec ... python -m unittest` works in the image.
COPY test_server.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
CMD ["python3", "/app/server.py"]
