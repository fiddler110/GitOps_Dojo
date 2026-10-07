# git-secrets — CTF target 8 (plan §7.3, CTF-3 "Secrets and misconfiguration",
# ties git-fundamentals). See app.py's module docstring: there is no bug in
# this image at all. The foothold is in Forgejo's git history
# (terminal/start.d/55-git-secrets.sh), not here.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10024 --no-create-home --home-dir /app --shell /usr/sbin/nologin gitsecrets

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
# 2222 is the decoy SSH listener app.py starts alongside the real app (plan
# §7.3's nmap primer) — see its module-bottom comment. Not a real sshd.
EXPOSE 5000 2222

USER gitsecrets
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
