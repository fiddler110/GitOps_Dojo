# cert-trust-bypass — CTF target 3 (plan §7.3, CTF-1, ties cert-autorenewal).
# See app.py's module docstring for the flaw and why this is plain HTTP.
FROM docker.io/library/python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10018 --no-create-home --home-dir /app --shell /usr/sbin/nologin certbypass

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER certbypass
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
