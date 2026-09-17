"""Small standalone helpers shared by dnsctl's command handlers: stderr
printing, interactive prompts, and a couple of string/argument parsers."""

from __future__ import annotations

import argparse
import re
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "change"


def parse_index_arg(text: str) -> list[int]:
    """Parse one --remove token: a plain int ("3"), a range ("1-6"), or
    comma-separated combos of either ("1,2,4-6"). Returns the expanded ints."""
    result = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo > hi:
                lo, hi = hi, lo
            result.extend(range(lo, hi + 1))
            continue
        if not re.fullmatch(r"\d+", part):
            raise argparse.ArgumentTypeError(
                f"invalid index or range: {part!r} (expected an integer like '3' or a range like '1-6')"
            )
        result.append(int(part))
    return result


def prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or (default or "")


def prompt_yes_no(message: str, default_yes: bool = True) -> bool:
    suffix = " [Y/n]" if default_yes else " [y/N]"
    answer = input(f"{message}{suffix}: ").strip().lower()
    if not answer:
        return default_yes
    return answer == "y"
