# ctf-flags — the flag submission service (plan §5). Pure stdlib Python,
# nothing to install and no network at build time. Holds a secret
# (STUDENT_PASSWORD_SEED) but no capability: no socket, no volume beyond its
# own code, reachable only on workshop_lab.
FROM docker.io/library/python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY service.py flags.py /app/
COPY _shared/ /app/_shared/
WORKDIR /app

RUN useradd --uid 10016 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf-flags
USER ctf-flags

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["python3", "/app/service.py"]
