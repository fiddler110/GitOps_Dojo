"""The request lines behind the SOC feed's SIEM log (plan 8.2). Pure data and builders, no network.

Three traffic classes, each with its own shape and detection tag (the tag names the attack class,
never the fix):

  scan     internet background noise: robots.txt, /.env, /wp-login.php, banner grabs, with the
           assorted user-agents of the tools that send them. Never touches the app's real routes.
  probe    someone poking at this app: quote / boolean tests in q=, login guessing, and - with the
           bonus flaws on - guesses at the database file and an export. Nothing here is the exploit.
  exploit  the real payload (the same request the CI gate runs). Its status, size and row count are
           what the target actually answered, reported by bot.py; a breach is a 200 with a big body.

Every record is synthetic or observed by the bot itself: no real client address ever appears (the
origin is an ISO country code picked by personas.py). With CTF_BONUS_FLAWS=off no record mentions the
bonus paths: they are not drawn at all (probes.py).
"""
import random

import probes

SCAN_UAS = ("Mozilla/5.0 zgrab/0.x", "curl/7.88.1", "python-requests/2.31.0", "Go-http-client/1.1",
            "Mozilla/5.0 (compatible; Nmap Scripting Engine)", "masscan/1.3", "Wget/1.21.3",
            "Mozilla/5.0 (compatible; CensysInspect/1.1)", "libwww-perl/6.67")
FUZZ_UAS = ("sqlmap/1.7.2#stable", "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "python-requests/2.31.0", "curl/7.88.1")
EXPLOIT_UAS = ("python-requests/2.31.0", "python-urllib3/2.0.7", "curl/7.88.1")

# (method, path, query, status, byte range, tag, ua pool or None for SCAN_UAS)
SCAN = (
    ("GET", "/robots.txt", "", 200, (60, 90), "scanner", None),
    ("GET", "/favicon.ico", "", 404, (140, 220), "scanner", None),
    ("GET", "/.env", "", 404, (140, 220), "sensitive file requested", None),
    ("GET", "/.git/config", "", 404, (140, 220), "sensitive file requested", None),
    ("GET", "/wp-login.php", "", 404, (140, 220), "CMS scanner", None),
    ("GET", "/xmlrpc.php", "", 404, (140, 220), "CMS scanner", None),
    ("GET", "/server-status", "", 403, (180, 260), "scanner", None),
    ("GET", "/phpmyadmin/", "", 404, (140, 220), "admin console probe", None),
    ("HEAD", "/", "", 200, (0, 0), "banner grab", None),
    ("OPTIONS", "/", "", 200, (0, 0), "banner grab", None),
    ("GET", "/healthz", "", 200, (2, 16), "scanner", None),
)
# The fuzzing / guessing class. Statuses mirror a customer-portal that answers a bad query with a 500.
FUZZ = (
    ("GET", "/search", "q=smith", 200, (180, 420), "search parameter sweep", FUZZ_UAS),
    ("GET", "/search", "q=%27", 500, (60, 140), "SQL meta-characters in parameter q", FUZZ_UAS),
    ("GET", "/search", "q=smith%27+AND+%271%27%3D%271", 200, (180, 420), "SQL boolean test in parameter q", FUZZ_UAS),
    ("GET", "/search", "q=smith%27+AND+%271%27%3D%272", 200, (20, 40), "SQL boolean test in parameter q", FUZZ_UAS),
    ("POST", "/login", "", 401, (30, 60), "failed login (credential guessing)", FUZZ_UAS),
    ("POST", "/login", "", 401, (30, 60), "failed login (credential guessing)", FUZZ_UAS),
    ("GET", "/", "", 200, (900, 1500), "scanner", FUZZ_UAS),
)
BONUS_TAG = "sensitive file requested"


def _pick(rng, row, klass):
    method, path, query, status, (lo, hi), tag, uas = row
    return {"method": method, "path": path, "query": query, "status": status, "bytes": rng.randint(lo, hi),
            "ua": rng.choice(uas or SCAN_UAS), "tag": tag, "klass": klass}


def scan_request(rng=None):
    return _pick(rng or random, (rng or random).choice(SCAN), "scan")


def probe_request(rng=None, bonus_on=None):
    """A fuzzing/guessing request. With the bonus flaws on, `probes.BONUS_SHARE` of them go after the
    data at rest (database file, dump, export) - unlabelled, answered 404 like any file that isn't served."""
    rng = rng or random
    if bonus_on is None:
        bonus_on = probes.bonus_enabled()
    if bonus_on and rng.random() < probes.BONUS_SHARE:
        path = rng.choice(probes.BONUS_PATHS)
        return _pick(rng, ("GET", path, "", 404, (140, 220), BONUS_TAG, SCAN_UAS), "probe")
    return _pick(rng, rng.choice(FUZZ), "probe")


def exploit_request(payload_query, observed=None, breached=False, rng=None):
    """The exploit request. OBSERVED: what the bot saw come back ({"status", "bytes", "rows"}) or
    None when the target could not be reached (reported as a gateway error with no body)."""
    rng = rng or random
    obs = observed or {}
    rows = len(obs.get("rows") or ())
    rec = {"method": "GET", "path": "/search", "query": payload_query, "status": obs.get("status", 502),
           "bytes": obs.get("bytes", 0), "ua": rng.choice(EXPLOIT_UAS), "klass": "exploit",
           "tag": "bulk data egress" if breached else "SQL injection payload in parameter q",
           "rows_returned": rows}
    return rec


def request_for(outcome, rng=None, bonus_on=None, observed=None, payload_query=""):
    """The SIEM fields for one bot outcome (bot.post_event). recon is scan noise; a probe is mostly
    fuzzing/guessing with a share of background scans; the rest are the exploit request."""
    rng = rng or random
    if outcome == "recon":
        return scan_request(rng)
    if outcome == "probe":
        return scan_request(rng) if rng.random() < 0.3 else probe_request(rng, bonus_on)
    return exploit_request(payload_query, observed, breached=(outcome == "dump_success"), rng=rng)
