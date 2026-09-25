# Shared demo web app. Isolation between students is per-file ownership on
# the mounted cert_lab_webroot volume (see docker-compose.override.yml),
# not per-container — same "shared backend, per-file ownership" pattern
# dns-as-code uses for its shared DNS zone file. entrypoint.sh watches that
# volume and reloads nginx when a student adds or changes their vhost/certs,
# since students only ever get filesystem access to their own subdirectory
# of it (from inside web-terminal), never a way to reach into this
# container directly — no docker.sock, no cross-container exec, consistent
# with the allocator's existing no-docker.sock design principle.
FROM docker.io/library/nginx:1.27-alpine

RUN apk add --no-cache inotify-tools

# Sticky-bit shared directory (same mechanism as /tmp): any student can
# `mkdir /srv/webroot/$(whoami)` themselves — no sudo, no UID coordination
# with the student-account creation in engine/web-terminal/entrypoint.sh
# needed — and, because of the sticky bit, no student can touch a
# directory another student created. Pre-created here so a fresh, empty
# named volume gets these permissions the moment it's first populated from
# this image (Docker/Podman copy an image's existing content, permissions
# included, into an empty named volume on first mount); entrypoint.sh
# re-asserts it defensively on every start too.
RUN mkdir -p /srv/webroot && chmod 1777 /srv/webroot

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
