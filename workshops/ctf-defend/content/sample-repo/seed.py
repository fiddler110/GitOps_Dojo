"""Seed customer-portal's plaintext SQLite database.

Builds a small `customers` table of SYNTHETIC rows that reference this slot's
student handle (CTF-D25, §8.12). One row is the "secret" service account whose
password field holds the flag: a successful SQL-injection dump reveals it.

Everything here is lab-local fake data derived from the in-lab handle — no real
PII, ever. Plaintext at rest is deliberate scenario design so the dump is
legible on screen (the graded flaw is the SQL injection; cleartext storage is a
CTF-D17 bonus flaw).

Idempotent: safe to run on every start. If the DB already holds customers it
does nothing, so a student's running app keeps its data across restarts.
"""

import os
import sqlite3

DB_PATH = os.environ.get("CTF_DB_PATH", "/data/portal.db")


def _rows(student, flag):
    """Deterministic synthetic customers for `student` (e.g. "student07").

    Names/emails/passwords are obviously fake and tied to the handle so the
    dump clearly belongs to this student. The last row is the service account
    carrying the flag.
    """
    base = [
        ("Ada Lovelace",    "ada",    "hunter2",        "silver"),
        ("Grace Hopper",    "grace",  "nanosecond",     "gold"),
        ("Alan Turing",     "alan",   "enigma1912",     "silver"),
        ("Katherine Johnson","kath",  "trajectory",     "platinum"),
        ("Linus Torvalds",  "linus",  "justforfun",     "bronze"),
    ]
    customers = []
    for i, (name, user, pw, tier) in enumerate(base, start=1):
        customers.append((
            i,
            name,
            f"{user}.{student}@portal.lab",   # email tied to the handle
            pw,                                # cleartext password (bonus flaw)
            f"{student}-{1000 + i}",           # account id tied to the handle
            tier,
        ))
    # The secret service account: its "password" is the flag the dump yields.
    customers.append((
        len(base) + 1,
        "portal-service",
        f"service.{student}@portal.lab",
        flag,
        f"{student}-SVC",
        "service",
    ))
    return customers


def seed(db_path=DB_PATH):
    student = os.environ.get("CTF_STUDENT", "student07")
    flag = os.environ.get("CTF_FLAG", "flag{customer-portal-dev0000000000}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                password   TEXT NOT NULL,
                account_id TEXT NOT NULL,
                tier       TEXT NOT NULL
            )
            """
        )
        already = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if already == 0:
            conn.executemany(
                "INSERT INTO customers "
                "(id, name, email, password, account_id, tier) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                _rows(student, flag),
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print(f"seeded {DB_PATH} for {os.environ.get('CTF_STUDENT', 'student07')}")
