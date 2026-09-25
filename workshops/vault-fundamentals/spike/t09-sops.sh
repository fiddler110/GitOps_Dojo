#!/bin/sh
# P0 spike T0.9 (PLAN.md §10.6): sops encrypts a file with OpenBao's transit
# engine in a student's namespace, the file is committed, and only a token
# with transit decrypt can read it back. Throwaway; P2 turns it into lab 6.
# Run from the repo root with the stack up and OpenBao unsealed:
#   BAO_TOKEN=<root token> sh workshops/vault-fundamentals/spike/t09-sops.sh
# Re-runnable.
set -eu
: "${BAO_TOKEN:?Set BAO_TOKEN}"
S=student01; NS="students/$S"
bao() { podman exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$BAO_TOKEN" workshop_openbao bao "$@"; }
nb() { podman exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$BAO_TOKEN" -e BAO_NAMESPACE="$NS" workshop_openbao bao "$@"; }
as_student() { podman exec -i -u "$S" -w "/home/$S" -e SOPS_DISABLE_VERSION_CHECK=1 workshop_terminal sh -c "$1"; }
token() { nb token create -policy="$1" -ttl=10m -field=token; }

echo "== transit in $NS, key 'sops'"
bao namespace create students >/dev/null 2>&1 || true
bao namespace create -namespace=students "$S" >/dev/null 2>&1 || true
nb secrets enable transit >/dev/null 2>&1 || true
nb write -f transit/keys/sops >/dev/null
printf 'path "transit/encrypt/sops" { capabilities = ["update"] }\n' | nb policy write sops-encrypt - >/dev/null
printf 'path "transit/decrypt/sops" { capabilities = ["update"] }\n' | nb policy write sops-decrypt - >/dev/null
enc="$(token sops-encrypt)"; dec="$(token sops-decrypt)"; none="$(token default)"

echo "== encrypt and commit (VAULT_NAMESPACE form)"
as_student "set -e; rm -rf t09 && mkdir t09 && cd t09 && git init -q && \
  printf 'db_user: app\ndb_password: hunter2\n' > secrets.yaml && \
  VAULT_ADDR=\$BAO_ADDR VAULT_NAMESPACE=$NS VAULT_TOKEN=$enc \
    sops encrypt -i --hc-vault-transit \$BAO_ADDR/v1/transit/keys/sops secrets.yaml && \
  git add secrets.yaml && git -c user.name=$S -c user.email=$S@dojo commit -qm 'encrypted config' && \
  git show --stat --oneline HEAD | head -2 && grep -c 'ENC\\[' secrets.yaml && \
  ! grep -q hunter2 secrets.yaml && echo 'plaintext absent: ok'"

out="${TMPDIR:-/tmp}/t09.out"
try() { # try LABEL TOKEN [EXTRA_ENV]
  if as_student "cd t09 && VAULT_ADDR=\$BAO_ADDR VAULT_NAMESPACE=$NS VAULT_TOKEN=$2 ${3:-} sops decrypt secrets.yaml" \
      > "$out" 2>&1; then echo "  $1: decrypted ($(grep -c hunter2 "$out") match)"
  else echo "  $1: refused: $(grep -o 'Code: [0-9]*\|permission denied\|failed to decrypt[^:]*' "$out" | head -1)"; fi
}
echo "== decrypt from the committed file"
try "decrypt-only token" "$dec"
try "encrypt-only token" "$enc"
try "default-policy token" "$none"

echo "== key rotation: old data key still opens; rewrap keeps it working"
nb write -f transit/keys/sops/rotate >/dev/null
try "after rotate" "$dec"
as_student "cd t09 && VAULT_ADDR=\$BAO_ADDR VAULT_NAMESPACE=$NS VAULT_TOKEN=$BAO_TOKEN \
  sops rotate -i secrets.yaml && grep -o 'vault:v[0-9]*' secrets.yaml | head -1"

echo "== path-embedded namespace form (no VAULT_NAMESPACE)"
if as_student "cd t09 && printf 'k: v\\n' > p.yaml && VAULT_ADDR=\$BAO_ADDR VAULT_TOKEN=$enc sops encrypt \
    --hc-vault-transit \$BAO_ADDR/v1/$NS/transit/keys/sops p.yaml >/dev/null 2>/tmp/t09p.err"; then echo "  works"
else echo "  fails: $(as_student 'tail -1 /tmp/t09p.err')"; fi
