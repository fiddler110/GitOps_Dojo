## Rules for challenges and capstones (apply to every workshop)

Students share one Forgejo, one DNS server, one CA, one cloud and one vault, so a challenge that changes shared state
breaks for the second person to try it. Every challenge and capstone must follow these:

1. **Write only to a space keyed on `{user}`:** their own repo, zone, namespace, slot or name prefix. Never `main` of a
   shared repo, a shared zone's apex, or an unprefixed name.
2. **Verify only that space.** Assertions read `{user}`-keyed state, never global state (a shared `main`, a whole zone,
   "the cloud is empty"), so another student's work can neither pass nor fail yours.
3. **No dependency on another student.** No peer approval, no "wait for a classmate". If a review or a merge is part of
   the goal, the seed provides the other party (a seeded PR from a bot account), or the facilitator, and only where
   truly required (the catalog says so).
4. **Change no shared config:** CA lifetimes, quotas, policies, branch protection and shared zones are read-only to a challenge.
5. **Seed per student.** The service creates one seed for each student (a repo, a branch set, a zone file) when the
   challenge is first opened. It is never one shared seed with a per-student label, because a fix to it lands for everyone.
6. **Independent of each other.** A challenge must still pass if another challenge was never attempted, or was undone
   (a pass is recorded when it is checked, and later clean-up never undoes it).

The catalog validator enforces what it can: every challenge declares a `space` containing `{user}`, and every
structured `verify` assertion mentions `{user}`.
