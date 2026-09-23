# One-shot: creates the certs.dojo.test zone on dns-server and one A
# record per configured student pointing at demo-app, via PowerDNS's HTTP
# API. See seed.sh. Runs every `docker compose up`; idempotent.
FROM docker.io/library/alpine:3.20

RUN apk add --no-cache curl jq

COPY seed.sh /seed.sh
RUN chmod +x /seed.sh

ENTRYPOINT ["/seed.sh"]
