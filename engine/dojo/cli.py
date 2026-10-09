"""The dojo command line. Each command is a thin layer over a module that does
the work, so the logic is usable (and testable) without Click.

`./dojo <workshop> [flags]` starts a workshop: any first word that isn't a
command is taken as a workshop name (`./dojo start <workshop>` also works).
Tab completion comes from these same definitions (engine/completions/).
"""
from __future__ import annotations

import json
import os
import subprocess
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
    from .envfiles import known_profiles
    head, _, last = incomplete.rpartition(",")
    return [f"{head},{n}" if head else n for n in sorted(known_profiles()) if n.startswith(last)]


def _complete_service(ctx, param, incomplete):
    """The running stack's services, from Compose's labels."""
    from .envfiles import operator_env
    return sorted({c.service for c in Runtime().containers(project_name(operator_env()))
                   if c.service.startswith(incomplete)})


ENV_OPTION = click.option("--env", "env_name", metavar="NAME", shell_complete=_complete_env,
                          help="Also apply profile NAME (a [profiles.NAME] in dojo.local.toml and a [NAME] section in .env) on top; "
                               "NAME,NAME joins several, the last wins.")


def start_options(f):
    for opt in reversed([
        click.option("--test", "test", is_flag=False, flag_value="", default=None, metavar="[N]",
                     help="Also start demo bot students: 3, or N (max 35). testuser1-3 are "
                          "expert/intermediate/novice; any beyond get one of those at random."),
        click.option("--fast", is_flag=True,
                     help="With --test: bots skip every pause and typing delay, put mistakes in every round "
                          "(intermediate, novice), and stop after one round. For checks, not demos."),
        ENV_OPTION,
        click.option("--terminal", "terminal", type=click.Choice(["code-server", "zellij"]), default=None,
                     help="Terminal flavor for this run: code-server (VS Code + tmux) or zellij (terminal only). "
                          "Beats dojo.toml, profiles and workshop.env."),
        click.option("--dry-run", is_flag=True, help="Preview what would be rebuilt and started; change nothing."),
        click.option("--build-only", is_flag=True, help="Build or refresh the images and stop there (no password checks)."),
        click.option("--allow-default-passwords", is_flag=True,
                     help="Start even with public default passwords on a non-loopback address."),
        click.option("--pass", "--cookie", "--code", "gate_pass", default=None, metavar="CODE",
                     help="Ask for this access code on a page in front of everything, sign-in included (--pass, --cookie and --code are the same)."),
    ]):
        f = opt(f)
    return f


def _start(workshop: str, test, fast, env_name, dry_run, build_only, allow_default_passwords, gate_pass=None, terminal=None) -> None:
    from .start import StartOptions, run_start
    sys.exit(run_start(StartOptions(workshop, test=test, fast=fast, env_name=env_name, dry_run=dry_run,
                                    build_only=build_only, allow_default_passwords=allow_default_passwords,
                                    gate_pass=gate_pass, terminal=terminal)))


def _workshop_command(name: str) -> click.Command:
    """`./dojo <name> [flags]`: the start command with the workshop filled in."""
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


QUIET_COMMANDS = {"help", "stop", "teardown", "alias-setup", "restart", "status", "doctor", "config", "list",
                  "modules", "logs", "completion", "exec", "shell", "urls", "open", "wait", "version", "roster",
                  "reset-student", "backup", "restore", "export-results", "prune", "validate", "test", "ps"}


def _offer_completion() -> None:
    """The one-time, interactive offer to install `dojo` and tab completion (the script
    no-ops once answered, and outside a terminal). Not for read-only commands, previews or completing."""
    args = sys.argv[1:]
    if os.environ.get("_DOJO_COMPLETE") or not args or args[0].startswith(("-", "_")) or args[0] in QUIET_COMMANDS:
        return
    if "--dry-run" in args or "--build-only" in args:
        return
    script = paths.ENGINE / "scripts" / "install-completion.sh"
    if script.is_file():
        subprocess.run(["sh", str(script)], check=False)


@click.group(cls=DojoGroup, context_settings=SETTINGS, no_args_is_help=True)
def cli() -> None:
    """GitOps Dojo command centre: start, inspect and stop workshop stacks."""
    from . import migrate
    if migrate.needed() and not os.environ.get("_DOJO_COMPLETE"):
        for line in migrate.migrate():
            console.print(f"[yellow]{escape(line)}[/]")
    _offer_completion()


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
@click.argument("service", required=False, shell_complete=_complete_service)
@click.option("-f", "--follow", is_flag=True, help="Keep printing new lines.")
@click.option("-n", "--tail", default="100", show_default=True, help="Lines to show from the end (per service).")
@click.option("--all", "all_services", is_flag=True, help="Every service, colour-prefixed, merged in time order.")
@click.option("--since", default=None, metavar="WHEN", help="Only lines newer than WHEN: 10m, 2h, or a timestamp.")
@click.option("--grep", "pattern", default=None, metavar="PATTERN", help="Only lines matching this regular expression.")
@click.option("--errors", is_flag=True,
              help="Scan every service once for Traceback/ERROR/panic/Exception and summarise per service "
                   "(exits 1 if any are found). -n sets how many lines per service are scanned (default 2000).")
def logs(service: Optional[str], follow: bool, tail: str, all_services: bool, since: Optional[str],
         pattern: Optional[str], errors: bool) -> None:
    """Show service logs (by Compose service name, e.g. web-terminal).

    \b
    logs SERVICE [-f] [-n N]       one service
    logs --all [--since 10m]       every service, merged and colour-prefixed
    logs SERVICE --grep PATTERN    filter lines
    logs --errors                  which services logged errors, and the last one"""
    from . import logs as logs_mod
    from .stackapi import StackError, running
    rt = Runtime()
    try:
        containers = [c for c in running(rt) if c.state not in ("waiting",)]
    except StackError as exc:
        fail(str(exc))
        sys.exit(1)
    if not (service or all_services or errors):
        fail(f"Name a service, or use --all or --errors ('{PROG} status' lists the services).")
        sys.exit(2)
    if service and not (all_services or errors):
        match = [c for c in containers if c.service == service]
        if not match:
            fail(f"No container for service '{service}' is running ('{PROG} status' lists them).")
            sys.exit(1)
        if not pattern:
            os.execvp(rt.cli, [rt.cli, "logs", "--tail", tail, *(["--since", since] if since else []),
                               *(["-f"] if follow else []), match[0].name])
        containers = match
    elif service:
        containers = [c for c in containers if c.service == service]
        if not containers:
            fail(f"No container for service '{service}' is running.")
            sys.exit(1)
    if errors:
        data = {c.service: logs_mod.fetch(rt, c, "2000" if tail == "100" else tail, since) for c in containers}
        found = logs_mod.scan_errors(data)
        if not found:
            console.print(f"[green]No Traceback/ERROR/panic/Exception in {len(data)} service log(s).[/]")
            return
        table = Table(box=None, pad_edge=False, header_style="dim")
        table.add_column("service")
        table.add_column("hits", justify="right")
        table.add_column("last", overflow="fold")
        for svc, d in sorted(found.items(), key=lambda kv: -kv[1]["count"]):
            table.add_row(f"[red]{escape(svc)}[/]", str(d["count"]), escape(d["last"][:200]))
        console.print(table)
        console.print(f"[yellow]{len(found)} of {len(data)} service(s) logged errors; "
                      f"'{PROG} logs SERVICE --grep Traceback' shows them.[/]")
        sys.exit(1)
    colours = {c.service: logs_mod.COLOURS[i % len(logs_mod.COLOURS)] for i, c in enumerate(sorted(containers, key=lambda c: c.service))}
    width = max((len(c.service) for c in containers), default=0)

    def emit(svc: str, line: str) -> None:
        console.print(f"[{colours[svc]}]{escape(svc.ljust(width))}[/] | {escape(line)}", highlight=False, soft_wrap=True)

    if follow:
        logs_mod.follow(rt, containers, tail, since, emit, pattern)
        return
    data = {c.service: logs_mod.fetch(rt, c, tail, since) for c in containers}
    for svc, _, line in logs_mod.grep_filter(logs_mod.merged(data), pattern):
        emit(svc, line)


# --- looking ----------------------------------------------------------------------
@cli.command("list", context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print the list as JSON (for scripts).")
def list_cmd(as_json: bool) -> None:
    """Show the workshops, in learning-path order."""
    shops = all_workshops()
    if as_json:
        click.echo(json.dumps([{"name": w.name, "title": w.title, "order": w.order, "duration": w.duration or None,
                                "modules": w.modules} for w in shops], indent=2))
        return
    console.print("Available workshops (in learning-path order):")
    width = max((len(w.title) for w in shops), default=0)
    for w in shops:
        order = " " if w.order is None else str(w.order)
        title = escape(w.title).ljust(width) if w.duration else escape(w.title)
        console.print(f"  {order:>2}  [cyan]{w.name:<20}[/] {title}"
                      + (f"  [dim]{escape(w.duration)}[/]" if w.duration else ""))


@cli.command("modules", context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print the list as JSON (for scripts).")
def modules_cmd(as_json: bool) -> None:
    """Show the modules and which workshops use them."""
    if as_json:
        click.echo(json.dumps([{"name": m.name, "summary": m.summary, "used_by": m.used_by} for m in all_modules()], indent=2))
        return
    console.print('Available modules (add to a workshop with MODULES="name ..." in its workshop.env):')
    for m in all_modules():
        console.print(f"  [cyan]{m.name:<20}[/] {escape(m.summary)}")
        console.print(f"  {'':<20} [dim]used by: {', '.join(m.used_by) or '(none)'}[/]")


@cli.command(context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print the status as JSON (for scripts).")
@click.option("-w", "--watch", is_flag=True, help="Redraw every few seconds until Ctrl-C.")
@click.option("--interval", default=3.0, show_default=True, help="Seconds between redraws with --watch.")
def status(as_json: bool, watch: bool, interval: float) -> None:
    """What is running: workshop, address, each service's health, students.

    Also flags a build or start currently in flight (another ./dojo is
    mid-way through acquiring the lock, so a new 'dojo <workshop>' here
    would refuse). 'dojo ps' is a shorter alias for the same command."""
    if watch and not as_json:
        import time
        rt = Runtime()
        try:
            while True:
                info = status_mod.collect(rt)
                console.clear()
                status_mod.show(info)
                time.sleep(max(1.0, interval))
        except KeyboardInterrupt:
            return
    info = status_mod.collect(Runtime())
    if as_json:
        click.echo(json.dumps(info, indent=2))
    else:
        status_mod.show(info)


@cli.command("ps", context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print the status as JSON (for scripts).")
def ps(as_json: bool) -> None:
    """Shorter alias for 'dojo status' -- containers, lab health, in-flight starts."""
    info = status_mod.collect(Runtime())
    if as_json:
        click.echo(json.dumps(info, indent=2))
    else:
        status_mod.show(info)


@cli.command(context_settings=SETTINGS)
@click.argument("workshop", required=False, shell_complete=_complete_workshop)
@ENV_OPTION
@click.option("--fix", is_flag=True,
              help="First apply the safe fixes: remove a stale run lock, create a missing .env with 'setup --default', "
                   "chmod 600 .env. Never touches containers, images or volumes.")
@click.option("--json", "as_json", is_flag=True, help="Print the checks as JSON (for scripts).")
def doctor(workshop: Optional[str], env_name: Optional[str], fix: bool, as_json: bool) -> None:
    """Check this machine (and optionally one WORKSHOP) before a class.

    Exits 1 if anything would stop a start."""
    from .maintain import apply_fixes
    fixed = apply_fixes() if fix else []
    if fixed and not as_json:
        for line in fixed:
            console.print(f"[green]fixed:[/] {escape(line)}")
        console.print()
    results = doctor_mod.run_checks(Runtime(), workshop, env_name)
    if as_json:
        from dataclasses import asdict
        click.echo(json.dumps({"fixed": fixed, "checks": [asdict(c) for c in results],
                               "ok": not any(c.level == doctor_mod.FAIL for c in results)}, indent=2))
        sys.exit(1 if any(c.level == doctor_mod.FAIL for c in results) else 0)
    sys.exit(doctor_mod.show(results))


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
@click.option("--modules", "mods", default="", metavar="'A B'", help="Modules to use ('./dojo modules' lists them).")
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
# --- working with the running stack -------------------------------------------------
def _stack_errors(fn):
    """Turn a StackError into a red one-line message and exit 1."""
    import functools
    from .stackapi import StackError

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except StackError as exc:
            fail(str(exc))
            sys.exit(1)
    return wrapper


def _exec(service: str, cmd: Tuple[str, ...]) -> None:
    from .tools import exec_argv
    rt = Runtime()
    argv = exec_argv(rt, service, list(cmd))
    os.execvp(argv[0], argv)


@cli.command("exec", context_settings={**SETTINGS, "ignore_unknown_options": True})
@click.argument("service", shell_complete=_complete_service)
@click.argument("cmd", nargs=-1, type=click.UNPROCESSED)
@_stack_errors
def exec_cmd(service: str, cmd: Tuple[str, ...]) -> None:
    """Run a command in a service's container (a shell, bash if it has one, without CMD).

    \b
    exec web-terminal                 interactive shell
    exec git-server -- ls -l /data    one command (use -- before CMD's own flags)"""
    _exec(service, cmd)


@cli.command("shell", context_settings=SETTINGS)
@click.argument("service", required=False, default="web-terminal", shell_complete=_complete_service)
@_stack_errors
def shell_cmd(service: str) -> None:
    """Open a shell in a service's container (default: web-terminal). Alias of 'exec SERVICE'."""
    _exec(service, ())


@cli.command(context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print as JSON (for scripts).")
@_stack_errors
def urls(as_json: bool) -> None:
    """Where students, the facilitator and the slides go, and the logins.

    Passwords appear only when they are public defaults; otherwise just their length
    (the real ones: 'config WORKSHOP KEY --show-secrets')."""
    from .tools import urls as urls_info
    info = urls_info()
    if as_json:
        click.echo(json.dumps(info, indent=2))
        return
    console.print(f"[bold]Students:[/]     {info['student']}")
    console.print(f"[bold]Facilitator:[/]  {info['admin']}")
    console.print(f"[bold]Slides:[/]       {info['slides']}")
    for who, d in info["logins"].items():
        console.print(f"[bold]{who.capitalize()} login:[/] {escape(d['username'])} / {escape(d['password'] or '(not set)')}")


@cli.command("open", context_settings=SETTINGS)
@click.argument("where", type=click.Choice(["student", "admin", "slides"]), default="student")
@_stack_errors
def open_cmd(where: str) -> None:
    """Print a URL and open it in a browser (wslview or xdg-open, if present)."""
    from .tools import open_in_browser, urls as urls_info
    url = urls_info()[where]
    click.echo(url)
    if not open_in_browser(url):
        console.print("[dim]No wslview/xdg-open found: open the address above yourself.[/]")


@cli.command("wait", context_settings=SETTINGS)
@click.option("--timeout", default=600.0, show_default=True, help="Seconds to wait before giving up.")
def wait_cmd(timeout: float) -> None:
    """Block until every service is healthy; exit 1 on timeout."""
    from .tools import wait_ready
    rt = Runtime()

    def note(total, bad):
        console.print(f"  {total - len(bad)} of {total} ready" + (f"; waiting on {', '.join(f'{s} ({st})' for s, st in bad)}" if bad else ""))
    res = wait_ready(rt, timeout, on_change=note)
    if res["ok"]:
        console.print(f"[green]All services ready after {res['waited']:.0f}s.[/]")
        return
    fail(f"Not ready after {timeout:.0f}s: " + ", ".join(f"{s} ({st})" for s, st in res["not_ready"]))
    sys.exit(1)


@cli.command("version", context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print as JSON (for scripts).")
def version_cmd(as_json: bool) -> None:
    """The checkout's git revision, the container engine and the pinned Python wheels."""
    from .tools import version_info
    info = version_info(Runtime())
    if as_json:
        click.echo(json.dumps(info, indent=2))
        return
    g = info["git"]
    console.print(f"[bold]dojo:[/]    {g['rev'] or '(not a git checkout)'}"
                  f"{' on ' + g['branch'] if g['branch'] else ''}{' (uncommitted changes)' if g['dirty'] else ''}")
    console.print(f"[bold]engine:[/]  {info['engine'] or 'none found'} {info['engine_version'] or ''}  ·  compose: {info['compose'] or '?'}")
    console.print(f"[bold]python:[/]  {info['python']}")
    console.print("[bold]wheels:[/]  " + ", ".join(f"{w['name']} {w['version']}" for w in info["wheels"]))


# --- students and results ------------------------------------------------------------
@cli.command(context_settings=SETTINGS)
@click.option("--json", "as_json", is_flag=True, help="Print as JSON (for scripts).")
@_stack_errors
def roster(as_json: bool) -> None:
    """The students (and demo bots) holding a slot, whether they are active, any reset in progress."""
    from . import results
    rows = results.roster(Runtime())
    if as_json:
        click.echo(json.dumps(rows, indent=2))
    else:
        results.show_roster(rows)


@cli.command("reset-student", context_settings=SETTINGS)
@click.argument("user")
@click.option("--optional", default="", metavar="IDS", help="Comma-joined optional reset steps (as ticked in the Roster).")
@click.option("-y", "--yes", is_flag=True, help="Do not ask for confirmation.")
@_stack_errors
def reset_student(user: str, optional: str, yes: bool) -> None:
    """Put one student back as at stack start (the Roster's Reset). Deletes their work; no undo."""
    from . import results
    if not yes:
        click.confirm(f"Reset {user}? Their repos, files and progress for this workshop are deleted", abort=True)
    console.print(results.reset_student(Runtime(), user, optional))


@cli.command("export-results", context_settings=SETTINGS)
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", show_default=True)
@click.option("--out", "out_file", type=click.Path(dir_okay=False), default=None, help="Write here instead of stdout.")
@_stack_errors
def export_results(fmt: str, out_file: Optional[str]) -> None:
    """Scores and achievements from the achievements module (json adds the CTF/SOC data)."""
    from . import results
    text = results.render(results.fetch_results(Runtime()), fmt)
    if out_file:
        with open(out_file, "w") as fh:
            fh.write(text)
        console.print(f"Wrote {out_file}")
    else:
        click.echo(text, nl=False)


# --- keeping and checking -------------------------------------------------------------
@cli.command(context_settings=SETTINGS)
@click.argument("path", required=False, type=click.Path())
@_stack_errors
def backup(path: Optional[str]) -> None:
    """Snapshot every volume of the stack (Forgejo, student homes, achievements ...) into one tar.

    Podman only. Taken from a running stack, so a database written at that instant may be
    mid-write; 'stop' is not needed, but a quiet moment is best."""
    from . import backup as backup_mod
    from pathlib import Path
    res = backup_mod.backup(Runtime(), Path(path) if path else None)
    if res["live"]:
        console.print("[yellow]Containers were running: the snapshot is crash-consistent, not quiesced.[/]")
    console.print(f"Backed up {len(res['volumes'])} volume(s) of {res['workshop'] or 'the stack'} to "
                  f"[cyan]{res['path']}[/] ({res['bytes'] / 1048576:.1f} MB)")


@cli.command(context_settings=SETTINGS)
@click.argument("path", type=click.Path())
@click.option("-y", "--yes", is_flag=True, help="Do not ask for confirmation (also replaces leftover volumes).")
@_stack_errors
def restore(path: str, yes: bool) -> None:
    """Load a 'backup' into a stopped, fresh stack, then start the workshop to use it.

    Refuses while any container exists, or when the backup is of another workshop."""
    from . import backup as backup_mod
    from pathlib import Path
    rt = Runtime()
    m = backup_mod.plan_restore(rt, Path(path))
    console.print(f"Backup of [cyan]{m.get('workshop') or '?'}[/] taken {m.get('created', '?')}: {len(m.get('volumes', []))} volume(s)")
    if m["existing"]:
        console.print(f"[yellow]{len(m['existing'])} of them already exist here and will be replaced.[/]")
    if not yes:
        click.confirm("Restore these volumes?", abort=True)
    done = backup_mod.restore(rt, Path(path), m)
    console.print(f"Restored {len(done)} volume(s). Now start it: [cyan]{PROG} {m.get('workshop', '<workshop>')} "
                  f"{' '.join(m.get('args', []))}[/]".rstrip())


@cli.command(context_settings=SETTINGS)
@click.option("--dry-run", is_flag=True, help="List what would be removed; remove nothing.")
def prune(dry_run: bool) -> None:
    """Remove dangling gitopsdojo images left by rebuilds. Never touches volumes or containers."""
    from . import maintain
    res = maintain.prune(Runtime(), dry_run)
    if not res["supported"]:
        console.print("[yellow]prune works on podman only (docker keeps no per-image history to tell ours apart).[/]")
        return
    verb = "Would remove" if dry_run else "Removed"
    for i in res["removed"]:
        console.print(f"  {i['id']}  {escape(i['was'])}  {i['size'] / 1048576:.0f} MB")
    for i in res["skipped"]:
        console.print(f"  [yellow]kept {i['id']} (in use){'' }[/]")
    console.print(f"{verb} {len(res['removed'])} image(s), {res['bytes'] / 1048576:.0f} MB.")


@cli.command(context_settings=SETTINGS)
@click.argument("workshops", nargs=-1, shell_complete=_complete_workshop)
def validate(workshops: Tuple[str, ...]) -> None:
    """Static checks of every workshop pack (or the named ones): nothing is started.

    workshop.env, MODULES exist, extensions.json (the renderer --dry-run uses), achievements
    catalog. Exits 1 if any pack fails."""
    from . import validate as validate_mod
    bad = 0
    for name, checks in validate_mod.validate(list(workshops)):
        problems = [(t, p) for t, p in checks if p]
        bad += bool(problems)
        console.print(f"[{'red' if problems else 'green'}]{'x' if problems else '+'}[/] [bold]{name}[/]"
                      + ("" if problems else f"  [dim]{', '.join(t for t, _ in checks)}[/]"))
        for title, probs in problems:
            for line in probs:
                console.print(f"    [red]{escape(title)}:[/] {escape(line)}")
    console.print()
    if bad:
        fail(f"{bad} pack(s) failed.")
        sys.exit(1)
    console.print("[green]All packs valid.[/]")


@cli.command("test", context_settings=SETTINGS)
@click.argument("workshop", shell_complete=_complete_workshop)
@click.option("--n", "-n", "bots", default=3, show_default=True, type=click.IntRange(1, 35), help="Fast demo bots.")
@click.option("--matrix", default=None, metavar="KEY=a,b", help="Run once per value with KEY=value exported (stopping between runs).")
@click.option("--keep", is_flag=True, help="Leave the stack up after the (last) run instead of stopping it.")
@click.option("--timeout", default=15.0, show_default=True, metavar="MIN", help="Minutes to wait for the bots, per run.")
@ENV_OPTION
def test_cmd(workshop: str, bots: int, matrix: Optional[str], keep: bool, timeout: float, env_name: Optional[str]) -> None:
    """Start WORKSHOP with fast bots, wait for them to finish, report pass/fail, then stop.

    The same as 'WORKSHOP --test N --fast' and waiting on every ~/.dojo-bot-done. The stack is stopped
    afterwards even on failure or Ctrl-C (unless --keep). Exits 1 if any run failed."""
    from . import testrun
    from .start import StartOptions, run_start
    from .stop import run_stop
    try:
        spec = testrun.parse_matrix(matrix)
    except ValueError as exc:
        fail(str(exc))
        sys.exit(2)

    def start(w, n, env):
        return run_start(StartOptions(w, test=str(n), fast=True, env_name=env))

    try:
        results = testrun.run_matrix(workshop, bots, spec, keep, timeout * 60, env_name, start,
                                     lambda: run_stop(False), Runtime(), say=console.print)
    except KeyboardInterrupt:
        fail("Interrupted (the stack was stopped).")
        sys.exit(130)
    table = Table(box=None, pad_edge=False, header_style="dim")
    for col in ("run", "result", "bots done", "skipped steps", "time", "note"):
        table.add_column(col)
    for r in results:
        table.add_row(escape(r.label), "[green]PASS[/]" if r.ok else "[red]FAIL[/]", f"{r.done}/{r.bots}",
                      str(len(r.skips)), f"{r.seconds / 60:.1f} min", escape(r.note))
    console.print()
    console.print(table)
    for r in results:
        for line in r.skips[:5]:
            console.print(f"  [yellow]{escape(r.label)}[/] {escape(line[:200])}")
    sys.exit(0 if all(r.ok for r in results) else 1)


@cli.command("_operator-env", context_settings=SETTINGS, hidden=True)
@ENV_OPTION
def operator_env_cmd(env_name: Optional[str]) -> None:
    """Print the operator's settings (dojo.toml, dojo.local.toml, .env, profiles) as `export` lines,
    for shell scripts: eval "$(./dojo _operator-env [--env NAME])"."""
    import shlex
    from .envfiles import operator_env
    try:
        env = operator_env(env_name)
    except EnvError as exc:
        fail(str(exc))
        sys.exit(1)
    for key, value in sorted(env.items()):
        click.echo(f"export {key}={shlex.quote(value)}")


@cli.command("_config-get", context_settings=SETTINGS, hidden=True)
@click.argument("key")
@ENV_OPTION
def config_get_cmd(key: str, env_name: Optional[str]) -> None:
    """One operator setting's current value (used by setup for its prompt defaults)."""
    from .envfiles import operator_env
    click.echo(operator_env(env_name).get(key, ""))


@cli.command("_config-set", context_settings=SETTINGS, hidden=True)
@click.argument("key")
@click.argument("value")
@click.option("--profile", default=None, help="Write under [profiles.NAME.*] instead of the base settings.")
def config_set_cmd(key: str, value: str, profile: Optional[str]) -> None:
    """Set one non-secret setting in dojo.local.toml (used by setup)."""
    from . import config as config_mod
    try:
        config_mod.set_value(key, value, profile=profile, skip_default=True)
    except config_mod.ConfigError as exc:
        fail(str(exc))
        sys.exit(1)


def _passthrough(name: str, script: str, help_text: str) -> None:
    """A command run by its shell script with every argument as given (so
    `./dojo setup --help` is the script's own help)."""
    @cli.command(name, help=help_text, add_help_option=False,
                 context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cmd(args):
        os.execvp("sh", ["sh", str(paths.ENGINE / "scripts" / script), *args])


_passthrough("setup", "env-setup.sh", "Create or update .env (--default, --force, --rotate-class).")


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
    click.echo((paths.ENGINE / "completions" / f"dojo.{shell}").read_text())


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
