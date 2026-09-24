# OpenBao server for the whole class (PLAN.md §5.1). Plain HTTP on
# workshop_lab only: nothing outside the stack reaches this port, and the
# gateway fronts /ui/ and /v1/ for browsers (PLAN.md §5.4).
ui            = true
disable_mlock = true

storage "raft" {
  path    = "/openbao/file"
  node_id = "openbao-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"
