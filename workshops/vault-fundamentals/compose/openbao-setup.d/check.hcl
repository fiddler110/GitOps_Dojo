# Read-only: what the achievements service (plugins/bao) looks at in a student's own namespace.
# It never writes, and never reads a secret's value (metadata only).
path "students/+/sys/policies/acl/*"  { capabilities = ["read"] }
path "students/+/auth/+/role/*"       { capabilities = ["read"] }
path "students/+/database/roles/*"    { capabilities = ["read"] }
path "students/+/sys/leases/lookup/*" { capabilities = ["read", "list", "sudo"] }
path "students/+/+/metadata/*"        { capabilities = ["read"] }
