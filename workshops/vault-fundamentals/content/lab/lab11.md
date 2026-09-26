# Lab 11 — Deploy with workload identity

**Goal:** deploy your app to a server the way it's done well at work. The **pipeline deploys** the app but **can't read its secrets**. The **app gets its own secrets** by proving *where it runs*, with an identity the platform gives it, like an Azure managed identity or a Kubernetes service account. Nobody hands the app a password, not even you.

---

## 1. Catch up

This lab uses your namespace, `team/app` and the `app-read` policy (Labs 4 and 6), lab 9's CI login, and your fork (Lab 8). If you skipped any of them, this block catches you up (it's safe to run anyway):

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
bao kv get team/app >/dev/null 2>&1 || until bao kv put team/app db_password=app-db-pass api_key=app-api-key; do sleep 2; done
printf 'path "team/data/app" {\n  capabilities = ["read"]\n}\n' | bao policy write app-read -
printf 'path "team/data/ci" {\n  capabilities = ["read"]\n}\n' | bao policy write ci-read -
bao read auth/jwt-ci/role/ci-main >/dev/null 2>&1 || bao write auth/jwt-ci/role/ci-main - <<EOF
{ "role_type": "jwt", "user_claim": "sub", "bound_audiences": ["openbao"], "token_policies": ["ci-read"],
  "bound_claims": { "repository": "$USER/vault-fundamentals", "ref": "refs/heads/main" }, "token_ttl": "5m" }
EOF
[ -d ~/lab/vault-fundamentals ] || {
  curl -u "$USER" -H "Content-Type: application/json" -d '{}' \
    http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks
  git clone http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals
}
cd ~/lab/vault-fundamentals && git switch main && git pull
git config credential.helper 'cache --timeout=3600'
```

## 2. Meet the platform

`app-host` runs one **slot** per student. Your slot is a Linux user with your name, and your app runs there as that user. Nobody else's code runs as you, and yours can't see theirs.

Every few minutes the platform writes your slot a fresh **identity token**: a JWT, signed with the platform's own key, valid for ten minutes, readable only by your slot. It says `sub: slot:<you>`. Its public keys are published, the way Kubernetes and Azure publish theirs:

```bash
curl -s http://app-host:8080/.well-known/jwks.json | jq '.keys[] | {kid, kty, alg}'
```

Your namespace already trusts those keys (your facilitator set that up, as with `jwt-ci` in Lab 9):

```bash
bao read auth/jwt-platform/config
```

## 3. A role for your slot

What's missing is the **role**: which slot may log in, and what it gets. Only your slot, with the audience `openbao`, and only `app-read`:

```bash
bao write auth/jwt-platform/role/app \
  role_type=jwt user_claim=sub bound_audiences=openbao \
  bound_subject="slot:$USER" \
  token_policies=app-read token_ttl=15m token_max_ttl=1h
```

`bound_subject` is the whole trust decision: a token that says `slot:<someone else>` is refused, even though the same platform signed it.

## 4. The app, and the Agent next to it

The app goes in `app/` in your repo. Three files, and **none of them holds a secret**.

The Agent's config (as in Lab 6, but it logs in with the platform's token instead of an AppRole secret ID):

```bash
mkdir -p app
cat > app/agent.hcl <<EOF
vault {
  address = "http://openbao:8200"
}

# Log in with the identity the platform gives this slot.
auto_auth {
  method "jwt" {
    namespace  = "students/$USER"
    mount_path = "auth/jwt-platform"
    config = {
      path = "/run/platform/$USER/token"
      role = "app"
      # The platform owns this file and replaces it every few minutes.
      remove_jwt_after_reading = false
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

How the platform starts it (`$HOME` is your slot's home, `/srv/apps/<you>`):

```bash
cat > app/start.sh <<'EOF'
#!/bin/sh
# Run by app-host as this slot's user, with $PORT and $SLOT set.
mkdir -p "$HOME/secrets"
bao agent -config=agent.hcl &
exec python3 app.py
EOF
```

The app itself knows nothing about vaults. It reads the Agent's file on every request and shows fingerprints, never values. It also shows what the platform says about it, and tries to read another slot's identity:

```bash
cat > app/app.py <<'EOF'
"""The team app on app-host (Labs 11-13)."""
import base64
import hashlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SLOT = os.environ["SLOT"]
SECRETS = f"/srv/apps/{SLOT}/secrets"


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def read_env(name):
    path = os.path.join(SECRETS, name)
    with open(path) as f:
        conf = dict(line.split("=", 1) for line in f.read().split() if "=" in line)
    return conf, int(time.time() - os.stat(path).st_mtime)


def page():
    out = [f"Team app in slot {SLOT} on app-host", ""]
    with open(os.environ["PLATFORM_TOKEN_FILE"]) as f:
        payload = f.read().split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    out.append(f"platform identity: sub={claims['sub']}, expires in {int(claims['exp'] - time.time())} s")
    others = [s for s in sorted(os.listdir("/run/platform")) if s != SLOT]
    if others:
        try:
            open(f"/run/platform/{others[0]}/token").close()
            out.append(f"!! this app can read {others[0]}'s identity")
        except OSError as e:
            out.append(f"{others[0]}'s identity: {e.strerror}")
    try:
        conf, age = read_env("app.env")
        out.append(f"secrets: rendered by the Agent {age} s ago")
        out += [f"  {k} fingerprint: {fingerprint(v)}" for k, v in sorted(conf.items())]
    except OSError as e:
        out.append(f"secrets: none yet ({e.strerror})")
    try:
        db, age = read_env("db.env")
    except OSError:
        out.append("database: not set up (Lab 12)")
    else:
        import pg8000.native
        try:
            conn = pg8000.native.Connection(db["DB_USER"], password=db["DB_PASSWORD"],
                                            host="app-db", database=f"app_{SLOT}")
            user, notes = conn.run("SELECT current_user, (SELECT count(*) FROM notes)")[0]
            conn.close()
            out.append(f"database: connected as {user} (login rendered {age} s ago), {notes} notes")
        except Exception as e:
            out.append(f"database: {type(e).__name__}: {str(e)[:120]}")
    return "\n".join(out) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = page().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


print(f"app: listening on port {os.environ['PORT']}", flush=True)
ThreadingHTTPServer(("127.0.0.1", int(os.environ["PORT"])), Handler).serve_forever()
EOF
```

## 5. The pipeline deploys, and can't read

The deploy workflow uses **two identities, one per job to do**. It asks Forgejo for an ID token with the audience `app-host` and sends it with the app: the platform checks Forgejo's signature and deploys only from **your repo, on `main`**, to **your slot**. Then it logs in to the vault as CI (Lab 9's `ci-main` role) and shows it **can't** read `team/app`:

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
      - name: Deploy to app-host with this job's identity
        run: |
          id_token="$(curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=app-host" | jq -j .value)"
          tar -czf app.tgz -C src/app .
          curl -sS --fail-with-body -H "Authorization: Bearer $id_token" \
            --data-binary @app.tgz http://app-host:8080/deploy | jq .
      - name: The pipeline can't read the app's secrets
        run: |
          id_token="$(mktemp)"
          curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=openbao" | jq -j .value > "$id_token"
          export BAO_TOKEN="$(bao write -field=token auth/jwt-ci/login role=ci-main jwt=@"$id_token")"
          rm -f "$id_token"
          if bao kv get team/app >/dev/null 2>&1; then
            echo "The pipeline CAN read team/app: that's one leak away from production."; exit 1
          fi
          echo "team/app: permission denied for the pipeline, as it should be."
EOF
git add app .forgejo/workflows/deploy.yml
git commit -m "Deploy the app to app-host"
git push
```

In Forgejo → **Actions**, open the **deploy** run. The deploy step prints `"state": "running"` and your slot; the last step says the pipeline was refused `team/app`.

## 6. Look at the app

From the terminal:

```bash
curl -s http://app-host:8080/$USER/
```

Or open the **My App** card on the landing page, then **Open the app**. You'll see:

- `platform identity: sub=slot:<you>`: who the platform says this app is.
- Another slot's identity: `Permission denied`. The app runs as your slot's user; it can't read a neighbour's token.
- `API_KEY` and `DB_PASSWORD` fingerprints. Compare one with the vault:

```bash
printf %s "$(bao kv get -field=api_key team/app)" | sha256sum | cut -c1-12
```

The **My App** page also shows your slot's log: the Agent's `authentication successful` and `rendered` lines.

## 7. Rotate, with no deploy

```bash
bao kv patch team/app api_key=rotated-$(date +%s)
sleep 12
curl -s http://app-host:8080/$USER/ | grep API_KEY
printf %s "$(bao kv get -field=api_key team/app)" | sha256sum | cut -c1-12
```

The new fingerprint is live. No commit, no pipeline run, no restart: the Agent noticed and rewrote the file.

## 8. A branch can't deploy

```bash
git switch -c try-a-branch
git commit --allow-empty -m "Try a deploy from a branch"
git push -u origin try-a-branch
```

The **deploy** run fails at its deploy step: `deploy refused: only main deploys; this run is on 'refs/heads/try-a-branch'`. The same person, the same repo, the same workflow: the platform still says no, because the job's identity says it's a branch.

```bash
git switch main
git push origin --delete try-a-branch
unset BAO_NAMESPACE
```

## At work

- **Azure**: the app gets a **managed identity** (App Service, Container Apps, a VM, AKS workload identity). Key Vault trusts Entra ID, and the app reads with that identity: no connection string, no client secret. The pipeline deploys with its own **workload identity federation** credential, which has no Key Vault read role.
- **Kubernetes**: the pod's **service account token** (projected, short-lived) logs in to Vault's `kubernetes` or `jwt` auth method; the Vault Agent injector or the CSI driver writes the secrets to a file.
- **Anywhere**: if the platform can't vouch for the app, the next best is AppRole with a **response-wrapped**, single-use secret ID delivered by the deploy (Lab 6's secret zero, made small).

## Check yourself

1. What stops student02's app from logging in as your app? *(It can't read your slot's token file (the platform gives each slot its own user), and your role accepts only `sub: slot:<you>`.)*
2. The pipeline deployed the app. Why can't it read the app's secrets? *(It has two identities with different rights: the platform lets it deploy, the vault gives it `ci-read` only. Separation of duties.)*
3. Where is the app's password stored on the server? *(In a file only the slot's user can read, written by the Agent from the vault. It isn't in the repo, the image, the pipeline or an environment variable, and a rotation reaches it without a deploy.)*

**Rules used:** 2 (the app proves where it runs; no password handed over), 5 (deploy without read), 3 (ten-minute platform tokens, fifteen-minute vault tokens), 1 (one slot, one path), 4 (no secret zero: the platform is the root of trust).
