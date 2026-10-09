# What 60-tfstate-treasure.sh needs on each start. The openbao module's
# setup.sh appends it to the module's own provisioner policy
# (modules/openbao/setup/policies/provisioner.hcl). Exact paths only: a hook
# that writes somewhere new adds its path here.
#
# Deliberately NOT granted: anything under secret/data/students/* or a
# "student" policy -- this pack attaches no policy at all to a student's own
# SSO/CLI login (see docker-compose.override.yml), so secret/data/tfstate-treasure/*
# is reachable only through the one narrow AppRole role 60-tfstate-treasure.sh
# makes per student.
path "sys/mounts"        { capabilities = ["read"] }
path "sys/mounts/secret" { capabilities = ["create", "read", "update"] }
path "secret/data/tfstate-treasure/+"     { capabilities = ["create", "read", "update"] }
path "secret/metadata/tfstate-treasure/+" { capabilities = ["read"] }

# "+" matches one whole path SEGMENT; "tfstate-treasure-student01" is a
# single segment with a shared prefix, not a separate segment, so this needs
# "*" (suffix glob -- matches the rest of the path, mid-segment included).
path "sys/auth"        { capabilities = ["read"] }
path "sys/auth/approle" { capabilities = ["create", "read", "update", "sudo"] }
path "sys/policies/acl/tfstate-treasure-*" { capabilities = ["create", "read", "update"] }
path "auth/approle/role/tfstate-treasure-*" { capabilities = ["create", "read", "update"] }
