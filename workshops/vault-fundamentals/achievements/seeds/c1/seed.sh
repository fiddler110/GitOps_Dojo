#!/bin/sh
# Sets up challenge c1 in YOUR namespace only. Safe to run twice. It prints paths, never values.
set -eu
BAO_NAMESPACE="students/$USER"
export BAO_NAMESPACE
bao secrets list | grep -q '^challenge/' || bao secrets enable -path=challenge kv-v2
bao kv get challenge/one >/dev/null 2>&1 || bao kv put challenge/one value=alpha-$RANDOM >/dev/null
bao kv get challenge/two >/dev/null 2>&1 || bao kv put challenge/two value=bravo-$RANDOM >/dev/null
bao auth list | grep -q '^approle/' || bao auth enable approle
bao write auth/approle/role/buddy-{user} token_ttl=15m >/dev/null
echo "ready: secrets challenge/one and challenge/two, AppRole buddy-{user} with no policy"
