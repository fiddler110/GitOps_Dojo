#!/bin/sh
set -eu

student_count="${STUDENT_COUNT:-30}"
student_password="${STUDENT_PASSWORD:-student123}"
student_prefix="${STUDENT_PREFIX:-student}"
workshop_name="${WORKSHOP_NAME:-Workshop Lab}"
facilitator_username="${FACILITATOR_USERNAME:-root}"
facilitator_password="${FACILITATOR_PASSWORD:?Set FACILITATOR_PASSWORD in engine/.env}"
lab_seed_dir="${LAB_SEED_DIR:-/opt/lab}"
student_shell="${STUDENT_SHELL:-/bin/zsh}"

# Demo/test bots -- see ./run.sh's --test flag and engine/README.md's "Demo
# bots (--test)" section. BOT_COUNT is 0 (disabled) unless a facilitator
# explicitly asked for demo bots, via `./run.sh <workshop> --test` or by
# setting BOT_COUNT in .env directly.
bot_count="${BOT_COUNT:-0}"
bot_prefix="${BOT_PREFIX:-testuser}"
bot_password="${BOT_PASSWORD:-testuser123}"
forgejo_org="${FORGEJO_ORG:-training}"
forgejo_repo="${FORGEJO_REPO:-sample-training-repo}"
forgejo_fork_workflow="${FORGEJO_FORK_WORKFLOW:-0}"

case "$student_count" in
  ''|*[!0-9]*)
    echo "STUDENT_COUNT must be a positive integer" >&2
    exit 1
    ;;
esac

if [ "$student_count" -lt 1 ] || [ "$student_count" -gt 99 ]; then
  echo "STUDENT_COUNT must be between 1 and 99" >&2
  exit 1
fi

case "$bot_count" in
  ''|*[!0-9]*)
    echo "BOT_COUNT must be a non-negative integer" >&2
    exit 1
    ;;
esac

if [ "$bot_count" -gt 35 ]; then
  echo "BOT_COUNT must be 35 or fewer" >&2
  exit 1
fi

mkdir -p /home

if ! id "$facilitator_username" >/dev/null 2>&1; then
  useradd --create-home --home-dir "/home/$facilitator_username" --shell "$student_shell" "$facilitator_username"
else
  usermod --shell "$student_shell" "$facilitator_username"
fi

echo "$facilitator_username:$facilitator_password" | chpasswd
mkdir -p /etc/sudoers.d
printf '%s ALL=(ALL) ALL\n' "$facilitator_username" > /etc/sudoers.d/facilitator
chmod 440 /etc/sudoers.d/facilitator

facilitator_home="$(getent passwd "$facilitator_username" | cut -d: -f6)"
mkdir -p "$facilitator_home/lab"

# Copy any lab file the facilitator doesn't already have (new files land on
# every restart), but never overwrite a file the facilitator has touched.
if [ -d "$lab_seed_dir" ]; then
  cp -Rn "$lab_seed_dir"/. "$facilitator_home/lab/"
fi

if [ -f "$lab_seed_dir/README.md" ]; then
  rm -f "$facilitator_home/lab/README.md"
  ln -s "$lab_seed_dir/README.md" "$facilitator_home/lab/README.md"
fi

# Authored under engine/web-terminal/zshrc.facilitator (see that file to
# add aliases etc.). Always resynced to the current version on every
# container start, same as the README.md symlink above.
rm -f "$facilitator_home/.zshrc"
ln -s /opt/dojo-shell/zshrc.facilitator "$facilitator_home/.zshrc"

# The schema/update settings below switch off background fetches that can
# only fail here: this container has no network route out, so SchemaStore
# (redhat.vscode-yaml), JSON schema downloads and extension update checks
# would just retry for nothing in every account's extension host. Same
# settings in the student settings.json further down.
code_server_settings_dir="$facilitator_home/.local/share/code-server/User"
if [ ! -f "$code_server_settings_dir/settings.json" ]; then
  mkdir -p "$code_server_settings_dir"
  cat > "$code_server_settings_dir/settings.json" <<'EOF'
{
  "workbench.colorTheme": "GitHub Dark",
  "workbench.startupEditor": "none",
  "chat.disableAIFeatures": true,
  "workbench.panel.defaultLocation": "right",
  "task.allowAutomaticTasks": "on",
  "extensions.ignoreRecommendations": true,
  "extensions.autoCheckUpdates": false,
  "extensions.autoUpdate": false,
  "yaml.schemaStore.enable": false,
  "json.schemaDownload.enable": false
}
EOF
fi

# Auto-reveals a live terminal on the right-hand panel as soon as the
# workspace opens (a fresh workspace never shows one on its own --
# task.allowAutomaticTasks above skips the "allow automatic tasks" prompt
# this depends on). See the matching block for students below.
if [ ! -f "$facilitator_home/lab/.vscode/tasks.json" ]; then
  mkdir -p "$facilitator_home/lab/.vscode"
  cat > "$facilitator_home/lab/.vscode/tasks.json" <<'EOF'
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Terminal",
      "type": "shell",
      "command": "zsh",
      "isBackground": true,
      "presentation": {
        "reveal": "always",
        "panel": "dedicated"
      },
      "runOptions": {
        "runOn": "folderOpen"
      },
      "problemMatcher": []
    }
  ]
}
EOF
fi

chown -R "$facilitator_username:$facilitator_username" "$facilitator_home"

# -- Per-UID loopback isolation ---------------------------------------------
# All accounts' code-server/ttyd processes live in this one container, bound
# to 0.0.0.0, on deterministic ports, with --auth none / ttyd -W (writable,
# no auth) -- see workspace-control.py. The intended access-control point is
# Caddy + the allocator's forward_auth, sitting in front of this container.
# But because every account shares this one network namespace, student01's
# own shell can `curl 127.0.0.1:9002` and get full read/write access to
# student02's IDE/terminal, completely bypassing Caddy/allocator. This
# iptables chain is what actually enforces "your own ports only" at the OS
# level, matching the trust boundary the rest of the stack assumes exists.
#
# FACILITATOR_IDE_PORT/FACILITATOR_TERM_PORT here must match the same-named
# constants in workspace-control.py.
facilitator_ide_port=9099
facilitator_term_port=9599

echo "Setting up per-account loopback isolation (DOJO_ISOLATION iptables chain)..." >&2

# Idempotent: re-running entrypoint.sh (e.g. a container restart without
# recreation) must not accumulate duplicate rules, so flush an existing
# chain instead of erroring on -N, and only add the OUTPUT jump if it isn't
# already there.
iptables -N DOJO_ISOLATION 2>/dev/null || iptables -F DOJO_ISOLATION
iptables -C OUTPUT -j DOJO_ISOLATION 2>/dev/null || iptables -A OUTPUT -j DOJO_ISOLATION

# Root/PID1 always needs to reach every account's ports for its own
# readiness probes (workspace-control.py's port_open()/start_workspace()).
iptables -A DOJO_ISOLATION -p tcp -m owner --uid-owner 0 -j ACCEPT

# Reusable for the facilitator, each student, and each bot below: allows
# only the given account's own uid to reach its own IDE/term ports.
add_isolation_rule() {
  user="$1"
  ide_port="$2"
  term_port="$3"
  uid="$(id -u "$user")"
  iptables -A DOJO_ISOLATION -p tcp --dport "$ide_port" -m owner --uid-owner "$uid" -j ACCEPT
  iptables -A DOJO_ISOLATION -p tcp --dport "$term_port" -m owner --uid-owner "$uid" -j ACCEPT
}

# Mostly a no-op when FACILITATOR_USERNAME defaults to "root" (uid 0 is
# already allowed above), but must still work correctly if a deployment sets
# a non-root facilitator username.
add_isolation_rule "$facilitator_username" "$facilitator_ide_port" "$facilitator_term_port"

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"

  if [ "$username" = "$facilitator_username" ]; then
    echo "FACILITATOR_USERNAME must not match a generated student username: $username" >&2
    exit 1
  fi

  if ! id "$username" >/dev/null 2>&1; then
    useradd --create-home --home-dir "/home/$username" --shell "$student_shell" "$username"
  else
    usermod --shell "$student_shell" "$username"
  fi

  echo "$username:$student_password" | chpasswd
  mkdir -p "/home/$username/lab"

  # Copy any lab file the student doesn't already have (new files land on
  # every restart), but never overwrite a file the student has touched.
  if [ -d "$lab_seed_dir" ]; then
    cp -Rn "$lab_seed_dir"/. "/home/$username/lab/"
  fi

  chown -R "$username:$username" "/home/$username"

  # 9000+counter/9500+counter must match IDE_PORT_BASE/TERM_PORT_BASE in
  # workspace-control.py.
  add_isolation_rule "$username" "$((9000 + counter))" "$((9500 + counter))"

  # Keep the authored instructions current while preserving student work.
  if [ -f "$lab_seed_dir/README.md" ]; then
    rm -f "/home/$username/lab/README.md"
    ln -s "$lab_seed_dir/README.md" "/home/$username/lab/README.md"
  fi

  if [ ! -f "/home/$username/.gitconfig" ]; then
    cat > "/home/$username/.gitconfig" <<EOF
[user]
	name = $username
	email = $username@example.com
[init]
	defaultBranch = main
EOF
    chown "$username:$username" "/home/$username/.gitconfig"
  fi

  student_code_server_settings_dir="/home/$username/.local/share/code-server/User"
  if [ ! -f "$student_code_server_settings_dir/settings.json" ]; then
    mkdir -p "$student_code_server_settings_dir"
    cat > "$student_code_server_settings_dir/settings.json" <<'EOF'
{
  "workbench.colorTheme": "GitHub Dark",
  "workbench.startupEditor": "none",
  "chat.disableAIFeatures": true,
  "workbench.panel.defaultLocation": "right",
  "task.allowAutomaticTasks": "on",
  "extensions.ignoreRecommendations": true,
  "extensions.autoCheckUpdates": false,
  "extensions.autoUpdate": false,
  "yaml.schemaStore.enable": false,
  "json.schemaDownload.enable": false,
  "terminal.integrated.profiles.linux": {
    "dojo-shell": {
      "path": "/opt/dojo-shell/tmux-terminal.sh"
    }
  },
  "terminal.integrated.defaultProfile.linux": "dojo-shell"
}
EOF
    chown -R "$username:$username" "/home/$username/.local"
  fi

  # Auto-reveals a live terminal on the right-hand panel as soon as the
  # workspace opens -- see the matching facilitator block above for why.
  # Runs through /opt/dojo-shell/tmux-terminal.sh (also set as the default
  # terminal profile above), same as any terminal the student opens
  # manually -- each gets its own uniquely-named tmux session, so splits
  # and extra tabs stay independent instead of mirroring each other. A
  # facilitator's /admin/watch/<sid> mirror then follows whichever of the
  # student's sessions (this one, another VS Code terminal, or the
  # standalone Terminal tool's `main`) was most recently active -- see
  # workspace-control.py's most_active_session(). Not done for the
  # facilitator's own task below, since nobody needs to watch the
  # facilitator.
  if [ ! -f "/home/$username/lab/.vscode/tasks.json" ]; then
    mkdir -p "/home/$username/lab/.vscode"
    cat > "/home/$username/lab/.vscode/tasks.json" <<'EOF'
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Terminal",
      "type": "shell",
      "command": "/opt/dojo-shell/tmux-terminal.sh",
      "isBackground": true,
      "presentation": {
        "reveal": "always",
        "panel": "dedicated"
      },
      "runOptions": {
        "runOn": "folderOpen"
      },
      "problemMatcher": []
    }
  ]
}
EOF
    chown -R "$username:$username" "/home/$username/lab/.vscode"
  fi

  # Authored under engine/web-terminal/zshrc.student (see that file to add
  # aliases etc.). Always resynced to the current version on every
  # container start, same as the README.md symlink above.
  rm -f "/home/$username/.zshrc"
  ln -s /opt/dojo-shell/zshrc.student "/home/$username/.zshrc"

  counter=$((counter + 1))
done

# Demo/test bot accounts -- separate from the studentNN pool above (own
# prefix, own numbering starting at 1) so they never compete with real
# students for a slot. Each gets a home dir/lab copy/git identity just like
# a student, plus a small credentials file bot-runner.sh reads at startup
# (see that script) -- there's no browser login for these, so there's no
# other way to hand them BOT_PASSWORD/FORGEJO_ORG/FORGEJO_REPO that
# survives this process being killed and restarted by bot-supervisor.sh.
bot_counter=1
while [ "$bot_counter" -le "$bot_count" ]; do
  bot_username="$(printf '%s%d' "$bot_prefix" "$bot_counter")"

  if [ "$bot_username" = "$facilitator_username" ]; then
    echo "BOT_PREFIX must not produce a username matching FACILITATOR_USERNAME: $bot_username" >&2
    exit 1
  fi

  if ! id "$bot_username" >/dev/null 2>&1; then
    useradd --create-home --home-dir "/home/$bot_username" --shell "$student_shell" "$bot_username"
  else
    usermod --shell "$student_shell" "$bot_username"
  fi

  echo "$bot_username:$bot_password" | chpasswd
  mkdir -p "/home/$bot_username/lab"

  if [ -d "$lab_seed_dir" ]; then
    cp -Rn "$lab_seed_dir"/. "/home/$bot_username/lab/"
  fi

  # Persona: bots 1-3 are always expert/intermediate/novice; any bot past
  # that gets a random one of the three, so a big --test N gives a mixed
  # cohort. Sticky across container restarts (reuse what's already in the
  # env file) so a bot's saved step index never lands on a different
  # persona's step list.
  bot_persona=""
  if [ -f "/home/$bot_username/.dojo-bot.env" ]; then
    bot_persona="$(sed -n 's/^BOT_PERSONA=//p' "/home/$bot_username/.dojo-bot.env" | head -1)"
  fi
  case "$bot_persona" in
    expert|intermediate|novice) ;;
    *)
      if [ "$bot_counter" -le 3 ]; then
        idx=$(( bot_counter - 1 ))
      else
        idx=$(( $(od -An -N2 -tu2 /dev/urandom | tr -d ' ') % 3 ))
      fi
      case "$idx" in
        0) bot_persona=expert ;;
        1) bot_persona=intermediate ;;
        *) bot_persona=novice ;;
      esac
      ;;
  esac

  cat > "/home/$bot_username/.dojo-bot.env" <<EOF
BOT_USER=$bot_username
BOT_PASSWORD=$bot_password
BOT_PERSONA=$bot_persona
FORGEJO_ORG=$forgejo_org
FORGEJO_REPO=$forgejo_repo
FORGEJO_FORK_WORKFLOW=$forgejo_fork_workflow
EOF
  chmod 600 "/home/$bot_username/.dojo-bot.env"

  rm -f "/home/$bot_username/.zshrc"
  ln -s /opt/dojo-shell/zshrc.student "/home/$bot_username/.zshrc"

  chown -R "$bot_username:$bot_username" "/home/$bot_username"

  # 9700+bot_counter/9750+bot_counter must match BOT_IDE_PORT_BASE/
  # BOT_TERM_PORT_BASE in workspace-control.py -- a separate range from the
  # student ports above so a bot's trailing digit never collides with a
  # same-numbered student's IDE/term port (see change 2 in this file's
  # accompanying commit/PR, and workspace-control.py's BOT_IDE_PORT_BASE
  # comment).
  add_isolation_rule "$bot_username" "$((9700 + bot_counter))" "$((9750 + bot_counter))"

  bot_counter=$((bot_counter + 1))
done

# Default-deny catch-all: must be the LAST rule appended to DOJO_ISOLATION,
# after every add_isolation_rule call above (facilitator + all students +
# all bots) -- iptables evaluates rules in order and the first match wins,
# so anything not already ACCEPTed by uid above falls through to this DROP.
# Range covers every control-plane port range in the stack: student/
# facilitator IDE (9000-9099), student/facilitator term (9500-9599),
# facilitator watch-mirror ports (9600-9699), bot IDE/term (9700-9799), and
# bot watch-mirror ports (9800-9899). This only filters packets originating
# from processes inside this container (the OUTPUT chain) -- traffic
# arriving from the Caddy gateway container over the docker network is
# unaffected.
iptables -A DOJO_ISOLATION -p tcp -m multiport --dports 9000:9099,9500:9599,9600:9699,9700:9799,9800:9899 -j DROP

if [ "$bot_count" -gt 0 ]; then
  echo "Provisioned $bot_count demo bot account(s) with prefix '$bot_prefix'."
  # Backgrounded, not exec'd: workspace-control.py below stays PID 1 for the
  # container's whole life (see its own comment for why). This loop's job
  # is just to (re)create each bot's tmux `main` session -- see
  # bot-supervisor.sh for the restart-after-Release mechanics.
  BOT_COUNT="$bot_count" BOT_PREFIX="$bot_prefix" /opt/dojo-shell/bot-supervisor.sh &
fi

cat >/etc/motd <<EOF
Welcome to the ${workshop_name} CLI.

Student accounts: ${student_prefix}01 through $(printf '%s%02d' "$student_prefix" "$student_count")
Each account has its own home directory under /home.
Student shells use zsh with zoxide. Use 'z <dir>' to jump to recent directories.
Facilitator login: ${facilitator_username}
EOF

echo "Provisioned $student_count student terminal accounts."
echo "Facilitator shell username: $facilitator_username"
echo "Student shell usernames: ${student_prefix}01 through $(printf '%s%02d' "$student_prefix" "$student_count")"

# No per-account login prompt here anymore: the allocator service (see
# engine/allocator/) assigns each browser session an account and tells
# workspace-control.py (over the internal workshop_lab network only, never
# published through the gateway) to spawn that account's code-server/ttyd
# process on demand -- see engine/allocator/server.py and
# engine/web-terminal/workspace-control.py.
exec python3 /usr/local/bin/workspace-control.py
