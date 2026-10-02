#!/bin/sh
# vault-fundamentals tenancy (T1.5), with the stack up, as two students
# signed in by the terminal's CLI login: each reads their own folder in the
# shared secret/ mount, gets 403 on the other's, and is admin in their own
# namespace only. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/tenancy.sh [student01 student02]
a="${1:-student01}"; b="${2:-student02}"
. "$(dirname "$0")/../../assets/test-lib.sh"   # ok, denied (as the student in $s), finish
s="$a"

echo "== $a in the shared vault"
ok     "reads the welcome secret" "bao kv get -field=message secret/students/$a/welcome"
ok     "writes and reads a new secret" "bao kv put secret/students/$a/t1 v=1 && bao kv get -field=v secret/students/$a/t1"
ok     "destroys its versions" "bao kv metadata delete secret/students/$a/t1"
denied "403 on $b's folder" "bao kv get secret/students/$b/welcome"
denied "403 writing $b's folder" "bao kv put secret/students/$b/x v=1"

echo "== $a in namespaces"
ok     "enables an engine in students/$a" "bao secrets enable -namespace=students/$a -path=t15 kv-v2 && bao secrets disable -namespace=students/$a t15"
ok     "writes a policy in students/$a" 'echo "path \"x/*\" { capabilities = [\"read\"] }" | bao policy write -namespace=students/'"$a"' t15 - && bao policy delete -namespace=students/'"$a"' t15'
denied "403 in students/$b" "bao secrets list -namespace=students/$b"
denied "403 enabling an engine in the root namespace" "bao secrets enable -path=t15 kv-v2"

finish
