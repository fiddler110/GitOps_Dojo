# Lab 10 (optional) — Dynamic database credentials

**Goal:** stop sharing a database password. The vault **makes a new Postgres login** for whoever asks (you, then your app), with a **lease**: it expires by itself, you can renew it, and you can revoke it early. There is no long-lived database password left to leak.

This lab is optional. Lab 11 doesn't need it.

---

## 1. What's already set up

Your team has its own database on `app-db`, called `app_<you>`, with a `notes` table. Your namespace has a `database/` engine, and its connection to that database is already configured (by "the DBA", your facilitator):

```bash
export BAO_NAMESPACE=students/$USER
bao read database/config/app-db
```

It logs in as `vault_<you>`, a Postgres user that may create logins. Its password isn't shown, and **no person knows it**: set-up gave the vault a first password and had the vault change it straight away (`rotate-root`). Only the vault can log in as `vault_<you>`.

## 2. A role: what a login may do

A **role** is the SQL the vault runs to make a login, and how long it lives. Each login joins `app_<you>_rw` (may read and add notes, nothing else), gets a random name and password, and expires in five minutes unless renewed:

```bash
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

```bash
creds="$(bao read -format=json database/creds/app)"
DB_USER="$(jq -r .data.username <<<"$creds")"
export PGPASSWORD="$(jq -r .data.password <<<"$creds")"
LEASE="$(jq -r .lease_id <<<"$creds")"
echo "user $DB_USER, lease $LEASE, $(jq .lease_duration <<<"$creds") s"
```

The user name says where it came from (`v-...-app-...`). Use it:

```bash
psql -h app-db -U "$DB_USER" -d app_$USER -c "INSERT INTO notes (body) VALUES ('written with a login that expires')"
psql -h app-db -U "$DB_USER" -d app_$USER -c "SELECT id, author, body FROM notes"
```

`author` is the login that wrote each row: every writer is its own identity now, so the database's own logs can tell them apart.

It gets `app_<you>`, and no one else's database:

```bash
OTHER=student01; [ "$USER" = student01 ] && OTHER=student02
psql -h app-db -U "$DB_USER" -d app_$OTHER -c "SELECT 1"   # permission denied for database
```

## 4. Leases: look, renew, revoke

```bash
bao lease lookup "$LEASE"      # ttl counting down from 5 minutes
bao lease renew "$LEASE"       # back to 5 minutes, up to max_ttl (30 minutes)
bao lease revoke "$LEASE"      # the vault runs the revocation SQL now
psql -h app-db -U "$DB_USER" -d app_$USER -c "SELECT 1"   # the login is gone
```

If nobody renews it, the same happens by itself when the lease runs out. A login that leaks from a log or a laptop is worth five minutes.

## 5. The app gets its own

Your app on `app-host` (Lab 9) can ask for a login the same way. Let its platform identity read `database/creds/app` too:

```bash
printf 'path "database/creds/app" {\n  capabilities = ["read"]\n}\n' | bao policy write db-app -
bao write auth/jwt-platform/role/app \
  role_type=jwt user_claim=sub bound_audiences=openbao \
  bound_subject="slot:$USER" \
  token_policies=app-read,db-app token_ttl=15m token_max_ttl=1h
```

Add a second template to the Agent's config, then deploy:

```bash
cd ~/lab/vault-fundamentals
cat >> app/agent.hcl <<EOF

# Lab 10: a database login made for this app; the Agent renews its lease.
template {
  destination = "/srv/apps/$USER/secrets/db.env"
  perms       = "0600"
  contents    = <<-EOT
  {{ with secret "database/creds/app" }}DB_USER={{ .Data.username }}
  DB_PASSWORD={{ .Data.password }}{{ end }}
  EOT
}
EOF
git add app/agent.hcl
git commit -m "The app gets its own database login from the vault"
git push
```

When the **deploy** run is green:

```bash
curl -s http://app-host:8080/$USER/ | grep database
```

`database: connected as v-...` and a count of notes. The app connected with a login made for it; nobody typed, stored or deployed a database password. The Agent renews the lease while the app runs, and asks for a new login when `max_ttl` is reached.

See both logins, yours (revoked) and the app's (live), from the vault's side:

```bash
bao list sys/leases/lookup/database/creds/app
unset BAO_NAMESPACE PGPASSWORD OTHER
```

## At work

- **Azure**: Azure SQL and Azure Database for PostgreSQL take **Entra ID authentication**, so the app's managed identity logs in with a token and there's no database password at all. Where a password is unavoidable, a vault's database engine (or Key Vault with rotation) makes it short-lived.
- **Everywhere**: the same engine exists for MySQL, SQL Server, MongoDB, and cloud IAM (AWS, Azure, GCP credentials made on demand).

## Check yourself

1. Who knows `vault_<you>`'s password? *(Nobody but the vault. It was rotated right after set-up.)*
2. A login leaks from a CI log. What's the damage? *(Up to the rest of its lease, at most `max_ttl`, and only on `app_<you>`'s notes; revoke its lease and it's gone at once.)*
3. What does the app store to reach the database? *(Nothing it was given: its platform identity gets a vault token, and the vault makes it a login.)*

**Rules used:** 3 (short-lived and revocable), 2 (the app's identity, not a password), 1 (one database, read and insert only), 7 (revoke is a normal operation), 6 (every login is its own name in the database's logs).
