"""Validation and argv builders for ctf-builder's one git operation: clone a
student's own repo and check out a commit, with no shell and no argument
injection (CLAUDE.md: subprocess arg lists, never shell=True with
interpolated input). Pure, tested in tests/test_gitref.py.
"""
import re

# The roster's own padding (student01..) but a little looser, so a
# differently-prefixed pack still works; still bounded and shell-safe.
_USER_RE = re.compile(r"^[a-z][a-z0-9]{0,31}$")

# A git ref or sha: no leading '-' (git option injection, e.g. "--upload-pack="),
# no whitespace, no control characters, no "..". Branch names, tags and
# 40/64-hex SHAs all match; bounded so a request body can't carry a megabyte
# of "ref".
_REF_RE = re.compile(r"^(?!-)[A-Za-z0-9._/-]{1,200}$")


def safe_user(user):
    return bool(_USER_RE.match(user or ""))


def safe_ref(ref):
    if not ref or ".." in ref or ref.endswith(".lock") or ref.startswith("/"):
        return False
    return bool(_REF_RE.match(ref))


def repo_url_for(user, git_server, repo_name):
    """The one repo ctf-builder will ever clone for this user. Built from a
    validated `user` and the builder's own fixed `repo_name` — never a URL the
    caller hands in (see docker_build.py's module docstring)."""
    return f"http://{git_server}/{user}/{repo_name}.git"


def clone_argv(repo_url, dest):
    """`--` stops option parsing even if a validated value still looked
    option-like: defence in depth alongside safe_user/safe_ref. Never
    shell=True, never string interpolation into a shell command."""
    return ["git", "clone", "--quiet", "--no-tags", "--", repo_url, dest]


def checkout_argv(dest, ref):
    # `ref` BEFORE `--`: a bare `git checkout -- <ref>` treats <ref> as a
    # PATHSPEC (restore this file from the index), not a revision -- it
    # fails with "pathspec '<ref>' did not match any file(s) known to git"
    # for any real commit/branch (found live: a merge's own SHA, right after
    # the push that created it, every time). `<ref> --` still checks out the
    # revision and still stops option parsing (safe_ref already forbids a
    # leading '-', so this is defence in depth, not the only guard).
    return ["git", "-C", dest, "checkout", "--quiet", ref, "--"]
