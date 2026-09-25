# Every student's policy, from the vault-fundamentals setup hook (10-tenancy.sh).
# One policy for the whole class: {{identity.entity.name}} is the signed-in
# student's entity name (student01, ...), filled in on every request. The
# openbao module attaches it to each student's entity, so the web UI (SSO)
# and the terminal (CLI login) get the same access.

# Lab 3, the shared vault: your own folder in the shared `secret/` mount.
# Anyone else's folder is a 403.
path "secret/data/students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list"]
}
# Browsing down to it (the UI lists as it goes): the folder names are the
# class list, which isn't secret; what is in them is.
path "secret/metadata/" {
  capabilities = ["list"]
}
path "secret/metadata/students/" {
  capabilities = ["list"]
}
path "secret/metadata/students/{{identity.entity.name}}" {
  capabilities = ["read", "list"]
}
path "secret/metadata/students/{{identity.entity.name}}/*" {
  capabilities = ["read", "list", "delete"]
}
path "secret/delete/students/{{identity.entity.name}}/*" {
  capabilities = ["update"]
}
path "secret/undelete/students/{{identity.entity.name}}/*" {
  capabilities = ["update"]
}
path "secret/destroy/students/{{identity.entity.name}}/*" {
  capabilities = ["update"]
}

# Lab 4 onwards, your own vault: admin in your namespace students/<you>, and
# nowhere else. A path in a root-namespace policy includes the namespace.
path "students/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
}

# Lab 3 reads this policy: `bao policy read student`.
path "sys/policies/acl/student" {
  capabilities = ["read"]
}
