# GeoIP database (optional)

Drop `dbip-city-lite.mmdb` here (git-ignored; run `modules/achievements/tools/fetch_geoip.sh`) and the
cyber map places each student at their real city instead of the facilitator's home region. This
folder is already inside the container's `/opt/achievements` mount, so no compose change is needed.
Data: IP to City Lite by DB-IP.com, CC BY 4.0 (the map page carries the attribution).
