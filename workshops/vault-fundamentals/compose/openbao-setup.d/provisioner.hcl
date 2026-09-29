# What this workshop's hooks (10-tenancy.sh, 20-ci.sh, 30-platform.sh) need
# on each start. The openbao module's setup.sh appends it to the module's own
# provisioner policy (modules/openbao/setup/policies/provisioner.hcl). Exact
# paths only: a hook that writes somewhere new adds its path here.

# 10-tenancy: the shared KV mount, the student policy, the namespace students/
# and one child namespace per account, a rate-limit quota each, and each
# account's welcome secret (write, never read).
path "sys/mounts"        { capabilities = ["read"] }
path "sys/mounts/secret" { capabilities = ["create", "read", "update"] }
path "sys/policies/acl/student" { capabilities = ["create", "read", "update"] }
path "sys/namespaces/students"  { capabilities = ["create", "read", "update"] }
path "students/sys/namespaces/*" { capabilities = ["create", "read", "update"] }
path "sys/quotas/rate-limit/students-*" { capabilities = ["create", "read", "update"] }
path "secret/data/students/+/welcome"   { capabilities = ["create", "update"] }

# 20-ci and 30-platform, in each students/<name> namespace: two JWT auth
# methods and their config, the database engine and its connection to app-db,
# whose first password it then rotates so no person knows it (not the
# credentials the engine hands out).
path "students/+/sys/auth"              { capabilities = ["read"] }
path "students/+/sys/auth/jwt-ci"       { capabilities = ["create", "read", "update", "sudo"] }
path "students/+/sys/auth/jwt-platform" { capabilities = ["create", "read", "update", "sudo"] }
path "students/+/auth/jwt-ci/config"       { capabilities = ["create", "read", "update"] }
path "students/+/auth/jwt-platform/config" { capabilities = ["create", "read", "update"] }
path "students/+/sys/mounts"          { capabilities = ["read"] }
path "students/+/sys/mounts/database" { capabilities = ["create", "read", "update"] }
path "students/+/database/config/app-db"      { capabilities = ["create", "read", "update"] }
path "students/+/database/rotate-root/app-db" { capabilities = ["update"] }
