# cloud-policy-as-code demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE): replaces the
# git-fundamentals default with Labs 0-12, run the way a student would with the commands the lab pages give.
# Every persona walks every lab (a policy workshop is one story; there is no useful "half"). The capstone is
# left for people. The mistakes the labs teach are made on purpose, in round 1 and every round: the denied
# eastus group (Lab 1), the costCenter denial (Lab 3), the legacy group under a deny rule (Lab 4), the
# failing pull request (Lab 11) and the portal change that drift catches (Lab 12).
#
# Each round starts by undoing the last one (step_cpc_reset, rounds 2+), so every lab can run again from
# scratch. --fast runs one round with no pacing; the only waits are the bounded loops below (CI runs).
# Slow policy applies (about 100 s each in Dojo Cloud) are never padded with extra sleeps; every apply
# takes -lock-timeout=120s because the Forgejo runner may be applying the same state at the same time.
#
# Dojo Cloud credentials come from the broker (same dojo-env a student's login shell evals): ARM_*/TF_VAR_owner.

CPC_LAB="$HOME/lab/$FORGEJO_REPO"
CPC_FORK="$BOT_USER/$FORGEJO_REPO"
CPC_GW="${DOJO_GATEWAY_URL:-http://gateway:8080}"   # the portal API is reached through the gateway, signed in as this bot
CPC_TF="-no-color -input=false"
CPC_APPLY="tofu apply -auto-approve -lock-timeout=120s $CPC_TF"

cpc_ready() {
  if [ -z "${ARM_CLIENT_ID:-}" ] && [ -x /usr/local/bin/dojo-env ]; then
    eval "$(/usr/local/bin/dojo-env 2>/dev/null)"
  fi
  [ -n "${ARM_CLIENT_ID:-}" ] || { narrate "no Dojo Cloud credentials for $BOT_USER yet (dojo-env/broker not ready) -- skipping this step"; return 1; }
  cd "$CPC_LAB" 2>/dev/null || return 1
}

# cpc_run_line WORKFLOW MINID: "<id> <status>" of the newest run of WORKFLOW (e.g. pr.yml) with an id above MINID.
cpc_run_line() {
  api_curl "$API/repos/$CPC_FORK/actions/runs?limit=50" | python3 -c '
import json, sys
wf, minid = sys.argv[1], int(sys.argv[2])
try:
    d = json.load(sys.stdin)
    runs = d.get("workflow_runs", []) if isinstance(d, dict) else d
    runs = [r for r in runs if wf in json.dumps(r) and int(r.get("id", 0)) > minid]
    r = max(runs, key=lambda r: int(r["id"]))
    print(r["id"], r.get("status") or r.get("conclusion") or "")
except Exception:
    pass' "$1" "$2"
}

cpc_max_id() { local l; l="$(cpc_run_line "$1" 0)"; echo "${l%% *}" | grep -E '^[0-9]+$' || echo 0; }

# cpc_wait_run WORKFLOW MINID SECONDS: wait (bounded) for a run above MINID to finish; sets CPC_STATUS
# (success, failure, cancelled, skipped, or timeout) and prints it.
cpc_wait_run() {
  local end=$(( SECONDS + $3 )) line st
  CPC_STATUS=timeout
  while [ "$SECONDS" -lt "$end" ]; do
    line="$(cpc_run_line "$1" "$2")"; st="${line#* }"
    case "$st" in success|failure|cancelled|skipped) CPC_STATUS="$st"; break ;; esac
    sleep 5
  done
  narrate "$1 run: $CPC_STATUS"
  [ "$CPC_STATUS" != timeout ]
}

# cpc_open_pr BRANCH TITLE: open a pull request inside the fork (base main); sets CPC_PR.
cpc_open_pr() {
  local json
  json="$(api_curl -X POST "$API/repos/$CPC_FORK/pulls" -H 'Content-Type: application/json' \
    -d "{\"head\":\"$1\",\"base\":\"main\",\"title\":\"$2\",\"body\":\"Demo bot (round $ROUND), safe to ignore.\"}")"
  CPC_PR="$(printf '%s' "$json" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2)"
  if [ -z "$CPC_PR" ]; then   # already open from an earlier try
    CPC_PR="$(api_curl "$API/repos/$CPC_FORK/pulls?state=open" | python3 -c '
import json, sys
b = sys.argv[1]
try:
    print(next(p["number"] for p in json.load(sys.stdin) if p["head"]["ref"] == b))
except Exception:
    pass' "$1")"
  fi
  [ -n "$CPC_PR" ] && narrate "pull request #$CPC_PR: $2"
}

cpc_merge_pr() {
  run_cmd "curl -s -o /dev/null -w 'merge: HTTP %{http_code}\\n' --netrc-file ~/.dojo-bot-netrc -X POST -H 'Content-Type: application/json' -d '{\"Do\":\"merge\"}' $API/repos/$CPC_FORK/pulls/$CPC_PR/merge"
}

# cpc_portal_enforcement MODE: what the portal's "Disable enforcement" button calls, through the gateway as this bot.
cpc_portal_enforcement() {
  local pw jar="$HOME/.cpc-portal-jar" body
  pw="$(awk '{for (i = 1; i < NF; i++) if ($i == "password") print $(i + 1)}' "$HOME/.dojo-bot-netrc" | head -1)"
  curl -s -o /dev/null -c "$jar" --data-urlencode "username=$BOT_USER" --data-urlencode "password=$pw" "$CPC_GW/login"
  for body in "{\"mode\":\"$1\"}"; do
    run_cmd "curl -s -o /dev/null -w 'portal: HTTP %{http_code}\\n' -b '$jar' -X POST -H 'Content-Type: application/json' -d '$body' $CPC_GW/cloud/api/policy/assignments/team-baseline/enforcement" || true
    [ "$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" -X POST -H 'Content-Type: application/json' -d "$body" "$CPC_GW/cloud/api/policy/assignments/team-baseline/enforcement")" -lt 300 ] && return 0
  done
  return 1
}

# cpc_scratch_init: ~/lab/scratch with the app's provider setup (Labs 1, 2, 3, 5, 6).
cpc_scratch_init() {
  run_cmd "rm -rf ~/lab/scratch && mkdir -p ~/lab/scratch && cd ~/lab/scratch"
  run_cmd "cp $CPC_LAB/infra/{providers,versions,variables}.tf ."
  run_cmd "tofu init -no-color -input=false >/dev/null && echo init ok"
}

# cpc_rg NAME LOCATION TAGLINES: append a scratch resource group to main.tf.
cpc_rg() {
  cat >> main.tf <<EOT
resource "azurerm_resource_group" "$1" {
  name     = "rg-\${var.owner}-$1"
  location = "$2"
  tags = {
$3
  }
}

EOT
}

# cpc_cg IMAGE CPU: append the scratch container group (in the scratch resource group) to main.tf.
cpc_cg() {
  cat >> main.tf <<EOT

resource "azurerm_container_group" "scratch" {
  name                = "ci-\${var.owner}-scratch"
  location            = azurerm_resource_group.scratch.location
  resource_group_name = azurerm_resource_group.scratch.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "\${var.owner}-scratch"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "$1"
    cpu    = $2
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
}

# Undo the last round: destroy what it built (policy first), put the fork's main back on the team's,
# and wait for the pipeline that push starts. Does nothing in round 1.
step_cpc_reset() {
  [ "$ROUND" -gt 1 ] || return 0
  cpc_ready || return 0
  narrate "round $ROUND -- undoing last round: destroy, then the fork's main back to the team's"
  run_cmd "rm -rf ~/lab/scratch; rm -f infra/drift-demo.tf"
  cpc_portal_enforcement Default || true
  run_cmd "(cd policy/cloud && tofu destroy -auto-approve -lock-timeout=120s $CPC_TF)"
  run_cmd "(cd infra && tofu destroy -auto-approve -lock-timeout=120s $CPC_TF)"
  run_cmd "git checkout -q -f main && git fetch -q upstream"
  run_cmd "git branch -D drop-costcenter waive-legacy-costcenter 2>/dev/null; git push origin --delete drop-costcenter waive-legacy-costcenter 2>/dev/null"
  local min; min="$(cpc_max_id main.yml)"
  run_cmd "git reset -q --hard upstream/main && git clean -fdq && git push -q -f origin main"
  cpc_wait_run main.yml "$min" 900 || true
  return 0
}

# Lab 0: fork (done by step_ensure_clone), lab-prep, then the app applied from infra/.
step_cpc_lab0() {
  cpc_ready || return 0
  narrate "Lab 0 -- lab-prep saves the cloud login as Actions secrets and protects main"
  run_cmd "lab-prep 0"
  run_cmd "ls infra policy/cloud policy/cloud/rules policy/rego .forgejo/workflows"
  run_cmd "cat infra/main.tf | head -20"
  narrate "Lab 0 -- first apply: the app"
  run_cmd "cd $CPC_LAB/infra && tofu init $CPC_TF >/dev/null && echo init ok"
  run_cmd "$CPC_APPLY"
  run_cmd "tofu state list"
}

# Lab 1: the platform's built-in guardrails, refused three ways in a scratch folder.
step_cpc_lab1() {
  cpc_ready || return 0
  narrate "Lab 1 -- built-in guardrails in a scratch folder"
  cpc_scratch_init
  narrate "a group in eastus: the mistake the lab expects"
  cpc_rg scratch eastus '    owner = var.owner
    env   = "dev"'
  run_cmd "$CPC_APPLY"
  narrate "right -- 403 RequestDisallowedByPolicy, location not allowed. Canada Central, but no env tag."
  : > main.tf; cpc_rg scratch canadacentral '    owner = var.owner'
  run_cmd "$CPC_APPLY"
  narrate "refused again: missing tag 'env'. Putting it back."
  run_cmd "sed -i 's/owner = var.owner/owner = var.owner\\n    env   = \"dev\"/' main.tf"
  run_cmd "$CPC_APPLY"
  narrate "now a container group asking for twice the CPU"
  cpc_cg dojo/hello:1.0 0.5
  run_cmd "$CPC_APPLY"
  narrate "refused with a 400 this time. Back to 0.25 and apply."
  run_cmd "sed -i 's/cpu    = 0.5/cpu    = 0.25/' main.tf"
  run_cmd "$CPC_APPLY"
  run_cmd "tofu destroy -auto-approve -lock-timeout=120s $CPC_TF"
  cd "$CPC_LAB" || return 1
}

# Lab 2: predict the verdict: allowed region, blank tag, unapproved image.
step_cpc_lab2() {
  cpc_ready || return 0
  narrate "Lab 2 -- predict the verdict"
  cpc_scratch_init
  cpc_rg scratch canadaeast '    owner = var.owner
    env   = "dev"'
  run_cmd "$CPC_APPLY"
  narrate "case 2: an empty env tag on a second group"
  cpc_rg blank canadacentral '    owner = var.owner
    env   = ""'
  run_cmd "$CPC_APPLY"
  run_cmd "python3 -c \"s = open('main.tf').read(); open('main.tf', 'w').write(s.split('resource \\\"azurerm_resource_group\\\" \\\"blank\\\"')[0])\""
  narrate "case 3: an image that is not on the approved list"
  cpc_cg dojo/hello:3.0 0.25
  run_cmd "$CPC_APPLY"
  run_cmd "tofu destroy -auto-approve -lock-timeout=120s $CPC_TF"
  cd "$CPC_LAB" || return 1
}

# Lab 3: the first policy as code (slow: definition and assignment replicate for about 100 s each).
step_cpc_lab3() {
  cpc_ready || return 0
  narrate "Lab 3 -- first policy as code: require a costCenter tag"
  cd policy/cloud || return 1
  run_cmd "cat rules/require-costcenter-tag.json"
  run_cmd "sed -i '5,27s/^# \\{0,1\\}//' main.tf"
  run_cmd "tofu fmt"
  run_cmd "tofu init $CPC_TF >/dev/null && tofu plan $CPC_TF | tail -4"
  run_cmd "$CPC_APPLY"
  narrate "a group without costCenter: the denial the lab shows"
  cpc_scratch_init
  cpc_rg scratch canadacentral '    owner = var.owner
    env   = "dev"'
  run_cmd "$CPC_APPLY"
  narrate "refused by 'Require a costCenter tag'. Adding the tag."
  run_cmd "sed -i 's/env   = \"dev\"/env   = \"dev\"\\n    costCenter = \"cc-1001\"/' main.tf"
  run_cmd "$CPC_APPLY"
  run_cmd "tofu destroy -auto-approve -lock-timeout=120s $CPC_TF"
  narrate "Lab 3 -- what the policy thinks of the app: add costCenter to local.tags"
  run_cmd "cd $CPC_LAB/infra"
  run_cmd "sed -i '0,/env   = \"dev\"/s//env        = \"dev\"\\n    costCenter = \"cc-1001\"/' main.tf"
  run_cmd "tofu fmt && tofu plan $CPC_TF | tail -3"
  run_cmd "$CPC_APPLY"
  cd "$CPC_LAB" || return 1
}

# Lab 4: audit first. The legacy group is refused under deny, then allowed after the switch to audit.
step_cpc_lab4() {
  cpc_ready || return 0
  narrate "Lab 4 -- the legacy resource group, refused under deny"
  cat >> infra/main.tf <<'EOT'

# Lab 4: an older resource group with no costCenter tag.
resource "azurerm_resource_group" "legacy" {
  name     = "rg-${var.owner}-legacy"
  location = var.location
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
  run_cmd "cd infra && tofu fmt && $CPC_APPLY"
  narrate "refused: 403. Switching the assignment to audit, one parameter."
  run_cmd "cd ../policy/cloud && tofu fmt"
  run_cmd "sed -i '/^  policy_definition_id = azurerm_policy_definition.require_costcenter.id\$/a\\  parameters = jsonencode({\\n    effect = { value = \"audit\" }\\n  })' main.tf"
  run_cmd "tofu fmt && tofu plan $CPC_TF | tail -4"
  run_cmd "$CPC_APPLY"
  run_cmd "cd $CPC_LAB/infra && $CPC_APPLY"
  run_cmd "cd $CPC_LAB && git add infra policy && git commit -q -m 'Audit the costCenter rule; add the legacy resource group'"
}

# Lab 5: one definition, two assignments (one DoNotEnforce), app to 2.0, then enforce.
step_cpc_lab5() {
  cpc_ready || return 0
  narrate "Lab 5 -- allowed images: a definition and two assignments"
  cd policy/cloud || return 1
  run_cmd "cat rules/allowed-images.json | head -12"
  run_cmd "sed -i '/^# Lab 5:/,/^# Lab 6:/{/^# Lab [56]:/!s/^# \\{0,1\\}//}' main.tf"
  run_cmd "tofu fmt && tofu plan $CPC_TF | tail -3"
  run_cmd "$CPC_APPLY"
  narrate "the app still runs 1.0, which images-strict would refuse: move it to 2.0"
  run_cmd "cd $CPC_LAB/infra && sed -i 's#dojo/hello:1.0#dojo/hello:2.0#' main.tf"
  run_cmd "tofu plan $CPC_TF | tail -3"
  run_cmd "$CPC_APPLY"
  narrate "enforce the strict assignment: one line"
  run_cmd "cd ../policy/cloud && sed -i 's/^\\( *enforce *= \\)false/\\1true/' main.tf && tofu fmt && tofu plan $CPC_TF | tail -4"
  run_cmd "$CPC_APPLY"
  narrate "a container on 1.0 in the app group: refused by images-strict"
  cpc_scratch_init
  cat > main.tf <<'EOT'
data "azurerm_resource_group" "rg" {
  name = "rg-${var.owner}-app"
}

resource "azurerm_container_group" "scratch" {
  name                = "ci-${var.owner}-scratch"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${var.owner}-scratch"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:1.0"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
  }
}
EOT
  run_cmd "$CPC_APPLY"
  narrate "now the legacy group, which only the subscription assignment covers"
  run_cmd "sed -i 's/-app\"/-legacy\"/' main.tf"
  run_cmd "$CPC_APPLY"
  run_cmd "tofu destroy -auto-approve -lock-timeout=120s $CPC_TF"
  run_cmd "cd $CPC_LAB && git add infra policy && git commit -q -m 'Allowed images: one definition, two assignments; app on 2.0'"
}

# Lab 6: a policy set replaces the two subscription assignments.
step_cpc_lab6() {
  cpc_ready || return 0
  narrate "Lab 6 -- the team baseline policy set"
  cd policy/cloud || return 1
  run_cmd "sed -i '/^# Lab 6:/,/^# Lab 7:/{/^# Lab [67]:/!s/^# \\{0,1\\}//}' main.tf"
  python3 - <<'EOT'
import re
s = open("main.tf").read()
for name in ("require_costcenter", "images_subscription"):
    s = re.sub(r'(?:#[^\n]*\n)*resource "azurerm_subscription_policy_assignment" "%s" \{\n.*?\n\}\n\n?' % name, "", s, flags=re.S)
open("main.tf", "w").write(s)
EOT
  narrate "removed the two assignments the set replaces"
  run_cmd "tofu fmt && tofu validate $CPC_TF"
  run_cmd "tofu plan $CPC_TF | tail -3"
  run_cmd "$CPC_APPLY"
  narrate "a group without costCenter is refused through the set"
  cpc_scratch_init
  cpc_rg scratch canadacentral '    owner = var.owner
    env   = "dev"'
  run_cmd "$CPC_APPLY"
  run_cmd "tofu destroy -auto-approve -lock-timeout=120s $CPC_TF"
  run_cmd "cd $CPC_LAB && git add infra policy && git commit -q -m 'Team baseline policy set replaces the separate subscription assignments'"
}

# Lab 7: modify and remediation. The experiment's second container group is removed again at the end.
step_cpc_lab7() {
  cpc_ready || return 0
  narrate "Lab 7 -- modify: the cloud adds managedBy for you"
  cd policy/cloud || return 1
  run_cmd "cat rules/add-managedby-tag.json | head -12"
  python3 - <<'EOT'
# Uncomment Lab 7 up to (not including) the remediation block, which comes in step 6 of the lab.
lines = open("main.tf").read().split("\n")
out, sec, rem = [], False, False
for l in lines:
    if l.startswith("# Lab 7:"):
        sec = True
    elif l.startswith("# Lab 8:"):
        sec = False
    if sec and not l.startswith("# Lab 7:") and "azurerm_resource_group_policy_remediation" in l:
        rem = True
    if sec and not rem and not l.startswith("# Lab 7:") and l.startswith("#"):
        l = l[2:] if l.startswith("# ") else l[1:]
    out.append(l)
open("main.tf", "w").write("\n".join(out))
EOT
  run_cmd "tofu fmt && tofu validate $CPC_TF"
  run_cmd "$CPC_APPLY"
  narrate "a second container group: accepted, then modified on the way in"
  cat >> ../../infra/main.tf <<'EOT'

resource "azurerm_container_group" "second" {
  name                = "ci-${var.owner}-second"
  location            = azurerm_resource_group.app.location
  resource_group_name = azurerm_resource_group.app.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${var.owner}-second"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:2.0"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = local.tags
}
EOT
  run_cmd "cd $CPC_LAB/infra && tofu fmt && $CPC_APPLY"
  run_cmd "tofu plan $CPC_TF | tail -8"
  narrate "OpenTofu wants to remove managedBy: tell it the tag is not its business"
  python3 - <<'EOT'
s = open("main.tf").read()
s = s.replace("  tags = local.tags\n}", "  tags = local.tags\n\n  # The modify policy adds managedBy outside this config; do not fight it.\n  lifecycle {\n    ignore_changes = [tags[\"managedBy\"]]\n  }\n}")
open("main.tf", "w").write(s)
EOT
  run_cmd "tofu fmt && tofu plan $CPC_TF | tail -3"
  narrate "remediate what already exists"
  run_cmd "cd ../policy/cloud && sed -i '/^# Lab 7:/,/^# Lab 8:/{/^# Lab [78]:/!s/^# \\{0,1\\}//}' main.tf && tofu fmt"
  run_cmd "$CPC_APPLY"
  narrate "tidy up: delete the second group (keep the lifecycle on app)"
  python3 - <<'EOT'
import re
p = "../../infra/main.tf"
s = open(p).read()
s = re.sub(r'\nresource "azurerm_container_group" "second" \{\n.*?\n\}\n', "", s, flags=re.S)
open(p, "w").write(s)
EOT
  run_cmd "cd $CPC_LAB/infra && tofu fmt && $CPC_APPLY"
  run_cmd "cd $CPC_LAB && git add infra policy && git commit -q -m 'Modify policy: managedBy tag added by the cloud, ignored by OpenTofu'"
}

# Lab 8: an exemption through a pull request: push a branch, open the PR in the fork, wait for green, merge.
step_cpc_lab8() {
  cpc_ready || return 0
  narrate "Lab 8 -- a waiver for the legacy group, reviewed as code"
  cd policy/cloud || return 1
  run_cmd "sed -i '/^# Lab 8:/,\$ {/^# Lab 8:/!s/^# \\{0,1\\}//}' main.tf"
  run_cmd "d=\$(date -u -d '+7 days' +%Y-%m-%dT00:00:00Z); sed -i \"s/^\\( *expires_on *= \\).*/\\1\\\"\$d\\\"/\" main.tf; grep expires_on main.tf"
  run_cmd "tofu fmt && tofu validate $CPC_TF && cd $CPC_LAB"
  run_cmd "git checkout -q -B waive-legacy-costcenter"
  run_cmd "git add policy/cloud/main.tf && git commit -q -m 'Waive costCenter on the legacy resource group (OPS-123)'"
  local min; min="$(cpc_max_id pr.yml)"
  run_cmd "git push -q -f -u origin waive-legacy-costcenter"
  cpc_open_pr waive-legacy-costcenter "[$BOT_USER] Waive costCenter on the legacy RG" || return 1
  cpc_wait_run pr.yml "$min" 900 || return 1
  [ "$CPC_STATUS" = success ] || { narrate "the policy check did not pass on the waiver"; return 1; }
  min="$(cpc_max_id main.yml)"
  cpc_merge_pr
  cpc_wait_run main.yml "$min" 900 || true
  run_cmd "git checkout -q main && git pull -q --no-edit"
}

# Lab 9: conftest over a plan, ahead of the cloud's 403.
step_cpc_lab9() {
  cpc_ready || return 0
  narrate "Lab 9 -- check the plan before the cloud does"
  cd infra || return 1
  run_cmd "tofu plan -out=plan.out $CPC_TF >/dev/null && tofu show -json plan.out > plan.json && python3 -m json.tool plan.json | head -8"
  run_cmd "cd .. && cat policy/rego/costcenter.rego | head -20"
  narrate "a resource group with no costCenter"
  cd "$CPC_LAB" || return 1
  cat >> infra/main.tf <<'EOT'

resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = var.location
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
  run_cmd "cd infra && tofu plan -out=plan.out $CPC_TF >/dev/null && tofu show -json plan.out > plan.json && cd .. && conftest test --policy policy/rego --namespace main infra/plan.json"
  narrate "conftest says no; the cloud says no too"
  run_cmd "cd infra && $CPC_APPLY"
  narrate "add the tag and the plan passes"
  python3 - <<'EOT'
p = "infra/main.tf"
s = open(p).read()
i = s.rindex('    env   = "dev"\n  }\n}')
s = s[:i] + '    env   = "dev"\n    costCenter = "cc-1001"\n  }\n}' + s[i + len('    env   = "dev"\n  }\n}'):]
open(p, "w").write(s)
EOT
  run_cmd "cd $CPC_LAB/infra && tofu fmt && tofu plan -out=plan.out $CPC_TF >/dev/null && tofu show -json plan.out > plan.json && cd .. && conftest test --policy policy/rego --namespace main infra/plan.json"
  narrate "drop the scratch block again"
  python3 - <<'EOT'
p = "infra/main.tf"
s = open(p).read()
open(p, "w").write(s.split('\nresource "azurerm_resource_group" "scratch"')[0].rstrip("\n") + "\n")
EOT
  run_cmd "cd infra && tofu plan $CPC_TF | tail -2; cd $CPC_LAB && git status --short"
}

# Lab 10: test the policy: a failing test first, then the fix, then push to main (and wait for the pipeline).
step_cpc_lab10() {
  cpc_ready || return 0
  narrate "Lab 10 -- test the policy"
  run_cmd "opa test policy/rego --ignore fixtures -v | tail -4"
  narrate "write the failing test first: canadawest is not allowed"
  printf '\ntest_canadawest_denied if {\n\tcount(deny) == 1 with input as rc("canadawest")\n}\n' >> policy/rego/regions_test.rego
  run_cmd "opa test policy/rego --ignore fixtures | tail -4"
  narrate "red for the right reason: the rule checks a prefix, not the set. Fix it."
  run_cmd "sed -i 's/not startswith(loc, \"canada\")/not loc in allowed_regions/' policy/rego/regions.rego"
  run_cmd "opa fmt --diff policy/rego; opa test policy/rego --ignore fixtures -v | tail -4"
  printf '\ntest_near_misses_denied if {\n\tevery loc in ["eastus", "westeurope", "canada", "canadacentral2", ""] {\n\t\tcount(deny) == 1 with input as rc(loc)\n\t}\n}\n' >> policy/rego/regions_test.rego
  run_cmd "opa test policy/rego --ignore fixtures --coverage | python3 -c \"import sys,json; print(json.load(sys.stdin)['coverage'])\""
  run_cmd "conftest test --policy policy/rego --namespace main policy/rego/fixtures/plan-good.json"
  run_cmd "conftest test --policy policy/rego --namespace main policy/rego/fixtures/plan-bad.json"
  local min; min="$(cpc_max_id main.yml)"
  run_cmd "git add policy/rego && git commit -q -m 'regions.rego: check the allowed set, not a prefix; test canadawest'"
  run_cmd "git pull -q --no-edit --rebase; git push -q origin main"
  cpc_wait_run main.yml "$min" 900 || true
  return 0
}

# Lab 11: the pipeline: a pull request that must fail (costCenter dropped), the fix, green, merge, main applies.
step_cpc_lab11() {
  cpc_ready || return 0
  narrate "Lab 11 -- a pull request the pipeline should refuse"
  run_cmd "git checkout -q -B drop-costcenter"
  run_cmd "sed -i '/costCenter = \"cc-1001\"/d' infra/main.tf"
  run_cmd "cd infra && tofu plan -out=plan.out $CPC_TF >/dev/null && tofu show -json plan.out > plan.json && cd .. && conftest test --policy policy/rego --namespace main infra/plan.json"
  run_cmd "git add infra/main.tf && git commit -q -m 'Drop the costCenter tag (this should be refused)'"
  local min; min="$(cpc_max_id pr.yml)"
  run_cmd "git push -q -f -u origin drop-costcenter"
  cpc_open_pr drop-costcenter "[$BOT_USER] Drop costCenter (expect a failure)" || return 1
  cpc_wait_run pr.yml "$min" 900 || return 1
  narrate "the Policy check ended: $CPC_STATUS (the lab expects failure at the Conftest step)"
  narrate "fix: restore costCenter and add a team tag"
  run_cmd "git checkout -q main -- infra/main.tf && sed -i 's/costCenter = \"cc-1001\"/&\\n    team       = \"platform\"/' infra/main.tf && tofu fmt infra && git diff --stat"
  run_cmd "git add infra/main.tf && git commit -q -m 'Restore costCenter; add a team tag'"
  min="$(cpc_max_id pr.yml)"
  run_cmd "git push -q origin drop-costcenter"
  cpc_wait_run pr.yml "$min" 900 || return 1
  [ "$CPC_STATUS" = success ] || { narrate "the fixed pull request is still red"; return 1; }
  min="$(cpc_max_id main.yml)"
  cpc_merge_pr
  cpc_wait_run main.yml "$min" 900 || true
  run_cmd "git checkout -q main && git pull -q --no-edit"
}

# Lab 12: drift: enforcement switched off in the portal, found by drift.yml, put back from git.
step_cpc_lab12() {
  cpc_ready || return 0
  narrate "Lab 12 -- drift: a clean baseline first"
  local min code
  min="$(cpc_max_id drift.yml)"
  run_cmd "curl -s -o /dev/null -w 'dispatch drift: HTTP %{http_code}\\n' --netrc-file ~/.dojo-bot-netrc -X POST -H 'Content-Type: application/json' -d '{\"ref\":\"main\"}' $API/repos/$CPC_FORK/actions/workflows/drift.yml/dispatches"
  cpc_wait_run drift.yml "$min" 600 || return 1
  [ "$CPC_STATUS" = success ] || narrate "baseline is not green; the policy apply below puts git back"
  narrate "2 a.m.: disable enforcement of team-baseline in the portal"
  cpc_portal_enforcement DoNotEnforce || { narrate "the portal did not accept the change (see HTTP codes above)"; return 1; }
  cat > infra/drift-demo.tf <<'EOT'
resource "azurerm_resource_group" "drift_demo" {
  name     = "rg-${var.owner}-drift"
  location = var.location
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
  run_cmd "cd infra && $CPC_APPLY"
  narrate "no refusal: the policy is not enforcing. Let the detector look."
  min="$(cpc_max_id drift.yml)"
  run_cmd "curl -s -o /dev/null -w 'dispatch drift: HTTP %{http_code}\\n' --netrc-file ~/.dojo-bot-netrc -X POST -H 'Content-Type: application/json' -d '{\"ref\":\"main\"}' $API/repos/$CPC_FORK/actions/workflows/drift.yml/dispatches"
  cpc_wait_run drift.yml "$min" 600 || return 1
  narrate "drift run: $CPC_STATUS (the lab expects failure: DRIFT: someone changed policy outside git)"
  narrate "make git win: apply policy/cloud from the terminal (the lab's second way)"
  run_cmd "cd $CPC_LAB/policy/cloud && $CPC_APPLY"
  min="$(cpc_max_id drift.yml)"
  run_cmd "curl -s -o /dev/null -w 'dispatch drift: HTTP %{http_code}\\n' --netrc-file ~/.dojo-bot-netrc -X POST -H 'Content-Type: application/json' -d '{\"ref\":\"main\"}' $API/repos/$CPC_FORK/actions/workflows/drift.yml/dispatches"
  cpc_wait_run drift.yml "$min" 600 || return 1
  narrate "drift run after the fix: $CPC_STATUS (expected success)"
  narrate "clean up the group that slipped through"
  run_cmd "cd $CPC_LAB/infra && rm drift-demo.tf && $CPC_APPLY"
  cd "$CPC_LAB" || return 1
  [ "$CPC_STATUS" = success ]
}

STEPS=(
  step_ensure_clone
  step_sync_main
  step_cpc_reset
  step_cpc_lab0
  step_cpc_lab1
  step_cpc_lab2
  step_cpc_lab3
  step_cpc_lab4
  step_cpc_lab5
  step_cpc_lab6
  step_cpc_lab7
  step_cpc_lab8
  step_cpc_lab9
  step_cpc_lab10
  step_cpc_lab11
  step_cpc_lab12
  step_wrap_round
)
