"""Which path an ordinary WARN-level `probe` alert carries (plan 8.7, CTF-D17).

A probe is a synthetic alert, never a real request, and never the exploit. Most probes name the
paths the graded fix touches (search, login, the front page). With the bonus flaws switched on
(CTF_BONUS_FLAWS=on, the ctf-defend default) a share of them name paths that go after the data at
rest instead (the database file, a dump, an export). Nothing marks the second group as special:
a student who sees an odd cluster of hits on a path the main fix never touched has a lead.

With the toggle off the second group is never drawn, so the target's alerts only ever name the
graded area. Bonus flaws are never exploited by the bots: no code here sends a payload.
"""
import os
import random

MAIN_PATHS = ("/", "/search?q=smith", "/search?q=%27", "/login", "/healthz", "/robots.txt")
# Data-at-rest probes: the customer-portal bonus flaw (passwords stored as typed). One list per
# bonus-carrying target would go here as more defend targets join the pack.
BONUS_PATHS = ("/portal.db", "/data/portal.db", "/backup/customers.sql", "/export/customers.csv")
BONUS_SHARE = 0.3        # of probes, when the bonus flaws are on


def bonus_enabled(env=os.environ):
    return str(env.get("CTF_BONUS_FLAWS", "on")).strip().lower() in ("on", "1", "true", "yes")


def probe_path(rng=None, bonus_on=None):
    rng = rng or random
    if bonus_on is None:
        bonus_on = bonus_enabled()
    if bonus_on and rng.random() < BONUS_SHARE:
        return rng.choice(BONUS_PATHS)
    return rng.choice(MAIN_PATHS)
