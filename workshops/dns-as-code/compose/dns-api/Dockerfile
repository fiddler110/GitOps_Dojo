# PowerDNS API gate (see gate.py). Stdlib-only Python.
FROM docker.io/library/python:3.12-alpine
WORKDIR /app
COPY gate.py test_gate.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER nobody
EXPOSE 8081
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8081/healthz || exit 1
CMD ["python3", "/app/gate.py"]
