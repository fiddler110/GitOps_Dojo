# The facilitator: admin across the root namespace and every child namespace
# (a path in the root namespace's policy also matches students/<name>/...).
# Not root: it is an ordinary, revocable policy on an ordinary identity.
path "*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
}
