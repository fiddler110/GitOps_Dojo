# Sourced by bootstrap.sh. The shell twin of engine/allocator/dojo_secret.py
# (read that for the why): forgejo_password <user> prints
#   base32(HMAC-SHA256(STUDENT_PASSWORD_SEED, "forgejo:" + user))[:16]
# or the shared STUDENT_PASSWORD when no seed is set.
#
# The Forgejo image has no openssl or python, so HMAC is built from
# sha256sum, xxd and od. The seed only ever reaches those on stdin (printf
# is a shell builtin), never in an argv. engine/allocator/tests/
# test_dojo_secret.py checks this against the Python version.

_dojo_hex() { od -An -tx1 -v | tr -d ' \n'; }

# _dojo_pad <key hex> <pad byte>: the 64-byte HMAC block XORed with the pad.
_dojo_pad() {
  _out=""
  for _b in $(printf '%s' "$1" | sed 's/../& /g'); do
    _out="$_out$(printf '%02x' $((0x$_b ^ $2)))"
  done
  printf '%s' "$_out"
}

dojo_derive() {
  _seed="$1"; _msg="$2:$3"
  _key="$(printf '%s' "$_seed" | _dojo_hex)"
  # Keys longer than the block are hashed first, as HMAC specifies.
  [ "${#_key}" -le 128 ] || _key="$(printf '%s' "$_seed" | sha256sum | cut -c1-64)"
  while [ "${#_key}" -lt 128 ]; do _key="${_key}00"; done
  _inner="$({ printf '%s' "$(_dojo_pad "$_key" 0x36)" | xxd -r -p; printf '%s' "$_msg"; } | sha256sum | cut -c1-64)"
  _mac="$(printf '%s%s' "$(_dojo_pad "$_key" 0x5c)" "$_inner" | xxd -r -p | sha256sum | cut -c1-64)"
  # 16 base32 characters = the first 80 bits, as two 40-bit halves.
  _alpha=ABCDEFGHIJKLMNOPQRSTUVWXYZ234567
  _out=""
  for _half in "$(printf '%s' "$_mac" | cut -c1-10)" "$(printf '%s' "$_mac" | cut -c11-20)"; do
    _v=$((0x$_half)); _i=7
    while [ "$_i" -ge 0 ]; do
      _c=$(( (_v >> (5 * _i)) & 31 ))
      _out="$_out$(printf '%s' "$_alpha" | cut -c$((_c + 1)))"
      _i=$((_i - 1))
    done
  done
  printf '%s\n' "$_out"
}

forgejo_password() {
  if [ -z "${STUDENT_PASSWORD_SEED:-}" ]; then
    printf '%s\n' "${STUDENT_PASSWORD:-student123}"
  else
    dojo_derive "$STUDENT_PASSWORD_SEED" forgejo "$1"
  fi
}
