#!/bin/sh
# start.d hook, run once by the base entrypoint (engine/web-terminal/
# entrypoint.sh) as root, after every account exists and before any
# workspace is served.
#
# Gives every account (students, the facilitator, --test bots) its own
# sandbox for Part 1 of the labs: ~/lab/my-zone, a local git repo whose
# dnsconfig.js declares only <user>.dojo.test. dnscontrol only touches zones
# its config declares, so a plain `dnscontrol push` from here can't change
# anyone else's zone or the shared dojo.test (which the dns-api gate refuses
# from terminals anyway). Skipped for an account that already has one.
set -eu

zone_parent="${DNS_PARENT_ZONE:-dojo.test}"

make_zone_repo() {
  user="$1" home="$2"
  base="$home/lab"
  [ -d "$base" ] || base="$home"
  dir="$base/my-zone"
  [ -e "$dir" ] && return 0
  zone="$user.$zone_parent"
  mkdir -p "$dir"

  cat > "$dir/dnsconfig.js" <<EOF
// Your own zone: $zone. Nobody else's config declares it, so this is yours
// to break and fix. Edit, then \`dnscontrol preview\`, then \`dnscontrol push\`.
var PDNS = NewDnsProvider("powerdns", {
	"zone_kind": "Native",
	"soa_edit_api": "DEFAULT",
});
var REG = NewRegistrar("none");

D("$zone", REG,
	DnsProvider(PDNS),
	DefaultTTL(300),

	// Every zone needs these two. Leave them as they are.
	SOA("@", "ns1.$zone_parent.", "hostmaster.$zone_parent.", 3600, 600, 604800, 1440),
	NAMESERVER("ns1.$zone_parent."),

	A("@", "203.0.113.10"),
	A("www", "203.0.113.10"),
	TXT("@", "owner=$user"),
);
EOF

  # No secret here: dnscontrol reads "$DNS_API_KEY" from the environment,
  # each account's own key (the dns-gate module writes and exports it).
  cat > "$dir/creds.json" <<'EOF'
{
  "powerdns": {
    "TYPE": "POWERDNS",
    "apiUrl": "http://dns-api:8081",
    "apiKey": "$DNS_API_KEY",
    "serverName": "localhost"
  }
}
EOF

  # Same path as in the shared repo, so Lab 1 can point at it. The mount comes
  # from compose/docker-compose.override.yml; without it, just skip the docs.
  if [ -f /opt/dojo/dns-docs/record-types.md ]; then
    mkdir -p "$dir/docs"
    cp /opt/dojo/dns-docs/record-types.md "$dir/docs/"
  fi

  git -C "$dir" init -q -b main
  git -C "$dir" add dnsconfig.js creds.json
  [ -f "$dir/docs/record-types.md" ] && git -C "$dir" add docs/record-types.md
  git -C "$dir" -c user.name="$user" -c user.email="$user@example.com" \
    commit -q -m "Start $zone"
  chown -R "$user:$(id -gn "$user")" "$dir"
}

for home in /home/*; do
  [ -d "$home" ] || continue
  user="$(stat -c %U "$home")"
  [ "$user" = "$(basename "$home")" ] || continue
  make_zone_repo "$user" "$home"
done
