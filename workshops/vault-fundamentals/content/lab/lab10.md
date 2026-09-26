# Lab 10 — Deploy with a delivered secret ID

**Goal:** automate what you did by hand in Lab 6. There, *you* handed the app its AppRole secret ID. Here the **deploy pipeline** is the trusted deliverer: at every deploy it logs in with its own job identity (Lab 9), asks the vault for a **new, wrapped, single-use** secret ID for the app, and ships the wrapper with the app. The Agent next to the app opens it, logs in once, and deletes it. The pipeline never sees the secret ID and can't read the app's secrets.

This is the talk's **option 2** for secret zero. Option 3, one secret ID kept in the CI settings forever, is what this replaces.

---

## 1. Catch up

This lab uses your namespace, `team/app` and the `app-read` policy (Labs 4 and 6), AppRole (Lab 6), and your fork (Lab 8). If you skipped any of them, this block catches you up (it's safe to run anyway):

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
bao kv get team/app >/dev/null 2>&1 || until bao kv put team/app db_password=app-db-pass api_key=app-api-key; do sleep 2; done
printf 'path "team/data/app" {\n  capabilities = ["read"]\n}\n' | bao policy write app-read -
bao auth list | grep -q '^approle/' || bao auth enable approle
[ -d ~/lab/vault-fundamentals ] || {
  curl -u "$USER" -H "Content-Type: application/json" -d '{}' \
    http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks
  git clone http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals
}
cd ~/lab/vault-fundamentals && git switch main && git pull
git config credential.helper 'cache --timeout=3600'
```

## 2. The app's role, made strict

Lab 6's role handed out secret IDs that lasted an hour and worked any number of times. Start the role again, with the settings a delivered secret ID should have:

```bash
bao delete auth/approle/role/app
bao write auth/approle/role/app \
    token_policies=app-read token_period=10m \
    secret_id_num_uses=1 secret_id_ttl=5m
```

- `bao delete` first: every secret ID Lab 6 made dies with the old role.
- `secret_id_num_uses=1`: a secret ID logs in **once**, then it's spent.
- `secret_id_ttl=5m`: one that's never used is worthless after five minutes.
- `token_period=10m`: a **periodic** token. It has no maximum age: it lives as long as someone renews it within ten minutes. The Agent does that for as long as the app runs, so the app never needs a second login, or a second secret ID. If the app stops, nobody renews it and it lapses.

## 3. The deliverer's policy

The deliverer may **make** secret IDs for `app`, and nothing else. It can't read `team/app`, and it can't even see a secret ID: the policy refuses any request that isn't **response-wrapped**. Keep it as code, in the repo:

```bash
mkdir -p policies
cat > policies/app-deliver.hcl <<'EOF'
# The deploy pipeline: mint secret IDs for the app role, wrapped, nothing else.
path "auth/approle/role/app/secret-id" {
  capabilities     = ["update"]
  min_wrapping_ttl = "10s"   # an unwrapped request is refused
  max_wrapping_ttl = "120s"  # and a wrapper can't live longer than 2 minutes
}
EOF
bao policy write app-deliver policies/app-deliver.hcl
```

## 4. Be the deliverer once, by hand

Before a pipeline does it, do it yourself with a token that has only `app-deliver` (the way Lab 4 tested `app-read`):

```bash
DELIVER=$(bao token create -orphan -policy=app-deliver -ttl=10m -field=token)
BAO_TOKEN=$DELIVER bao kv get team/app                           # 403: it can't even see team/
BAO_TOKEN=$DELIVER bao write -f auth/approle/role/app/secret-id  # permission denied: not wrapped
WRAPPED=$(BAO_TOKEN=$DELIVER bao write -f -wrap-ttl=60s -field=wrapping_token auth/approle/role/app/secret-id)
bao write sys/wrapping/lookup token="$WRAPPED"
```

The first two are refused: `kv get` stops at its preflight check (`preflight capability check returned 403`: this token can't even see the `team/` mount), and the unwrapped request gets `permission denied`. The last request worked. What came back isn't the secret ID: it's a **wrapping token**, a single-use key to a box that holds it. The lookup shows the box's label, not what's inside: `creation_path` (where it was made, so the app can check it came from the right place) and `creation_ttl` (60 seconds, then it's gone).

Open it, as the app would. Then try to open it again, as someone who intercepted it would:

```bash
SECRET_ID=$(bao unwrap -field=secret_id "$WRAPPED") && echo "unwrapped: got a secret ID"
bao unwrap "$WRAPPED"
```

The second one fails: `wrapping token is not valid or does not exist`. A wrapper opens **once**. If the app ever gets that error, someone opened its wrapper first: an interception you *know* about, instead of one you don't.

Now use the secret ID, twice:

```bash
ROLE_ID=$(bao read -field=role_id auth/approle/role/app/role-id)
bao write -format=json auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID" \
  | jq '.auth | {policies, lease_duration, renewable}'
bao write auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID"
bao token revoke "$DELIVER"
unset SECRET_ID WRAPPED DELIVER
```

The first login gets `app-read` and a 600-second, renewable token. The second: `invalid role or secret ID`. It was spent at the first login. (Nobody renews the token you just got, so it lapses in ten minutes by itself.)

That's the whole hand-off. Next, a pipeline does it at every deploy.

## 5. A CI identity for the deliverer

The pipeline logs in with its **job's own identity**, as in Lab 9, so it has no stored secret of its own. A new role on the same `jwt-ci` login: only your fork, only `main`, and only `app-deliver`:

```bash
bao write auth/jwt-ci/role/deliver-main - <<EOF
{
  "role_type": "jwt",
  "user_claim": "sub",
  "bound_audiences": ["openbao"],
  "bound_claims": {
    "repository": "$USER/vault-fundamentals",
    "ref": "refs/heads/main"
  },
  "token_policies": ["app-deliver"],
  "token_ttl": "5m"
}
EOF
```

## 6. The app, and the Agent next to it

The app goes in `app/` in your repo. It runs on `app-host`, which runs one **slot** per student: a Linux user with your name, whose home is `/srv/apps/<you>`. `app-host` starts `app/start.sh` there at each deploy.

The **role ID** goes in the repo. It's the app's user name, not a secret: on its own it logs nobody in.

```bash
mkdir -p app
bao read -field=role_id auth/approle/role/app/role-id > app/role-id
```

The Agent's config is Lab 6's, plus one line: `secret_id_response_wrapping_path`. With it, the Agent expects a **wrapper** in `secret-id`, not a secret ID. It checks the wrapper was made at exactly that path before it opens it, so a wrapper from anywhere else is refused, and it deletes the file after reading.

```bash
cat > app/agent.hcl <<EOF
vault {
  address = "http://openbao:8200"
}

# Log in once with the delivered secret ID, then keep the token alive.
auto_auth {
  method "approle" {
    namespace = "students/$USER"
    config = {
      role_id_file_path                   = "role-id"
      secret_id_file_path                 = "secret-id"
      secret_id_response_wrapping_path    = "auth/approle/role/app/secret-id"
      remove_secret_id_file_after_reading = true
    }
  }
}

template_config {
  static_secret_render_interval = "10s"
}

template {
  destination = "/srv/apps/$USER/secrets/app.env"
  perms       = "0600"
  contents    = <<-EOT
  {{ with secret "team/data/app" }}DB_PASSWORD={{ .Data.data.db_password }}
  API_KEY={{ .Data.data.api_key }}{{ end }}
  EOT
}
EOF
```

How `app-host` starts it. Each start renders the secrets afresh: nothing an earlier run wrote is kept.

```bash
cat > app/start.sh <<'EOF'
#!/bin/sh
# Run by app-host as this slot's user, in $HOME/app, with $PORT and $SLOT set.
rm -rf "$HOME/secrets" && mkdir -p "$HOME/secrets"
bao agent -config=agent.hcl &
exec python3 app.py
EOF
```

The app knows nothing about vaults, as in Lab 6. It shows fingerprints of what the Agent rendered, whether the delivered file is still there, and it can be told to stop (you'll need that at the end):

```bash
cat > app/app.py <<'EOF'
"""The team app on app-host, logging in with a delivered secret ID (Lab 10)."""
import hashlib
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SLOT = os.environ["SLOT"]
SECRETS = f"/srv/apps/{SLOT}/secrets/app.env"


def page():
    out = [f"Team app in slot {SLOT} on app-host, AppRole login", ""]
    if os.path.exists("secret-id"):
        out.append("delivered secret-id file: still here")
    else:
        out.append("delivered secret-id file: gone (the Agent read it, then deleted it)")
    try:
        with open(SECRETS) as f:
            conf = dict(line.split("=", 1) for line in f.read().split() if "=" in line)
        age = int(time.time() - os.stat(SECRETS).st_mtime)
        out.append(f"secrets: rendered by the Agent {age} s ago")
        out += [f"  {k} fingerprint: {hashlib.sha256(v.encode()).hexdigest()[:12]}" for k, v in sorted(conf.items())]
    except OSError as e:
        out.append(f"secrets: none ({e.strerror})")
    return "\n".join(out) + "\n"


class Handler(BaseHTTPRequestHandler):
    def reply(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(page())

    def do_POST(self):
        # POST /restart: stop, as a crash or a server reboot would. app-host starts it again.
        if self.path.rstrip("/").endswith("/restart"):
            self.reply("stopping; app-host will start me again\n")
            threading.Timer(0.5, os._exit, (1,)).start()
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


print(f"app: listening on port {os.environ['PORT']}", flush=True)
ThreadingHTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
EOF
```

None of these files holds a secret. Nor does the repo: `secret-id` isn't in it. The pipeline adds it to the bundle at deploy time.

## 7. The pipeline delivers, then deploys

The deploy workflow uses **two identities, one per job to do**, as the platform expects:

- To the **vault**, it's `deliver-main`: it checks that it can't read `team/app`, then asks for a wrapped secret ID and writes the wrapper into the bundle, **without printing it**.
- To **`app-host`**, it sends a Forgejo ID token with the audience `app-host`. The platform checks Forgejo's signature and deploys only from **your repo, on `main`**, to **your slot**.

```bash
mkdir -p .forgejo/workflows
cat > .forgejo/workflows/deploy.yml <<'EOF'
name: deploy
on: push
jobs:
  deploy:
    runs-on: host
    enable-openid-connect: true
    env:
      BAO_ADDR: http://openbao:8200
      BAO_NAMESPACE: students/${{ github.repository_owner }}
    steps:
      - name: Get the code
        run: |
          git clone -q "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY.git" src
          git -C src checkout -q "$GITHUB_SHA"
      - name: Deliver a new secret ID for the app, wrapped
        run: |
          id_token="$(mktemp)"
          curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=openbao" | jq -j .value > "$id_token"
          BAO_TOKEN="$(bao write -field=token auth/jwt-ci/login role=deliver-main jwt=@"$id_token")"
          rm -f "$id_token"
          export BAO_TOKEN
          if bao kv get team/app >/dev/null 2>&1; then
            echo "The deliverer CAN read team/app: that's one leak away from production."; exit 1
          fi
          echo "team/app: permission denied for the deliverer, as it should be."
          (umask 077; bao write -f -wrap-ttl=60s -field=wrapping_token \
             auth/approle/role/app/secret-id > src/app/secret-id)
          echo "What the wrapper says about itself (never the wrapper itself):"
          bao write -format=json sys/wrapping/lookup token=@src/app/secret-id | jq .data
          bao token revoke -self
      - name: Deploy to app-host with this job's identity
        run: |
          id_token="$(curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=app-host" | jq -j .value)"
          tar -czf app.tgz -C src/app .
          rm -f src/app/secret-id
          curl -sS --fail-with-body -H "Authorization: Bearer $id_token" \
            --data-binary @app.tgz http://app-host:8080/deploy | jq .
          rm -f app.tgz
EOF
git add policies app .forgejo/workflows/deploy.yml
git commit -m "Deploy the app; the pipeline delivers its secret ID"
git push
```

In Forgejo → **Actions**, open the **deploy** run:

- The deliver step says `permission denied for the deliverer`, then shows the wrapper's `creation_path` and a `creation_ttl` of 60. No secret ID, and no wrapper, is in the log.
- The deploy step prints `"state": "running"` and your slot.

## 8. Look at the app

```bash
curl -s http://app-host:8080/$USER/
printf %s "$(bao kv get -field=api_key team/app)" | sha256sum | cut -c1-12
```

Or open the **My App** card on the landing page, then **Open the app**. You'll see:

- `delivered secret-id file: gone`. The Agent opened the wrapper, logged in, and deleted the file.
- `API_KEY` and `DB_PASSWORD` fingerprints; the `API_KEY` one matches the vault's.

The **My App** page also shows your slot's log: the Agent's `authentication successful` and `rendered` lines.

## 9. Check what's left

The secret ID is spent, so the vault no longer lists it. The audit log shows who did what: `deliver-main` made it, and the app's login used it.

```bash
bao list auth/approle/role/app/secret-id
bao-audit --path auth/approle -n 4 --json \
  | jq '.[] | {time, path, display_name, policies, remote_address}'
```

- `No value found`: no secret ID for `app` is left to steal, anywhere.
- `auth/approle/role/app/secret-id` came from the pipeline: its `display_name` names the `jwt-ci` login, your repo and `refs/heads/main`, and its only policy is `app-deliver`.
- `auth/approle/login` came a few seconds later from a **different address** (`app-host`), with `app-read`: the Agent, using the secret ID once.

Push again, and it all happens again with a **brand-new** secret ID. That is the rotation: nobody schedules it, every deploy just does it.

## 10. A branch gets nothing

The deliverer's role trusts `main` only:

```bash
git switch -c try-a-branch
git commit --allow-empty -m "Try a deploy from a branch"
git push -u origin try-a-branch
```

The **deploy** run fails at the deliver step: `claim "ref" does not match any associated bound claim values`. A branch can't get a secret ID for your app, so unreviewed code can't log in as it.

```bash
git switch main
git push origin --delete try-a-branch
```

## 11. The cost: a restart without a deploy

The app crashes, or the server reboots. `app-host` starts it again, as any platform would. Try it:

```bash
curl -s -X POST http://app-host:8080/$USER/restart
sleep 15
curl -s http://app-host:8080/$USER/
```

The app is back, but it has **no secrets**. On the **My App** page, the log shows the platform restarting it, then the Agent trying again and again: `error="no known secret ID"`. Its secret ID was spent at the last deploy, and the file is gone. That's exactly what you asked for (used once, then worthless), and it has a price: **only a new deploy brings the app back**, because only the deliverer can make a new secret ID.

```bash
git commit --allow-empty -m "Redeploy: a new secret ID"
git push
sleep 45
curl -s http://app-host:8080/$USER/
unset BAO_NAMESPACE
```

The fingerprints are back. It works, but the app now depends on the pipeline to start. That's the trade-off of option 2. **What if nobody had to deliver anything?** If the platform itself could vouch for the app, a restart would just log in again. That's Lab 11.

## At work

- **GitHub Actions / GitLab / Azure DevOps**: the same shape. The pipeline logs in with its OIDC identity (Lab 9), `hashicorp/vault-action` or a `vault write -wrap-ttl=...` step mints the wrapped secret ID, and the deploy puts it where the Agent reads it: a Kubernetes secret mounted as a file, a file dropped by the deploy tool, a VM's `cloud-init`.
- **Don't store it in CI**: a long-lived secret ID in a CI variable (option 3) never rotates, anyone who can edit a workflow can print it, and it logs in from anywhere. It's the thing this lab replaces.
- **Where you can**, skip the delivery: an Azure managed identity, a Kubernetes service account, a cloud instance identity. Lab 11.

## Check yourself

1. What can the pipeline do in the vault? *(Make wrapped secret IDs for the `app` role, and nothing else. It can't read `team/app`, can't get an unwrapped secret ID, and only from `main`.)*
2. Someone copies the wrapper from the bundle and opens it first. What happens? *(They get a secret ID the app then can't have: the app's Agent fails with `wrapping token is not valid or does not exist`, which tells you it was intercepted. And that secret ID dies in five minutes or at one use.)*
3. Why does a restart without a deploy fail, and why is that the price, not a bug? *(The secret ID was single-use and spent at the last deploy. Single use is what makes it worthless to a thief; the cost is that only the deliverer can start the app again.)*
4. Why is the role ID fine in git? *(It's a user name: on its own it logs nobody in. The half that matters travels separately, once, wrapped.)*

**Rules used:** 4 (secret zero, delivered small), 5 (the deliverer deploys, it can't read), 3 (a five-minute, single-use secret ID; a periodic token), 7 (every deploy rotates it), 6 (the audit shows both halves), 1 (one role, one path, one branch).

**Next:** [lab11.md](lab11.md)
