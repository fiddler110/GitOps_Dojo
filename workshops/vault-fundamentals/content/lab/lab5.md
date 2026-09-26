# Lab 5 — The app reads a secret

**Goal:** take one small app through the three places its secret can live: in the code, in a git-ignored `.env` file, and in the vault. Then two habits every app that reads secrets needs: keep them out of the logs, and keep the token alive.

**In this lab you will:**

1. Recall where Lab 1 left the secret: in the code.
2. Move it to a `.env` file that git ignores, and see what that does and doesn't fix.
3. Move it to the vault, and have the app ask for it with a Python client.
4. Catch a secret leaking into a debug log, and fix the log line.
5. Watch a token's time run down, and renew it.

---

## 1. In the code

You did this in Lab 1: the token was written into `app.py`, git kept it forever, and rotating was the only fix. Nobody means to commit a secret. It happens because the secret is in a file that git tracks.

## 2. In a git-ignored `.env` file

The usual next step: keep the values in a `.env` file that git ignores, and have the code read them from the **environment**. Make a folder and a repo for the app:

```bash
mkdir -p ~/lab/app && cd ~/lab/app
git init -b main
```

In VS Code, create three files in **app**. First **`.env`**, the secrets, one `NAME=value` per line:

```sh
DB_PASSWORD=dev-db-pass-123
API_KEY=dev-api-key-456
```

Then **`.gitignore`**, the list of files git must never add. One line:

```gitignore
.env
```

Then **`app_env.py`**, the app. `os.environ["NAME"]` reads an environment variable, and fails if it isn't set:

```python
import os

db_password = os.environ["DB_PASSWORD"]
api_key = os.environ["API_KEY"]
print(f"connecting to the database with a {len(db_password)}-character password")
```

Save all three. Now load `.env` into your shell and run the app. `. ./.env` runs the file's lines in this shell, and `set -a` ... `set +a` around it **exports** each variable, so the programs you start can see them:

```bash
set -a; . ./.env; set +a
python3 app_env.py
```

Commit, and check that `.env` stays out. `git status --short` lists what git would add:

```bash
git add .
git status --short         # .gitignore and app_env.py, no .env
git commit -m "Read the secrets from the environment"
```

Better than Lab 1: the secret isn't in git. But look at what's still true:

- `.env` is a plaintext file on every developer's laptop, and it gets passed around in chat when someone new joins.
- Nobody knows who has a copy, it never expires, and changing it means telling everyone.
- Every program you start from this shell can read it. Start another one and see:

```bash
bash -c 'echo "any child process sees: $API_KEY"'
```

Environment variables are inherited by every **child process** (a program started from this one), printed by debug pages and crash reports, and dumped by `env` in a CI log. Clear them from your shell before moving on:

```bash
unset DB_PASSWORD API_KEY
```

## 3. In the vault

Put the app's secrets in your folder of the shared vault (Lab 3):

```bash
bao kv put secret/students/$USER/app db_password=vault-db-pass-789 api_key=vault-api-key-012
```

Now the app asks the vault for them itself. `hvac` is Python's Vault client, and it works with OpenBao unchanged. In VS Code, create **app → `app_vault.py`**:

```python
import logging
import os

import hvac

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger("app")

# hvac finds the vault by itself: VAULT_ADDR from the environment, and the
# token from VAULT_TOKEN or ~/.vault-token (your terminal signed you in).
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
```

Read it before you run it:

- `hvac.Client()` connects to the vault, signed in as whoever the token belongs to.
- `read_secret_version` is the same request as `bao kv get`: engine `secret`, path `students/<you>/app`.
- `resp["data"]["data"]` is the key-value pairs; `resp["data"]["metadata"]` has the version.
- The `log` lines write messages at two levels: `info` always shows, `debug` only when `LOG_LEVEL=DEBUG`. Keep an eye on the `debug` line; step 4 comes back to it.

Save it and run it:

```bash
python3 app_vault.py
```

No `.env` file, no values in the environment, nothing to commit. Delete the file; the app doesn't need it (VS Code shows it gone):

```bash
rm .env
```

Now rotate the password in one place, and run the app again:

```bash
bao kv patch secret/students/$USER/app db_password=rotated-db-pass-000
python3 app_vault.py       # version 2, a new length, no commit, nobody told
```

Every read also went into the vault's audit log, with who read what and when. A `.env` file can't tell you that.

**Whose identity did the app use?** Yours: it read `~/.vault-token`. That's fine on your laptop, but a server has no person signed in. The app needs an identity of its own, and something to keep its token fresh. That's Lab 6.

## 4. Don't log secrets

Someone is chasing a bug in production and turns on debug logging. Putting `LOG_LEVEL=DEBUG` in front of a command sets it for that one run:

```bash
LOG_LEVEL=DEBUG python3 app_vault.py
```

`loaded config: {'api_key': ..., 'db_password': ...}`: both secrets, in plain text, now on their way to the log system, where many more people can read them than can read the vault, and where they're kept for months. The line looked harmless when it was written.

Log *that* you loaded the config, never *what* it holds. In VS Code, change the `log.debug` line in `app_vault.py` to log only the key names, and save:

```python
log.debug("loaded config keys: %s", sorted(secret))
```

Run it with debug logging again:

```bash
LOG_LEVEL=DEBUG python3 app_vault.py
```

`loaded config keys: ['api_key', 'db_password']`: enough to debug with, nothing to leak. The same goes for exception reports, `print` while debugging, and a CI step that runs `env`.

## 5. Tokens run out

Your token has a **TTL** (time to live). A program that runs for days has to **renew** its token before the TTL runs out, and log in again when it reaches its maximum. See it happen. In VS Code, create **app → `token_ttl.py`**:

```python
import hvac

client = hvac.Client()
print("ttl before renewing:", client.auth.token.lookup_self()["data"]["ttl"], "seconds")
client.auth.token.renew_self()
print("ttl after renewing: ", client.auth.token.lookup_self()["data"]["ttl"], "seconds")
```

`lookup_self` is `bao token lookup` (Lab 0); `renew_self` asks the vault for more time. Save it and run it:

```bash
python3 token_ttl.py
```

The TTL went back up. Renewing resets the clock, but only up to the token's maximum TTL; after that it has to log in again. `hvac` won't do any of this for you. Every app would need the same renew-and-log-in loop, which is why Lab 6 hands the job to **OpenBao Agent**.

## Check yourself

1. `.env` is in `.gitignore`. What can still go wrong? *(It's plaintext on every laptop, shared by hand, never expires, and leaks through the environment to every child process and crash report.)*
2. You rotate the password in the vault. Which apps need a commit or a new build? *(None. They read the new version on their next read.)*
3. Where else, apart from logs, do secrets escape a running app? *(Exception reports, debug pages, `env` in CI output, core dumps.)*

**Rules used:** 8 (never in git or logs), 6 (audit everything: every vault read is logged), 3 (short-lived: tokens expire and must be renewed).

**Next:** [lab6.md](lab6.md)
