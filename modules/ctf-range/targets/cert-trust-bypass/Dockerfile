# cert-trust-bypass — CTF target 3 (plan §7.3, CTF-1, ties cert-autorenewal).
# See app.py's module docstring for the flaw and why this is plain HTTP.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10018 --no-create-home --home-dir /app --shell /usr/sbin/nologin certbypass

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000

USER certbypass
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
