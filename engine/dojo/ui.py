"""One console and the house style: cyan steps, green ok, yellow changed or
waiting, red problems. Rich drops colour on its own when stdout isn't a
terminal or NO_COLOR is set."""
from __future__ import annotations

import sys

from rich.console import Console
from rich.markup import escape

# Not a terminal (a log, a pipe): wide lines rather than Rich's 80-column default.
console = Console(highlight=False, width=None if sys.stdout.isatty() else 160)
err = Console(stderr=True, highlight=False, width=None if sys.stderr.isatty() else 160)

STATE_STYLE = {"healthy": "green", "running": "green", "done": "green", "starting": "yellow",
               "waiting": "yellow", "pending": "yellow", "working": "yellow", "unhealthy": "red", "failed": "red"}
STATE_MARK = {"green": "+", "yellow": "~", "red": "x"}


def step(text: str) -> None:
    console.print(f"[bold cyan]==> {escape(text)}[/]")


def ok(text: str) -> None:
    console.print(f"  [green]{escape(text)}[/]")


def changed(text: str) -> None:
    console.print(f"  [yellow]{escape(text)}[/]")


def bad(text: str) -> None:
    console.print(f"  [red]{escape(text)}[/]")


def fail(text: str) -> None:
    err.print(f"[red]{escape(text)}[/]")
