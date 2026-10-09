#!/usr/bin/env python3
"""Student self-service login + facilitator dashboard for the workshop engine.

One thread per connection (http.server.ThreadingHTTPServer, remediation
T3.4). It used to be single-threaded so that slot claiming needed no lock,
but then one idle or slow client stalled /auth-check -- and with it every
student's VS Code and terminal -- for the whole 3 s socket timeout, once per
idle connection. Now an idle socket only times out in its own thread.

Locking rules (keep them when touching shared state):
- `_state_lock` guards `slots` and `token_index`. Claiming a slot
  (claim_slot) finds the first free studentNN and writes it in one critical
  section, so two concurrent /assign requests can never get the same slot.
- Never hold a lock across I/O: no control_request, forgejo_login_request,
  probe or socket write inside one. Handlers copy what they need under the
  lock (slot_snapshot, held_slots), release it, then do the I/O.
- A release first records the slot's token, stops the workspace without the
  lock, then clears the slot only if the token is unchanged, so a slow
  release never frees a slot someone else has claimed in the meantime.
- AssignLimit, audit(), audit_check() and each TTLCache (READY_CACHE,
  STATUS_CACHE) have their own small lock; `_save_lock` orders slot-table
  writes to disk, taken only after `_state_lock` is released.

The slot table survives an allocator crash or restart: every claim and
release writes it to ALLOCATOR_STATE_FILE (a named volume, so `./dojo
stop` still wipes it), and start-up reads it back. The write happens after
the lock is released, under its own `_save_lock`, and a version number makes
sure an older snapshot never overwrites a newer one. Everything else (rate
limits, audit dedupe, reset progress) is in-memory only.

Besides the request threads there is one background daemon per service
that probes the lab's services (Forgejo, terminals, slides, plus whatever a
workshop lists in STATUS_CHECKS) every few seconds for the facilitator's
status strip (/admin/api/status). They never touch `slots`, `token_index`
or anything else a request handler mutates: their only output is one status
snapshot, rebuilt under `_probe_lock` and replaced wholesale (a single
reference assignment, atomic in CPython), and request handlers only ever
read that snapshot. All upstream I/O for status happens in those threads; no
request handler waits on a probe.

Modules (one process; server.py only wires them up):
- config.py      settings from the environment, manifests, port layout, audit()
- accounts.py    /login: session cookies, password checks, LoginGuard
- allocation.py  the slot table and its state file, ports, workspace-control
                 client (control_request), READY/STATUS caches, reset steps
- probes.py      the status probe threads and their snapshot
- pages.py       icons, CSP, page shells; the CSS and JS are in static/
- handler.py     Handler: plumbing, identity, GET/POST routing
- views.py       ViewsMixin: the HTML pages
- api.py         ApiMixin: /auth-check, admin APIs, assign/release/reset
- reset.py       the reset worker and Forgejo steps (dojo_secret.py: passwords)
"""
import http.server

from allocation import load_slots
import allocation
from handler import Handler
from probes import start_status_probes


class AllocatorServer(http.server.ThreadingHTTPServer):
    """One daemon thread per connection, so a slow or idle client only ties
    up its own thread (for at most Handler.timeout) and never the class."""
    daemon_threads = True
    request_queue_size = 128  # a whole class arriving at once (default 5)


def make_server(addr):
    return AllocatorServer(addr, Handler)


def main():
    load_slots()
    start_status_probes()
    allocation.RESETS.start()
    server = make_server(("0.0.0.0", 8080))
    server.serve_forever()


if __name__ == "__main__":
    main()
