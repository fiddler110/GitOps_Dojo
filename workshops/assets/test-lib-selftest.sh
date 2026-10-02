#!/bin/sh
# Offline self-test of workshops/assets/test-lib.sh (RV18): no stack. A fake container CLI runs
# `exec [-i] [-u U] CONTAINER CMD...` here on the host, `su - USER -c CMD` becomes `sh -c CMD` with
# USER set, and the Forgejo log archive is a temporary folder. CI runs it; so can you:
#   sh workshops/assets/test-lib-selftest.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# -- the fake CLI ---------------------------------------------------------------------------------------------
mkdir -p "$tmp/bin" "$tmp/archive/data/gitea/actions_log/amy/repo/1"
cat > "$tmp/bin/fakecli" <<'EOF'
#!/bin/sh
[ "$1" = exec ] || { echo "fakecli: only exec" >&2; exit 2; }
shift
while :; do case "$1" in -i) shift ;; -u|-e) shift 2 ;; *) break ;; esac; done
container="$1"; shift
if [ "$1" = su ]; then USER="$3" exec sh -c "$5"; fi
case "$container" in
  workshop_forge)  # the archive's /data is the temporary folder's ./data: rewrite each argument
    cd "$FAKE_ARCHIVE" || exit 2
    for a in "$@"; do set -- "$@" "$(printf '%s' "$a" | sed 's# /data/# ./data/#g; s#^/data/#./data/#')"; shift; done
    exec "$@" ;;
  *) exec "$@" ;;
esac
EOF
chmod +x "$tmp/bin/fakecli"
export FAKE_ARCHIVE="$tmp/archive"

lib() { # lib SCRIPT: run SCRIPT after sourcing the library, with the fake CLI; prints its output, then "rc=N"
  DOJO_CLI="$tmp/bin/fakecli" sh -c ". '$here/test-lib.sh'; $1" 2>&1; echo "rc=$?"
}

# -- this test's own reporting (not the library's, which is what is under test) ---------------------------------
bad=0
expect() { # expect NAME OUTPUT TEXT...
  _n="$1"; _o="$2"; shift 2
  for _t in "$@"; do
    case "$_o" in *"$_t"*) ;; *) echo "  FAIL: $_n (no '$_t')"; printf '%s\n' "$_o" | sed 's/^/        | /'; bad=1; return ;; esac
  done
  echo "  ok:   $_n"
}
refuse() { # refuse NAME OUTPUT TEXT
  case "$2" in *"$3"*) echo "  FAIL: $1 ('$3' is there)"; bad=1 ;; *) echo "  ok:   $1" ;; esac
}

echo "== reporting"
o="$(lib 'pass one; check two "abc" b; absent three "abc" z; result 0 four; finish all')"
expect "passes end in PASS and exit 0" "$o" "  ok:   one" "  ok:   two" "  ok:   three" "  ok:   four" "PASS: all" "rc=0"
o="$(lib 'check miss "line1
line2" zz; absent there "abc" b; result 3 nonzero; pass after; finish all')"
expect "failures are reported, the run carries on, then exit 1" "$o" \
  "  FAIL: miss (no 'zz')" "        line2" "  FAIL: there ('b' is there)" "  FAIL: nonzero" "  ok:   after" "FAIL: all" "rc=1"
o="$(lib 'fail plain; finish')"
expect "finish with no name" "$o" "FAIL" "rc=1"

echo "== students"
o="$(lib 's=amy; ok "runs as the student" "test \"\$USER\" = amy"; has "has" "echo hello world" world
        lacks "lacks" "echo hello" secret; denied "refused" "echo Error: permission denied; exit 2"; finish')"
expect "ok, has, lacks, denied pass" "$o" "  ok:   runs as the student" "  ok:   has" "  ok:   lacks" "  ok:   refused" "PASS" "rc=0"
o="$(lib 's=amy; ok "a failing command" "echo boom; exit 3"; has "missing" "echo hi" bye; lacks "present" "echo secret" secret
        denied "allowed" "echo fine"; finish')"
expect "and fail with the output's tail" "$o" "  FAIL: a failing command" "        boom" "  FAIL: missing" \
  "  FAIL: present" "  FAIL: allowed" "rc=1"
o="$(lib 'as_user bob echo "\$USER" two words; echo "piped" | as "cat"')"
expect "as_user joins its words; as passes stdin" "$o" "bob two words" "piped"

echo "== job logs"
for n in 1 2; do printf 'job %s output\n' "$n" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.buffer.write(z.compress(sys.stdin.buffer.read()))' \
  > "$tmp/archive/data/gitea/actions_log/amy/repo/1/$n.log.zst" 2>/dev/null || { echo "  skip: no compression.zstd (python3 < 3.14)"; break; }; done
if [ -s "$tmp/archive/data/gitea/actions_log/amy/repo/1/1.log.zst" ]; then
  o="$(lib 'log_files amy/repo; job_logs amy/repo; wait_logs amy/repo 2 5 && echo two-there; wait_logs amy/repo 3 1 || echo three-missing')"
  expect "lists, reads and waits for archived logs" "$o" "/1/1.log.zst" "job 1 output" "job 2 output" "two-there" "three-missing"
  o="$(lib 'before="$(log_files amy/repo | head -1)"; new_logs amy/repo "$before" 1 5')"
  expect "new_logs prints only the logs after BEFORE" "$o" "job 2 output"
  refuse "and not the earlier one" "$o" "job 1 output"
fi

echo "== lab text"
cat > "$tmp/lab.md" <<'EOF'
# Lab

```bash
echo one
```

Then edit:

```hcl
name = "studentXX"
```

```bash
cat >> main.tf <<'HCL'
x = 1
HCL
sed -i 's/a/b/' f
```
EOF
o="$(lib "md_line '$tmp/lab.md' \"sed -i 's/a\"; echo; md_line '$tmp/lab.md' nope || echo none")"
expect "md_line finds the first line with a prefix, else fails" "$o" "sed -i 's/a/b/' f" "none"
o="$(lib "md_range '$tmp/lab.md' \"^cat >> main.tf\" '^HCL\$'")"
expect "md_range takes a block between two lines" "$o" "cat >> main.tf <<'HCL'" "x = 1" "HCL"
refuse "and stops at its end" "$o" "sed -i"
o="$(lib "md_blocks '$tmp/lab.md' amy 2 1 hcl:1:dir/x.hcl")"
expect "md_blocks gives bash blocks in the asked order and writes files" "$o" \
  "cat >> main.tf" "echo one" "mkdir -p dir && cat > dir/x.hcl <<'LABFILE'" 'name = "amy"'

echo
if [ "$bad" = 0 ]; then echo "test-lib selftest: PASS"; else echo "test-lib selftest: FAIL"; exit 1; fi
