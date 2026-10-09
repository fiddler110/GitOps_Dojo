# ctf-secrets-config setup hook, sourced by the openbao module's setup.sh on
# every start with the provisioner token (BAO_TOKEN, `log`, `retry`,
# `enable_once`, `class_users`, `par_each` are set). Safe to re-run.
#
# Target 11 `tfstate-treasure` (plan row 11, CTF-3, ties `tofu-basics` +
# `vault-fundamentals`): the credential a leaked terraform.tfstate commonly
# holds is here an AppRole role_id/secret_id, scoped to read exactly one
# student's flag at secret/data/tfstate-treasure/<user> and nothing else --
# the student's own OpenBao login (SSO or CLI) has NO policy in this pack
# (see docker-compose.override.yml), so that path is unreachable any other
# way. The matching half -- seeding each student's own `infra-state` Forgejo
# repo with a terraform.tfstate holding these same two values -- is
# compose/terminal/start.d/95-tfstate-treasure.sh (web-terminal).
#
# Both hooks derive the flag and the role_id/secret_id independently from
# STUDENT_PASSWORD_SEED (same "two copies, not shared code" idiom as every
# other flag/token in this range, e.g. flags.py's render() and
# 55-git-secrets.sh's deploy_token_for) -- but this container is Alpine's
# openbao image with no python3/openssl (confirmed: only sh/sha256sum/od), so
# the HMAC-SHA256 flags.render() needs is done by hand below with sha256sum,
# checked against RFC 4231's test vector and against flags.py's own output
# for a real seed before being trusted for a real flag (see
# docs/CTF-WORKSHOP-PLAN.md's checkpoint).

here=/etc/openbao-setup.d

bao secrets list -format=json 2>/dev/null | grep -q '"secret/"' \
  || retry 30 bao secrets enable -path=secret -version=2 kv >/dev/null
retry 30 enable_once auth enable approle

# --- HMAC-SHA256, hex in/out, no python3/openssl --------------------------
hex_xor() { # HEXSTR BYTE -> hex, HEXSTR XORed byte-by-byte with hex BYTE
  _hx="$1"; _hb_d=$((0x$2)); _out=""; _rest="$_hx"
  while [ -n "$_rest" ]; do
    _pair=$(printf '%s' "$_rest" | cut -c1-2)
    _rest=$(printf '%s' "$_rest" | cut -c3-)
    _out="$_out$(printf '%02x' $((0x$_pair ^ _hb_d)))"
  done
  printf '%s' "$_out"
}
hex_to_bytes() { # HEXSTR -> its raw bytes on stdout (POSIX printf has no \xHH, use octal)
  _rest="$1"; _fmt=""
  while [ -n "$_rest" ]; do
    _pair=$(printf '%s' "$_rest" | cut -c1-2)
    _rest=$(printf '%s' "$_rest" | cut -c3-)
    _fmt="$_fmt\\$(printf '%03o' $((0x$_pair)))"
  done
  printf "$_fmt"
}
ascii_hex() { printf '%s' "$1" | od -An -v -tx1 | tr -d ' \n'; }
sha256_hex_of_bytes_hex() { hex_to_bytes "$1" | sha256sum | cut -d' ' -f1; }
hmac_sha256_hex() { # KEY_HEX MSG_HEX -> hex
  _key_hex="$1"; _msg_hex="$2"
  _klen=$(( ${#_key_hex} / 2 ))
  if [ "$_klen" -gt 64 ]; then _key_hex="$(sha256_hex_of_bytes_hex "$_key_hex")"; _klen=32; fi
  _pad=$(( (64 - _klen) * 2 )); _i=0; _zeros=""
  while [ "$_i" -lt "$_pad" ]; do _zeros="${_zeros}0"; _i=$((_i + 1)); done
  _key_padded="${_key_hex}${_zeros}"
  _inner="$(sha256_hex_of_bytes_hex "$(hex_xor "$_key_padded" 36)${_msg_hex}")"
  sha256_hex_of_bytes_hex "$(hex_xor "$_key_padded" 5c)${_inner}"
}

# derive CHALLENGE USER: flags.py's render(), minus the "flag{...}" wrapper
# and the dev-seed fallback (this hook only ever runs with a real seed set
# in .env; an empty seed is a misconfigured install, not a dev mode
# worth special-casing here).
seed_hex="$(ascii_hex "${STUDENT_PASSWORD_SEED:?STUDENT_PASSWORD_SEED must be set for tfstate-treasure}")"
derive() { hmac_sha256_hex "$seed_hex" "$(ascii_hex "ctf:$1:$2")" | cut -c1-16; }

flag_for()      { printf 'flag{tfstate-treasure-%s}\n' "$(derive tfstate-treasure "$1")"; }
role_id_for()   { derive tfstate-treasure-role "$1"; }
secret_id_for() { derive tfstate-treasure-secret "$1"; }

tfstate_treasure_one() {
  s="$1"
  policy="tfstate-treasure-$s"
  role="tfstate-treasure-$s"

  printf 'path "secret/data/tfstate-treasure/%s" {\n  capabilities = ["read"]\n}\n' "$s" \
    | retry 30 bao policy write "$policy" - >/dev/null \
    || { log "tfstate-treasure: could not write policy for $s"; exit 1; }

  retry 30 bao write "auth/approle/role/$role" \
    role_id="$(role_id_for "$s")" token_policies="$policy" \
    token_ttl=15m token_max_ttl=15m secret_id_num_uses=0 >/dev/null \
    || { log "tfstate-treasure: could not write role for $s"; exit 1; }
  retry 30 bao write "auth/approle/role/$role/custom-secret-id" \
    secret_id="$(secret_id_for "$s")" >/dev/null \
    || { log "tfstate-treasure: could not set secret_id for $s"; exit 1; }

  # Write-once (cas=0): a re-run that already has a flag leaves it alone.
  out="$(printf '{"options":{"cas":0},"data":{"flag":"%s"}}' "$(flag_for "$s")" \
    | bao write secret/data/tfstate-treasure/"$s" - 2>&1)" && return 0
  case "$out" in *check-and-set*) return 0 ;; esac
  log "tfstate-treasure: could not seed the flag for $s: $out"
  return 1
}

par_each tfstate_treasure_one || { log "tfstate-treasure: could not provision every student"; exit 1; }
log "tfstate-treasure: done"
