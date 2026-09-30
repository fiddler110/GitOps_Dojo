# OpenBao server for the whole class (docs/archive/VAULT-FUNDAMENTALS-PLAN.md §5.1). Plain HTTP on
# workshop_lab only: nothing outside the stack reaches this port, and the
# gateway fronts /ui/ and /v1/ for browsers (VAULT-FUNDAMENTALS-PLAN.md §5.4).
ui            = true
disable_mlock = true

storage "raft" {
  path    = "/openbao/file"
  node_id = "openbao-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
  # setup/setup.sh makes its temporary root token from the unseal key on every start after the first
  # (`bao operator generate-root`). OpenBao 2.5.3+ refuses those endpoints unauthenticated by default, and
  # with no token to hand (the setup volume keeps none, FIND-17) a restart of openbao-setup could never
  # get one: every restart failed with 403. Accepted: the endpoint needs the unseal key, which is on the
  # setup volume only, and this is a class lab.
  disable_unauthed_generate_root_endpoints = false
}

api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"

# Audit (VAULT-FUNDAMENTALS-PLAN.md §3 principle 6, labs 4 and 12). OpenBao (2.6 and later) refuses to
# enable audit devices through the API; they are declared here instead.
#
# openbao-audit reads the file as OpenBao's own uid (compose.yml).
# hmac_accessor: accessors are written in the clear, so a leaked token can be
# traced by its accessor (lab 12). An accessor can look a token up or revoke
# it, not use it; tokens and secret values stay HMACed.
audit "file" "file" {
  options {
    file_path     = "/openbao/logs/audit.log"
    hmac_accessor = "false"
  }
}
