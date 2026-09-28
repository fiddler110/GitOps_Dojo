# Workshop bot steps for dojo-introduction (see engine/web-terminal/bot-runner.sh's
# BOT_STEPS_FILE). There is no lab here, so the bots walk the tool tour
# (content/lab/tools-tour.md) instead, which gives the facilitator's Roster live
# terminals, the Audit tab vault requests, the Runners tab jobs, DNS Zones new
# records and the Dojo Cloud portal a resource group to show.
#
# Each step is safe to run again. BOT_USER is testuserN; the my-zone folder and
# the vault namespace are made for bots the same as for students.

step_tour_git() {
  step_ensure_clone
  cd "$REPO_DIR" || return 1
  narrate "Tour 1-2 -- a branch and a push, which starts a pipeline on a single-use runner"
  run_cmd "git checkout -B tour-${BOT_USER} 2>/dev/null || git checkout tour-${BOT_USER}"
  run_cmd "git commit --allow-empty -q -m 'Tour round ${ROUND}'"
  run_cmd "git push -q -u origin tour-${BOT_USER} 2>&1 | tail -1"
  orient
}

step_tour_vault() {
  narrate "Tour 3 -- the vault: who am I, read my secret, write one, read it back"
  run_cmd "bao token lookup | grep -E '^(display_name|policies)'"
  run_cmd "bao kv get secret/students/${BOT_USER}/welcome | tail -2"
  run_cmd "bao kv put secret/students/${BOT_USER}/tour round=${ROUND} >/dev/null && bao kv get -field=round secret/students/${BOT_USER}/tour"
  run_cmd "BAO_NAMESPACE=students/${BOT_USER} bao auth list | head -4"
}

step_tour_dns() {
  narrate "Tour 4 -- DNS as code: my own zone, previewed then pushed"
  cd "$HOME/lab/my-zone" || return 1
  run_cmd "dnscontrol preview 2>&1 | tail -3"
  run_cmd "dnscontrol push 2>&1 | tail -3"
  run_cmd "dig @dns-server www.${BOT_USER}.dojo.test A +short"
  cd "$REPO_DIR" 2>/dev/null || cd "$HOME"
}

step_tour_cert() {
  narrate "Tour 5 -- the certificate authority"
  run_cmd "step ca health --ca-url https://step-ca:9443 --root /opt/step-ca-root/root_ca.crt"
  run_cmd "step certificate inspect --short /opt/step-ca-root/root_ca.crt | head -3"
}

step_tour_cloud() {
  narrate "Tour 6 -- OpenTofu against Dojo Cloud"
  cd "$REPO_DIR/cloud" || return 1
  run_cmd ". <(dojo-env) && tofu init -input=false 2>&1 | tail -1"
  run_cmd ". <(dojo-env) && tofu apply -auto-approve -input=false 2>&1 | tail -2"
  cd "$REPO_DIR"
}

step_wrap_round() {
  narrate "round $ROUND done -- removing this round's cloud resource group before the break"
  if [ -d "$REPO_DIR/cloud" ]; then
    run_cmd "cd $REPO_DIR/cloud && . <(dojo-env) && tofu destroy -auto-approve -input=false 2>&1 | tail -1"
  fi
  narrate "taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# Expert: the whole tour every round. Intermediate: everything but the cloud.
# Novice: git and the vault only.
case "$PERSONA" in
  expert)
    STEPS=(step_tour_git step_tour_vault step_tour_dns step_tour_cert step_tour_cloud step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_tour_git step_tour_vault step_tour_dns step_tour_cert step_wrap_round)
    ;;
  novice)
    STEPS=(step_tour_git step_tour_vault step_wrap_round)
    ;;
esac
