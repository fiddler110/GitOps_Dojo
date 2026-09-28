#!/bin/sh
# The openbao module's CLI login (T1.4), with the stack up: each account's
# shell gets a token for its own entity with no manual login, and one account
# can't get another's JWT or token. Exits 1 on any failure.
#   sh modules/openbao/tests/cli_login.sh [student01 student02 facilitator-account]
a="${1:-student01}"; b="${2:-student02}"; f="${3:-$(podman exec workshop_terminal printenv FACILITATOR_USERNAME)}"
failed=0
check() { if [ "$1" = 0 ]; then echo "  ok:   $2"; else echo "  FAIL: $2"; failed=1; fi; }
as() { u="$1"; shift; podman exec workshop_terminal su - "$u" -c "$*" 2>&1; }

for u in "$a" "$b" "$f"; do
  echo "== $u: a new shell is signed in"
  as "$u" 'rm -f ~/.vault-token ~/.cache/openbao-login' >/dev/null
  out="$(as "$u" 'bao token lookup -format=json')"
  printf '%s' "$out" | grep -q '"entity_id": "[0-9a-f]' ; check $? "bao token lookup works with an entity"
  want=student; [ "$u" = "$f" ] && want=facilitator
  printf '%s' "$out" | tr -d ' \n' | grep -q "\"identity_policies\":\[\"$want\"\]"; check $? "the entity has the $want policy"
  ent="$(as "$u" 'bao token lookup -format=json' | sed -n 's/.*"entity_id": "\([^"]*\)".*/\1/p')"
  name="$(podman exec -e BAO_ADDR=http://openbao:8200 -e BAO_TOKEN="$(podman exec workshop_openbao_setup cat /setup/provisioner-token)" \
    workshop_openbao_setup bao read -field=name identity/entity/id/"$ent" 2>&1)"
  exp="$u"; [ "$u" = "$f" ] && exp=facilitator
  [ "$name" = "$exp" ]; check $? "same entity as the SSO login ($name)"
done

echo "== $b can't get $a's credentials"
as "$b" "cat /home/$a/.vault-token" >/dev/null; [ $? -ne 0 ]; check $? "$b can't read $a's ~/.vault-token"
as "$b" 'cat /var/lib/openbao-broker/key.pem' >/dev/null; [ $? -ne 0 ]; check $? "$b can't read the broker key"
sub="$(as "$b" "python3 -c 'import socket,base64,json;s=socket.socket(socket.AF_UNIX);s.connect(\"/run/openbao-broker/broker.sock\");t=s.recv(9999).decode().split(\".\")[1];print(json.loads(base64.urlsafe_b64decode(t+\"==\"))[\"sub\"])'")"
[ "$sub" = "$b" ]; check $? "the broker gives $b a JWT for $b only (sub=$sub)"
nob="$(podman exec -u nobody workshop_terminal python3 -c 'import socket;s=socket.socket(socket.AF_UNIX);s.connect("/run/openbao-broker/broker.sock");print(len(s.recv(9999)))')"
[ "$nob" = 0 ]; check $? "an account outside the roster gets nothing ($nob bytes)"

echo "== a token from bao login is left alone"
as "$a" 'bao login -no-print -method=jwt role=terminal jwt=$(python3 -c "import socket;s=socket.socket(socket.AF_UNIX);s.connect(\"/run/openbao-broker/broker.sock\");print(s.recv(9999).decode())"); cat ~/.vault-token > /tmp/own-$USER' >/dev/null
[ "$(as "$a" 'cat ~/.vault-token')" = "$(as "$a" 'cat /tmp/own-$USER; rm -f /tmp/own-$USER')" ]; check $? "a new shell keeps the user's own token"

[ "$failed" = 0 ] && echo PASS || { echo FAILED; exit 1; }
