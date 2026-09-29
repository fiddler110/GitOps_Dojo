# The provisioner: openbao-setup's identity while it sets the vault up on each
# start (setup.sh). It lives for one start only: minted from a temporary root
# token, used for the module's own set-up below and the workshop's hooks, then
# revoked. Nothing keeps it.
#
# This file covers the module's own set-up (setup.sh, sso.sh, cli.sh). A
# workshop whose hooks need more adds /etc/openbao-setup.d/provisioner.hcl,
# which setup.sh appends to this one (vault-fundamentals: its tenancy, CI and
# platform hooks). Grant the exact paths the hooks write, nothing wider.
#
# It is not a boundary against itself: a token that writes policies and
# identities can grant itself more. What limits it is that it exists only for
# the few minutes of a start.

# The UI's framing header (setup.sh).
path "sys/config/ui/headers/Content-Security-Policy" { capabilities = ["create", "read", "update", "sudo"] }

# The facilitator policy (setup.sh).
path "sys/policies/acl/facilitator" { capabilities = ["create", "read", "update"] }

# SSO through Forgejo (sso.sh) and CLI login from the terminal (cli.sh): the two
# auth methods, their config and one role each.
path "sys/auth"      { capabilities = ["read"] }
path "sys/auth/oidc" { capabilities = ["create", "read", "update", "sudo"] }
path "sys/auth/jwt"  { capabilities = ["create", "read", "update", "sudo"] }
path "auth/oidc/config"        { capabilities = ["create", "read", "update"] }
path "auth/oidc/role/forgejo"  { capabilities = ["create", "read", "update"] }
path "auth/jwt/config"         { capabilities = ["create", "read", "update"] }
path "auth/jwt/role/terminal"  { capabilities = ["create", "read", "update"] }

# One entity per account, aliased to its SSO and CLI logins.
path "identity/entity/name/*" { capabilities = ["create", "read", "update"] }
path "identity/entity-alias"  { capabilities = ["create", "update"] }

# Its own token: created with -no-default-policy, so these must be granted here.
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/renew-self"  { capabilities = ["update"] }
path "auth/token/revoke-self" { capabilities = ["update"] }
