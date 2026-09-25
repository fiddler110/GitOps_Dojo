# vault-fundamentals setup hook: lab 8 starts half-configured (PLAN.md S19).
# Sourced by the openbao module's setup.sh on every start with the provisioner
# token; safe to re-run. In each student's namespace, the JWT auth method
# `jwt-ci` trusts Forgejo Actions: its signing keys (fetched from git-server
# directly) and its issuer string (the public URL Forgejo puts in `iss`).
# The student writes the role (which repo and branch may log in) and the
# policy it gets.

issuer="${PUBLIC_BASE_URL%/}/git/api/actions"
jwks=http://git-server:3000/api/actions/.well-known/keys

for s in $(class_users); do
  export BAO_NAMESPACE="students/$s"
  bao auth list -format=json 2>/dev/null | grep -q '"jwt-ci/"' \
    || retry 10 bao auth enable -path=jwt-ci -description="Forgejo Actions job tokens (lab 8)" jwt >/dev/null
  retry 10 bao write auth/jwt-ci/config jwks_url="$jwks" bound_issuer="$issuer" >/dev/null
  unset BAO_NAMESPACE
done
log "ci: auth/jwt-ci in $(class_users | wc -l) namespaces, trusting $issuer"
