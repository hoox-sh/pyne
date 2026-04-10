# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import click


@click.group()
@click.version_option()
def cli():
    pass


@cli.command(short_help="Parse pinescript file to AST tree.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.option(
    "--encoding",
    default="utf-8",
    help="Text encoding of the file.",
)
@click.option(
    "--indent",
    type=int,
    default=2,
    help="Indentation with of an AST dump.",
)
@click.option(
    "--output-file",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    help="Path to output dump file, defaults to standard output.",
    default="-",
)
def parse_and_dump(filename, encoding, indent, output_file):
    from pynescript.ast import dump
    from pynescript.ast import parse

    with click.open_file(filename, "r", encoding=encoding) as f:
        script_node = parse(f.read(), filename)

    script_node_dump = dump(script_node, indent=indent)

    with click.open_file(output_file, "w", encoding=encoding) as f:
        f.write(script_node_dump)


@cli.command(short_help="Parse pinescript file and unparse back to pinescript.")
@click.argument(
    "filename",
    metavar="PATH",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.option(
    "--encoding",
    default="utf-8",
    help="Text encoding of the file.",
)
@click.option(
    "--output-file",
    metavar="PATH",
    type=click.Path(writable=True, allow_dash=True),
    help="Path to output dump file, defaults to standard output.",
    default="-",
)
def parse_and_unparse(filename, encoding, output_file):
    from pynescript.ast import parse
    from pynescript.ast import unparse

    with click.open_file(filename, "r", encoding=encoding) as f:
        script_node = parse(f.read(), filename)

    unparsed_script = unparse(script_node)

    with click.open_file(output_file, "w", encoding=encoding) as f:
        f.write(unparsed_script)


@cli.command(short_help="Download builtin scripts.")
@click.option(
    "--script-dir",
    type=click.Path(exists=False, file_okay=False, writable=True),
    help="Diretory where scripts to be saved (like tests/data/builtin_scripts).",
    required=True,
)
def download_builtin_scripts(script_dir):
    from pynescript.util.pine_facade import download_builtin_scripts as download

    download(script_dir)


@cli.command(short_help="Lint Pine Script file for issues.")
@click.argument(
    "filename",
    metavar="PATH",
    type=str,
    required=False,
)
@click.option(
    "--encoding",
    default="utf-8",
    help="Text encoding of the file.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt to fix issues where possible.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["errors", "warnings", "all"], case_sensitive=False),
    default="errors",
    help="Exit with error code on this severity level.",
)
def lint(filename, encoding, fix, fail_on):
    """Lint Pine Script files for issues.

    If no FILE is provided, reads from stdin.
    Use '-' to read from stdin explicitly.
    """
    from pynescript.ast.linter import lint_file, lint_script

    if filename == "-" or filename is None:
        import sys

        source = sys.stdin.read()
        warnings = lint_script(source, "<stdin>")
    else:
        with open(filename, "r", encoding=encoding) as f:
            source = f.read()
        warnings = lint_script(source, filename)

    if not warnings:
        click.echo("No issues found.")
        return

    has_errors = any(w.severity == "error" for w in warnings)
    has_warnings = any(w.severity == "warning" for w in warnings)

    for w in warnings:
        severity_emoji = "❌" if w.severity == "error" else "⚠️"
        click.echo(f"{severity_emoji} {w}")

    click.echo(f"\nSummary: {len(warnings)} issue(s) found")

    if fail_on == "errors" and has_errors:
        raise click.ClickException("Lint failed with errors.")
    elif fail_on == "warnings" and (has_errors or has_warnings):
        raise click.ClickException("Lint failed with warnings or errors.")
    elif fail_on == "all" and warnings:
        raise click.ClickException("Lint found issues.")


if __name__ == "__main__":
    cli(prog_name="pynescript")  # pragma: no cover
