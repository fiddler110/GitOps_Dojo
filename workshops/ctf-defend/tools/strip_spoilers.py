#!/usr/bin/env python3
"""Write a student copy of a target file with the answers taken out.

The range's targets (modules/ctf-range/targets/<t>/) are annotated for whoever maintains them:
docstrings and comments name the flaw ("THE BUG", "THE FIX", a commented-out SAFE query). In
ctf-defend the student starts from that source and has to find and fix the flaw themselves, so
content/sync-sample-repos.sh copies every file through this script:

  *.py          every comment and every docstring removed (the shebang is kept). The result is
                checked: its AST must equal the original's minus the docstrings, so the code runs
                identically.
  Dockerfile    full-line comments removed (a leading `# syntax=` directive is kept).
  *.sh          full-line comments removed (the shebang is kept); refuses a heredoc.
  anything else copied unchanged.

Usage: strip_spoilers.py SRC DST
"""
import ast
import io
import os
import re
import sys
import tokenize

DOC_PARENTS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstrings(tree):
    """(node, parent) for every docstring expression in the tree."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, DOC_PARENTS) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.append((first, node))
    return out


def _without_docstrings(tree):
    for expr, parent in _docstrings(tree):
        parent.body.remove(expr)
        if not parent.body:
            parent.body.append(ast.Pass())
    return ast.dump(tree, include_attributes=False)


def strip_python(src):
    lines = src.splitlines(keepends=True)
    drop = set()          # 0-based line numbers to delete
    cut = {}              # 0-based line -> column to truncate a trailing comment at
    replace = {}          # 0-based line -> replacement text (docstring that was a whole body)

    tree = ast.parse(src)
    for expr, parent in _docstrings(tree):
        first, last = expr.lineno - 1, expr.end_lineno - 1
        drop.update(range(first, last + 1))
        if len(parent.body) == 1:     # the body was only the docstring: keep it valid
            indent = re.match(r"\s*", lines[first]).group(0)
            replace[first] = indent + "pass\n"

    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        row, col = tok.start[0] - 1, tok.start[1]
        if row == 0 and tok.string.startswith("#!"):
            continue
        if lines[row][:col].strip():
            cut[row] = col
        else:
            drop.add(row)

    out = []
    for i, line in enumerate(lines):
        if i in replace:
            out.append(replace[i])
        elif i in drop:
            continue
        elif i in cut:
            out.append(line[:cut[i]].rstrip() + "\n")
        else:
            out.append(line)
    text = re.sub(r"\n{3,}", "\n\n\n", "".join(out)).lstrip("\n")

    if ast.dump(ast.parse(text), include_attributes=False) != _without_docstrings(ast.parse(src)):
        raise SystemExit("strip_spoilers: stripped Python no longer matches the original's code")
    return text


def strip_full_line_comments(src, keep_first):
    out = []
    for i, line in enumerate(src.splitlines(keepends=True)):
        if line.lstrip().startswith("#") and not (i == 0 and keep_first(line)):
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).lstrip("\n")


def strip(path, src):
    name = os.path.basename(path)
    if name.endswith(".py"):
        return strip_python(src)
    if name == "Dockerfile":
        return strip_full_line_comments(src, lambda l: l.lower().startswith("# syntax="))
    if name.endswith(".sh"):
        if "<<" in src:
            raise SystemExit(f"strip_spoilers: {path} has a heredoc; strip it by hand")
        return strip_full_line_comments(src, lambda l: l.startswith("#!"))
    return src


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    src, dst = argv[1], argv[2]
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(strip(src, text))
    os.chmod(dst, os.stat(src).st_mode & 0o777)


if __name__ == "__main__":
    main(sys.argv)
