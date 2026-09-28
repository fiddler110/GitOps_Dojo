# One-shot: creates the certs.dojo.test zone on dns-server and one A
# record per configured student pointing at demo-app, via PowerDNS's HTTP
# API. See seed.sh. Runs every `docker compose up`; idempotent.
FROM docker.io/library/alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc

RUN apk add --no-cache curl jq

COPY seed.sh /seed.sh
RUN chmod +x /seed.sh

ENTRYPOINT ["/seed.sh"]
