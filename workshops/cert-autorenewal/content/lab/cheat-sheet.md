# Cheat Sheet

Condensed reference for every command used across Labs 1-5. `me="$(whoami)"`
and `host="${me}.certs.dojo.test"` are assumed set in most examples below —
see each lab for the first time they're introduced.

## Trust (Lab 1)

```sh
step certificate inspect /opt/step-ca-root/root_ca.crt --short   # what's in the root cert
step certificate fingerprint /opt/step-ca-root/root_ca.crt        # its SHA-256 fingerprint
step ca bootstrap --ca-url https://step-ca:9000 --fingerprint <fp> # trust it (step CLI only)
step ca health --ca-url https://step-ca:9000                      # confirm you can reach the CA
```

certbot and acme.sh each need telling about this root **separately** —
that's the two env vars/flags below, not `step ca bootstrap`.

| Client | How it trusts step-ca's own HTTPS listener |
| ------ | -------------------------------------------- |
| certbot | `REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt` (env var, every invocation) |
| acme.sh | `--ca-bundle /opt/step-ca-root/root_ca.crt` (flag, every invocation) |

## ACME directory URL

```text
https://step-ca:9000/acme/acme/directory
```

(`acme` appears twice: once for the ACME protocol, once as this CA's
provisioner name — coincidence of the defaults, not a typo.)

## Issue — certbot, http-01 (Lab 2)

```sh
mkdir -p ~/certbot/{config,work,logs}
REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt \
certbot certonly \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  --webroot -w "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --agree-tos --non-interactive --email "${me}@example.com"
# cert lands at ~/certbot/config/live/${host}/{fullchain.pem,privkey.pem}
```

## Issue — acme.sh, http-01 (Lab 3)

```sh
acme.sh --issue \
  --webroot "/srv/webroot/${me}/html" \
  -d "${host}" \
  --server https://step-ca:9000/acme/acme/directory \
  --ca-bundle /opt/step-ca-root/root_ca.crt \
  --cert-home ~/acmesh-lab3 \
  --accountemail "${me}@example.com"
```

## Issue — certbot, dns-01 (Lab 5)

```sh
certbot certonly --manual --preferred-challenges dns-01 \
  --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs \
  -d "${host}" --server https://step-ca:9000/acme/acme/directory \
  --agree-tos --email "${me}@example.com"
# pauses; deploy the printed TXT record (see below), then press Enter
```

## Install (Labs 2 & 3)

```sh
cp <issued-fullchain> "/srv/webroot/${me}/certs/fullchain.pem"
cp <issued-privkey>   "/srv/webroot/${me}/certs/privkey.pem"
```

Copying into `/srv/webroot/${me}/certs/` is the entire "install" step —
`demo-app` watches that volume and reloads nginx itself.

## Verify

```sh
openssl x509 -in <cert> -noout -dates -subject -issuer   # validity window, who it's for/from
demo_ip="$(dig @dns-server "${host}" +short)"
curl --resolve "${host}:80:${demo_ip}"  "http://${host}/"
curl --resolve "${host}:443:${demo_ip}" --cacert /opt/step-ca-root/root_ca.crt "https://${host}/" -v
```

## DNS (Lab 5)

```sh
dig @dns-server "${host}" A +short                       # your seeded A record (already there, Labs 1-4)
dig @dns-server "_acme-challenge.${host}" TXT +short      # your dns-01 TXT record, once you've added one

curl -s -H "X-API-Key: workshop-not-a-secret" -H "Content-Type: application/json" \
  -X PATCH "http://dns-server:8081/api/v1/servers/localhost/zones/certs.dojo.test." \
  -d '{"rrsets":[{"name":"_acme-challenge.'"${host}"'.","type":"TXT","ttl":60,
        "changetype":"REPLACE","records":[{"content":"\"VALUE\"","disabled":false}]}]}'
```

## Automate (Lab 4)

```sh
crontab -e
# * * * * * REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt /home/USERNAME/renew-and-reload.sh >> /home/USERNAME/renew.log 2>&1
```

## Glossary

| Term | Meaning here |
| ---- | ------------- |
| ACME | The protocol (RFC 8555) all three clients speak to `step-ca` — account, order, challenge, finalize. |
| http-01 | Prove domain control by serving a file at a well-known HTTP path. |
| dns-01 | Prove domain control by publishing a specific DNS TXT record. |
| Provisioner | step-ca's term for a configured way of authenticating requests — ours is an ACME provisioner named `acme`. |
| Claims | Per-provisioner limits/defaults — here, the 5-10 minute cert lifetime that makes Lab 4 observable. |
| Webroot | The directory nginx already serves, where an http-01 client drops its challenge file. |
