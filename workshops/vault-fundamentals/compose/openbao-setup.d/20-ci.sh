# vault-fundamentals setup hook: lab 9 starts half-configured (VAULT-FUNDAMENTALS-PLAN.md S19).
# Sourced by the openbao module's setup.sh on every start with the provisioner
# token; safe to re-run. In each student's namespace, the JWT auth method
# `jwt-ci` trusts Forgejo Actions: its signing keys (fetched from git-server
# directly) and its issuer string (the public URL Forgejo puts in `iss`).
# The student writes the role (which repo and branch may log in) and the
# policy it gets.

issuer="${PUBLIC_BASE_URL%/}/git/api/actions"
jwks=http://git-server:3000/api/actions/.well-known/keys

ci_one() {
  export BAO_NAMESPACE="students/$1"
  retry 10 enable_once auth enable -path=jwt-ci -description="Forgejo Actions job tokens (lab 9)" jwt
  retry 10 bao write auth/jwt-ci/config jwks_url="$jwks" bound_issuer="$issuer" >/dev/null
}
par_each ci_one || exit 1
log "ci: auth/jwt-ci in $(class_users | wc -l) namespaces, trusting $issuer"
