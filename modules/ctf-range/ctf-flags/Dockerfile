# ctf-flags — the flag submission service (plan §5). Pure stdlib Python,
# nothing to install and no network at build time. Holds a secret
# (STUDENT_PASSWORD_SEED) but no capability: no socket, no volume beyond its
# own code, reachable only on workshop_lab.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

COPY service.py flags.py /app/
COPY _shared/ /app/_shared/
WORKDIR /app

RUN useradd --uid 10016 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf-flags
USER ctf-flags

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["python3", "/app/service.py"]
