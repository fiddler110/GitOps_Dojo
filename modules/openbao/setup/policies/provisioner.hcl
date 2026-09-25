# openbao-setup's own identity after root is revoked: re-runs setup, resets a
# student, re-creates a namespace. It manages structure (namespaces, policies,
# auth methods, identities, mounts) in the root namespace and in each
# students/<name> namespace, and writes seed secrets it can't read back.
#
# It is not a security boundary against itself: anything that can write
# policies and identities can grant itself more. What protects it is where it
# lives: only on the openbao_setup volume, which only openbao-setup mounts.

path "sys/namespaces"   { capabilities = ["list"] }
path "sys/namespaces/*" { capabilities = ["create", "read", "update", "delete", "list"] }

path "sys/policies/acl"            { capabilities = ["list"] }
path "sys/policies/acl/*"          { capabilities = ["create", "read", "update", "delete", "list"] }
path "students/+/sys/policies/acl/*" { capabilities = ["create", "read", "update", "delete", "list"] }

path "sys/auth"              { capabilities = ["read"] }
path "sys/auth/*"            { capabilities = ["create", "read", "update", "delete", "sudo"] }
path "students/+/sys/auth"   { capabilities = ["read"] }
path "students/+/sys/auth/*" { capabilities = ["create", "read", "update", "delete", "sudo"] }

path "sys/mounts"              { capabilities = ["read"] }
path "sys/mounts/*"            { capabilities = ["create", "read", "update", "delete"] }
path "students/+/sys/mounts"   { capabilities = ["read"] }
path "students/+/sys/mounts/*" { capabilities = ["create", "read", "update", "delete"] }

# Auth method config and roles (OIDC, JWT), not token creation.
path "auth/oidc/*"            { capabilities = ["create", "read", "update", "delete", "list"] }
path "auth/jwt/*"             { capabilities = ["create", "read", "update", "delete", "list"] }
path "students/+/auth/jwt/*"  { capabilities = ["create", "read", "update", "delete", "list"] }
path "students/+/auth/jwt-*"  { capabilities = ["create", "read", "update", "delete", "list"] }

path "identity/*" { capabilities = ["create", "read", "update", "delete", "list"] }

path "sys/config/ui/headers/*" { capabilities = ["create", "read", "update", "delete", "sudo"] }

# Seed secrets: write, never read.
path "secret/data/*"               { capabilities = ["create", "update"] }
path "students/+/secret/data/*"    { capabilities = ["create", "update"] }
path "students/+/transit/keys/*"   { capabilities = ["create", "update"] }
