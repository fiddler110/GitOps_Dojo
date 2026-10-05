"""The dojo command line. Each command is a thin layer over a module that does
the work, so the logic is usable (and testable) without Click.

`./run.sh <workshop> [flags]` starts a workshop: any first word that isn't a
command is taken as a workshop name (`./run.sh start <workshop>` also works).
Tab completion comes from these same definitions (engine/completions/).
"""
from __future__ import annotations

import json
import os
import sys
from typing import List, Optional, Tuple

import click
from click.shell_completion import CompletionItem
from rich.markup import escape
from rich.table import Table

from . import doctor as doctor_mod
from . import paths
from . import stack
from . import status as status_mod
from .envfiles import EnvError, mask, resolve
from .runtime import Runtime, project_name
from .ui import console, fail
from .workshops import modules as all_modules
from .workshops import workshops as all_workshops

PROG = paths.PROG
SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}


# --- completion helpers -------------------------------------------------------------
def _complete_workshop(ctx, param, incomplete):
    return [CompletionItem(w.name, help=w.title) for w in all_workshops() if w.name.startswith(incomplete)]


def _complete_env(ctx, param, incomplete):
    return [p.name[len(".env."):] for p in paths.ENGINE.glob(".env.*")
            if p.name not in (".env.example", ".env.previous", ".env.new")
            and p.name[len(".env."):].startswith(incomplete)]


def _complete_service(ctx, param, incomplete):
    """The running stack's services, from Compose's labels."""
    from .envfiles import operator_env
    return sorted({c.service for c in Runtime().containers(project_name(operator_env()))
                   if c.service.startswith(incomplete)})


ENV_OPTION = click.option("--env", "env_name", metavar="NAME", shell_complete=_complete_env,
                          help="Also load engine/.env.NAME on top of engine/.env (its values win).")


def start_options(f):
    for opt in reversed([
        click.option("--test", "test", is_flag=False, flag_value="", default=None, metavar="[N]",
                     help="Also start demo bot students: 3, or N (max 35). testuser1-3 are "
                          "expert/intermediate/novice; any beyond get one of those at random."),
        click.option("--fast", is_flag=True,
                     help="With --test: bots skip every pause and typing delay, put mistakes in every round "
                          "(intermediate, novice), and stop after one round. For checks, not demos."),
        ENV_OPTION,
        click.option("--dry-run", is_flag=True, help="Preview what would be rebuilt and started; change nothing."),
        click.option("--build-only", is_flag=True, help="Build or refresh the images and stop there (no password checks)."),
        click.option("--allow-default-passwords", is_flag=True,
                     help="Start even with public default passwords on a non-loopback address."),
    ]):
        f = opt(f)
    return f


def _start(workshop: str, test, fast, env_name, dry_run, build_only, allow_default_passwords) -> None:
    from .start import StartOptions, run_start
    sys.exit(run_start(StartOptions(workshop, test=test, fast=fast, env_name=env_name, dry_run=dry_run,
                                    build_only=build_only, allow_default_passwords=allow_default_passwords)))


def _workshop_command(name: str) -> click.Command:
    """`./run.sh <name> [flags]`: the start command with the workshop filled in."""
    @click.command(name=name, context_settings=SETTINGS, help=f"Build and start the {name} workshop.")
    @start_options
    def cmd(**kw):
        _start(name, **kw)
    return cmd


class DojoGroup(click.Group):
    def get_command(self, ctx, name):
        cmd = super().get_command(ctx, name)
        if cmd is None and not name.startswith("-"):
            return _workshop_command(name)  # start validates the name and says if no such workshop
        return cmd

    def shell_complete(self, ctx, incomplete):
        items = super().shell_complete(ctx, incomplete)
        return items + _complete_workshop(ctx, None, incomplete)

    def format_epilog(self, ctx, formatter):
        with formatter.section(f"Workshops ({paths.PROG} <workshop> [--test [N]] [--env NAME] [--dry-run] ...)"):
            formatter.write_dl([(w.name, w.title) for w in all_workshops()])
        formatter.write_paragraph()
        formatter.write_text(f"Run '{PROG} <command> --help' for a command's own options.")


@click.group(cls=DojoGroup, context_settings=SETTINGS, no_args_is_help=True)
def cli() -> None:
    """GitOps Dojo command centre: start, inspect and stop workshop stacks."""


# --- the stack ----------------------------------------------------------------------
@cli.command(context_settings=SETTINGS)
@click.argument("workshop", shell_complete=_complete_workshop)
@start_options
def start(workshop, **kw) -> None:
    """Build and start WORKSHOP (the same as giving WORKSHOP as the command)."""
    _start(workshop, **kw)


@cli.command(context_settings=SETTINGS)
@click.argument("services", nargs=-1, shell_complete=_complete_service)
@click.option("--clean", is_flag=True, help="Stop (deleting every volume), then start fresh.")
def restart(services: Tuple[str, ...], clean: bool) -> None:
    """Restart the workshop last started here, with the same flags.

    \b
    restart              recreate every container; volumes are kept, so student
                         homes, Forgejo repos and accounts survive
    restart SERVICE...   recreate only those services; the rest keep running
    restart --clean      stop (deletes every volume, no undo), then a fresh start"""
    from .start import run_restart
    sys.exit(run_restart(list(services), clean))


@cli.command(context_settings=SETTINGS)
@click.option("--dry-run", is_flag=True, help="List what would be removed; remove nothing.")
def stop(dry_run: bool) -> None:
    """Stop the stack and delete ALL its volumes (student homes, Forgejo data). No undo."""
    from .stop import run_stop
    sys.exit(run_stop(dry_run))


@cli.command("teardown", context_settings=SETTINGS, hidden=True)
@click.option("--dry-run", is_flag=True)
def teardown(dry_run: bool) -> None:
    """Same as stop."""
    from .stop import run_stop
    sys.exit(run_stop(dry_run))


@cli.command("build-all", context_settings=SETTINGS)
@ENV_OPTION
@click.option("--dry-run", is_flag=True, help="Only report what would be built.")
def build_all(env_name: Optional[str], dry_run: bool) -> None:
    """Build or refresh every workshop's images, one after another; start nothing."""
    from .start import run_build_all
    sys.exit(run_build_all(env_name, dry_run))


@cli.command(context_settings=SETTINGS)
@click.argument("service", shell_complete=_complete_service)
@click.option("-f", "--follow", is_flag=True, help="Keep printing new lines.")
@click.option("-n", "--tail", default="100", show_default=True, help="Lines to show from the end.")
def logs(service: str, follow: bool, tail: str) -> None:
    """Show a running service's log (by Compose service name, e.g. web-terminal)."""
    from .envfiles import operator_env
    rt = Runtime()
    match = [c for c in rt.containers(project_name(operator_env())) if c.service == service]
    if not match:
        fail(f"No container for service '{service}' is running ('{PROG} status' lists them).")
        sys.exit(1)
    os.execvp(rt.cli, [rt.cli, "logs", "--tail", tail, *(["-f"] if follow else []), match[0].name])


# --- looking ----------------------------------------------------------------------
@cli.command("list", context_settings=SETTINGS)
def list_cmd() -> None:
    """Show the workshops, in learning-path order."""
    console.print("Available workshops (in learning-path order):")
    shops = all_workshops()
    width = max((len(w.title) for w in shops), default=0)
    for w in shops:
        order = " " if w.order is None else str(w.order)
        title = escape(w.title).ljust(width) if w.duration else escape(w.title)
        console.print(f"  {order:>2}  [cyan]{w.name:<20}[/] {title}"
                      + (f"  [dim]{escape(w.duration)}[/]" if w.duration else ""))


@cli.command("modules", context_settings=SETTINGS)
def modules_cmd() -> None:
    """Show the modules and which workshops use them."""
    console.print('Available modules (add to a workshop with MODULES="name ..." in its workshop.env):')
    for m in all_modules():
        console.print(f"  [cyan]{m.name:<20}[/] {escape(m.summary)}")
        console.print(f"  {'':<20} [dim]used by: {', '.join(m.used_by) or '(none)'}[/]")


@cli.command(context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print the status as JSON (for scripts).")
def status(as_json: bool) -> None:
    """What is running: workshop, address, each service's health, students."""
    info = status_mod.collect(Runtime())
    if as_json:
        click.echo(json.dumps(info, indent=2))
    else:
        status_mod.show(info)


@cli.command(context_settings=SETTINGS)
@click.argument("workshop", required=False, shell_complete=_complete_workshop)
@ENV_OPTION
def doctor(workshop: Optional[str], env_name: Optional[str]) -> None:
    """Check this machine (and optionally one WORKSHOP) before a class.

    Exits 1 if anything would stop a start."""
    sys.exit(doctor_mod.show(doctor_mod.run_checks(Runtime(), workshop, env_name)))


@cli.command(context_settings=SETTINGS)
@click.argument("workshop", shell_complete=_complete_workshop)
@click.argument("keys", nargs=-1)
@ENV_OPTION
@click.option("--show-secrets", is_flag=True, help="Print passwords and tokens instead of their length.")
def config(workshop: str, keys: Tuple[str, ...], env_name: Optional[str], show_secrets: bool) -> None:
    """The settings WORKSHOP would start with, and where each one came from.

    With KEYS, every value each key was given, in load order, so you can see
    which file won (e.g. `config dns-as-code PUBLIC_BASE_URL --env home`)."""
    try:
        res = resolve(workshop, env_name)
    except EnvError as exc:
        fail(str(exc))
        sys.exit(1)
    shown = (lambda k, v: v) if show_secrets else mask
    for w in res.warnings:
        console.print(f"[yellow]{escape(w)}[/]")
    if keys:
        for key in keys:
            chain = res.origins.get(key)
            if not chain:
                where = "from the calling shell's environment" if key in res.env else "not set"
                console.print(f"[bold]{key}[/]: {escape(shown(key, res.env.get(key, '')))}  [dim]({where})[/]")
                continue
            console.print(f"[bold]{key}[/] = {escape(shown(key, chain[-1].value))}")
            for i, o in enumerate(chain):
                won = i == len(chain) - 1
                value = escape(shown(key, o.value))
                console.print(f"  {'[green]→[/]' if won else ' '} {escape(o.source):<44} "
                              + (value if won else f"[dim]{value}[/]"))
        return
    table = Table(box=None, pad_edge=False, header_style="dim")
    table.add_column("setting")
    table.add_column("value", overflow="fold")
    table.add_column("from", style="dim")
    for key in sorted(res.origins):
        chain = res.origins[key]
        note = f"  (overrides {len(chain) - 1})" if len(chain) > 1 else ""
        table.add_row(key, escape(shown(key, chain[-1].value)), escape(chain[-1].source) + note)
    console.print(f"[bold]{workshop}[/] with modules: {', '.join(res.modules) or 'none'}")
    console.print(table)


@cli.command("new-workshop", context_settings=SETTINGS)
@click.argument("name")
@click.option("--title", default="", help="Display name (default: from NAME, e.g. 'Dns As Code').")
@click.option("--description", default="", help="One sentence, shown on the login page.")
@click.option("--modules", "mods", default="", metavar="'A B'", help="Modules to use ('./run.sh modules' lists them).")
@click.option("--order", type=int, default=-1, help="Place in the learning path (default: last).")
@click.option("--duration", default="", metavar="'~2 h'", help="How long a session takes, shown by 'list'.")
@click.option("--org", default="training", show_default=True, help="Forgejo organisation of the sample repo.")
@click.option("--repo", default="", help="Forgejo name of the sample repo (default: NAME).")
@click.option("--terminal", is_flag=True, help="Also add compose/terminal/Dockerfile for extra tools.")
@click.option("--dry-run", is_flag=True, help="List the files it would write; write nothing.")
def new_workshop(name, title, description, mods, order, duration, org, repo, terminal, dry_run) -> None:
    """Start a new workshop pack in workshops/NAME/ from workshops/assets/template/:
    workshop.env, slides, a first lab and a sample repo, with TODOs to fill in."""
    from .scaffold import Scaffold, ScaffoldError, create, plan, prepare
    try:
        s = prepare(Scaffold(name, title, description, mods, order, duration, org, repo, terminal), cli.commands)
        files = plan(s) if dry_run else create(s)
    except (ScaffoldError, OSError) as exc:
        fail(str(exc))
        sys.exit(1)
    console.print(f"{'Would write' if dry_run else 'Wrote'} [bold]workshops/{name}/[/] "
                  f"([cyan]{escape(s.title)}[/], order {s.order}, modules: {s.modules or 'none'}, "
                  f"repo {s.org}/{s.repo}):")
    for f in files:
        console.print(f"  {f}")
    if dry_run:
        return
    console.print(f"\nNext: fill in the TODOs (workshops/{name}/README.md lists them), then\n"
                  f"  {PROG} {name} --dry-run\n  {PROG} {name}")


# --- setup, still shell scripts ---------------------------------------------------
def _passthrough(name: str, script: str, help_text: str) -> None:
    """A command run by its shell script with every argument as given (so
    `./run.sh setup --help` is the script's own help)."""
    @cli.command(name, help=help_text, add_help_option=False,
                 context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cmd(args):
        os.execvp("sh", ["sh", str(paths.ENGINE / "scripts" / script), *args])


_passthrough("setup", "env-setup.sh", "Create or update engine/.env (--default, --force, --rotate-class).")


@cli.command("capacity", add_help_option=False,
             context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def capacity(args):
    """Size the terminal resource limits for this machine ([WORKSHOP] --students N).

    With WORKSHOP first, every service it starts (modules included) is counted."""
    args = list(args)
    script = str(paths.ENGINE / "scripts" / "capacity-calc.sh")
    if args and args[0] in {w.name for w in all_workshops()}:
        workshop = args.pop(0)
        try:
            res = resolve(workshop, None)
            env = dict(res.env)
            env.setdefault("WEB_TERMINAL_IMAGE", "gitopsdojo/web-terminal:base")
            limits, oneshot = stack.mem_limits(Runtime(), stack.extra_files(res), env)
        except (EnvError, RuntimeError, OSError) as exc:
            fail(f"Could not read {workshop}'s services: {exc}")
            sys.exit(1)
        counted = {k: v for k, v in limits.items() if k != "web-terminal" and k not in oneshot}
        for name in sorted(k for k, v in counted.items() if v is None):
            console.print(f"[yellow]WARNING: {name} has no mem_limit, so nothing caps it; it isn't counted.[/]")
        total = sum(v for v in counted.values() if v)
        args = ["--other-services-mb", str(total),
                "--other-services-from", f"{workshop}: " + ", ".join(f"{k} {v}" for k, v in sorted(counted.items()) if v),
                *args]
    os.execvp("sh", ["sh", script, *args])
_passthrough("alias-setup", "alias-setup.sh", "Install the 'dojo' command (~/.local/bin) and tab completion (--check, --remove).")


@cli.command(context_settings=SETTINGS)
@click.argument("shell", type=click.Choice(["bash", "zsh"]))
def completion(shell: str) -> None:
    """Print the tab-completion script for SHELL (eval it, or source the file it names)."""
    click.echo((paths.ENGINE / "completions" / f"run.sh.{shell}").read_text())


@cli.command("help", context_settings=SETTINGS)
@click.pass_context
def help_cmd(ctx) -> None:
    """Show this overview."""
    click.echo(ctx.parent.get_help())


def _terminated(signum, frame):
    raise KeyboardInterrupt  # SIGTERM cleans up like Ctrl-C: lock, live view, child processes


def main() -> None:
    import signal
    signal.signal(signal.SIGTERM, _terminated)
    cli(prog_name=PROG, complete_var="_DOJO_COMPLETE")
