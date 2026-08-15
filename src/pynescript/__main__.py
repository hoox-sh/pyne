# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click CLI for the ``pyne`` console script (alias: ``pynescript``).

Installed entry points::

    pyne = pynescript.__main__:cli
    pynescript = pynescript.__main__:cli   # backward-compatible alias

Also ``python -m pynescript``.

Commands
--------
- ``check`` — parse-only validation (CI-friendly exit codes)
- ``format`` / ``fmt`` — parse → unparse (optional in-place write)
- ``parse-and-dump`` / ``dump`` / ``ast`` — AST dump
- ``parse-and-unparse`` / ``unparse`` — round-trip source
- ``lint`` — linter with colored / JSON output
- ``compile`` — transpile or compile-check via Numba pipeline
- ``prewarm`` — warm Numba builtins / optional script IR caches (H2)
- ``run`` — compile + execute on synthetic OHLCV
- ``data`` — fetch market bars (mock / Yahoo / …)
- ``info`` — version and optional extras (numba, rich, …)

The Language Server is a **separate** console script (``pyne-lsp`` /
``pynescript-lsp``), not a subcommand of this group. See
:mod:`pynescript.langserver.__main__`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import click

# Explicit version: PyPI dist is ``hoox-pyne``; import package is ``pynescript``.
from pynescript.__about__ import __version__ as _CLI_VERSION


def _configure_stdio() -> None:
    """Prefer UTF-8 on stdout/stderr so Windows cp1252 does not crash ``--help``.

    Click prints help before the ``cli()`` body runs, so this must run at
    import time (console-script entry is ``pynescript.__main__:cli``).
    """
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf is None:
            continue
        try:
            reconf(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            pass


_configure_stdio()


# ---------------------------------------------------------------------------
# Theme (PYNE volt) + optional Rich
# ---------------------------------------------------------------------------

_ACCENT = "#B7EF09"
_MUTED = "#CBCCBD"
_OK = "#B7EF09"
_FAIL = "#E7000B"
_WARN = "#EBA941"
_FG = "#EFEFE8"

_EPILOG = """\
\b
Examples:
  pynescript check script.pine
  pynescript format script.pine -w
  pynescript dump script.pine --indent 2
  pynescript lint script.pine --json
  pynescript compile script.pine --emit
  pynescript run script.pine --bars 100
  pynescript data AAPL --provider yahoo --period 6mo
  pynescript info

\b
Aliases:  dump -> parse-and-dump  ast -> parse-and-dump  unparse -> parse-and-unparse
          fmt -> format  ls -> info

Language server:  pynescript-lsp  (separate entry point, not a subcommand)
Docs:             https://hoox.sh/pyne
"""


def _has_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _console(*, force: bool = False) -> Any | None:
    """Rich console when TTY + rich available; honors ``NO_COLOR``."""
    import os

    if os.environ.get("NO_COLOR"):
        return None
    if not _has_rich():
        return None
    if not force and not sys.stdout.isatty():
        return None
    from rich.console import Console
    from rich.theme import Theme

    return Console(
        theme=Theme(
            {
                "pyne.accent": f"bold {_ACCENT}",
                "pyne.ok": f"bold {_OK}",
                "pyne.fail": f"bold {_FAIL}",
                "pyne.warn": f"bold {_WARN}",
                "pyne.muted": _MUTED,
                "pyne.fg": _FG,
            }
        )
    )


def _echo(msg: str = "", *, err: bool = False) -> None:
    click.echo(msg, err=err)


def _echo_status(kind: str, msg: str, *, err: bool = False) -> None:
    """kind: ok | fail | warn | info"""
    con = _console()
    if con is not None:
        style = {
            "ok": "pyne.ok",
            "fail": "pyne.fail",
            "warn": "pyne.warn",
            "info": "pyne.accent",
        }.get(kind, "pyne.fg")
        mark = {"ok": "✔", "fail": "✘", "warn": "!", "info": "◆"}.get(kind, "·")
        con.print(f"[{style}]{mark}[/{style}] {msg}", stderr=err)
        return
    mark = {"ok": "OK", "fail": "FAIL", "warn": "WARN", "info": "INFO"}.get(kind, "")
    prefix = f"{mark}: " if mark else ""
    _echo(f"{prefix}{msg}", err=err)


def _read_source(path: str | None, encoding: str = "utf-8") -> tuple[str, str]:
    """Return (source, label). path None or '-' → stdin."""
    if path is None or path == "-":
        return sys.stdin.read(), "<stdin>"
    p = Path(path)
    return p.read_text(encoding=encoding), str(p)


def _write_out(text: str, output_file: str, encoding: str = "utf-8") -> None:
    with click.open_file(output_file, "w", encoding=encoding) as f:
        f.write(text)
        if text and not text.endswith("\n") and output_file == "-":
            f.write("\n")


def _synthetic_ohlcv(n: int = 50) -> dict[str, list[float]]:
    """Deterministic walk for CLI ``run`` (matches showcase-style bars)."""
    ohlcv: dict[str, list[float]] = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        l = round(min(o, c) - 0.8, 2)
        ohlcv["open"].append(float(o))
        ohlcv["high"].append(float(h))
        ohlcv["low"].append(float(max(l, 0.01)))
        ohlcv["close"].append(float(c))
        ohlcv["volume"].append(float(1000 + i))
        price = c
    return ohlcv


# ---------------------------------------------------------------------------
# Click group with aliases
# ---------------------------------------------------------------------------

_COMMAND_ALIASES: dict[str, str] = {
    "dump": "parse-and-dump",
    "ast": "parse-and-dump",
    "unparse": "parse-and-unparse",
    "fmt": "format",
    "ls": "info",
}


class PyneGroup(click.Group):
    """Click group with short aliases and ordered command listing."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        resolved = _COMMAND_ALIASES.get(cmd_name)
        if resolved is not None:
            return super().get_command(ctx, resolved)
        # prefix match for convenience (unique only)
        matches = [n for n in self.list_commands(ctx) if n.startswith(cmd_name)]
        if len(matches) == 1:
            return super().get_command(ctx, matches[0])
        return None

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        # Map alias to canonical name so help/usage show the real command
        if args:
            head = args[0]
            if head in _COMMAND_ALIASES:
                args = [_COMMAND_ALIASES[head], *args[1:]]
        return super().resolve_command(ctx, args)

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(super().list_commands(ctx))


def _print_banner() -> None:
    from pynescript import __version__

    con = _console()
    if con is not None:
        con.print(
            f"[pyne.accent]◆ PYNE[/] [pyne.fg]pynescript[/] "
            f"[pyne.muted]v{__version__}[/]"
        )
        con.print(
            "[pyne.muted]Pine Script toolchain — parse · lint · compile · run[/]"
        )
    else:
        _echo(f"PYNE pynescript v{__version__}")
        _echo("Pine Script toolchain — parse · lint · compile · run")


@click.group(
    cls=PyneGroup,
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 100,
        "show_default": True,
    },
    invoke_without_command=True,
    epilog=_EPILOG,
)
@click.version_option(
    _CLI_VERSION,
    "--version",
    "-V",
    message="%(version)s",
    prog_name="pynescript",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output (also honors NO_COLOR).",
)
@click.pass_context
def cli(ctx: click.Context, no_color: bool) -> None:
    """Pyne / pynescript -- Pine Script parse, lint, compile, and run.

    Use ``pynescript COMMAND -h`` for per-command help.
    """
    if no_color:
        import os

        os.environ["NO_COLOR"] = "1"
    ctx.ensure_object(dict)
    ctx.obj["no_color"] = no_color
    if ctx.invoked_subcommand is None:
        _print_banner()
        _echo()
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@cli.command("info", short_help="Show version and optional runtime extras.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def info_cmd(as_json: bool) -> None:
    """Print package version, Python, and available optional features."""
    import platform

    from pynescript import __version__

    try:
        from pynescript.compiler.engine import has_numba

        numba = has_numba()
    except Exception:
        numba = False

    payload = {
        "name": "pynescript",
        "distribution": "hoox-pyne",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numba": numba,
        "rich": _has_rich(),
        "entry_points": {
            "cli": "pyne",
            "cli_alias": "pynescript",
            "lsp": "pyne-lsp",
            "lsp_alias": "pynescript-lsp",
        },
        "docs": "https://hoox.sh/pyne",
    }

    if as_json:
        _echo(json.dumps(payload, indent=2))
        return

    con = _console()
    if con is not None:
        from rich.table import Table

        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column(style="pyne.muted")
        t.add_column(style="pyne.fg")
        t.add_row("package", f"pynescript {__version__} (hoox-pyne)")
        t.add_row("python", payload["python"])
        t.add_row("platform", str(payload["platform"])[:60])
        t.add_row("numba", "yes" if numba else "no (object-mode compile only)")
        t.add_row("rich", "yes" if payload["rich"] else "no (plain output)")
        t.add_row("cli", "pyne (alias: pynescript)")
        t.add_row("lsp", "pyne-lsp (alias: pynescript-lsp)")
        t.add_row("docs", payload["docs"])
        con.print(t)
    else:
        _echo(f"package:  pynescript {__version__} (hoox-pyne)")
        _echo(f"python:   {payload['python']}")
        _echo(f"platform: {payload['platform']}")
        _echo(f"numba:    {'yes' if numba else 'no'}")
        _echo(f"rich:     {'yes' if payload['rich'] else 'no'}")
        _echo("cli:      pyne (alias: pynescript)")
        _echo("lsp:      pyne-lsp (alias: pynescript-lsp)")
        _echo(f"docs:     {payload['docs']}")


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


@cli.command("check", short_help="Parse-only validation (exit 1 on syntax errors).")
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(exists=False, dir_okay=True, file_okay=True, readable=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding.")
@click.option("-q", "--quiet", is_flag=True, help="Only set exit code; no per-file lines.")
@click.option(
    "--ext",
    default=".pine",
    show_default=True,
    help="When PATH is a directory, only check files with this suffix.",
)
def check_cmd(paths: tuple[str, ...], encoding: str, quiet: bool, ext: str) -> None:
    """Validate that PATH(s) parse as Pine Script.

    Accepts files and directories (directories are walked for ``--ext``).
    Reads stdin when no paths are given (or a single ``-``).
    """
    from pynescript.ast import parse
    from pynescript.ast.error import SyntaxError as PineSyntaxError

    files = _expand_paths(paths, ext=ext)
    if not files and (not paths or paths == ("-",)):
        files = ["-"]
    if not files:
        raise click.ClickException("no input files")

    ok = 0
    fail = 0
    for path in files:
        try:
            source, label = _read_source(path if path != "-" else "-", encoding)
            parse(source, label if path != "-" else "<stdin>")
            ok += 1
            if not quiet:
                _echo_status("ok", label)
        except (PineSyntaxError, SyntaxError, ValueError, OSError) as e:
            fail += 1
            if not quiet:
                msg = str(e).split("\n")[0][:200]
                _echo_status("fail", f"{path}: {msg}", err=True)

    if not quiet:
        _echo()
        if fail:
            _echo_status("fail", f"{ok} ok, {fail} failed")
        else:
            _echo_status("ok", f"{ok} file(s) ok")

    if fail:
        raise SystemExit(1)


def _expand_paths(paths: tuple[str, ...], *, ext: str) -> list[str]:
    out: list[str] = []
    for raw in paths:
        if raw == "-":
            out.append("-")
            continue
        p = Path(raw)
        if p.is_dir():
            out.extend(str(f) for f in sorted(p.rglob(f"*{ext}")) if f.is_file())
        elif p.is_file():
            out.append(str(p))
        else:
            raise click.ClickException(f"not found: {raw}")
    return out


# ---------------------------------------------------------------------------
# parse-and-dump / parse-and-unparse / format
# ---------------------------------------------------------------------------


@cli.command("parse-and-dump", short_help="Parse a file and dump the AST.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option("--indent", type=int, default=2, help="Indentation width of the AST dump.")
@click.option(
    "--output-file",
    "-o",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    help="Output path (default: stdout).",
    default="-",
)
def parse_and_dump(filename: str, encoding: str, indent: int, output_file: str) -> None:
    """Parse PATH and write a structured AST dump (:func:`pynescript.ast.dump`)."""
    from pynescript.ast import dump
    from pynescript.ast import parse

    source, label = _read_source(filename if filename != "-" else "-", encoding)
    script_node = parse(source, label)
    _write_out(dump(script_node, indent=indent), output_file, encoding)


@cli.command("parse-and-unparse", short_help="Parse a file and unparse back to source.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option(
    "--output-file",
    "-o",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    help="Output path (default: stdout).",
    default="-",
)
def parse_and_unparse(filename: str, encoding: str, output_file: str) -> None:
    """Parse PATH and unparse it back to Pine source (:func:`pynescript.ast.unparse`)."""
    from pynescript.ast import parse
    from pynescript.ast import unparse

    source, label = _read_source(filename if filename != "-" else "-", encoding)
    _write_out(unparse(parse(source, label)), output_file, encoding)


@cli.command("format", short_help="Format Pine via parse -> unparse.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option(
    "-w",
    "--write",
    "write_inplace",
    is_flag=True,
    help="Write formatted source back to PATH (not for stdin).",
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Exit 1 if formatting would change the file (no write).",
)
@click.option(
    "--output-file",
    "-o",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    default="-",
    help="Output path when not using --write (default: stdout).",
)
def format_cmd(
    filename: str,
    encoding: str,
    write_inplace: bool,
    check_only: bool,
    output_file: str,
) -> None:
    """Canonicalize Pine source by round-tripping through the AST.

    This is structural (not a full style formatter): comments and exact
    whitespace may change; semantics are preserved.
    """
    from pynescript.ast import parse
    from pynescript.ast import unparse

    if filename == "-" and write_inplace:
        raise click.ClickException("cannot --write stdin")

    source, label = _read_source(filename if filename != "-" else "-", encoding)
    formatted = unparse(parse(source, label))
    if not formatted.endswith("\n"):
        formatted += "\n"
    # normalize comparison: ensure source ends with newline for check
    original = source if source.endswith("\n") else source + "\n"

    if check_only:
        if original != formatted:
            if filename != "-":
                _echo_status("fail", f"would reformat {label}")
            raise SystemExit(1)
        _echo_status("ok", f"already formatted: {label}")
        return

    if write_inplace:
        Path(filename).write_text(formatted, encoding=encoding)
        _echo_status("ok", f"formatted {label}")
        return

    _write_out(formatted.rstrip("\n"), output_file, encoding)


# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------


@cli.command("lint", short_help="Lint Pine Script for issues.")
@click.argument("filename", metavar="PATH", type=str, required=False)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option(
    "--fail-on",
    type=click.Choice(["errors", "warnings", "all", "never"], case_sensitive=False),
    default="errors",
    help="Exit non-zero on this severity (never = always 0).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit findings as JSON array.")
@click.option("-q", "--quiet", is_flag=True, help="Summary only (or silence with --json).")
def lint(filename: str | None, encoding: str, fail_on: str, as_json: bool, quiet: bool) -> None:
    """Lint a Pine Script file (or stdin).

    If no PATH is provided, reads from stdin. Use ``-`` for stdin explicitly.
    """
    from pynescript.ast.linter import lint_script

    source, label = _read_source(filename, encoding)
    warnings = lint_script(source, label)

    if as_json:
        payload = [
            {
                "code": w.code,
                "message": w.message,
                "line": w.line,
                "column": w.column,
                "severity": w.severity,
                "file": label,
            }
            for w in warnings
        ]
        _echo(json.dumps(payload, indent=2))
    elif not warnings:
        if not quiet:
            _echo_status("ok", "No issues found.")
    else:
        if not quiet:
            con = _console()
            if con is not None:
                from rich.table import Table

                table = Table(show_header=True, header_style="pyne.accent", box=None, padding=(0, 1))
                table.add_column("sev", style="pyne.muted", width=6)
                table.add_column("code", style="pyne.fg")
                table.add_column("line", justify="right", style="pyne.muted")
                table.add_column("message", style="pyne.fg", overflow="fold")
                for w in warnings:
                    sev_style = "pyne.fail" if w.severity == "error" else "pyne.warn"
                    table.add_row(
                        f"[{sev_style}]{w.severity[:3]}[/{sev_style}]",
                        w.code,
                        str(w.line or ""),
                        w.message,
                    )
                con.print(table)
            else:
                for w in warnings:
                    mark = "E" if w.severity == "error" else "W"
                    _echo(f"{mark} [{w.code}] {w.message} @ {w.line}:{w.column}")

        n_err = sum(1 for w in warnings if w.severity == "error")
        n_warn = len(warnings) - n_err
        if not quiet or not as_json:
            _echo_status(
                "warn" if n_err == 0 else "fail",
                f"{len(warnings)} issue(s): {n_err} error(s), {n_warn} warning(s)",
            )

    has_errors = any(w.severity == "error" for w in warnings)
    has_warnings = any(w.severity == "warning" for w in warnings)

    if fail_on == "never":
        return
    if fail_on == "errors" and has_errors:
        raise SystemExit(1)
    if fail_on == "warnings" and (has_errors or has_warnings):
        raise SystemExit(1)
    if fail_on == "all" and warnings:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# compile / run
# ---------------------------------------------------------------------------


@cli.command("compile", short_help="Compile or transpile Pine to the Numba host pipeline.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option(
    "--emit",
    is_flag=True,
    help="Print generated Python source (transpile only; no exec/JIT).",
)
@click.option(
    "--output-file",
    "-o",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    default="-",
    help="Where to write --emit output (default: stdout).",
)
@click.option("--time/--no-time", "show_time", default=True, help="Print compile timing.")
def compile_cmd(
    filename: str, encoding: str, emit: bool, output_file: str, show_time: bool
) -> None:
    """Compile PATH through :func:`pynescript.compiler.compile_script`.

    Without ``--emit``, loads the compiled entry (and warm-ups Numba when
    applicable). With ``--emit``, only prints the generated Python module.
    """
    from pynescript.compiler.engine import compile_script
    from pynescript.compiler.engine import has_numba
    from pynescript.compiler.engine import transpile

    source, label = _read_source(filename if filename != "-" else "-", encoding)
    t0 = time.perf_counter() if show_time else 0.0

    try:
        if emit:
            code = transpile(source)
            _write_out(code, output_file, encoding)
            elapsed = (time.perf_counter() - t0) * 1000 if show_time else None
            if show_time and output_file != "-":
                _echo_status("ok", f"emitted {len(code)} chars in {elapsed:.0f}ms")
            elif show_time and output_file == "-" and sys.stderr.isatty():
                click.echo(f"# transpile {elapsed:.0f}ms  numba={has_numba()}", err=True)
            return

        compiled = compile_script(source)
        elapsed = (time.perf_counter() - t0) * 1000 if show_time else None
        mode = "object" if compiled.object_mode else "numeric"
        plots = len(compiled.plot_titles)
        msg = f"compiled {label}  mode={mode}  plots={plots}"
        if elapsed is not None:
            msg += f"  {elapsed:.0f}ms"
        if not has_numba() and not compiled.object_mode:
            msg += "  (numba missing?)"
        _echo_status("ok", msg)
        if compiled.plot_titles:
            _echo(
                f"  plots: {', '.join(compiled.plot_titles[:12])}" + ("…" if plots > 12 else "")
            )
    except Exception as e:
        _echo_status("fail", f"{type(e).__name__}: {e}", err=True)
        raise SystemExit(1) from e


@cli.command("prewarm", short_help="Warm Numba builtins and optional script IR caches.")
@click.argument(
    "filenames",
    metavar="PATH...",
    nargs=-1,
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of Pine files.")
@click.option(
    "--force",
    is_flag=True,
    help="Re-run builtin warm-up even if already completed this process.",
)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable summary.")
def prewarm_cmd(filenames: tuple[str, ...], encoding: str, force: bool, as_json: bool) -> None:
    """Pay cold JIT cost before the first run (H2 warm-compile product path).

    Without PATH args, only shared Numba kernels are warmed (and the disk
    compile-cache directory is ensured). With PATH args, each file is also
    :func:`compile_script`'d into memory/disk IR caches.
    """
    from pynescript.compiler.engine import compile_cache_stats
    from pynescript.compiler.engine import prewarm_scripts

    sources: list[str] = []
    for path in filenames:
        text, _label = _read_source(path, encoding)
        sources.append(text)

    t0 = time.perf_counter()
    result = prewarm_scripts(sources or None, force_builtins=force)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    result = {**result, "prewarm_ms": round(elapsed_ms, 2)}

    if as_json:
        click.echo(json.dumps(result, indent=2, default=str))
    else:
        numba = "yes" if result.get("has_numba") else "no"
        _echo_status(
            "ok",
            f"prewarm  numba={numba}  builtins={result.get('builtins_warmed')}  "
            f"scripts_ok={result.get('scripts_ok', 0)}  "
            f"scripts_failed={result.get('scripts_failed', 0)}  "
            f"{elapsed_ms:.0f}ms",
        )
        disk = result.get("disk_cache_dir")
        if disk:
            _echo(f"  disk_cache: {disk}")
        stats = compile_cache_stats()
        _echo(
            f"  cache: source={stats.get('source_entries')}/{stats.get('source_max')}  "
            f"ir={stats.get('ir_entries')}/{stats.get('ir_max')}"
        )
        for err in result.get("errors") or []:
            _echo(f"  fail: {err}", err=True)
    if result.get("scripts_failed"):
        raise SystemExit(1)


@cli.command("run", short_help="Compile and run on synthetic OHLCV bars.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True),
)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option("--bars", type=int, default=50, show_default=True, help="Synthetic bar count.")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print plot series as JSON (last values + lengths).",
)
@click.option("-q", "--quiet", is_flag=True, help="Only print errors / exit code.")
def run_cmd(filename: str, encoding: str, bars: int, as_json: bool, quiet: bool) -> None:
    """Compile PATH and execute on a deterministic synthetic OHLCV series.

    Uses the Numba/object compile pipeline (same as Pro API ``mode=compile``).
    """
    from pynescript.compiler.engine import compile_script

    if bars < 2:
        raise click.ClickException("--bars must be >= 2")

    source, label = _read_source(filename if filename != "-" else "-", encoding)
    ohlcv = _synthetic_ohlcv(bars)

    t0 = time.perf_counter()
    try:
        compiled = compile_script(source)
        result = compiled.run(
            ohlcv["open"],
            ohlcv["high"],
            ohlcv["low"],
            ohlcv["close"],
            ohlcv["volume"],
        )
    except Exception as e:
        _echo_status("fail", f"{type(e).__name__}: {e}", err=True)
        raise SystemExit(1) from e
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Separate plot series from strategy extras
    plots: dict[str, Any] = {}
    extras: dict[str, Any] = {}
    for k, v in (result or {}).items():
        if str(k).startswith("__"):
            extras[k] = v
        else:
            plots[k] = v

    if as_json:
        summary = {
            "file": label,
            "bars": bars,
            "mode": "object" if compiled.object_mode else "numeric",
            "elapsed_ms": round(elapsed_ms, 2),
            "plots": {
                title: {
                    "len": int(getattr(series, "__len__", lambda: 0)()),
                    "last": _jsonable_last(series),
                }
                for title, series in plots.items()
            },
            "extras": {k: _jsonable_last(v) for k, v in extras.items()},
        }
        _echo(json.dumps(summary, indent=2, default=str))
        return

    if quiet:
        return

    mode = "object" if compiled.object_mode else "numeric"
    _echo_status("ok", f"ran {label}  bars={bars}  mode={mode}  {elapsed_ms:.0f}ms")
    if plots:
        con = _console()
        if con is not None:
            from rich.table import Table

            table = Table(show_header=True, header_style="pyne.accent", box=None, padding=(0, 1))
            table.add_column("plot", style="pyne.fg")
            table.add_column("n", justify="right", style="pyne.muted")
            table.add_column("last", justify="right", style="pyne.accent")
            for title, series in plots.items():
                n = len(series) if hasattr(series, "__len__") else "?"
                table.add_row(str(title), str(n), _fmt_num(_jsonable_last(series)))
            con.print(table)
        else:
            for title, series in plots.items():
                _echo(f"  {title}: n={len(series) if hasattr(series, '__len__') else '?'}  "
                      f"last={_jsonable_last(series)}")
    else:
        _echo("  (no plot series)")
    if extras:
        keys = ", ".join(sorted(extras))
        _echo(f"  extras: {keys}")


def _jsonable_last(series: Any) -> Any:
    if series is None:
        return None
    try:
        if hasattr(series, "__len__") and len(series) == 0:
            return None
        if hasattr(series, "__getitem__") and hasattr(series, "__len__"):
            val = series[-1]
        else:
            val = series
        if hasattr(val, "item"):
            val = val.item()
        if isinstance(val, float):
            if val != val:  # NaN
                return None
            return round(val, 6)
        if isinstance(val, (int, str, bool)) or val is None:
            return val
        return str(val)
    except Exception:
        return str(series)[:80]


def _fmt_num(v: Any) -> str:
    if v is None:
        return "na"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


@cli.command("data", short_help="Fetch market data from providers.")
@click.argument("symbol")
@click.option(
    "--provider",
    type=click.Choice(["mock", "yahoo", "alphavantage", "ccxt"], case_sensitive=False),
    default="mock",
    help="Data provider.",
)
@click.option("--period", default="1y", help="Period (1d, 1w, 1mo, 3mo, 6mo, 1y, 2y, 5y).")
@click.option("--interval", default="1d", help="Interval (1m, 5m, 15m, 30m, 60m, 1d, 1w).")
@click.option("--api-key", default="", help="API key for Alpha Vantage or CCXT.")
@click.option("--secret", default="", help="API secret for CCXT.")
@click.option("--exchange", default="binance", help="Exchange for CCXT.")
@click.option(
    "--format",
    "out_fmt",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format.",
)
@click.option(
    "--output-file",
    "-o",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    default="-",
    help="Write output to PATH (default: stdout).",
)
def data(
    symbol: str,
    provider: str,
    period: str,
    interval: str,
    api_key: str,
    secret: str,
    exchange: str,
    out_fmt: str,
    output_file: str,
) -> None:
    """Fetch market data for SYMBOL.

    \b
    Examples:
      pynescript data AAPL
      pynescript data BTC-USD --provider yahoo --period 6mo
      pynescript data BTC/USDT --provider ccxt --exchange binance --format csv
    """
    from pynescript.util.data import DataProviderError
    from pynescript.util.data import get_provider

    try:
        if provider == "alphavantage" and not api_key:
            _echo_status("warn", "Using demo API key (limited access)")
            api_key = "demo"

        kwargs: dict[str, Any] = {}
        if provider == "alphavantage":
            kwargs["api_key"] = api_key or "demo"
        elif provider == "ccxt":
            kwargs["exchange"] = exchange
            if api_key:
                kwargs["api_key"] = api_key
            if secret:
                kwargs["secret"] = secret

        prov = get_provider(provider, **kwargs)
        result = prov.fetch(symbol, period, interval)
        closes = result["close"]
        n = len(closes)
        if n == 0:
            raise click.ClickException("provider returned 0 bars")

        if out_fmt == "json":
            # compact series summary + optional full OHLCV when small
            payload = {
                "symbol": result.get("symbol", symbol),
                "provider": provider,
                "period": period,
                "interval": interval,
                "bars": n,
                "open": list(result["open"]),
                "high": list(result["high"]),
                "low": list(result["low"]),
                "close": list(closes),
                "volume": list(result.get("volume") or []),
            }
            text = json.dumps(payload, indent=2)
            _write_out(text, output_file)
            return

        if out_fmt == "csv":
            lines = ["open,high,low,close,volume"]
            vols = result.get("volume") or [0] * n
            for i in range(n):
                lines.append(
                    f"{result['open'][i]},{result['high'][i]},{result['low'][i]},"
                    f"{closes[i]},{vols[i]}"
                )
            _write_out("\n".join(lines) + "\n", output_file)
            return

        # table summary
        first_c = float(closes[0])
        last_c = float(closes[-1])
        chg = ((last_c / first_c) - 1.0) * 100.0 if first_c else 0.0
        vols = result.get("volume") or []
        avg_vol = (sum(vols) / len(vols)) if vols else 0.0
        hi = max(result["high"]) if result.get("high") else last_c
        lo = min(result["low"]) if result.get("low") else last_c

        rows = [
            ("symbol", str(result.get("symbol", symbol))),
            ("provider", provider),
            ("bars", str(n)),
            ("period / interval", f"{period} / {interval}"),
            ("first close", f"{first_c:.4f}"),
            ("last close", f"{last_c:.4f}"),
            ("change", f"{chg:+.2f}%"),
            ("high / low", f"{float(hi):.4f} / {float(lo):.4f}"),
            ("avg volume", f"{avg_vol:,.0f}"),
        ]

        con = _console() if output_file == "-" else None
        if con is not None:
            from rich.table import Table

            t = Table(title=f"[{_ACCENT}]OHLCV[/]", show_header=False, box=None, padding=(0, 2))
            t.add_column(style="pyne.muted")
            t.add_column(style="pyne.fg")
            for k, v in rows:
                t.add_row(k, v)
            con.print(t)
        else:
            lines = [f"{k}: {v}" for k, v in rows]
            _write_out("\n".join(lines) + "\n", output_file)

    except DataProviderError as e:
        raise click.ClickException(str(e)) from e


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    cli(prog_name="pynescript")  # pragma: no cover
