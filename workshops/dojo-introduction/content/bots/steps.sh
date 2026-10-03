# Workshop bot steps for dojo-introduction (see engine/web-terminal/bot-runner.sh's
# BOT_STEPS_FILE). There is no lab here, so the bots walk the tool tour
# (content/lab/tools-tour.md) instead, which gives the facilitator's Roster live
# terminals, the Runners tab jobs, DNS Zones new records and the Dojo Cloud
# portal a resource group to show.
#
# Each step is safe to run again. The commands pipe through tail (no pipefail), so each step ends by checking
# its result (branch on the server, record served, group in state): a failed git push, DNS push or apply then fails the
# step, and --fast retries it or reports it skipped, instead of passing on a hidden error. BOT_USER is testuserN; the my-zone folder is
# made for bots the same as for students.

step_tour_git() {
  step_ensure_clone
  cd "$REPO_DIR" || return 1
  narrate "Tour 1-2 -- a branch and a push, which starts a pipeline on a single-use runner"
  run_cmd "git checkout -B tour-${BOT_USER} 2>/dev/null || git checkout tour-${BOT_USER}"
  run_cmd "git commit --allow-empty -q -m 'Tour round ${ROUND}'"
  run_cmd "git push -q -u origin tour-${BOT_USER} 2>&1 | tail -1"
  run_cmd "git ls-remote --exit-code origin tour-${BOT_USER} | cut -c1-12" || return 1
  orient
}

step_tour_dns() {
  # The dns-gate hook writes this bot's key after bot-runner.sh has started.
  if [ -z "${DNS_API_KEY:-}" ] && [ -r "$HOME/.config/dojo/dns-api-key" ]; then
    DNS_API_KEY="$(cat "$HOME/.config/dojo/dns-api-key")"
    export DNS_API_KEY
  fi
  narrate "Tour 3 -- DNS as code: my own zone, previewed then pushed"
  cd "$HOME/lab/my-zone" || return 1
  run_cmd "dnscontrol preview 2>&1 | tail -3"
  run_cmd "dnscontrol push 2>&1 | tail -3"
  run_cmd "dig @dns-server www.${BOT_USER}.dojo.test A +short | grep 203.0.113.10" || return 1
  cd "$REPO_DIR" 2>/dev/null || cd "$HOME"
}

step_tour_cloud() {
  narrate "Tour 4 -- OpenTofu against Dojo Cloud"
  cd "$REPO_DIR/cloud" || return 1
  run_cmd ". <(dojo-env) && tofu init -input=false 2>&1 | tail -1"
  run_cmd ". <(dojo-env) && tofu apply -auto-approve -input=false 2>&1 | tail -2"
  run_cmd "tofu state list | grep azurerm_resource_group.tour" || return 1
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
# Novice: git only.
case "$PERSONA" in
  expert)
    STEPS=(step_tour_git step_tour_dns step_tour_cloud step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_tour_git step_tour_dns step_wrap_round)
    ;;
  novice)
    STEPS=(step_tour_git step_wrap_round)
    ;;
esac
