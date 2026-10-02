# Dojo Cloud control plane. Stdlib-only Python plus openssl (private CA).
FROM docker.io/library/python:3.12-alpine@sha256:4c47124a8391cb7a9f571164147d154777cf012a4ece5f86097130d7a4478111
RUN apk add --no-cache openssl
WORKDIR /app
COPY auth.py events.py policy.py docker_api.py state.py pki.py portal_api.py server.py /app/
COPY _shared/ /app/_shared/
# The Dojo Portal single-page app (served by portal_api.py from PORTAL_DIR, default /app/portal).
COPY portal/ /app/portal/
# Unit tests ride along so `podman exec ... python -m unittest` works in the image.
COPY test_policy_auth.py test_executor.py test_events.py test_portal_api.py /app/
ENV PYTHONUNBUFFERED=1
# Needs to bind :443 (the provider connects to https://<host> with no port) and
# talk to the shared docker.sock; the compose overlay drops every other capability.
EXPOSE 443 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
CMD ["python3", "/app/server.py"]
