#!/bin/sh
set -eu

python3 /app/seed.py
exec python3 /app/app.py
