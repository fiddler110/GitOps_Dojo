FROM python:3.12-alpine

# Stdlib only -- no pip installs, matches this repo's minimal-deps convention.
COPY server.py /usr/local/bin/allocator-server.py

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

# Runs as root's default user (python:3.12-alpine's default) -- this
# service only ever talks to other containers over the internal git_lab
# network and holds no credentials, secrets, or host access.
CMD ["python3", "/usr/local/bin/allocator-server.py"]
