FROM docker.io/library/python:3.12-alpine

# Stdlib only -- no pip installs, matches this repo's minimal-deps convention.
COPY server.py /usr/local/bin/allocator-server.py
# Run once per ./run.sh start, in a throwaway container of this image, to
# check and render the workshop's extensions.json (see the script).
COPY render_extensions.py /usr/local/bin/render_extensions.py

EXPOSE 8080
# Must send X-Gateway-Token -- server.py now rejects every request
# (including this one) that lacks it (see server.py's gateway_authorized()),
# same pattern as web-terminal/Dockerfile's own HEALTHCHECK sending
# X-Control-Token to workspace-control.py.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null --header="X-Gateway-Token: ${GATEWAY_TOKEN}" http://127.0.0.1:8080/ || exit 1

# Runs as the image's default root user (python:3.12-alpine's default) --
# container-scoped root, not host root. server.py holds Forgejo admin
# credentials and the control-plane shared secret (CONTROL_TOKEN) in its
# environment, so this is not a low-value target -- it's reachable only
# from other containers on the internal workshop_lab Docker network, which
# has no published port and no host access.
CMD ["python3", "/usr/local/bin/allocator-server.py"]
