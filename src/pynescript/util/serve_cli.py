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

"""Click commands that start the existing Pro API and datafeed apps.

``pyne serve`` calls :func:`backend.app.main` (the same entry as
``python -m backend.app`` and ``make run``). ``pyne datafeed serve`` calls
:func:`backend.datafeed_app.main`. Neither command builds a second server.
Production gunicorn still loads ``backend.app:app`` and
``backend.datafeed_app:app``.

The backend package is imported lazily. If that package or the needed extra
is missing, the command exits non-zero and prints
``pip install 'hoox-pyne[pro]'`` or ``pip install 'hoox-pyne[datafeed]'``
instead of a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

import importlib

from collections.abc import Callable

import click


_PRO_MODULE = "backend.app"
_PRO_ENTRY = "backend.app:main"
_DATAFEED_MODULE = "backend.datafeed_app"
_DATAFEED_ENTRY = "backend.datafeed_app:main"


def _install_command(extra: str) -> str:
    return f"pip install 'hoox-pyne[{extra}]'"


def _guided(exc: ImportError, extra: str) -> click.ClickException:
    """Install hint for a missing backend package or extra. Never a traceback."""
    missing = exc.name or str(exc)
    install = _install_command(extra)
    msg = f"Cannot start: the backend package or the [{extra}] extra is missing ({missing}).\nInstall with:\n{install}"
    return click.ClickException(msg)


def _load_main(module: str, extra: str) -> Callable[[], None]:
    try:
        imported = importlib.import_module(module)
    except ImportError as exc:
        raise _guided(exc, extra) from exc
    main = getattr(imported, "main", None)
    if not callable(main):
        install = _install_command(extra)
        msg = f"Cannot start: {module}.main is not callable.\nInstall with:\n{install}"
        raise click.ClickException(msg)
    return main


def _run(module: str, entry: str, extra: str, *, dry_run: bool) -> None:
    main = _load_main(module, extra)
    if dry_run:
        click.echo(entry)
        return
    main()


@click.command("serve", short_help="Start the Pro API (backend.app:main).")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the existing entry and exit without listening.",
)
def serve_cmd(dry_run: bool) -> None:
    """Start the existing Pro API.

    Calls ``backend.app:main``, the same entry as ``python -m backend.app``
    and ``make run``. This does not start a second server. Production
    gunicorn still loads ``backend.app:app``.

    ``HOST`` (default 127.0.0.1) and ``PORT`` (default 5002) are read by
    that entry.

    \b
    If the backend package or the [pro] extra is missing:
      pip install 'hoox-pyne[pro]'
    """
    _run(_PRO_MODULE, _PRO_ENTRY, "pro", dry_run=dry_run)


@click.group(
    "datafeed",
    invoke_without_command=True,
    short_help="Start the CCXT datafeed gateway.",
)
@click.pass_context
def datafeed_group(ctx: click.Context) -> None:
    """Run the existing datafeed gateway (``backend.datafeed_app``).

    \b
    Examples:
      pyne datafeed serve
      pyne datafeed serve --dry-run
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@datafeed_group.command("serve", short_help="Start the datafeed gateway (backend.datafeed_app:main).")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the existing entry and exit without listening.",
)
def datafeed_serve_cmd(dry_run: bool) -> None:
    """Start the existing datafeed app.

    Calls ``backend.datafeed_app:main``, the same entry as
    ``python -m backend.datafeed_app``. This does not start a second server.
    Production gunicorn loads ``backend.datafeed_app:app`` (``GUNICORN_APP``).

    ``HOST`` (default all interfaces, same as ``python -m backend.datafeed_app``)
    and ``PORT`` (default 8080) are read by that entry.

    \b
    If the backend package or the [datafeed] extra is missing:
      pip install 'hoox-pyne[datafeed]'
    """
    _run(_DATAFEED_MODULE, _DATAFEED_ENTRY, "datafeed", dry_run=dry_run)
