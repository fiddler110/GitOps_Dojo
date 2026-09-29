# The reset token's per-student paths (the openbao module's policies/reset.hcl
# appends this file): delete a student's namespace students/<name> and build it
# again the way 10-tenancy.sh, 20-ci.sh and 30-platform.sh do, and clear their
# folder in the shared secret/ mount. Nothing else in the root namespace: not
# the namespace students/ itself, no policies, auth methods or identities.

path "students/sys/namespaces"   { capabilities = ["list"] }
path "students/sys/namespaces/*" { capabilities = ["create", "read", "update", "delete"] }
path "sys/quotas/rate-limit/students-*" { capabilities = ["create", "read", "update", "delete"] }
path "secret/data/students/+/welcome"   { capabilities = ["create", "update"] }
path "secret/metadata/students/*"       { capabilities = ["list", "delete"] }

path "students/+/sys/auth"              { capabilities = ["read"] }
path "students/+/sys/auth/jwt-ci"       { capabilities = ["create", "read", "update", "sudo"] }
path "students/+/sys/auth/jwt-platform" { capabilities = ["create", "read", "update", "sudo"] }
path "students/+/auth/jwt-ci/config"       { capabilities = ["create", "read", "update"] }
path "students/+/auth/jwt-platform/config" { capabilities = ["create", "read", "update"] }
path "students/+/sys/mounts"          { capabilities = ["read"] }
path "students/+/sys/mounts/database" { capabilities = ["create", "read", "update"] }
path "students/+/database/config/app-db"      { capabilities = ["create", "read", "update"] }
path "students/+/database/rotate-root/app-db" { capabilities = ["update"] }
