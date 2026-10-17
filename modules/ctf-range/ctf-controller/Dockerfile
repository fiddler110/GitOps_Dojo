# ctf-controller — the unprivileged control plane for the CTF range. Pure
# stdlib Python, so there is nothing to install and no network at build or run
# time. It holds no capability of its own: its only power is the ctf-host
# docker socket, shared through a named volume and reachable only because
# compose group_add's it into the socket's group (CTF_GID), exactly as
# cloud-api is the sole member of cloud-host's socket group.
FROM docker.io/library/python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

COPY controller.py docker_api.py flags.py schedule.py view.py /app/
COPY _shared/ /app/_shared/
# The attack-range card's page shell (plan §4, CTF-D20) — static assets only,
# served by controller.py itself; nothing here talks to ctf-host.
COPY static/ /app/static/
WORKDIR /app

# A fixed non-root uid. The socket group is granted at runtime (compose
# group_add CTF_GID); the image itself owns nothing privileged.
RUN useradd --uid 10015 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf
USER ctf

ENV PYTHONUNBUFFERED=1
EXPOSE 9000
ENTRYPOINT ["python3", "/app/controller.py"]
