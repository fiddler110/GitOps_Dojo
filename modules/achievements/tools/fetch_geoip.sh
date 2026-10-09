#!/usr/bin/env bash
# Fetch DB-IP's free "IP to City Lite" database (CC BY 4.0, https://db-ip.com/db/download/ip-to-city-lite)
# into modules/achievements/geoip/ for the cyber map's student locations. Optional: without it every
# student sits in CTF_HOME_REGION (default Toronto). Run once on the host before ./dojo ctf-defend;
# the file is git-ignored and re-fetching monthly is plenty. The student terminals never see it.
set -euo pipefail
dest="$(cd "$(dirname "$0")/.." && pwd)/geoip"
mkdir -p "$dest"
for offset in 0 1 2; do
  ym="$(date -d "$(date +%Y-%m-15) -${offset} month" +%Y-%m)"
  url="https://download.db-ip.com/free/dbip-city-lite-${ym}.mmdb.gz"
  echo "trying $url"
  if curl -fL --retry 2 -o "$dest/.dl.gz" "$url"; then
    gunzip -f "$dest/.dl.gz" && mv "$dest/.dl" "$dest/dbip-city-lite.mmdb"
    echo "wrote $dest/dbip-city-lite.mmdb ($(du -h "$dest/dbip-city-lite.mmdb" | cut -f1))"
    exit 0
  fi
done
echo "could not fetch the database; the map falls back to CTF_HOME_REGION" >&2
exit 1
