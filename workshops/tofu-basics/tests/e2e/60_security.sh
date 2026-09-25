#!/usr/bin/env bash
# shellcheck shell=bash
# Area security (PLAN T9.2 live half and T9.8): what a curious student with a shell can and cannot do.
#   1  ARM authorisation and token forgery   (cross-tenant read and write, forged and tampered tokens, bad secrets)
#   2  the portal API's trust rule           (X-Auth-User counts only with X-Gateway-Token; students cannot get that token)
#   3  secrets and the credential broker     (signing key, broker identity, no root, no docker.sock)
#   4  reaching cloud-host                   (not on the student's network, no published ports, no TCP Docker API)
#   5  student containers on cloud-host      (--icc=false really blocks traffic, no route to cloud-api, hardened spec)
# Changes nothing a student owns. Two throw-away probe containers (secchk-a, secchk-b) run on cloud-host for part 5 and
# are removed before and after. Part 1 does one cross-tenant PUT that must be refused (it would create rg-sectest-probe
# in the other student's subscription; if a FAIL says it was accepted, delete that group).
# Sourced by tests/e2e.sh; running this file directly hands over with --only security.
# NOT covered: Caddy's header handling and the allocator's session logic (the gateway), and docker proper (T9.8 on the VM).

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only security "$@"; fi

# on_host LABEL CONTAINER cmd...   run a command inside a container (as $ONHOST_USER if set, else its default user); sets RC and OUT.
on_host() {
  local label=$1 ctr=$2; shift 2
  SEQ=$((SEQ + 1)); OUT="$LOG_DIR/$(printf '%s-%03d-%s' "$AREA" "$SEQ" "${label//[^A-Za-z0-9_.-]/_}").log"
  if is_dry; then dry "in $ctr${ONHOST_USER:+ as $ONHOST_USER}: $*"; : > "$OUT"; RC=0; return 0; fi
  timeout -k 5 90 "$CLI" exec ${ONHOST_USER:+-u "$ONHOST_USER"} "$ctr" "$@" 2>&1 | mask > "$OUT"; RC=${PIPESTATUS[0]}
  { printf '$ [%s %s] %s\n' "$ctr" "$label" "$*"; cat "$OUT"; printf '[rc=%s]\n\n' "$RC"; } | mask >> "$SESSION_LOG"
}

skip_check() { record SKIP "$AREA" "$1"; say "  SKIP  $1"; }

# The probe containers are throw-away: hello's image (busybox) with the same hardening flags the cloud host uses.
PROBE_FLAGS=(--cap-drop ALL --security-opt no-new-privileges --memory 32m --pids-limit 32)
remove_probes() { on_host rm-probes "$CLOUD_HOST_CONTAINER" docker rm -f secchk-a secchk-b; }

area_security() {
  local other fac other_sub other_cid ip_host ip_api
  other=$(user_name 2); [ "$other" = "$STUDENT" ] && other=$(user_name 1)
  if is_dry; then fac=admin; other_sub=OTHER-SUB; other_cid=OTHER-CID
  else
    fac=$("$CLI" exec "$CLOUD_API_CONTAINER" printenv FACILITATOR_USERNAME 2>/dev/null)
    other_sub=$(portal_sub "$other"); other_cid=$("$CLI" exec -u "$other" "$TERMINAL_CONTAINER" zsh -lc 'printenv ARM_CLIENT_ID' 2>/dev/null)
    [ -n "$fac" ] && [ -n "$other_sub" ] && [ -n "$other_cid" ] || abort_area "could not learn the facilitator name or $other's ids"
  fi
  say "  probing as $STUDENT; the other tenant is $other"

  # ---- 1. ARM authorisation and token forgery ---------------------------------------------------------------------
  local arm_probe="python3 - '$other_sub' '$other_cid' '$fac' <<'PY'"$'\n'"$(is_dry && echo '(helpers/sec_arm.py)' || cat "$TB_HELPERS/sec_arm.py")"$'\nPY'
  as_student "$STUDENT" "$arm_probe" 180 arm-probes
  expect_has "the student can get a token with their own credentials and read their own subscription" \
    'own_login=200' 'own_subscription=200'
  expect_has "listing subscriptions shows exactly one: their own" 'subscriptions_listed=1'
  expect_has "another student's subscription: read is refused with 403" 'other_subscription_read=403'
  expect_has "another student's subscription: write is refused with 403" 'other_subscription_write=403'
  expect_has "a subscription that does not exist gives the same 403 (no way to probe which ids exist)" 'unknown_subscription_read=403'
  expect_has "no token, or a garbage token, is 401" 'no_bearer=401' 'garbage_bearer=401'
  expect_has "a token with its payload swapped to the facilitator (old signature kept) is 401" \
    'payload_swapped_to_facilitator_keeping_signature=401'
  expect_has "an unsigned token (alg none) is 401" 'alg_none=401'
  expect_has "tokens signed with a guessed key are 401 (empty, 'dojo', the student's own client secret)" \
    'token_signed_with_empty_key=401' 'token_signed_with_guessed_key=401' 'token_signed_with_client_secret_as_key=401'
  expect_has "the token endpoint refuses a wrong secret, an empty secret, another client with my secret, an unknown client" \
    'wrong_credential=401' 'empty_credential=401' 'other_client_with_my_credential=401' 'unknown_client=401'
  expect_lacks "the probe printed no token or secret" 'eyJ' 'dojo~'

  # ---- 2. the portal API trusts X-Auth-User only together with X-Gateway-Token ------------------------------------
  local base=http://cloud-api:8080/cloud/api probe='' h
  for h in "" "-H 'X-Auth-User: $fac'" "-H 'X-Auth-User: $fac' -H 'X-Gateway-Token: dojo'" \
           "-H 'X-Auth-User: $fac' -H 'X-Gateway-Token:'" "-H 'X-Auth-User: $fac' -H \"X-Gateway-Token: \$ARM_CLIENT_SECRET\"" \
           "-H 'X-Auth-User: $other'"; do
    probe+="echo \"me[\$(curl -s -m 10 -o /dev/null -w '%{http_code}' $h $base/me)] \"; "
    probe+="echo \"progress[\$(curl -s -m 10 -o /dev/null -w '%{http_code}' $h $base/admin/progress)] \"; "
    probe+="echo \"purge[\$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST -d '{\"subscriptionId\":\"$other_sub\"}' $h $base/admin/purge)] \"; "
  done
  as_student "$STUDENT" "$probe" 120 forged-headers
  expect_lacks "forged X-Auth-User (alone, with an empty, wrong or guessed X-Gateway-Token) never gets through: /me, /admin/progress, /admin/purge are all 401" \
    'me[200]' 'progress[200]' 'purge[200]' 'me[403]' 'progress[403]' 'purge[403]' 'me[000]'
  expect_has "the refusals are 401 (unauthenticated)" 'me[401]' 'progress[401]' 'purge[401]'
  as_student "$STUDENT" 'echo "env_has_gw=$(env | grep -c "^GATEWAY_TOKEN=")"; leaks=0; for f in /proc/[0-9]*/environ; do tr "\0" "\n" < "$f" 2>/dev/null | grep -q "^GATEWAY_TOKEN=" && leaks=$((leaks+1)); done; echo "readable_environ_leaks=$leaks"' 60 gateway-token
  expect_has "the student's shell has no GATEWAY_TOKEN and no process environment they can read holds it" \
    'env_has_gw=0' 'readable_environ_leaks=0'

  # ---- 3. secrets and the broker ------------------------------------------------------------------------------------
  as_student "$STUDENT" 'echo "uid=$(id -u)"; ls -ld /run/cloud-secrets 2>&1; cat /run/cloud-secrets/signing.key 2>&1 | head -c 200; echo; echo "readable=$(find /run/cloud-secrets -type f -readable 2>/dev/null | wc -l)"; echo "sudo=$(sudo -n true >/dev/null 2>&1; echo $?)"; echo "dockersock=$(ls /var/run/docker.sock /run/docker.sock 2>/dev/null | wc -l)"' 60 secrets
  expect_lacks "the student is not root" 'uid=0'
  expect_has "the signing key cannot be read (permission denied), and no file in cloud-secrets is readable" 'readable=0'
  expect_lacks "nothing looks like a key or a secret in that output" 'dojo~' 'BEGIN'
  expect_lacks "passwordless sudo does not work" 'sudo=0'
  expect_has "there is no docker.sock in the student terminal" 'dockersock=0'
  # The broker has no request format: identity comes from SO_PEERCRED alone, so what a student gets is their own or nothing.
  local ask='import json,socket,sys
s=socket.socket(socket.AF_UNIX); s.settimeout(3); s.connect("/run/dojo-broker/broker.sock"); d=b""
while True:
    c=s.recv(65536)
    if not c: break
    d+=c
j=json.loads(d or b"{}"); print("broker_keys=%d sub=%s" % (len(j), j.get("ARM_SUBSCRIPTION_ID","")))'
  as_student "$STUDENT" "python3 -c '$ask'" 30 broker-own
  expect_has "the broker gives a student their own subscription id" "sub=$(is_dry && echo SUB || portal_sub "$STUDENT")"
  ONHOST_USER=nobody on_host broker-nobody "$TERMINAL_CONTAINER" python3 -c "$ask"
  expect_has "the broker gives a user who is not on the roster nothing" 'broker_keys=0'

  # ---- 4. reaching cloud-host ---------------------------------------------------------------------------------------
  ip_host=$(is_dry && echo 10.0.0.2 || "$CLI" inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$CLOUD_HOST_CONTAINER" 2>/dev/null | awk '{print $1}')
  ip_api=$(is_dry && echo 10.0.0.3 || "$CLI" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}' "$CLOUD_API_CONTAINER" 2>/dev/null | tr ' ' '\n' | grep -i cloud_net | cut -d= -f2)
  local nets
  nets=$(is_dry && echo "x" || "$CLI" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$TERMINAL_CONTAINER" 2>/dev/null)
  expect_ok "the terminal container is not on the cloud network (its networks: ${nets:-?})" bash -c '! grep -qi cloud_net <<<"$1"' _ "$nets"
  nets=$(is_dry && echo "x" || "$CLI" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$CLOUD_HOST_CONTAINER" 2>/dev/null)
  expect_ok "cloud-host is not on the student network (its networks: ${nets:-?})" bash -c '! grep -qi workshop_lab <<<"$1"' _ "$nets"
  local ports
  ports=$(is_dry && echo "map[]" || "$CLI" inspect -f '{{.HostConfig.PortBindings}}' "$CLOUD_HOST_CONTAINER" 2>/dev/null)
  expect_eq "cloud-host publishes no ports on the host" "map[]" "$ports"
  as_student "$STUDENT" "for t in cloud-host workshop_cloud_host $ip_host; do for p in 2375 2376 80 8080; do python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(3); s.connect((sys.argv[1], int(sys.argv[2])))' \$t \$p >/dev/null 2>&1 && echo \"REACHED \$t:\$p\"; done; done; echo probed" 120 reach-host
  expect_has "from a student shell nothing on cloud-host answers (names and address, ports 2375, 2376, 80, 8080)" 'probed'
  expect_lacks "no REACHED line" 'REACHED'
  on_host tcp-listeners "$CLOUD_HOST_CONTAINER" sh -c 'command -v netstat >/dev/null || echo NO_NETSTAT; netstat -ltn 2>&1 | grep -E ":(2375|2376) " || echo none'
  expect_has "dockerd on cloud-host has no TCP listener (only the unix socket)" 'none'
  expect_lacks "and the check could run (netstat exists there)" 'NO_NETSTAT'

  # ---- 5. student containers on cloud-host (T9.8) ----------------------------------------------------------------------
  remove_probes
  on_host icc-option "$CLOUD_HOST_CONTAINER" docker network inspect bridge -f '{{index .Options "com.docker.network.bridge.enable_icc"}}'
  expect_has "the default bridge has enable_icc=false (dockerd runs with --icc=false)" 'false'
  on_host probe-b "$CLOUD_HOST_CONTAINER" docker run -d --name secchk-b "${PROBE_FLAGS[@]}" --entrypoint sh dojo/hello:1.0 -c 'echo ok > /tmp/index.html; exec httpd -f -p 80 -h /tmp'
  on_host probe-a "$CLOUD_HOST_CONTAINER" docker run -d --name secchk-a "${PROBE_FLAGS[@]}" --entrypoint sleep dojo/hello:1.0 300
  expect_rc "both probe containers started" 0
  if ! is_dry; then sleep 2; fi
  local ip_b gw
  ip_b=$(is_dry && echo 172.17.0.3 || "$CLI" exec "$CLOUD_HOST_CONTAINER" docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' secchk-b 2>/dev/null)
  gw=$(is_dry && echo 172.17.0.1 || "$CLI" exec "$CLOUD_HOST_CONTAINER" docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null)
  on_host control "$CLOUD_HOST_CONTAINER" sh -c "wget -T 3 -qO- http://$ip_b:80/ >/dev/null 2>&1 && echo control_ok || echo control_failed"
  expect_has "control: cloud-host itself can reach the probe server (so the test below is meaningful)" 'control_ok'
  on_host icc-a-to-b "$CLOUD_HOST_CONTAINER" docker exec secchk-a sh -c "wget -T 3 -qO- http://$ip_b:80/ >/dev/null 2>&1 && echo REACHED || echo blocked"
  expect_has "one student container cannot reach another (--icc=false)" 'blocked'
  expect_lacks "and did not get through" 'REACHED'
  on_host a-to-dockerd "$CLOUD_HOST_CONTAINER" docker exec secchk-a sh -c "for p in 2375 2376; do wget -T 2 -qO- http://$gw:\$p/version >/dev/null 2>&1 && echo REACHED \$p; done; ls /var/run/docker.sock 2>/dev/null; echo done"
  expect_has "a student container cannot reach the Docker API through the bridge gateway ($gw:2375/2376) and has no docker.sock" 'done'
  expect_lacks "no Docker API reached" 'REACHED' 'docker.sock'
  if [ -n "$ip_api" ]; then
    on_host a-to-cloud-api "$CLOUD_HOST_CONTAINER" docker exec secchk-a sh -c "wget -T 2 -qO- http://$ip_api:8080/readyz >/dev/null 2>&1 && echo REACHED 8080; nc -w 2 $ip_api 443 </dev/null >/dev/null 2>&1 && echo REACHED 443; echo done"
    expect_has "a student container has no route to cloud-api ($ip_api) (PLAN 15a-G: unverified until now)" 'done'
    expect_lacks "cloud-api not reached from inside a student container" 'REACHED'
  else skip_check "student container to cloud-api: could not find cloud-api's address on the cloud network"; fi
  remove_probes

  # The real container Dojo Cloud creates: the hardened template, as dockerd reports it. Deployed here through ARM
  # (rg-sectest / ci-sectest in the student's subscription) and deleted again below.
  local sec_deploy
  sec_deploy=$(is_dry && echo "python3 - up   # helpers/sec_deploy.py" || printf '%s\n' "python3 - up <<'PY'" "$(cat "$TB_HELPERS/sec_deploy.py")" PY)
  as_student "$STUDENT" "$sec_deploy" 200 deploy
  expect_has "a policy-clean container group deploys through ARM (for the checks below)" 'deploy_ok=yes'
  on_host managed "$CLOUD_HOST_CONTAINER" sh -c 'docker ps -q --filter label=dojo.managed=true'
  if is_dry || [ -s "$OUT" ]; then
    local spec
    read -r -d '' spec <<'SH'
for c in $(docker ps -q --filter label=dojo.managed=true); do
  docker inspect -f "{{.Name}} privileged={{.HostConfig.Privileged}} capdrop={{.HostConfig.CapDrop}} secopt={{.HostConfig.SecurityOpt}} mem={{.HostConfig.Memory}} cpu={{.HostConfig.NanoCpus}} pids={{.HostConfig.PidsLimit}} netmode={{.HostConfig.NetworkMode}} binds={{.HostConfig.Binds}} mounts={{len .Mounts}}" $c
done > /tmp/secchk-spec
cat /tmp/secchk-spec
echo "checked=$(wc -l < /tmp/secchk-spec)"
echo "unsafe=$(grep -cE 'privileged=true|netmode=host|mem=0 |cpu=0 |pids=(0|-1|<nil>) |mounts=[1-9]|binds=\[[^]]' /tmp/secchk-spec)"
echo "not_hardened=$(grep -vc 'capdrop=\[ALL\] secopt=\[no-new-privileges\]' /tmp/secchk-spec)"
rm -f /tmp/secchk-spec
SH
    on_host managed-spec "$CLOUD_HOST_CONTAINER" sh -c "$spec"
    expect_has "no deployed container is privileged, host-networked, mounted, or unlimited (memory, cpu, pids)" 'unsafe=0'
    expect_has "every deployed container drops all capabilities and sets no-new-privileges" 'not_hardened=0'
    expect_lacks "and at least one container was checked" 'checked=0'
  else skip_check "deployed-container spec: the deploy above left no running student container (see that failure)"; fi
  local sec_delete
  sec_delete=$(is_dry && echo "python3 - down   # helpers/sec_deploy.py" || printf '%s\n' "python3 - down <<'PY'" "$(cat "$TB_HELPERS/sec_deploy.py")" PY)
  as_student "$STUDENT" "$sec_delete" 200 undeploy
  expect_has "and its resource group is deleted again (the subscription is left as it was found)" 'delete_ok=yes'
}
