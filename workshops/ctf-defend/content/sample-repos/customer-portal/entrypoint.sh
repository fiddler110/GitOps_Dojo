#!/bin/sh
# Seed the SQLite DB (idempotent — no-op if already seeded, so data survives a
# restart) from this slot's CTF_STUDENT/CTF_FLAG, then run the app. The app
# itself never sees the student password seed; CTF_FLAG is the already-rendered
# flag value for this slot (§5).
set -eu

python3 /app/seed.py
exec python3 /app/app.py
