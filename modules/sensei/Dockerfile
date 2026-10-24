# Sensei: the allocator image (Python, no extras) plus git, for the one thing Forgejo's API
# can't do: merge a stale branch's base into it and resolve the roster conflict.
# The allocator image ends as a non-root user; apk needs root, and compose.yml
# runs sensei as 0:0 with every capability dropped anyway.
FROM topiary/allocator:local
USER root
RUN apk add --no-cache git
