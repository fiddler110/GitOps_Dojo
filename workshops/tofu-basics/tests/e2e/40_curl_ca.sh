#!/usr/bin/env bash
# shellcheck shell=bash
# Area curl_ca: Lab 4 step 4. As a student, plain `curl https://management.dojo.cloud/...` works WITHOUT -k because the
# broker puts CURL_CA_BUNDLE / SSL_CERT_FILE (a bundle of the system CAs plus Dojo Cloud's private CA) in the shell.
# Also proves the CA is what makes it work: without the variables curl refuses the certificate (exit 60, the
# `curl: (60) SSL certificate problem` row in Lab 4's troubleshooting table), and with -k the endpoint is reachable.
# Touches nothing in the cloud. Sourced by tests/e2e.sh; running this file directly hands over with --only curl_ca.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only curl_ca "$@"; fi

area_curl_ca() {
  local url='https://management.dojo.cloud/metadata/endpoints?api-version=2022-09-01'

  as_student "$STUDENT" 'echo "CURL_CA_BUNDLE=$CURL_CA_BUNDLE"; echo "SSL_CERT_FILE=$SSL_CERT_FILE"' 30 vars
  expect_has "the shell has CURL_CA_BUNDLE and SSL_CERT_FILE pointing at the bundle" \
    'CURL_CA_BUNDLE=/etc/dojo/ca-bundle.pem' 'SSL_CERT_FILE=/etc/dojo/ca-bundle.pem'
  as_student "$STUDENT" 'getent hosts management.dojo.cloud login.dojo.cloud graph.dojo.cloud portal.dojo.cloud | wc -l' 30 dns
  expect_eq "the four Dojo Cloud names resolve" 4 "$(head -n1 "$OUT")"

  as_student "$STUDENT" "curl -s -m 20 -o /dev/null -w '%{http_code}' '$url'; echo \" rc=\$?\"" 60 curl-plain
  expect_has "curl without -k gets 200 from the management endpoint (Lab 4 step 4)" '200 rc=0'
  as_student "$STUDENT" "curl -s -m 20 '$url' | python3 -m json.tool | head -4" 60 curl-json
  expect_has "the metadata document is what Lab 4 shows" \
    '"name": "dojocloud"' '"resourceManager": "https://management.dojo.cloud/"' '"microsoftGraphResourceId": "https://graph.dojo.cloud/"'

  as_student "$STUDENT" "env -u CURL_CA_BUNDLE -u SSL_CERT_FILE curl -s -m 20 -o /dev/null '$url'; echo \"rc=\$?\"" 60 curl-noca
  expect_has "without the bundle curl refuses the private CA (rc 60: the troubleshooting row in Lab 4)" 'rc=60'
  as_student "$STUDENT" "env -u CURL_CA_BUNDLE -u SSL_CERT_FILE curl -sk -m 20 -o /dev/null -w '%{http_code}' '$url'" 60 curl-k
  expect_has "with -k the endpoint answers, so the failure above is trust, not connectivity" '200'
  as_student "$STUDENT" "curl -s -m 10 -o /dev/null -w '%{http_code}' http://cloud-api:8080/readyz" 30 readyz
  expect_has "students can reach cloud-api:8080/readyz (the address Lab 5's troubleshooting box uses)" '200'
}
