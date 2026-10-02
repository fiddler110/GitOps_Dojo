#!/bin/sh
# vault-fundamentals lab 2 (pass, S37), with the stack up: runs lab2.md's
# `bash` blocks as one student, as written, except the two a person types into
# (the passphrase box, and `pass insert -m`/`pass edit`), which it feeds
# instead. It first removes what an earlier run left (~/.gnupg,
# ~/.password-store), so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_2.sh [student03]
# TERMINAL=<container> points it at another terminal container.
s="${1:-student03}"; DOJO_TERMINAL="${TERMINAL:-workshop_terminal}"
labs="$(dirname "$0")/../content/lab"
. "$(dirname "$0")/../../assets/test-lib.sh"   # as, has/lacks, finish, md_blocks
block() { _lab="$1"; shift; md_blocks "$labs/$_lab" "$s" "$@"; }

echo "== reset $s"
as 'gpgconf --kill gpg-agent; rm -rf ~/.gnupg ~/.password-store' >/dev/null 2>&1
as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null

echo "== lab 2: pass"
# Block 1 opens the passphrase box; the same key, with the passphrase given here.
has   "a key that expires in a year" "gpg --batch --pinentry-mode loopback --passphrase 'three words 42' $(block lab2.md 1 | sed 's/^gpg //')
$(block lab2.md 2)" "[expires:"
# The test's gpg-agent needs the passphrase once, as a person's would after typing it.
as "echo allow-loopback-pinentry > ~/.gnupg/gpg-agent.conf; gpgconf --reload gpg-agent" >/dev/null
has   "a store, with git history" "$(block lab2.md 3)" "Password store initialized for $s@dojo.test"
has   "insert -m (block 4, fed)" "printf 'first-password\nusername: app\nhost: db.internal\n' | $(block lab2.md 4)" "dojo/db"
has   "generate" "$(block lab2.md 5)" "dojo/api-token"
has   "the store is folders of .gpg files" "$(block lab2.md 6)" "db.gpg"
lacks "the file on disk is not plain text" "cat ~/.password-store/dojo/db.gpg" "first-password"
has   "encrypted for my key only" "$(block lab2.md 7)" "$s <$s@dojo.test>"
# gpg-agent caches the passphrase after the first use; give it once here.
as "echo | gpg --batch --pinentry-mode loopback --passphrase 'three words 42' -d ~/.password-store/dojo/db.gpg" >/dev/null 2>&1
has   "show, first line, one key" "$(block lab2.md 8)" "app"
has   "edit (block 9, with sed for nano)" "$(block lab2.md 9 | sed "s/EDITOR=nano/EDITOR='sed -i s\/first-password\/second-password\/'/")"' && pass show dojo/db | head -1' "second-password"
has   "history shows both versions" "$(block lab2.md 10)" "-first-password"
has   "a teammate's key" "$(block lab2.md 11)
gpg --list-keys teammate@dojo.test" "teammate"
has   "shared: encrypted for two" "$(block lab2.md 12)" "teammate <teammate@dojo.test>"
lacks "taken back: the new file is mine only" "$(block lab2.md 13)" "teammate <teammate@dojo.test>"
has   "but the old copy still opens for them" "$(block lab2.md 14)" "teammate <teammate@dojo.test>"

finish "lab 2"
