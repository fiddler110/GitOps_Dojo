# Dojo Cloud control plane. Stdlib-only Python plus openssl (private CA).
FROM docker.io/library/python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72
RUN apk add --no-cache openssl
WORKDIR /app
COPY auth.py events.py policy.py policy_engine.py policy_api.py docker_api.py state.py pki.py portal_api.py tfstate.py server.py /app/
COPY _shared/ /app/_shared/
# The Dojo Portal single-page app (served by portal_api.py from PORTAL_DIR, default /app/portal).
COPY portal/ /app/portal/
# Unit tests ride along so `podman exec ... python -m unittest` works in the image.
COPY test_policy_auth.py test_policy_engine.py test_policy_api.py test_executor.py test_events.py test_portal_api.py test_tfstate.py /app/
ENV PYTHONUNBUFFERED=1
# Needs to bind :443 (the provider connects to https://<host> with no port) and
# talk to the shared docker.sock; the compose overlay drops every other capability.
EXPOSE 443 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
CMD ["python3", "/app/server.py"]
