#!/bin/sh
# vault-fundamentals tenancy (T1.5), with the stack up, as two students
# signed in by the terminal's CLI login: each reads their own folder in the
# shared secret/ mount, gets 403 on the other's, and is admin in their own
# namespace only. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/tenancy.sh [student01 student02]
a="${1:-student01}"; b="${2:-student02}"
failed=0
ok()   { if eval "$2" >/dev/null 2>&1; then echo "  ok:   $1"; else echo "  FAIL: $1"; failed=1; fi; }
deny() { out="$(eval "$2" 2>&1)"; case "$out" in *"permission denied"*|*403*) echo "  ok:   $1" ;; *) echo "  FAIL: $1: $out" | head -3; failed=1 ;; esac; }
as() { podman exec workshop_terminal su - "$1" -c "$2"; }

echo "== $a in the shared vault"
ok   "reads the welcome secret" "as $a 'bao kv get -field=message secret/students/$a/welcome'"
ok   "writes and reads a new secret" "as $a 'bao kv put secret/students/$a/t1 v=1 && bao kv get -field=v secret/students/$a/t1'"
ok   "destroys its versions" "as $a 'bao kv metadata delete secret/students/$a/t1'"
deny "403 on $b's folder" "as $a 'bao kv get secret/students/$b/welcome'"
deny "403 writing $b's folder" "as $a 'bao kv put secret/students/$b/x v=1'"

echo "== $a in namespaces"
ok   "enables an engine in students/$a" "as $a 'bao secrets enable -namespace=students/$a -path=t15 kv-v2 && bao secrets disable -namespace=students/$a t15'"
ok   "writes a policy in students/$a" "as $a 'echo \"path \\\"x/*\\\" { capabilities = [\\\"read\\\"] }\" | bao policy write -namespace=students/$a t15 - && bao policy delete -namespace=students/$a t15'"
deny "403 in students/$b" "as $a 'bao secrets list -namespace=students/$b'"
deny "403 enabling an engine in the root namespace" "as $a 'bao secrets enable -path=t15 kv-v2'"

[ "$failed" = 0 ] && echo PASS || { echo FAILED; exit 1; }
