# app-db per-student SQL, sourced by init.sh (first start, every student) and
# reset-worker.sh (a facilitator's reset of one student). Runs as the postgres
# user over the local socket. For each student:
#   - a database app_<s> with a `notes` table, and CONNECT for no one else;
#   - a group role app_<s>_rw that may read and add notes;
#   - vault_<s>: may log in and create roles, and hand out app_<s>_rw (ADMIN
#     OPTION). The vault uses it to make each app its own short-lived login.
# vault_<s>'s first password goes to /bootstrap/<s> for the openbao-setup
# hook (30-platform.sh), which gives it to the vault and has the vault rotate
# it straight away: after that, only the vault knows it.

# Students (studentNN), then the demo bots (testuserN, ./run.sh --test).
users() {
  i=1
  while [ "$i" -le "${STUDENT_COUNT:-0}" ]; do printf '%s%02d\n' "${STUDENT_PREFIX:-student}" "$i"; i=$((i + 1)); done
  i=1
  while [ "$i" -le "${BOT_COUNT:-0}" ]; do printf '%s%d\n' "${BOT_PREFIX:-testuser}" "$i"; i=$((i + 1)); done
}

# make_student NAME: the student's database, roles and first password.
make_student() {
  # A tripwire, not a budget: connections one student's database accepts,
  # counting every login (the vault's short-lived roles too). 0 = unlimited.
  if [ "${APP_DB_CONN_LIMIT:-20}" -gt 0 ]; then _ms_n="${APP_DB_CONN_LIMIT:-20}"; else _ms_n=-1; fi
  _ms_pw="$(head -c 24 /dev/urandom | base64 | tr -d '/+=')"
  psql -v ON_ERROR_STOP=1 -q --username "${POSTGRES_USER:-postgres}" --dbname postgres <<SQL || return 1
CREATE ROLE app_${1}_rw NOLOGIN;
CREATE ROLE vault_${1} LOGIN CREATEROLE PASSWORD '${_ms_pw}';
GRANT app_${1}_rw TO vault_${1} WITH ADMIN OPTION;
CREATE DATABASE app_${1};
REVOKE ALL ON DATABASE app_${1} FROM PUBLIC;
GRANT CONNECT ON DATABASE app_${1} TO app_${1}_rw, vault_${1};
ALTER DATABASE app_${1} CONNECTION LIMIT ${_ms_n};
SQL
  psql -v ON_ERROR_STOP=1 -q --username "${POSTGRES_USER:-postgres}" --dbname "app_${1}" <<SQL || return 1
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_${1}_rw;
CREATE TABLE notes (
  id      serial PRIMARY KEY,
  body    text NOT NULL,
  author  text NOT NULL DEFAULT current_user,
  created timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON notes TO app_${1}_rw;
GRANT USAGE ON SEQUENCE notes_id_seq TO app_${1}_rw;
INSERT INTO notes (body, author) VALUES ('Welcome, ${1}: this database is yours.', 'setup');
SQL
  printf '%s' "$_ms_pw" > "/bootstrap/${1}.tmp" && mv "/bootstrap/${1}.tmp" "/bootstrap/${1}"
}

# drop_student NAME: everything make_student made, and every login the vault
# made from vault_<s> (members of app_<s>_rw, and the roles vault_<s> created,
# which Postgres 16+ makes it a member of). Safe to run again.
drop_student() {
  psql -v ON_ERROR_STOP=1 -q --username "${POSTGRES_USER:-postgres}" --dbname postgres <<SQL || return 1
DROP DATABASE IF EXISTS app_${1} WITH (FORCE);
DO \$\$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT m.rolname AS name FROM pg_auth_members am
      JOIN pg_roles g ON g.oid = am.roleid JOIN pg_roles m ON m.oid = am.member
      WHERE g.rolname = 'app_${1}_rw' AND m.rolname <> 'vault_${1}'
    UNION
    SELECT g.rolname FROM pg_auth_members am
      JOIN pg_roles g ON g.oid = am.roleid JOIN pg_roles m ON m.oid = am.member
      WHERE m.rolname = 'vault_${1}' AND g.rolname <> 'app_${1}_rw'
  LOOP
    CONTINUE WHEN r.name LIKE 'pg\\_%' OR r.name ~ '^(vault_.*|app_.*_rw|${POSTGRES_USER:-postgres})\$'
      OR (SELECT rolsuper FROM pg_roles WHERE rolname = r.name);
    EXECUTE format('DROP OWNED BY %I', r.name);
    EXECUTE format('DROP ROLE %I', r.name);
  END LOOP;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'vault_${1}') THEN
    DROP OWNED BY vault_${1};
    DROP ROLE vault_${1};
  END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_${1}_rw') THEN
    DROP OWNED BY app_${1}_rw;
    DROP ROLE app_${1}_rw;
  END IF;
END
\$\$;
SQL
  rm -f "/bootstrap/${1}"
}

# student_ready NAME: the student's database and vault_<s> exist, and so does
# the first password (what the vault's provision needs).
student_ready() {
  [ -s "/bootstrap/${1}" ] || return 1
  [ "$(psql -tAq --username "${POSTGRES_USER:-postgres}" --dbname postgres -c \
    "SELECT count(*) FROM pg_database WHERE datname = 'app_${1}'" 2>/dev/null)" = 1 ] || return 1
  [ "$(psql -tAq --username "${POSTGRES_USER:-postgres}" --dbname postgres -c \
    "SELECT count(*) FROM pg_roles WHERE rolname IN ('vault_${1}', 'app_${1}_rw')" 2>/dev/null)" = 2 ]
}
