# vault-fundamentals demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE): replaces
# the git-fundamentals default with Labs 0-9, run the way a student would, with the same commands as the
# lab pages. Labs 8 and 9 take their workflows and app straight from /opt/workshop-content/lab/*.md, so
# the bots stay in step with the labs. openbao-setup gives each bot (testuserN) an entity, a namespace
# students/testuserN, a database and an app-host slot, like a student (S33).
#
# How far a persona gets per round: novice Labs 0-3 (the vault user and admin); intermediate adds Labs
# 4-6 (code and git) and 7-8 (pipelines); expert adds Lab 9 (a deploy to app-host). Every round starts by
# undoing the last one (step_vf_reset), so each step can run again from scratch after a restart.
# The Forgejo UI steps (a repository secret) are the same API calls, and git and curl read ~/.netrc,
# made from the bot's own password file.

VF_LABS=/opt/workshop-content/lab
VF_NEIGHBOUR="${STUDENT_PREFIX:-student}01"

# vf_env: what a student's zsh does at login (bot-runner runs bash, so /etc/zsh/zshenv never fires):
# sign in to OpenBao through the terminal's broker (a no-op while the token is good).
vf_env() {
  export USER="$BOT_USER"
  : "${BAO_ADDR:=http://openbao:8200}"; : "${VAULT_ADDR:=$BAO_ADDR}"
  export BAO_ADDR VAULT_ADDR
  unset BAO_NAMESPACE
  [ -f "$HOME/.netrc" ] || install -m 600 "$NETRC" "$HOME/.netrc"
  /usr/local/bin/openbao-login --quiet >/dev/null 2>&1 || return 1
  # A bot starts at once, and can sign in before openbao-setup has bound its entity: that token has
  # no `student` policy, and openbao-login keeps it while it is valid. Sign in again once setup is done.
  if ! bao token lookup -format=json 2>/dev/null | grep -q '"student"'; then
    rm -f "$HOME/.vault-token"
    /usr/local/bin/openbao-login --quiet >/dev/null 2>&1 || return 1
    bao token lookup -format=json 2>/dev/null | grep -q '"student"' || return 1
  fi
  [ -s "$HOME/.vault-token" ]
}

# vf_block FILE N...: the Nth ```bash blocks of a lab page, joined (as tests/labs_9_11.sh does).
vf_block() {
  local f="$1"; shift
  python3 -B - "$VF_LABS/$f" "$@" <<'EOF'
import re, sys
blocks = re.findall(r"^```bash\n(.*?)^```$", open(sys.argv[1]).read(), re.S | re.M)
for n in sys.argv[2:]:
    sys.stdout.write(blocks[int(n) - 1])
EOF
}

# paste_cmd TEXT: like run_cmd, but a multi-line block shows up at once, the way a student pastes it
# from the lab page, instead of being typed out character by character.
paste_cmd() {
  printf '%s@%s:~%s$ ' "$BOT_USER" "$(hostname 2>/dev/null || echo dojo)" "${PWD#"$HOME"}"
  printf '%s\n' "$1"
  eval "$1"
  local rc=$?
  think
  return $rc
}

# vf_wait_app WHAT SECONDS: wait until this bot's app page shows WHAT.
vf_wait_app() {
  local end=$(( $(date +%s) + $2 ))
  while [ "$(date +%s)" -lt "$end" ]; do
    curl -s -m 5 "http://app-host:8080/$BOT_USER/" | grep -q "$1" && return 0
    sleep 5
  done
  return 1
}

# Undo the last round: the fork back to the team's main (no workflows, so the push starts no job),
# the lab folders, and what the labs wrote in the vault. Errors are expected on a first round.
step_vf_reset() {
  vf_env || { narrate "no vault token yet (openbao-setup may still be running), trying again"; return 1; }
  narrate "start of round $ROUND -- clearing last round's work"
  pkill -u "$BOT_USER" -f '[b]ao agent' 2>/dev/null
  rm -rf "$HOME/lab/leak" "$HOME/lab/my-vault" "$HOME/lab/app" "$HOME/lab/agent" "$HOME/lab/config-repo" \
    "/dev/shm/$BOT_USER"
  (
    export BAO_NAMESPACE="students/$BOT_USER"
    bao auth disable approle; bao secrets disable transit
    bao delete auth/jwt-ci/role/ci-main; bao delete auth/jwt-platform/role/app
    bao policy delete ci-read; bao policy delete sops-encrypt
  ) >/dev/null 2>&1
  cd "$REPO_DIR" || return 1
  git remote get-url upstream >/dev/null 2>&1 \
    || git remote add upstream "http://${GIT_SERVER}/${FORGEJO_ORG}/${FORGEJO_REPO}.git"
  run_cmd "git fetch -q upstream && git checkout -q -B main upstream/main && git clean -qfd"
  # -u so main tracks origin/main again: without it, a later step's bare "git push" (as the lab
  # pages write it) still targets upstream/main from the checkout above and collides with every
  # other bot pushing to the shared team repo, failing non-fast-forward (labs 7-9).
  run_cmd "git push -q -f -u origin main"
  git push -q origin --delete try-a-branch >/dev/null 2>&1
  return 0
}

step_vf_lab0() {
  vf_env || return 1
  narrate "Lab 0 -- the CLI is already signed in: what can this token do?"
  run_cmd "bao token lookup"
  run_cmd "ls -l ~/.vault-token"
}

# Lab 1: a secret committed, "deleted", and still in history; gitleaks finds it.
step_vf_lab1() {
  vf_env || return 1
  narrate "Lab 1 -- leak it: commit a secret, delete it, find it again"
  run_cmd "mkdir -p ~/lab/leak && cd ~/lab/leak && git init -q -b main"
  run_cmd "printf 'GITHUB_TOKEN=ghp_%s\n' 'Xk3L9mQ2vR7tW1yZ5bN8cD4fG6hJ0pS2aE7u' > config.env"
  run_cmd "git add config.env && git commit -qm 'Add config'"
  run_cmd "git rm -q config.env && git commit -qm 'Remove the secret'"
  run_cmd "git log -p | grep ghp_"
  narrate "still in history. Only rotating it at its source fixes that."
  run_cmd "gitleaks git --no-banner . ; echo \"gitleaks exit: \$?\""
}

step_vf_lab2() {
  vf_env || return 1
  local p="secret/students/$BOT_USER/db"
  narrate "Lab 2 -- the shared vault: KV v2 in my own folder"
  run_cmd "bao kv get secret/students/\$USER/welcome"
  run_cmd "bao kv put $p username=app password=first-password"
  run_cmd "bao kv put $p username=app password=second-password"
  run_cmd "bao kv patch $p password=third-password"
  run_cmd "bao kv get -version=1 $p"
  run_cmd "bao kv rollback -version=2 $p"
  run_cmd "bao kv get -field=password $p"
  if [ "$PERSONA" != expert ] || [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "what about a neighbour's folder?"
    run_cmd "bao kv get secret/students/$VF_NEIGHBOUR/welcome"
    narrate "403: the templated policy only lets me into my own folder"
    run_cmd "bao policy read student"
  fi
  run_cmd "bao kv metadata delete $p"
}

step_vf_lab3() {
  vf_env || return 1
  narrate "Lab 3 -- I'm the admin of my own namespace"
  run_cmd "export BAO_NAMESPACE=students/\$USER"
  run_cmd "bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2"
  run_cmd "bao kv put team/app db_password=app-db-pass api_key=app-api-key"
  run_cmd "bao kv put team/admin root_password=do-not-share"
  run_cmd "mkdir -p ~/lab/my-vault && cd ~/lab/my-vault"
  paste_cmd "printf 'path \"team/data/app\" {\n  capabilities = [\"read\"]\n}\n' > app-read.hcl"
  run_cmd "bao policy write app-read app-read.hcl"
  run_cmd "APP_TOKEN=\$(bao token create -orphan -policy=app-read -ttl=15m -field=token)"
  run_cmd "BAO_TOKEN=\$APP_TOKEN bao kv get team/app"
  run_cmd "BAO_TOKEN=\$APP_TOKEN bao kv get team/admin"
  narrate "permission denied, as it should be: least privilege"
  run_cmd "bao token revoke \"\$APP_TOKEN\""
  run_cmd "bao-audit | tail -5"
  unset BAO_NAMESPACE APP_TOKEN
}

# Labs 4-5: an app reads its secret with the SDK, then the Agent renders it to a file and follows a
# rotation. The agent is stopped at the end: a bot mustn't leave one running between rounds.
step_vf_lab4_5() {
  vf_env || return 1
  narrate "Lab 4 -- the app reads its secret from the vault"
  run_cmd "mkdir -p ~/lab/app && cd ~/lab/app"
  run_cmd "bao kv put secret/students/\$USER/app db_password=vault-db-pass-789 api_key=vault-api-key-012"
  paste_cmd "cat > app_vault.py <<'EOF'
import os
import hvac
c = hvac.Client()
r = c.secrets.kv.v2.read_secret_version(mount_point=\"secret\", path=f\"students/{os.environ['USER']}/app\",
                                        raise_on_deleted_version=True)
print(\"read version\", r[\"data\"][\"metadata\"][\"version\"], \"of the app's secret\")
EOF"
  run_cmd "python3 app_vault.py"
  run_cmd "bao kv patch secret/students/\$USER/app db_password=rotated-db-pass-000 && python3 app_vault.py"

  narrate "Lab 5 -- the Agent logs in by itself and writes the secret to a file in memory"
  run_cmd "export BAO_NAMESPACE=students/\$USER"
  run_cmd "bao auth enable approle"
  run_cmd "bao write auth/approle/role/app token_policies=app-read token_ttl=2m token_max_ttl=10m secret_id_ttl=1h"
  run_cmd "mkdir -p ~/lab/agent && cd ~/lab/agent && install -d -m 700 /dev/shm/\$USER"
  run_cmd "bao read -field=role_id auth/approle/role/app/role-id > role-id"
  run_cmd "bao write -f -field=secret_id auth/approle/role/app/secret-id > secret-id && chmod 600 role-id secret-id"
  paste_cmd "cat > agent.hcl <<EOF
vault {
  address = \"\$VAULT_ADDR\"
}
auto_auth {
  method \"approle\" {
    namespace = \"students/\$USER\"
    config = {
      role_id_file_path                   = \"role-id\"
      secret_id_file_path                 = \"secret-id\"
      remove_secret_id_file_after_reading = true
    }
  }
}
template_config {
  static_secret_render_interval = \"5s\"
}
template {
  destination = \"/dev/shm/\$USER/app.env\"
  perms       = \"0600\"
  contents    = <<-EOT
  {{ with secret \"team/data/app\" }}DB_PASSWORD={{ .Data.data.db_password }}{{ end }}
  EOT
}
EOF"
  run_cmd "(nohup bao agent -config=agent.hcl > agent.log 2>&1 &); sleep 5"
  run_cmd "ls -l /dev/shm/\$USER/app.env && cut -c1-14 /dev/shm/\$USER/app.env"
  run_cmd "bao kv patch team/app db_password=rotated-$ROUND-$RANDOM; sleep 8"
  run_cmd "cut -c1-20 /dev/shm/\$USER/app.env"
  narrate "picked up with no commit and no redeploy"
  run_cmd "pkill -u \$USER -f '[b]ao agent'"
  unset BAO_NAMESPACE
}

step_vf_lab6() {
  vf_env || return 1
  narrate "Lab 6 -- sops with the vault's transit engine: the file in git, the key in the vault"
  run_cmd "export BAO_NAMESPACE=students/\$USER"
  run_cmd "bao secrets enable transit && bao write -f transit/keys/sops"
  run_cmd "mkdir -p ~/lab/config-repo && cd ~/lab/config-repo && git init -q -b main"
  paste_cmd "printf 'creation_rules:\n  - path_regex: \\\\.enc\\\\.yaml\$\n    hc_vault_transit_uri: %s/v1/students/%s/transit/keys/sops\n' \"\$VAULT_ADDR\" \"\$USER\" > .sops.yaml"
  paste_cmd "printf 'database:\n  host: db.internal\n  password: s3cr3t-db-pass\n' > app.enc.yaml"
  run_cmd "sops encrypt -i app.enc.yaml && head -4 app.enc.yaml"
  run_cmd "sops decrypt --extract '[\"database\"][\"password\"]' app.enc.yaml"
  run_cmd "git add . && git commit -qm 'Encrypted config'"
  run_cmd "bao write -f transit/keys/sops/rotate && sops rotate -i app.enc.yaml && grep -c vault:v2 app.enc.yaml"
  unset BAO_NAMESPACE
}

# Labs 7-8: a repository secret and how masking fails, then the job logs in to the vault with its own
# OIDC token (lab8.md's vault-oidc workflow). Jobs run on the single-use runner pool.
step_vf_lab7_8() {
  vf_env || return 1
  cd "$REPO_DIR" || return 1
  local api="http://${GIT_SERVER}/api/v1/repos/$BOT_USER/$FORGEJO_REPO"
  narrate "Lab 7 -- a repository secret, used by a workflow (the UI step, by API)"
  run_cmd "curl -s -o /dev/null -w 'secret: HTTP %{http_code}\n' --netrc -X PUT -H 'Content-Type: application/json' -d '{\"data\":\"demo-key-$BOT_USER-$ROUND\"}' $api/actions/secrets/DEMO_API_KEY"
  paste_cmd "mkdir -p .forgejo/workflows && cat > .forgejo/workflows/secrets-demo.yml <<'EOF'
name: secrets-demo
on: push
jobs:
  demo:
    runs-on: host
    steps:
      - name: Use the secret
        env:
          API_KEY: \${{ secrets.DEMO_API_KEY }}
        run: |
          echo \"The key is \$API_KEY\"
          echo \"\$API_KEY\" | base64
EOF"
  run_cmd "git add . && git commit -qm 'Secrets demo' && git push -q"
  narrate "masked in the log, but base64 gets round the mask. Removing the secret."
  sleep 20
  run_cmd "curl -s -o /dev/null -w 'delete: HTTP %{http_code}\n' --netrc -X DELETE $api/actions/secrets/DEMO_API_KEY"
  run_cmd "git rm -q .forgejo/workflows/secrets-demo.yml && git commit -qm 'Remove the demo' && git push -q"

  narrate "Lab 8 -- no stored secret at all: the job's own identity, bound to main"
  run_cmd "export BAO_NAMESPACE=students/\$USER"
  run_cmd "bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2"
  run_cmd "bao kv put team/ci deploy_token=deploy-\$USER-\$RANDOM"
  paste_cmd "printf 'path \"team/data/ci\" {\n  capabilities = [\"read\"]\n}\n' | bao policy write ci-read -"
  paste_cmd "bao write auth/jwt-ci/role/ci-main - <<EOF
{\"role_type\":\"jwt\",\"user_claim\":\"sub\",\"bound_audiences\":[\"openbao\"],
 \"bound_claims\":{\"repository\":\"\$USER/vault-fundamentals\",\"ref\":\"refs/heads/main\"},
 \"token_policies\":[\"ci-read\"],\"token_ttl\":\"5m\"}
EOF"
  local wf
  wf="$(sed -n "/cat > .forgejo\/workflows\/vault-oidc.yml <<'EOF'/,/^EOF\$/p" "$VF_LABS/lab8.md")"
  [ -n "$wf" ] || { narrate "couldn't find the vault-oidc workflow in lab8.md"; return 1; }
  paste_cmd "mkdir -p .forgejo/workflows && $wf"
  run_cmd "git add .forgejo/workflows/vault-oidc.yml && git commit -qm 'CI logs in with its own identity' && git push -q"
  unset BAO_NAMESPACE
}

# Lab 9: the pipeline deploys the app to this bot's app-host slot, and the app gets its own secrets
# through its platform identity. Runs lab9.md's blocks 1-8 as written, then a rotation (block 11).
step_vf_lab9() {
  vf_env || return 1
  cd "$REPO_DIR" || return 1
  narrate "Lab 9 -- deploy with workload identity: the pipeline deploys, the app reads its own secrets"
  paste_cmd "$(vf_block lab9.md 1 2 3 4)" || return 1
  paste_cmd "$(vf_block lab9.md 5 6 7)" || return 1
  paste_cmd "$(vf_block lab9.md 8)" || return 1
  narrate "waiting for the deploy job"
  if vf_wait_app 'API_KEY fingerprint' 240; then
    run_cmd "curl -s http://app-host:8080/\$USER/ | head -12"
    paste_cmd "$(vf_block lab9.md 11)"
  else
    narrate "no app yet after 4 minutes -- the runners may be busy; moving on"
  fi
  unset BAO_NAMESPACE
}

case "$PERSONA" in
  expert)
    STEPS=(step_ensure_clone step_vf_reset step_vf_lab0 step_vf_lab1 step_vf_lab2 step_vf_lab3
           step_vf_lab4_5 step_vf_lab6 step_vf_lab7_8 step_vf_lab9 step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_ensure_clone step_vf_reset step_vf_lab0 step_vf_lab2 step_vf_lab3
           step_vf_lab4_5 step_vf_lab6 step_vf_lab7_8 step_wrap_round)
    ;;
  novice)
    STEPS=(step_ensure_clone step_vf_reset step_vf_lab0 step_vf_lab1 step_vf_lab2 step_vf_lab3
           step_wrap_round)
    ;;
esac
