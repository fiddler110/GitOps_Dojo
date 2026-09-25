# Lab 5 — OpenBao Agent

**Goal:** give the app an identity of its own and let **OpenBao Agent** do the vault work: it logs in, keeps the token fresh and writes the secret to a file only the app can read, in memory. Rotate the secret and the app picks it up without a commit or a restart.

The app itself stops talking to the vault at all. It reads a file.

---

## 1. Back in your namespace

This lab uses what you built in Lab 3. If you skipped it, the block below makes it; if you didn't, it changes nothing that matters:

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
# a new KV mount refuses writes for a moment while it upgrades: retry
until bao kv put team/app db_password=app-db-pass api_key=app-api-key; do sleep 2; done
printf 'path "team/data/app" {\n  capabilities = ["read"]\n}\n' | bao policy write app-read -
```

## 2. An identity for the app: AppRole

**AppRole** is a sign-in method for programs. The app gets a **role ID** (like a user name) and a **secret ID** (like a password), and signing in with both gives it a token with the role's policies.

```bash
bao auth enable approle
bao write auth/approle/role/app \
    token_policies=app-read token_ttl=2m token_max_ttl=10m secret_id_ttl=1h
```

The app's tokens get `app-read` only (Lab 3) and live two minutes, so you'll see the Agent renew one during this lab.

Now play the part of whoever deploys the app, and hand it its two IDs as files:

```bash
mkdir -p ~/lab/agent && cd ~/lab/agent
bao read -field=role_id auth/approle/role/app/role-id > role-id
bao write -f -field=secret_id auth/approle/role/app/secret-id > secret-id
chmod 600 role-id secret-id
```

Look at what just happened: to let the app log in without a secret in its code, you gave it... a secret. That's the **secret zero** problem. Here it's small (a secret ID that expires in an hour and that the Agent deletes as soon as it has read it), but something still had to deliver it. Labs 8 and 9 remove it by using an identity the platform already proves.

## 3. Configure the Agent

The Agent is part of `bao`. Its config says how to log in and what to write where. The secret goes to `/dev/shm`, which is memory (`tmpfs`), not disk:

```bash
install -d -m 700 /dev/shm/$USER
cat > agent.hcl <<EOF
vault {
  address = "$VAULT_ADDR"
}

# Log in with AppRole in your namespace, then keep the token alive.
auto_auth {
  method "approle" {
    namespace = "students/$USER"
    config = {
      role_id_file_path                   = "role-id"
      secret_id_file_path                 = "secret-id"
      remove_secret_id_file_after_reading = true
    }
  }
}

# Check the secret for changes every 5 seconds (the default is 5 minutes).
template_config {
  static_secret_render_interval = "5s"
}

template {
  destination = "/dev/shm/$USER/app.env"
  perms       = "0600"
  contents    = <<-EOT
  {{ with secret "team/data/app" }}DB_PASSWORD={{ .Data.data.db_password }}
  API_KEY={{ .Data.data.api_key }}{{ end }}
  EOT
}
EOF
```

Start it in the background, with its log in a file:

```bash
bao agent -config=agent.hcl > agent.log 2>&1 &
sleep 3
grep -E 'authentication successful|rendered' agent.log
```

## 4. What the Agent wrote

```bash
ls -l /dev/shm/$USER/        # -rw------- you: nobody else can read it
df -h /dev/shm | tail -1     # tmpfs: memory, gone when the machine stops
cat /dev/shm/$USER/app.env
ls                           # secret-id is gone: read once, then deleted
```

The secret never touched the disk, only its owner can read it, and the secret ID can't be stolen from the disk later because it isn't there any more.

## 5. The app reads a file

This app knows nothing about vaults. It reads the file every few seconds and prints a fingerprint of the password (never the password itself, Lab 4):

```bash
cat > app.py <<'EOF'
import hashlib
import os
import time

path = f"/dev/shm/{os.environ['USER']}/app.env"
while True:
    with open(path) as f:
        conf = dict(line.split("=", 1) for line in f.read().split())
    fingerprint = hashlib.sha256(conf["DB_PASSWORD"].encode()).hexdigest()[:8]
    print(time.strftime("%H:%M:%S"), "database password fingerprint", fingerprint, flush=True)
    time.sleep(3)
EOF
```

Split the terminal (`Ctrl+b %` in tmux) and run the app in the new pane:

```bash
cd ~/lab/agent && python3 app.py
```

## 6. Rotate it, live

Back in the first pane, rotate the password:

```bash
bao kv patch team/app db_password=rotated-$(date +%s)
```

Watch the app's pane: within about 5 seconds the fingerprint changes. No commit, no new build, no restart, and nobody had to tell the app. A real app would reload when the file changes, or the Agent can run a command after each render (`command` in the `template` block) to signal it.

## 7. The Agent keeps the token alive

The app's token lives two minutes. After a couple of minutes, look at the Agent's log:

```bash
grep -iE 'renew' agent.log | tail -3
```

The Agent renews the token as it goes, and logs in again when it reaches its maximum TTL (10 minutes). The app never sees a token at all.

## 8. Clean up

Stop the app (`Ctrl+c` in its pane), then stop the Agent and remove the rendered file:

```bash
kill %1                  # the Agent (or: pkill -u $USER -f 'bao agent')
rm -rf /dev/shm/$USER
unset BAO_NAMESPACE
```

## Check yourself

1. What did the app need to know about the vault? *(Nothing. It reads a file; the Agent logs in, renews and renders.)*
2. What is this app's secret zero, and what limits the damage if it leaks? *(The secret ID. It expires in an hour, the Agent deletes it after reading, and the token it gets can read one secret.)*
3. Why `/dev/shm` and `0600`? *(Memory, not disk: nothing left behind after a stop or in a backup. Only the app's user can read it.)*

**Rules used:** 4 (know your secret zero), 3 (short-lived tokens, renewed for you), 7 (rotation is routine), 8 (never on disk).

**Next:** [lab6.md](lab6.md)
