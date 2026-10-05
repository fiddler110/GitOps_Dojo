# ctf-builder — the only thing allowed to ask ctf-host to build (spike S6).
# Stdlib Python plus git (to clone the student's own repo itself; nothing it
# builds or pushes ever comes from the caller directly — see builder.py's
# module docstring). Shares ctf-host's docker socket exactly as ctf-controller
# does: a named volume, granted only through compose's group_add of the
# socket's group (CTF_GID).
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY builder.py docker_build.py gitref.py /app/
WORKDIR /app

# A fixed non-root uid, distinct from ctf-controller's 10015. The socket
# group is granted at runtime (compose group_add CTF_GID); the image itself
# owns nothing privileged. HOME is a tmpfs mount (compose) so git never tries
# to read or write a global config on the read-only root.
RUN useradd --uid 10016 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf-builder
USER ctf-builder

ENV PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    GIT_CONFIG_NOSYSTEM=1
EXPOSE 9100
ENTRYPOINT ["python3", "/app/builder.py"]
