# ctf-controller — the unprivileged control plane for the CTF range. Pure
# stdlib Python, so there is nothing to install and no network at build or run
# time. It holds no capability of its own: its only power is the ctf-host
# docker socket, shared through a named volume and reachable only because
# compose group_add's it into the socket's group (CTF_GID), exactly as
# cloud-api is the sole member of cloud-host's socket group.
FROM python:3.12-slim

COPY controller.py docker_api.py flags.py /app/
WORKDIR /app

# A fixed non-root uid. The socket group is granted at runtime (compose
# group_add CTF_GID); the image itself owns nothing privileged.
RUN useradd --uid 10015 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf
USER ctf

ENV PYTHONUNBUFFERED=1
EXPOSE 9000
ENTRYPOINT ["python3", "/app/controller.py"]
