#!/bin/sh
# vault-fundamentals lab 5 (with the stack up): the app reads a secret: .env vs hvac, versions, log leaks, renew.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_5.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
as 'rm -rf ~/lab/app; bao kv metadata delete secret/students/$USER/app' >/dev/null 2>&1
git_identity

echo "== lab 5: the app reads a secret"
lacks "a .env file stays out of git" 'mkdir -p ~/lab/app && cd ~/lab/app && git init -q -b main &&
    printf "DB_PASSWORD=dev-db-pass-123\nAPI_KEY=dev-api-key-456\n" > .env && echo .env > .gitignore &&
    printf "import os\nprint(len(os.environ[\"DB_PASSWORD\"]))\n" > app_env.py &&
    set -a && . ./.env && set +a && python3 app_env.py && git add . && git status --short' ' .env'
ok   "hvac is signed in with ~/.vault-token" 'python3 -c "import hvac, sys; sys.exit(not hvac.Client().is_authenticated())"'
ok   "puts the app secret" 'bao kv put secret/students/$USER/app db_password=vault-db-pass-789 api_key=vault-api-key-012'
as 'cat > ~/lab/app/app_vault.py' <<'EOF'
import logging
import os

import hvac

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger("app")
client = hvac.Client()
resp = client.secrets.kv.v2.read_secret_version(
    mount_point="secret",
    path=f"students/{os.environ['USER']}/app",
    raise_on_deleted_version=True,
)
secret = resp["data"]["data"]
log.debug("loaded config: %s", secret)
log.info("read version %s of the app's secret", resp["data"]["metadata"]["version"])
log.info("connecting to the database with a %d-character password", len(secret["db_password"]))
EOF
has  "the app reads version 1" 'cd ~/lab/app && python3 app_vault.py' 'read version 1'
has  "after a patch it reads version 2" 'bao kv patch secret/students/$USER/app db_password=rotated-db-pass-000 >/dev/null && cd ~/lab/app && python3 app_vault.py' 'read version 2'
has  "DEBUG logs the secret" 'cd ~/lab/app && LOG_LEVEL=DEBUG python3 app_vault.py' 'rotated-db-pass-000'
lacks "the fixed line doesn't" 'cd ~/lab/app && sed -i "s/log.debug(\"loaded config: %s\", secret)/log.debug(\"loaded config keys: %s\", sorted(secret.keys()))/" app_vault.py && LOG_LEVEL=DEBUG python3 app_vault.py' 'rotated-db-pass-000'
ok   "renew_self" 'python3 -c "import hvac; c = hvac.Client(); c.auth.token.renew_self(); print(c.auth.token.lookup_self()[\"data\"][\"ttl\"])"'
finish "lab 5"
