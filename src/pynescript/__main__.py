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
    from pynescript.ast.linter import lint_script

    if filename == "-" or filename is None:
        import sys

        source = sys.stdin.read()
        warnings = lint_script(source, "<stdin>")
    else:
        with open(filename, encoding=encoding) as f:
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


@cli.command(short_help="Fetch market data from providers.")
@click.argument("symbol")
@click.option(
    "--provider",
    type=click.Choice(["mock", "yahoo", "alphavantage", "ccxt"], case_sensitive=False),
    default="mock",
    help="Data provider to use.",
)
@click.option(
    "--period",
    default="1y",
    help="Time period (1d, 1w, 1mo, 3mo, 6mo, 1y, 2y, 5y).",
)
@click.option(
    "--interval",
    default="1d",
    help="Data interval (1m, 5m, 15m, 30m, 60m, 1d, 1w).",
)
@click.option(
    "--api-key",
    default="",
    help="API key for Alpha Vantage or CCXT.",
)
@click.option(
    "--secret",
    default="",
    help="API secret for CCXT.",
)
@click.option(
    "--exchange",
    default="binance",
    help="Exchange for CCXT (binance, coinbase, kraken, etc).",
)
def data(symbol, provider, period, interval, api_key, secret, exchange):
    """Fetch market data for SYMBOL.

    Examples:
        pynescript data AAPL
        pynescript data BTC-USD --provider=yahoo --period=6mo
        pynescript data EUR/USD --provider=alphavantage --api-key=YOUR_KEY
        pynescript data BTC/USDT --provider=ccxt --exchange=binance
    """
    from pynescript.util.data import DataProviderError
    from pynescript.util.data import get_provider

    try:
        if provider == "alphavantage" and not api_key:
            click.echo("Warning: Using demo API key (limited access)")
            api_key = "demo"

        kwargs = {}
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

        click.echo(f"Symbol: {result.get('symbol', symbol)}")
        click.echo(f"Bars: {len(result['close'])}")
        click.echo(f"Date range: {len(result['close'])} bars")
        click.echo(f"First close: {result['close'][0]:.2f}")
        click.echo(f"Last close: {result['close'][-1]:.2f}")
        click.echo(f"Volume (avg): {sum(result['volume']) // len(result['volume']):,}")

    except DataProviderError as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli(prog_name="pynescript")  # pragma: no cover
