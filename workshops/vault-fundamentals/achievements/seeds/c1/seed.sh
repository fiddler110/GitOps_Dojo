#!/bin/sh
# Sets up challenge c1 in YOUR namespace only. Safe to run twice. It prints paths, never values.
set -eu
BAO_NAMESPACE="students/{user}"
export BAO_NAMESPACE
bao secrets list | grep -q '^challenge/' || bao secrets enable -path=challenge kv-v2
# a new KV mount refuses writes for a moment while it upgrades: retry, as in Lab 9
n=0
until bao kv get challenge/one >/dev/null 2>&1 || bao kv put challenge/one value=alpha-$(date +%s) >/dev/null 2>&1; do
  n=$((n + 1)); [ "$n" -lt 15 ] || { echo "challenge/ isn't taking writes yet: run this again in a minute" >&2; exit 1; }
  sleep 2
done
bao kv get challenge/two >/dev/null 2>&1 || bao kv put challenge/two value=bravo-$(date +%N) >/dev/null
bao auth list | grep -q '^approle/' || bao auth enable approle
bao write auth/approle/role/buddy-{user} token_ttl=15m >/dev/null
echo "ready: secrets challenge/one and challenge/two, AppRole buddy-{user} with no policy"
