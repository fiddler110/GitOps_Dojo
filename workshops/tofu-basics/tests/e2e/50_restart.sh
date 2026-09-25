#!/usr/bin/env bash
# shellcheck shell=bash
# Area restart (opt-in: --with-restart, about 1 minute; it restarts $CLOUD_HOST_CONTAINER, so every student's containers
# blink). PLAN T8.9/T8.10: a deployed container survives a restart of cloud-host by itself (restart policy
# unless-stopped), /readyz comes back, and `plan` says `No changes`. The bounds come from PLAN T8.10's measurements
# (/readyz 200 again after 9-13 s, site back after 8-12 s, a plain stop 5.5-6.5 s) with generous slack:
# --ready-bound (default 45 s) and --site-bound (default 60 s), both counted from the moment the restart is issued.
# Note: `podman kill` / a hand `stop` is NOT restarted automatically (T8.10); this area uses `restart`, which starts it.
# Sourced by tests/e2e.sh; running this file directly hands over with --only restart.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only restart "$@"; fi

area_restart() {
  prepare_repo || abort_area "cannot prepare the starter repo"
  local d="$WORK/restart" label="rst-dev-$STUDENT" creates_before disappeared_before t_issue t_back ready_s site_s down_seen=0
  register_tofu_dir "$STUDENT" "$d"

  section "Deploy something to restart under (workload 'rst', so it cannot clash with the labs' names)"
  as_student "$STUDENT" "git clone -q '$REPO' '$d' && cd '$d' && sed -i 's/^workload .*/workload    = \"rst\"/' terraform.tfvars && terraform init -no-color -input=false && terraform apply -auto-approve -no-color -input=false" 480 deploy
  expect_rc "deploy succeeds" 0
  expect_has "two resources created" 'Apply complete! Resources: 2 added, 0 changed, 0 destroyed.'
  expect_wait "the site answers before the restart" 45 site_has "$STUDENT" "$label" '<h1>Hello from Dojo Cloud!</h1>'
  creates_before=$(activity_count "$STUDENT" 'Create/Update container group' Succeeded)
  disappeared_before=$(activity_count "$STUDENT" 'Container disappeared outside IaC' Succeeded)

  section "Restart $CLOUD_HOST_CONTAINER"
  if is_dry; then
    dry "$CLI restart $CLOUD_HOST_CONTAINER   (then poll /readyz and the site until they answer, up to ${READY_BOUND}s / ${SITE_BOUND}s)"
  else
    t_issue=$(now_ms)
    timeout -k 5 180 "$CLI" restart "$CLOUD_HOST_CONTAINER" >/dev/null 2>&1
    t_back=$(now_ms)
    say "  info: the restart command returned after $(fmt_secs $((t_back - t_issue)))s"
    while :; do   # /readyz: any non-200 seen means readiness noticed the outage; the first 200 after that is the recovery
      portal_call GET /readyz -
      if [ "$P_STATUS" = 200 ]; then
        if [ "$down_seen" = 1 ] || [ $(($(now_ms) - t_issue)) -gt $((READY_BOUND * 1000)) ] || [ $(($(now_ms) - t_back)) -gt 8000 ]; then break; fi
      else
        down_seen=1
      fi
      if [ $(($(now_ms) - t_issue)) -gt $((READY_BOUND * 1000 + 30000)) ]; then break; fi
      sleep 1
    done
    ready_s=$(( ($(now_ms) - t_issue) / 1000 ))
    if [ "$P_STATUS" = 200 ]; then
      say "  info: /readyz was 200 again $(fmt_secs $(($(now_ms) - t_issue)))s after the restart was issued (non-200 seen meanwhile: $([ "$down_seen" = 1 ] && echo yes || echo no))"
      [ "$down_seen" = 1 ] || warn "/readyz never showed a non-200 during the restart; readiness may be slower to notice than the restart is (informational)"
      expect_le "/readyz returns 200 within ${READY_BOUND}s of the restart (PLAN T8.10 measured 9-13 s)" "$ready_s" "$READY_BOUND"
    else
      fail "/readyz did not return to 200 within $((READY_BOUND + 30))s of the restart (status $P_STATUS: $(pj body.detail))"
    fi
    if wait_until "$SITE_BOUND" 2 site_has "$STUDENT" "$label" '<h1>Hello from Dojo Cloud!</h1>'; then
      site_s=$(( ($(now_ms) - t_issue) / 1000 ))
      say "  info: the site answered again ${site_s}s after the restart was issued"
      expect_le "the deployed container is back by itself within ${SITE_BOUND}s (PLAN T8.10 measured 8-12 s)" "$site_s" "$SITE_BOUND"
    else
      fail "the site did not answer within ${SITE_BOUND}s of the restart: the container did not come back by itself"
      _evidence
    fi
  fi
  expect_wait "portal shows the container Running again" 30 _restart_running

  section "Nothing needs fixing"
  as_student "$STUDENT" "cd '$d' && terraform plan -no-color -input=false" 240 plan-after
  expect_has "plan says No changes, with no apply in between" 'No changes. Your infrastructure matches the configuration.'
  expect_eq "no container group was re-created (activity log has no new create)" "$creates_before" "$(activity_count "$STUDENT" 'Create/Update container group' Succeeded)"
  expect_eq "and no 'disappeared outside IaC' drift was logged" "$disappeared_before" "$(activity_count "$STUDENT" 'Container disappeared outside IaC' Succeeded)"

  section "Destroy works after the restart"
  as_student "$STUDENT" "cd '$d' && terraform destroy -auto-approve -no-color -input=false" 480 destroy
  expect_has "destroy after the restart" 'Destroy complete! Resources: 2 destroyed.'
  portal_counts "$STUDENT"
  expect_eq "portal is empty again" "0/0/0" "$N_RG/$N_CG/$QUOTA_USED"
}

_restart_running() { [ "$(cg_state "$STUDENT")" = Running ]; }
