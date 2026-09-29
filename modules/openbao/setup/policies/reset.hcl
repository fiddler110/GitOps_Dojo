# The reset token: a periodic token for resetting one student (the
# student-reset plan's `openbao-reset` service). setup.sh mints it on each
# start, from the same temporary root as the provisioner, only when the
# workshop has an /etc/openbao-setup.d/reset.hcl, and appends that file to this
# one. The workshop's file grants the per-student paths only (delete and
# re-create a student's namespace and whatever its hooks put there); nothing in
# the root namespace's sys/ beyond that, and no policies, auth methods or
# identities for the class.
#
# The token is kept in memory (openbao-setup's tmpfs), never on the setup
# volume; only its accessor is kept there, so the next start can revoke it.

path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/renew-self"  { capabilities = ["update"] }
