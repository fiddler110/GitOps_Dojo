#!/bin/sh
# openbao-setup's tokens (remediation T5.3), with the stack up: after a start,
# /setup holds no live token, the provisioner is gone, and the reset token (in
# openbao-setup's tmpfs) reaches student namespaces but not the root
# namespace's sys/. Exits 1 on any failure.
#   sh modules/openbao/tests/setup_tokens.sh [--recreate student01]
# --recreate NAME deletes students/NAME and creates it again with the reset
# token: destructive (the student's vault work is gone; the next start's hooks
# set the namespace up again).
failed=0
check() { if [ "$1" = 0 ]; then echo "  ok:   $2"; else echo "  FAIL: $2"; failed=1; fi; }
setup() { podman exec -e BAO_ADDR=http://openbao:8200 workshop_openbao_setup "$@" 2>&1; }
as_token() { t="$1"; shift; podman exec -e BAO_ADDR=http://openbao:8200 -e BAO_TOKEN="$t" workshop_openbao_setup "$@" 2>&1; }

echo "== /setup holds no live token"
for f in $(setup sh -c 'find /setup -type f'); do
  v="$(setup cat "$f" | head -1)"
  [ -n "$v" ] || continue
  as_token "$v" bao token lookup >/dev/null; [ $? -ne 0 ]; check $? "$f is not a token"
done
setup test -e /setup/root-token; [ $? -ne 0 ]; check $? "no root-token file"
setup test -e /setup/provisioner-token; [ $? -ne 0 ]; check $? "no provisioner-token file"
setup test -e /setup/pending-accessors; [ $? -ne 0 ]; check $? "no pending accessors (the start finished)"

echo "== the reset token"
reset="$(setup cat /run/openbao-setup/reset-token)"
[ -n "$reset" ]; check $? "openbao-setup holds one in memory"
as_token "$reset" bao token lookup -format=json | tr -d ' \n' | grep -q '"policies":\["reset"\]'
check $? "its only policy is reset"
as_token "$reset" bao token lookup -format=json | tr -d ' \n' | grep -q '"period":86400'
check $? "it is periodic (24h)"
out="$(as_token "$reset" sh -c 'BAO_NAMESPACE=students bao namespace lookup student01')"
printf '%s' "$out" | grep -q 'student01'; check $? "it reads students/student01"
# denied WHAT CMD...: CMD, as the reset token, fails with "permission denied".
denied() { w="$1"; shift; as_token "$reset" "$@" | grep -q 'permission denied'; check $? "refused: $w"; }
denied "sys/policies/acl in the root namespace" sh -c 'echo "path \"x\" { capabilities = [\"read\"] }" | bao policy write reset-test -'
denied "sys/auth in the root namespace" bao auth enable -path=reset-test userpass
denied "deleting the namespace students itself" bao namespace delete students
denied "identity" bao read identity/entity/name/student01
denied "the shared secret/ mount's data" bao kv get -mount=secret students/student01/welcome

if [ "${1:-}" = "--recreate" ]; then
  s="${2:-student01}"
  echo "== the reset token deletes and re-creates students/$s"
  as_token "$reset" sh -c "BAO_NAMESPACE=students bao namespace delete $s" >/dev/null; check $? "delete"
  i=0; until as_token "$reset" sh -c "BAO_NAMESPACE=students bao namespace create $s" >/dev/null; do
    i=$((i + 1)); [ "$i" -lt 30 ] || break; sleep 1
  done
  as_token "$reset" sh -c "BAO_NAMESPACE=students bao namespace lookup $s" >/dev/null; check $? "re-create"
fi

[ "$failed" = 0 ] && echo PASS || { echo FAILED; exit 1; }
