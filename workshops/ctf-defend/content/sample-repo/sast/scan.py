#!/usr/bin/env python3
"""Pinned, no-network SAST for customer-portal (target 14) — CWE-89.

The informational scan stage of CTF-5's defend pipeline (decisions CTF-D23/D24,
spike CTF-S17). It detects the *shape* of SQL injection: a SQL string built by
concatenation / f-string / %-format / .format() and handed to a DB cursor,
instead of a static query string with a params tuple.

Design posture (CTF-D24): self-contained and offline. Stdlib `ast` only, no
network, no external ruleset download — the one rule below IS the pinned
ruleset, chosen to cover *this lab's* planted flaw (CWE-89), not to chase newly
disclosed CVEs. When this moves into the `runner-pool` runner image it travels
as this file; nothing is fetched at run time.

NOT A GATE (CTF-D19/D23). Only the exploit re-run (exploit/dump.py) decides
red/yellow/green. This scan only *points* at the flaw, the way a real team's
pipeline output would. It therefore exits 0 even when it finds something, unless
`--strict` is passed (handy for a human spot-check, never used by the PR gate).

Exit codes:
  0  scan completed (findings may have been printed; informational).
  1  only with --strict: scan completed AND at least one finding.
  2  operational error (bad path, unparseable file) — not a verdict.
"""

import argparse
import ast
import sys

# The single pinned rule. Kept as data so the "ruleset" is legible and so the
# IaC/secret scanners for targets 8-11 (still open, see plan S17) can be added
# the same way without touching the engine below.
RULE_ID = "DOJO-PY-SQLI"
RULE_CWE = "CWE-89"
RULE_TITLE = "SQL built from untrusted input (use a parameterized query)"

# A string passed to one of these cursor methods is the SQL text.
_EXEC_METHODS = {"execute", "executescript", "executemany"}

# Only flag when the built string actually looks like SQL, so an ordinary
# f-string near a DB call is not a false positive. Covers the lab's targets.
_SQL_KEYWORDS = ("select", "insert", "update", "delete", "where", "from", "union")


def _looks_like_sql(text):
    low = text.lower()
    return any(kw in low for kw in _SQL_KEYWORDS)


def _collect_strings(node):
    """Yield the literal string fragments reachable in a dynamically-built
    expression, so we can tell whether the thing being built is SQL."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):  # an f-string
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                yield part.value
    elif isinstance(node, ast.BinOp):  # "a" + x, "a %s" % x
        yield from _collect_strings(node.left)
        yield from _collect_strings(node.right)
    elif isinstance(node, ast.Call):  # "...".format(x)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            yield from _collect_strings(node.func.value)


def _is_dynamic_sql(node):
    """True when `node` is a SQL string assembled from input rather than a
    single static literal. This is the CWE-89 shape."""
    if isinstance(node, ast.JoinedStr):
        # An f-string is only dynamic if it actually interpolates something.
        dynamic = any(isinstance(v, ast.FormattedValue) for v in node.values)
        return dynamic and _looks_like_sql("".join(_collect_strings(node)))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _looks_like_sql("".join(_collect_strings(node)))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return _looks_like_sql("".join(_collect_strings(node)))
    return False


class _Scanner(ast.NodeVisitor):
    """Flags `cursor.execute(<dynamic SQL>)`. Resolves one level of local
    `name = <expr>` indirection, which is how app.py is written
    (`sql = "..." + q; conn.execute(sql)`), while a parameterized call
    (`execute(sql, params)` with a static `sql`) raises nothing."""

    def __init__(self, filename):
        self.filename = filename
        self.findings = []
        self._assigns = {}  # last RHS seen for each simple name

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._assigns[node.targets[0].id] = node.value
        self.generic_visit(node)

    def _resolve(self, node):
        if isinstance(node, ast.Name) and node.id in self._assigns:
            return self._assigns[node.id]
        return node

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _EXEC_METHODS and node.args:
            # A params tuple (second positional arg) is the safe, parameterized
            # form — never a finding, regardless of how the string reads.
            has_params = len(node.args) >= 2
            sql_arg = self._resolve(node.args[0])
            if not has_params and _is_dynamic_sql(sql_arg):
                self.findings.append((node.lineno, func.attr))
        self.generic_visit(node)


def scan_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src, filename=path)
    except (OSError, SyntaxError) as exc:
        print(f"error: cannot scan {path}: {exc}", file=sys.stderr)
        return None
    scanner = _Scanner(path)
    scanner.visit(tree)
    return scanner.findings


def main():
    ap = argparse.ArgumentParser(description="CWE-89 SAST for customer-portal")
    ap.add_argument("paths", nargs="*", default=["app.py"],
                    help="Python files to scan (default: app.py)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any finding (a human spot-check; the PR gate never sets this)")
    args = ap.parse_args()

    total = 0
    had_error = False
    for path in args.paths:
        findings = scan_file(path)
        if findings is None:
            had_error = True
            continue
        for lineno, method in findings:
            total += 1
            print(f"{path}:{lineno}: {RULE_ID} ({RULE_CWE}) {RULE_TITLE}")
            print(f"    cursor.{method}() runs a string-built query here; "
                  f"use a '?' placeholder and a params tuple instead.")

    if had_error:
        return 2
    if total:
        print(f"\nSAST: {total} potential SQL-injection site(s) — informational, "
              f"not a gate (CTF-D23). The exploit re-run is the gate.")
    else:
        print("SAST: no CWE-89 patterns found.")
    return 1 if (args.strict and total) else 0


if __name__ == "__main__":
    sys.exit(main())
