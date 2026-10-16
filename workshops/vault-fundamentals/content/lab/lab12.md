# Lab 12 — Dynamic database credentials

**Goal:** stop sharing a database password. The vault **makes a new Postgres login** for whoever asks (you, then your app), with a **lease**: it expires by itself, you can renew it, and you can revoke it early. There is no long-lived database password left to leak.

**In this lab you will:**

1. Look at the database connection your facilitator set up, whose password nobody knows.
2. Write a role: the SQL the vault runs to make a login, and how long it lives.
3. Get a login, use it, and see what it can't reach.
4. Look up, renew and revoke its lease.
5. Let your app on `app-host` get logins of its own.

A **lease** is the vault's record of something it handed out that expires: here, a database login. Every lease has an ID and a TTL, and when it ends (by itself or by `revoke`), the vault cleans up after it.

---

## 1. What's already set up

Your team has its own database on `app-db`, called `app_<you>`, with a `notes` table. Your namespace has a `database/` engine, and its connection to that database is already configured (by "the DBA", your facilitator). The connection logs in as `vault_<you>`, a Postgres user that may create logins. Its password isn't shown, and **no person knows it**: set-up gave the vault a first password and had the vault change it straight away (`rotate-root`). Only the vault can log in as `vault_<you>`.

**Your turn:** read the connection. Before you do, predict: will the password be shown?

```sh
export BAO_NAMESPACE=students/$USER
bao read database/config/app-db
```

<!-- dojo-reveal: Result of reading the connection -->

No: the config shows the connection URL and the `vault_<you>` user name, but never the password.

<!-- /dojo-reveal -->

## 2. A role: what a login may do

A **role** is the SQL the vault runs to make a login, and how long it lives. Each login joins `app_<you>_rw` (may read and add notes, nothing else), gets a random name and password, and expires in five minutes unless renewed. The role goes in as JSON, read from the lines up to `EOF` (as in Lab 9).

**Your turn:** create the role.

```sh
bao write database/roles/app - <<EOF
{
  "db_name": "app-db",
  "creation_statements": ["CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' IN ROLE app_${USER}_rw;"],
  "revocation_statements": ["DROP ROLE IF EXISTS \"{{name}}\";"],
  "default_ttl": "5m",
  "max_ttl": "30m"
}
EOF
```

## 3. Get a login

Reading `database/creds/app` makes a new login. You keep the whole answer in `creds`, then pick out the user name, the password (into `PGPASSWORD`, where `psql` looks for one) and the lease ID with `jq`. `psql` is Postgres's command-line client.

**Your turn:** get a login. Before you run it, predict what the user name looks like and how long the lease is.

```sh
creds="$(bao read -format=json database/creds/app)"
DB_USER="$(jq -r .data.username <<<"$creds")"
export PGPASSWORD="$(jq -r .data.password <<<"$creds")"
LEASE="$(jq -r .lease_id <<<"$creds")"
echo "user $DB_USER, lease $LEASE, $(jq .lease_duration <<<"$creds") s"
```


<!-- dojo-reveal: Result of getting a login -->

The user name says where it came from (`v-...-app-...`), and the lease is 300 seconds.

<!-- /dojo-reveal -->

**Your turn:** use the login with `psql`: add a note, then list them all. Predict what the `author` column will show.

```sh
psql -h app-db -U "$DB_USER" -d app_$USER -c "INSERT INTO notes (body) VALUES ('written with a login that expires')"
psql -h app-db -U "$DB_USER" -d app_$USER -c "SELECT id, author, body FROM notes"
```

<!-- dojo-reveal: Result of the notes -->

`author` is the login that wrote each row: every writer is its own identity now, so the database's own logs can tell them apart.

<!-- /dojo-reveal -->

The login gets `app_<you>`, and no one else's database.

**Your turn:** try a neighbour's (the first line picks one that isn't you).

```sh
OTHER=student01; [ "$USER" = student01 ] && OTHER=student02
psql -h app-db -U "$DB_USER" -d app_$OTHER -c "SELECT 1"   # permission denied for database
```

<!-- dojo-reveal: Result of the neighbour's database -->

`permission denied for database`.

<!-- /dojo-reveal -->


## 4. Leases: look, renew, revoke

**Your turn:** run these one at a time, and watch the TTL. Predict what the last `psql` does.

```sh
bao lease lookup "$LEASE"      # ttl counting down from 5 minutes
bao lease renew "$LEASE"       # back to 5 minutes, up to max_ttl (30 minutes)
bao lease revoke -sync "$LEASE"      # the vault runs the revocation SQL now, and waits for it
psql -h app-db -U "$DB_USER" -d app_$USER -c "SELECT 1"   # the login is gone
```

<!-- dojo-reveal: Results of the lease commands -->

`lookup` shows a TTL counting down from 5 minutes, `renew` puts it back, and after `revoke` the `psql` fails: the login is gone. If nobody renews it, the same happens by itself when the lease runs out. A login that leaks from a log or a laptop is worth five minutes.

<!-- /dojo-reveal -->


## 5. The app gets its own

**Starting here?** Steps 1 to 4 need nothing from earlier labs: your database and its connection are already set up. This step works on the app you deployed in [Lab 11](lab11.md): its `app/agent.hcl`, its `jwt-platform` role and your fork in `~/lab/vault-fundamentals`. Without them, do Lab 11 first, or stop after step 4.

Your app on `app-host` (Lab 11) can ask for a login the same way. You make a policy that may read `database/creds/app`, and rewrite the app's role from Lab 11 with it added (`token_policies=app-read,db-app`).

**Your turn:** run these.

```sh
printf 'path "database/creds/app" {\n  capabilities = ["read"]\n}\n' | bao policy write db-app -
bao write auth/jwt-platform/role/app \
  role_type=jwt user_claim=sub bound_audiences=openbao \
  bound_subject="slot:$USER" \
  token_policies=app-read,db-app token_ttl=15m token_max_ttl=1h
```

Now you tell the Agent to fetch a login and write it to a second file, `db.env`. In VS Code, open **vault-fundamentals → app → `agent.hcl`** and add this at the very end, after the last `}` (the lab page fills in your user name; if you see student**XX**, replace it with yours):

```hcl
# Lab 12: a database login made for this app; the Agent renews its lease.
template {
  destination = "/srv/apps/studentXX/secrets/db.env"
  perms       = "0600"
  contents    = <<-EOT
  {{ with secret "database/creds/app" }}DB_USER={{ .Data.username }}
  DB_PASSWORD={{ .Data.password }}{{ end }}
  EOT
}
```

Save it. The app from Lab 11 already looks for `db.env` and connects when it's there.

**Your turn:** commit and push to deploy. When the **deploy** run is green, ask the app about its database. Predict what it says.

```sh
cd ~/lab/vault-fundamentals
git add app/agent.hcl
git commit -m "The app gets its own database login from the vault"
git push
# when the deploy run is green:
curl -s http://app-host:8080/$USER/ | grep database
```

<!-- dojo-reveal: Result of the app's database line -->

`database: connected as v-...` and a count of notes. The app connected with a login made for it; nobody typed, stored or deployed a database password. The Agent renews the lease while the app runs, and asks for a new login when `max_ttl` is reached.

<!-- /dojo-reveal -->

**Your turn:** see the logins the vault has live leases for, from its side. Predict: is yours from step 4 still listed?

```sh
bao list sys/leases/lookup/database/creds/app
unset BAO_NAMESPACE PGPASSWORD OTHER
```

<!-- dojo-reveal: Result of the lease list -->

The app's lease is there; yours, revoked in step 4, is gone.

<!-- /dojo-reveal -->


## At work

- **Azure**: Azure SQL and Azure Database for PostgreSQL take **Entra ID authentication**, so the app's managed identity logs in with a token and there's no database password at all. Where a password is unavoidable, a vault's database engine (or Key Vault with rotation) makes it short-lived.
- **Everywhere**: the same engine exists for MySQL, SQL Server, MongoDB, and cloud IAM (AWS, Azure, GCP credentials made on demand).

## Check yourself

1. Who knows `vault_<you>`'s password?

<!-- dojo-reveal: Show the answer -->

Nobody but the vault. It was rotated right after set-up.

<!-- /dojo-reveal -->

2. A login leaks from a CI log. What's the damage?

<!-- dojo-reveal: Show the answer -->

Up to the rest of its lease, at most `max_ttl`, and only on `app_<you>`'s notes; revoke its lease and it's gone at once.

<!-- /dojo-reveal -->

3. What does the app store to reach the database?

<!-- dojo-reveal: Show the answer -->

Nothing it was given: its platform identity gets a vault token, and the vault makes it a login.

<!-- /dojo-reveal -->


**Rules used:** 3 (short-lived and revocable), 2 (the app's identity, not a password), 1 (one database, read and insert only), 7 (revoke is a normal operation), 6 (every login is its own name in the database's logs).

**Next:** [lab13.md](lab13.md): an incident drill, a token leaked and you have to say what it did.

---

## Challenge c2: The Right Lease (bonus)

Database logins that last 2 minutes and never more than 10 in total, on a new role `c2-app`, and one login from it.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c2
cd ~/lab/challenge-lease
```

That makes your own repo `$USER/challenge-lease` and clones it to `~/lab/challenge-lease`, and prints the goal, with your own names in it. When you think it's done:

```sh
dojo check c2
```

A wrong answer costs nothing. `dojo check hint c2` gives a hint for part of the points, and
`dojo challenge reset c2` throws the repo away and starts you over from a fresh copy.

