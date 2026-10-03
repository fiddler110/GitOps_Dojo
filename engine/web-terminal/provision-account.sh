#!/bin/sh
# Creates or refreshes one student or demo-bot account: the Linux user, its
# home, the lab seed, git identity, code-server settings, the auto terminal
# task and the shared .zshrc. entrypoint.sh calls it for every account at
# start; a student reset (docs/archive/STUDENT-RESET-PLAN.md §4.3) calls it again for one
# account after removing that home. Idempotent: files a student may have
# changed are only written when missing.
#
# Usage: provision-account.sh <user>
#   <user> is ${STUDENT_PREFIX}NN (two digits) or ${BOT_PREFIX}N. The
#   facilitator is set up by entrypoint.sh, never here.
#
# Reads the same environment as entrypoint.sh, with the same defaults. The
# per-port DOJO_ISOLATION rules stay in entrypoint.sh: they must be appended
# in order, before the final DROP.
#
# Hardening (remediation T2.1, FIND-03): a student's Linux password is
# locked (only root's `su -` gets in, so one student can't `su` to
# another), the home is 0700, and git is signed in to Forgejo with the
# student's own token (forgejo-token.py). DOJO_DEFER_TOKEN=1 skips that last
# step: the entrypoint runs it for everyone at once, in the background,
# because Forgejo may still be starting.
set -eu

student_prefix="${STUDENT_PREFIX:-student}"
facilitator_username="${FACILITATOR_USERNAME:-root}"
lab_seed_dir="${LAB_SEED_DIR:-/opt/lab}"
student_shell="${STUDENT_SHELL:-/bin/zsh}"
bot_prefix="${BOT_PREFIX:-testuser}"
bot_password="${BOT_PASSWORD:-testuser123}"
forgejo_org="${FORGEJO_ORG:-training}"
forgejo_repo="${FORGEJO_REPO:-sample-training-repo}"
forgejo_fork_workflow="${FORGEJO_FORK_WORKFLOW:-0}"

username="${1:?usage: provision-account.sh <user>}"

if [ "$username" = "$facilitator_username" ]; then
  echo "provision-account.sh: $username is the facilitator" >&2
  exit 1
fi

# Which kind of account, from the name alone, so a reset needs nothing else.
kind=""
case "$username" in
  "$student_prefix"[0-9][0-9]) kind=student ;;
esac
if [ -z "$kind" ]; then
  bot_counter="${username#"$bot_prefix"}"
  case "$bot_counter" in
    "$username"|''|0*|*[!0-9]*) ;;
    *) kind=bot ;;
  esac
fi
if [ -z "$kind" ]; then
  echo "provision-account.sh: not a student or bot account: $username" >&2
  exit 1
fi

if ! id "$username" >/dev/null 2>&1; then
  useradd --create-home --home-dir "/home/$username" --shell "$student_shell" "$username"
else
  usermod --shell "$student_shell" "$username"
  # A reset removed the home but kept the user: start it again from
  # /etc/skel, as useradd --create-home does.
  if [ ! -d "/home/$username" ]; then
    mkdir -p "/home/$username"
    cp -a /etc/skel/. "/home/$username/"
  fi
fi

if [ "$kind" = bot ]; then
  # Demo/test bot: a home, lab copy and git identity like a student, plus a
  # small credentials file bot-runner.sh reads at startup (see that script)
  # -- there's no browser for these (portal_login there signs in with curl),
  # so there's no other way to hand
  # them BOT_PASSWORD/FORGEJO_ORG/FORGEJO_REPO that survives this process
  # being killed and restarted by bot-supervisor.sh.
  echo "$username:$bot_password" | chpasswd
  mkdir -p "/home/$username/lab"

  if [ -d "$lab_seed_dir" ]; then
    cp -Rn "$lab_seed_dir"/. "/home/$username/lab/"
  fi

  # Persona: bots 1-3 are always expert/intermediate/novice; any bot past
  # that gets a random one of the three, so a big --test N gives a mixed
  # cohort. Sticky across container restarts (reuse what's already in the
  # env file) so a bot's saved step index never lands on a different
  # persona's step list.
  bot_persona=""
  if [ -f "/home/$username/.dojo-bot.env" ]; then
    bot_persona="$(sed -n 's/^BOT_PERSONA=//p' "/home/$username/.dojo-bot.env" | head -1)"
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

  cat > "/home/$username/.dojo-bot.env" <<EOF
BOT_USER=$username
BOT_PASSWORD=$bot_password
BOT_PERSONA=$bot_persona
BOT_FAST=${BOT_FAST:-0}
FORGEJO_ORG=$forgejo_org
FORGEJO_REPO=$forgejo_repo
FORGEJO_FORK_WORKFLOW=$forgejo_fork_workflow
PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-}
EOF
  chmod 600 "/home/$username/.dojo-bot.env"

  rm -f "/home/$username/.zshrc"
  ln -s /opt/dojo-shell/zshrc "/home/$username/.zshrc"

  # The same git identity a student gets below: without it a bot's commits
  # outside the shared clone (dns-as-code's ~/lab/my-zone) fail.
  if [ ! -f "/home/$username/.gitconfig" ]; then
    cat > "/home/$username/.gitconfig" <<EOF
[user]
	name = $username
	email = $username@example.com
[init]
	defaultBranch = main
EOF
  fi

  chown -R "$username:$username" "/home/$username"
  chmod 700 "/home/$username"
  exit 0
fi

usermod -p '!' "$username"
mkdir -p "/home/$username/lab"

# Copy any lab file the student doesn't already have (new files land on
# every restart), but never overwrite a file the student has touched.
if [ -d "$lab_seed_dir" ]; then
  cp -Rn "$lab_seed_dir"/. "/home/$username/lab/"
fi

chown -R "$username:$username" "/home/$username"

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

# The schema/update settings switch off background fetches that can only
# fail here (no network route out) -- see the facilitator's settings.json in
# entrypoint.sh for the full reasoning, including restoreEditors.
student_code_server_settings_dir="/home/$username/.local/share/code-server/User"
if [ ! -f "$student_code_server_settings_dir/settings.json" ]; then
  mkdir -p "$student_code_server_settings_dir"
  cat > "$student_code_server_settings_dir/settings.json" <<'EOF'
{
  "workbench.colorTheme": "GitHub Dark",
  "editor.fontSize": 16,
  "terminal.integrated.fontSize": 16,
  "workbench.startupEditor": "none",
  "workbench.editor.restoreEditors": false,
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
# workspace opens -- see the matching facilitator block in entrypoint.sh for
# why. Runs through /opt/dojo-shell/tmux-terminal.sh (also set as the
# default terminal profile above), same as any terminal the student opens
# manually -- each gets its own uniquely-named tmux session, so splits and
# extra tabs stay independent instead of mirroring each other. A
# facilitator's /admin/watch/<sid> mirror then follows whichever of the
# student's sessions (this one, another VS Code terminal, or the standalone
# Terminal tool's `main`) was most recently active -- see
# workspace-control.py's most_active_session().
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

# Authored under engine/web-terminal/zshrc (see that file to add aliases
# etc.). Always resynced to the current version on every container start,
# same as the README.md symlink above.
rm -f "/home/$username/.zshrc"
ln -s /opt/dojo-shell/zshrc "/home/$username/.zshrc"

chmod 700 "/home/$username"

if [ "${DOJO_DEFER_TOKEN:-0}" != 1 ]; then
  python3 /usr/local/lib/dojo/forgejo-token.py --wait 60 "$username"
fi
