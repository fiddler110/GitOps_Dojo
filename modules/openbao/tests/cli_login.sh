#!/bin/sh
# The openbao module's CLI login (T1.4), with the stack up: each account's
# shell gets a token for its own entity with no manual login, and one account
# can't get another's JWT or token. Exits 1 on any failure.
#   sh modules/openbao/tests/cli_login.sh [student01 student02 facilitator-account]
. "$(dirname "$0")/../../../workshops/assets/test-lib.sh"   # as_user, result, finish
a="${1:-student01}"; b="${2:-student02}"; f="${3:-$("$DOJO_CLI" exec "$DOJO_TERMINAL" printenv FACILITATOR_USERNAME)}"

for u in "$a" "$b" "$f"; do
  echo "== $u: a new shell is signed in"
  as_user "$u" 'rm -f ~/.vault-token ~/.cache/openbao-login' >/dev/null
  out="$(as_user "$u" 'bao token lookup -format=json')"
  printf '%s' "$out" | grep -q '"entity_id": "[0-9a-f]' ; result $? "bao token lookup works with an entity"
  want=student; [ "$u" = "$f" ] && want=facilitator
  printf '%s' "$out" | tr -d ' \n' | grep -q "\"identity_policies\":\[\"$want\"\]"; result $? "the entity has the $want policy"
  ent="$(as_user "$u" 'bao token lookup -format=json' | sed -n 's/.*"entity_id": "\([^"]*\)".*/\1/p')"
  # Read as the facilitator (policy facilitator): nothing else keeps a token.
  name="$(as_user "$f" "bao read -field=name identity/entity/id/$ent")"
  exp="$u"; [ "$u" = "$f" ] && exp=facilitator
  [ "$name" = "$exp" ]; result $? "same entity as the SSO login ($name)"
done

echo "== $b can't get $a's credentials"
as_user "$b" "cat /home/$a/.vault-token" >/dev/null 2>&1; [ $? -ne 0 ]; result $? "$b can't read $a's ~/.vault-token"
as_user "$b" 'cat /var/lib/openbao-broker/key.pem' >/dev/null 2>&1; [ $? -ne 0 ]; result $? "$b can't read the broker key"
sub="$(as_user "$b" "python3 -c 'import socket,base64,json;s=socket.socket(socket.AF_UNIX);s.connect(\"/run/openbao-broker/broker.sock\");t=s.recv(9999).decode().split(\".\")[1];print(json.loads(base64.urlsafe_b64decode(t+\"==\"))[\"sub\"])'")"
[ "$sub" = "$b" ]; result $? "the broker gives $b a JWT for $b only (sub=$sub)"
nob="$("$DOJO_CLI" exec -u nobody "$DOJO_TERMINAL" python3 -c 'import socket;s=socket.socket(socket.AF_UNIX);s.connect("/run/openbao-broker/broker.sock");print(len(s.recv(9999)))')"
[ "$nob" = 0 ]; result $? "an account outside the roster gets nothing ($nob bytes)"

echo "== a token from bao login is left alone"
as_user "$a" 'bao login -no-print -method=jwt role=terminal jwt=$(python3 -c "import socket;s=socket.socket(socket.AF_UNIX);s.connect(\"/run/openbao-broker/broker.sock\");print(s.recv(9999).decode())"); cat ~/.vault-token > /tmp/own-$USER' >/dev/null
[ "$(as_user "$a" 'cat ~/.vault-token')" = "$(as_user "$a" 'cat /tmp/own-$USER; rm -f /tmp/own-$USER')" ]; result $? "a new shell keeps the user's own token"

finish
