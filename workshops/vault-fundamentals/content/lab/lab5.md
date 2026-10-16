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

The usual next step: keep the values in a `.env` file that git ignores, and have the code read them from the **environment**. Three files make it work:

- **`.env`** holds the secrets, one `NAME=value` per line.
- **`.gitignore`** lists the files git must never add.
- **`app_env.py`** is the app. `os.environ["NAME"]` reads an environment variable, and fails if it isn't set.

To use the file, `. ./.env` runs its lines in your shell, and `set -a` ... `set +a` around it **exports** each variable, so the programs you start can see them. `git status --short` lists what git would add.

```text
set -a; . ./.env; set +a
git status --short
```

Make a folder and a repo for the app:

```sh
mkdir -p ~/lab/app && cd ~/lab/app
git init -b main
```

In your terminal or VS Code, create three files in **app**: `.env`, `.gitignore` and `app_env.py`:

```sh
# Create our core files quickly with touch
touch .env .gitignore app_env.py
```

First open **`.env`** in your editor, the secrets, one `NAME=value` per line:

```sh
DB_PASSWORD=dev-db-pass-123
API_KEY=dev-api-key-456
```

Then open **`.gitignore`** and add the following, and save it:

```gitignore
.env
```

Then open **`app_env.py`** and add the app:

```python
import os

db_password = os.environ["DB_PASSWORD"]
api_key = os.environ["API_KEY"]
print(f"connecting to the database with a {len(db_password)}-character password")
```

Save all three.

**Your turn:** load `.env` into your shell, run the app, then commit. Before you run it, predict: which files will `git status --short` list?

```sh
set -a; . ./.env; set +a
python3 app_env.py
git add .
git status --short         # .gitignore and app_env.py, no .env
git commit -m "Read the secrets from the environment"
```

<!-- dojo-reveal: Results of running and committing -->

The app prints the password length. `git status --short` lists `.gitignore` and `app_env.py`, but no `.env`.

<!-- /dojo-reveal -->

Better than Lab 1: the secret isn't in git. But look at what's still true:

- `.env` is a plaintext file on every developer's laptop, and it gets passed around in chat when someone new joins.
- Nobody knows who has a copy, it never expires, and changing it means telling everyone.
- Every program you start from this shell can read it. Environment variables are inherited by every **child process** (a program started from this one), printed by debug pages and crash reports, and dumped by `env` in a CI log.

**Your turn:** predict what a child shell can see, then check. Then clear the variables from your shell before moving on.

```sh
bash -c 'echo "any child process sees: $API_KEY"'
unset DB_PASSWORD API_KEY
```

<!-- dojo-reveal: Result of the child process -->

The child prints `dev-api-key-456`: it inherited the variable.

<!-- /dojo-reveal -->


## 3. In the vault

The vault version of the app has two parts. First, put the app's secrets in your folder of the shared vault (Lab 3):

```sh
echo '{"db_password": "vault-db-pass-789", "api_key": "vault-api-key-012"}' | bao kv put secret/students/$USER/app -
```

Then the app asks the vault for them itself. `hvac` is Python's Vault client, and it works with OpenBao unchanged. In VS Code, create **app → `app_vault.py`** and add:

```python
import logging
import os

import hvac  # Python's Vault client; OpenBao speaks the same API

# Set up logging. The level comes from LOG_LEVEL (INFO if it isn't set):
# at INFO, log.debug(...) lines are skipped; at DEBUG, they are printed too.
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger("app")

# hvac finds the vault by itself: VAULT_ADDR from the environment, and the
# token from VAULT_TOKEN or ~/.vault-token (your terminal signed you in).
# Whatever that token's policies allow is all this app is allowed to do.
client = hvac.Client()

# Read the latest version of one secret from the KV v2 engine.
# This is the same request as: bao kv get secret/students/<you>/app
resp = client.secrets.kv.v2.read_secret_version(
    mount_point="secret",                       # the engine, mounted at secret/
    path=f"students/{os.environ['USER']}/app",  # the path inside it: your folder
    raise_on_deleted_version=True,              # fail loudly if the latest version was deleted
)

# The reply wraps the secret in two layers of "data":
#   resp["data"]["data"]     -> your key-value pairs (db_password, api_key)
#   resp["data"]["metadata"] -> facts about them (version, created_time, ...)
secret = resp["data"]["data"]
log.debug("loaded config: %s", secret)

log.info("read version %s of the app's secret", resp["data"]["metadata"]["version"])
# A real app would connect to the database here. We only print the length,
# so the password itself never reaches the screen.
log.info("connecting to the database with a %d-character password", len(secret["db_password"]))
```

Read it before you run it:

- `hvac.Client()` connects to the vault, signed in as whoever the token belongs to.
- `read_secret_version` is the same request as `bao kv get`: engine `secret`, path `students/<you>/app`.
- `resp["data"]["data"]` is the key-value pairs; `resp["data"]["metadata"]` has the version.
- The `log` lines write messages at two levels: `info` always shows, `debug` only when `LOG_LEVEL=DEBUG`. Keep an eye on the `debug` line; step 4 comes back to it.

Save it.

**Your turn:** run it, delete the `.env` file (the app doesn't need it), then rotate the password in one place and run the app again. Predict what the second run reports.

```sh
python3 app_vault.py
rm .env
printf '%s' 'rotated-db-pass-000' | bao kv patch secret/students/$USER/app db_password=-
python3 app_vault.py       # version 2, a new length, no commit, nobody told
```

<!-- dojo-reveal: Results of the vault app -->

The first run reads version 1 and a 16-character password. No `.env` file, no values in the environment, nothing to commit. The second reads version 2 with a new length.

<!-- /dojo-reveal -->

Every read also went into the vault's audit log, with who read what and when. A `.env` file can't tell you that.

**Whose identity did the app use?** Yours: it read `~/.vault-token`. That's fine on your laptop, but a server has no person signed in. The app needs an identity of its own, and something to keep its token fresh. That's Lab 6.

## 4. Don't log secrets

Someone is chasing a bug in production and turns on debug logging. Putting `LOG_LEVEL=DEBUG` in front of a command sets it for that one run. The rule: log _that_ you loaded the config, never _what_ it holds. Logs are read by many more people than can read the vault, and kept for months. The same goes for exception reports, `print` while debugging, and a CI step that runs `env`.

**Your turn:** run the app with debug logging. Before you do, predict what the `loaded config` line will contain.

```sh
LOG_LEVEL=DEBUG python3 app_vault.py
```

<!-- dojo-reveal: Result of the debug run -->

`loaded config: {'api_key': ..., 'db_password': ...}`: both secrets, in plain text, now on their way to the log system. The line looked harmless when it was written.

<!-- /dojo-reveal -->

Now fix it. Open `app_vault.py` in your editor, change the `log.debug` line to log only the key names, and save:

```python
log.debug("loaded config keys: %s", sorted(secret.keys()))
```

`secret.keys()` asks for the key names only, and says so. It also fails safe: if `secret` were ever a plain string instead of a dictionary, `.keys()` raises an error, whereas `sorted(secret)` would log the string one character at a time, which is the secret itself.

**Your turn:** run it with debug logging again.

```sh
LOG_LEVEL=DEBUG python3 app_vault.py
```

<!-- dojo-reveal: Result of the fixed run -->

`loaded config keys: ['api_key', 'db_password']`: enough to debug with, nothing to leak.

<!-- /dojo-reveal -->


## 5. Tokens run out

Your token has a **TTL** (time to live). A program that runs for days has to **renew** its token before the TTL runs out, and log in again when it reaches its maximum. `lookup_self` is `bao token lookup` (Lab 0); `renew_self` asks the vault for more time. See it happen. In VS Code, create **app → `token_ttl.py`** and add:

```python
import hvac

client = hvac.Client()
print("ttl before renewing:", client.auth.token.lookup_self()["data"]["ttl"], "seconds")
client.auth.token.renew_self()
print("ttl after renewing: ", client.auth.token.lookup_self()["data"]["ttl"], "seconds")
```

**Your turn:** save it and run it. Predict: will the second number be bigger or smaller?

```sh
python3 token_ttl.py
```

<!-- dojo-reveal: Result of the renewal -->

The TTL went back up.

<!-- /dojo-reveal -->

Renewing resets the clock, but only up to the token's maximum TTL; after that it has to log in again. `hvac` won't do any of this for you. Every app would need the same renew-and-log-in loop, which is why Lab 6 hands the job to **OpenBao Agent**.

## Check yourself

1. `.env` is in `.gitignore`. What can still go wrong?

<!-- dojo-reveal: Show the answer -->

It's plaintext on every laptop, shared by hand, never expires, and leaks through the environment to every child process and crash report.

<!-- /dojo-reveal -->

2. You rotate the password in the vault. Which apps need a commit or a new build?

<!-- dojo-reveal: Show the answer -->

None. They read the new version on their next read.

<!-- /dojo-reveal -->

3. Where else, apart from logs, do secrets escape a running app?

<!-- dojo-reveal: Show the answer -->

Exception reports, debug pages, `env` in CI output, core dumps.

<!-- /dojo-reveal -->


**Rules used:** 8 (never in git or logs), 6 (audit everything: every vault read is logged), 3 (short-lived: tokens expire and must be renewed).

**Next:** [lab6.md](lab6.md)
