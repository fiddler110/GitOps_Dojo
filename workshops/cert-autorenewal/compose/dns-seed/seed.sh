#!/bin/sh
# Creates the workshop's DNS zone and one A record per configured student
# via PowerDNS's HTTP API (https://doc.powerdns.com/authoritative/http-api/).
# Runs once per `docker compose up`; safe to re-run (a 409 on zone creation
# or a REPLACE on an existing rrset are both no-ops in effect).
#
# This makes http-01 (Labs 1-4) work without a DNS-editing step being a
# prerequisite. Lab 5 (the dns-01 capstone) is where students edit records
# themselves, against this same zone.
set -eu

ZONE="${CERT_LAB_ZONE:-certs.dojo.test}."
API_BASE="http://dns-server:8081/api/v1/servers/localhost"
API_KEY="${POWERDNS_API_KEY:-workshop-not-a-secret}"
STUDENT_COUNT="${STUDENT_COUNT:-30}"
STUDENT_PREFIX="${STUDENT_PREFIX:-student}"
DEMO_APP_IP="${DEMO_APP_IP:-172.30.0.20}"

# Wait for PowerDNS's API to be reachable.
for _ in $(seq 1 30); do
  if curl -sf -H "X-API-Key: ${API_KEY}" "${API_BASE}/zones" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "cert-autorenewal dns-seed: ensuring zone ${ZONE}"
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json" \
  -X POST "${API_BASE}/zones" \
  -d "$(jq -n --arg zone "${ZONE}" '{name: $zone, kind: "Native", nameservers: ["ns1." + $zone]}')" \
  | grep -qE '^(201|409|500)$' || echo "cert-autorenewal dns-seed: unexpected zone-create response"

i=1
while [ "${i}" -le "${STUDENT_COUNT}" ]; do
  num=$(printf '%02d' "${i}")
  host="${STUDENT_PREFIX}${num}.${ZONE}"
  echo "cert-autorenewal dns-seed: A ${host} -> ${DEMO_APP_IP}"
  curl -sf -H "X-API-Key: ${API_KEY}" -H "Content-Type: application/json" \
    -X PATCH "${API_BASE}/zones/${ZONE}" \
    -d "$(jq -n --arg name "${host}" --arg ip "${DEMO_APP_IP}" '{
          rrsets: [{
            name: $name, type: "A", ttl: 60, changetype: "REPLACE",
            records: [{content: $ip, disabled: false}]
          }]
        }')" >/dev/null
  i=$((i + 1))
done

echo "cert-autorenewal dns-seed: done (${STUDENT_COUNT} student records)"
