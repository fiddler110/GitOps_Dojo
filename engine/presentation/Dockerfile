# Serves WORKSHOP_CONTENT_DIR/slides as HTML via Marp's server mode
# (`marp -s --http --html .`, see docker-compose.yml).
#
# Replaces the upstream marpteam/marp-cli image (~1.07 GB), whose bulk is a
# Chromium + LLVM + ffmpeg + fonts layer (~760 MB) that exists only for
# Marp's PDF / PPTX / PNG export. This stack only ever serves the rendered
# HTML slides to a browser -- nothing here exports -- and server mode never
# launches a browser to do that, so none of it is needed.
#
# Two stages: npm and yarn (~25 MB) are only needed to fetch marp-cli, not
# to run it, so the runtime stage takes just the `node` binary and the
# installed package. Both stages stay on the same Alpine release so the
# copied node binary sees the musl / libstdc++ it was built against.
ARG ALPINE_VERSION=3.24

FROM docker.io/library/node:22-alpine${ALPINE_VERSION} AS build
WORKDIR /opt/marp
# package.json names the same marp-cli release the upstream image was pinned
# to (so slide rendering -- themes, directives -- doesn't change with this
# image swap); package-lock.json pins every package beneath it by version and
# integrity hash, so two builds get the same files. `npm ci` refuses to run
# if the two disagree. To upgrade: edit the version in package.json, then
#   npm install --package-lock-only --omit=dev
# in this directory (any Node 22) and commit both files.
COPY package.json package-lock.json ./
# Source maps and TypeScript declarations (~23 MB across its dependency
# tree) are only ever read by debuggers and editors, never by node at
# runtime.
RUN npm ci --omit=dev --no-audit --no-fund \
    && npm cache clean --force \
    && find node_modules \( -name '*.map' -o -name '*.d.ts' \) -type f -delete

FROM docker.io/library/alpine:${ALPINE_VERSION}
# libstdc++ / libgcc: the only shared libraries node needs beyond musl.
RUN apk add --no-cache libstdc++
COPY --from=build /usr/local/bin/node /usr/local/bin/node
COPY --from=build /opt/marp /opt/marp

# Non-root, like the upstream image's MARP_USER=1000:1000. Slides are
# mounted read-only under /home/marp/app (docker-compose.yml) and server
# mode only reads them, so no writable home is needed. The account exists so
# uid 1000 has a passwd entry: without one, Node's os.userInfo() throws,
# which podman hides by adding an entry itself and Docker does not.
RUN adduser -D -u 1000 -h /home/marp marp
USER 1000:1000
WORKDIR /home/marp/app
EXPOSE 8080
ENTRYPOINT ["node", "/opt/marp/node_modules/@marp-team/marp-cli/marp-cli.js"]
