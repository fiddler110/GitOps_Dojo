#!/bin/sh
# app-db first-start set-up (Lab 12), run once by the Postgres image's
# entrypoint on a new data volume, as the postgres user. For each student:
#   - a database app_<s> with a `notes` table, and CONNECT for no one else;
#   - a group role app_<s>_rw that may read and add notes;
#   - vault_<s>: may log in and create roles, and hand out app_<s>_rw (ADMIN
#     OPTION). The vault uses it to make each app its own short-lived login.
# vault_<s>'s first password goes to /bootstrap/<s> for the openbao-setup
# hook (30-platform.sh), which gives it to the vault and has the vault rotate
# it straight away: after that, only the vault knows it.
set -eu
umask 022

# Students (studentNN), then the demo bots (testuserN, ./run.sh --test).
users() {
  i=1
  while [ "$i" -le "${STUDENT_COUNT:-0}" ]; do printf '%s%02d\n' "${STUDENT_PREFIX:-student}" "$i"; i=$((i + 1)); done
  i=1
  while [ "$i" -le "${BOT_COUNT:-0}" ]; do printf '%s%d\n' "${BOT_PREFIX:-testuser}" "$i"; i=$((i + 1)); done
}
for s in $(users); do
  pw="$(head -c 24 /dev/urandom | base64 | tr -d '/+=')"
  psql -v ON_ERROR_STOP=1 -q --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE app_${s}_rw NOLOGIN;
CREATE ROLE vault_${s} LOGIN CREATEROLE PASSWORD '${pw}';
GRANT app_${s}_rw TO vault_${s} WITH ADMIN OPTION;
CREATE DATABASE app_${s};
REVOKE ALL ON DATABASE app_${s} FROM PUBLIC;
GRANT CONNECT ON DATABASE app_${s} TO app_${s}_rw, vault_${s};
SQL
  psql -v ON_ERROR_STOP=1 -q --username "$POSTGRES_USER" --dbname "app_${s}" <<SQL
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_${s}_rw;
CREATE TABLE notes (
  id      serial PRIMARY KEY,
  body    text NOT NULL,
  author  text NOT NULL DEFAULT current_user,
  created timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON notes TO app_${s}_rw;
GRANT USAGE ON SEQUENCE notes_id_seq TO app_${s}_rw;
INSERT INTO notes (body, author) VALUES ('Welcome, ${s}: this database is yours.', 'setup');
SQL
  printf '%s' "$pw" > "/bootstrap/${s}.tmp"
  mv "/bootstrap/${s}.tmp" "/bootstrap/${s}"
done
echo "app-db: databases for ${STUDENT_COUNT:-0} students and ${BOT_COUNT:-0} bots"
