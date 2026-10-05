#!/usr/bin/env python3
"""attacker-bot: ONE container for the whole room (plan §8.2, revised 2026-10-05 per the user -
not a fleet of per-student containers, and not a separate soc-feed tailer either). One thread
per student, each hitting that student's own target-NN the exact same way the student's own
terminal does: the published port ctf-host exposes on `ctf_net`,
`http://CTF_HOST:<CTF_HOST_PORT_BASE + roster index>` - so this needs no docker socket, no
ctf-controller integration and no place inside ctf-host at all. It computes the roster itself
from STUDENT_PREFIX/STUDENT_COUNT, the same formula controller.py's `roster()`/`host_port()`
use (duplicated here with this comment, not imported - achievements and ctf-controller already
duplicate small constants like this across services rather than share a module across trust
boundaries).

Posts straight to achievements over `workshop_lab`, the same trust tier as `ctf-flags`: this is
OUR code, not reachable by a student, so it can safely hold the adapter secret - no separate
soc-feed/log-tailing service needed. `ctf`/dump_success events feed the wall of shame; every
other outcome (`soc`/recon|probe|exploit_attempt|contained) feeds the SOC Alerts feed/countdown
(modules/achievements/service/store.py).

**Does nothing at all until the facilitator starts it** (revised 2026-10-05 at the user's
request, so a lab can build and sit idle while students are walked through the briefing): on
start this process polls achievements' `POST /api/soc/control` - a signed request, same scheme
as every event it posts - every few seconds until the facilitator's "Start Attack Swarm" button
(`store.py`'s `admin_soc_start()`) has set a `started_at`, then begins its persona threads from
that EXACT timestamp, so the bot's own phases and the countdown everyone's watching can never
drift apart. If achievements isn't wired at all (no adapter secret - a standalone/dev run),
it starts immediately instead, since there's no facilitator button to wait for.

Stdlib only.
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

from personas import Swarm

HERE = os.path.dirname(os.path.abspath(__file__))
# dojo_http/adapter_client: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has
# copied it in (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
from adapter_client import AdapterClient  # noqa: E402

# The built image has it at ./exploit/ (the Dockerfile COPYs it there); running from a repo
# checkout (tests, dev) it's still under targets/customer-portal/exploit/ - try both so this
# never needs a copy or a symlink kept in sync by hand.
for _candidate in (os.path.join(HERE, "exploit"),
                   os.path.join(HERE, "..", "targets", "customer-portal", "exploit")):
    if os.path.isdir(_candidate):
        sys.path.insert(0, _candidate)

CTF_EVENTS = {"dump_success"}   # everything else is a `soc` alert (see store.py's SOC_SEVERITY)


def roster(prefix, count):
    """Student handles in the same order/padding as controller.py's roster() - the roster
    index is also the published-port offset, so this MUST match exactly."""
    return [f"{prefix}{n:02d}" for n in range(1, count + 1)]


def target_url(host, port_base, index):
    return f"http://{host}:{port_base + index}"


def post_event(clients, attacker, outcome, challenge):
    """Signed POST to achievements, best effort (AdapterClient never blocks or raises) - plus a
    plain stdout line, for a human watching container logs."""
    source = "ctf" if outcome in CTF_EVENTS else "soc"
    clients[source].post({"event": outcome, "user": attacker.user, "challenge": challenge,
                          "persona": attacker.user, "origin": attacker.origin})
    print(f"[attacker-bot] {attacker.user} {outcome} (origin {attacker.origin})", flush=True)


def poll_control(url, secret, timeout=5):
    """One signed poll of achievements' /api/soc/control. Returns the room's started_at (a
    unix timestamp) once the facilitator has started the session, else None - never raises
    (a hiccup just means "not started yet" to the caller, same as a real "not yet" answer)."""
    body = b"{}"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Adapter-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    return doc.get("started_at") if isinstance(doc, dict) else None


def wait_for_start(control_url, secret, poll_seconds=5, sleep=time.sleep, now=time.time):
    """Blocks until the facilitator starts the session, returning the shared started_at. With
    no adapter secret configured (achievements not wired - a standalone/dev run), there is no
    facilitator button to wait for, so this starts immediately instead."""
    if not secret:
        return now()
    while True:
        started_at = poll_control(control_url, secret)
        if started_at is not None:
            return started_at
        sleep(poll_seconds)


def make_exploit_fn(url, timeout=5):
    """() -> True if the real payload still works against URL right now. Reuses the exact same
    payload the CI gate checks (targets/customer-portal/exploit/dump.py), so the bot and the
    gate can never disagree about what "patched" means."""
    import dump as dump_mod   # modules/ctf-range/targets/customer-portal/exploit/dump.py

    def exploit():
        try:
            rows = dump_mod.dump(url, timeout=timeout)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False     # an operational hiccup is not a breach
        return bool(rows)
    return exploit


def run(users, target_urls, challenge, started_at, clients, clock=time.time, sleep=time.sleep, rng=None,
       dwell_seconds=None, ramp_seconds=None):
    """Runs forever (the caller's process lifetime is the session's). TARGET_URLS: user -> URL.
    CLIENTS: {"ctf": AdapterClient, "soc": AdapterClient}. One thread per user; nothing here
    blocks on another user's thread."""
    import threading
    from personas import DWELL_SECONDS, RAMP_SECONDS

    swarm = Swarm(users, rng=rng, started_at=started_at,
                 dwell_seconds=DWELL_SECONDS if dwell_seconds is None else dwell_seconds,
                 ramp_seconds=RAMP_SECONDS if ramp_seconds is None else ramp_seconds)
    exploit_fns = {u: make_exploit_fn(target_urls[u]) for u in users}

    def attacker_loop(attacker):
        while True:
            now = clock()
            sleep(max(0.5, swarm.next_delay(attacker, now)))
            outcome, _extra = swarm.attempt(attacker, clock(), exploit_fns[attacker.user])
            post_event(clients, attacker, outcome, challenge)

    threads = [threading.Thread(target=attacker_loop, args=(a,), daemon=True) for a in swarm.attackers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def main():
    host = os.environ.get("CTF_HOST", "ctf-host")
    port_base = int(os.environ.get("CTF_HOST_PORT_BASE", "15000"))
    prefix = os.environ.get("STUDENT_PREFIX", "student")
    count = int(os.environ.get("STUDENT_COUNT", "0") or 0)
    challenge = os.environ.get("CTF_CHALLENGE", "customer-portal")
    adapter_url = os.environ.get("ACHIEVEMENTS_ADAPTER_URL", "http://achievements:8080/api/adapter")
    adapter_secret = os.environ.get("ACHIEVEMENTS_ADAPTER_SECRET", "")
    control_url = os.environ.get("ACHIEVEMENTS_SOC_CONTROL_URL", "http://achievements:8080/api/soc/control")
    dwell_seconds = int(os.environ.get("CTF_SOC_DWELL_SECONDS") or 0) or None
    ramp_seconds = int(os.environ.get("CTF_SOC_RAMP_SECONDS") or 0) or None

    users = roster(prefix, count)
    target_urls = {u: target_url(host, port_base, i) for i, u in enumerate(users)}
    clients = {"ctf": AdapterClient(adapter_url, adapter_secret, source="ctf"),
              "soc": AdapterClient(adapter_url, adapter_secret, source="soc")}
    print(f"[attacker-bot] {len(users)} students ready, targeting {host}:{port_base}+ - "
         "waiting for the facilitator to start the session...", flush=True)
    started_at = wait_for_start(control_url, adapter_secret)
    print(f"[attacker-bot] started - dwell clock begins now ({started_at})", flush=True)
    run(users, target_urls, challenge, started_at, clients, dwell_seconds=dwell_seconds, ramp_seconds=ramp_seconds)


if __name__ == "__main__":
    main()
