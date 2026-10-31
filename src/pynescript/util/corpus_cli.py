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

"""Click group ``pyne corpus`` — Rich UI over the Runtime corpus engine."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import click

from pynescript.util.corpus_runtime import DEFAULT_SETS
from pynescript.util.corpus_runtime import KNOWN_SETS
from pynescript.util.corpus_runtime import MODES
from pynescript.util.corpus_runtime import CorpusProgress
from pynescript.util.corpus_runtime import CorpusRunResult
from pynescript.util.corpus_runtime import discover_sets
from pynescript.util.corpus_runtime import resolve_cache_dir
from pynescript.util.corpus_runtime import resolve_data_root
from pynescript.util.corpus_runtime import run_corpus
from pynescript.util.rich_theme import ACCENT as _ACCENT
from pynescript.util.rich_theme import BORDER as _BORDER
from pynescript.util.rich_theme import OK as _OK
from pynescript.util.rich_theme import console as _console


def _status_style(status: str) -> str:
    if status == "OK":
        return "pyne.ok"
    if status == "EXPECTED_FAIL":
        return "pyne.warn"
    return "pyne.fail"


def _print_banner(
    console: Any,
    *,
    sets: list[str],
    mode: str,
    workers: int,
    bars: int,
    timeout: float,
    data: Path,
    total: int,
) -> None:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    t = Table(show_header=False, box=None, padding=(0, 1))
    t.add_row(Text("sets", style="pyne.muted"), Text(", ".join(sets), style="pyne.fg"))
    t.add_row(Text("mode", style="pyne.muted"), Text(mode, style="pyne.accent"))
    t.add_row(
        Text("workers / bars / timeout", style="pyne.muted"),
        Text(f"{workers} / {bars} / {timeout:g}s", style="pyne.fg"),
    )
    t.add_row(Text("scripts", style="pyne.muted"), Text(str(total), style="pyne.fg"))
    t.add_row(Text("data", style="pyne.muted"), Text(str(data), style="pyne.muted"))
    console.print(
        Panel(
            t,
            title="[pyne.accent]pyne corpus[/]",
            border_style=_BORDER,
            padding=(0, 1),
        )
    )


def _print_summary_rich(console: Any, result: CorpusRunResult) -> None:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    residual = result.ok + result.fail
    rate = 100 * result.ok / max(residual, 1)

    head = Table(show_header=False, box=None, padding=(0, 1))
    head.add_row(Text("OK", style="pyne.ok"), Text(str(result.ok)))
    head.add_row(Text("EXPECTED_FAIL", style="pyne.warn"), Text(str(result.expected_fail)))
    head.add_row(Text("PARSE_FAIL", style="pyne.fail"), Text(str(result.parse_fail)))
    head.add_row(Text("RUN_FAIL", style="pyne.fail"), Text(str(result.run_fail)))
    head.add_row(Text("TIMEOUT", style="pyne.fail"), Text(str(result.timeout_n)))
    head.add_row(Text("FAIL (residual)", style="pyne.fail"), Text(str(result.fail)))
    head.add_row(
        Text("OK rate (excl. expected)", style="pyne.muted"),
        Text(f"{rate:.2f}%", style="pyne.accent"),
    )
    head.add_row(
        Text("elapsed", style="pyne.muted"),
        Text(f"{result.elapsed_s:.1f}s", style="pyne.fg"),
    )
    console.print(Panel(head, title="[pyne.accent]summary[/]", border_style=_BORDER, padding=(0, 1)))

    by = Table(title="[pyne.accent]by set[/]", show_header=True, header_style="pyne.accent", box=None)
    by.add_column("set")
    by.add_column("OK", justify="right", style="pyne.ok")
    by.add_column("EXP", justify="right", style="pyne.warn")
    by.add_column("PARSE", justify="right", style="pyne.fail")
    by.add_column("RUN", justify="right", style="pyne.fail")
    by.add_column("T/O", justify="right", style="pyne.fail")
    by.add_column("FAIL", justify="right", style="pyne.fail")
    by.add_column("total", justify="right")
    for s in result.sets:
        c: Counter = result.by_set.get(s, Counter())
        by.add_row(
            s,
            str(c["OK"]),
            str(c["EXPECTED_FAIL"]),
            str(c["PARSE_FAIL"]),
            str(c["RUN_FAIL"]),
            str(c["TIMEOUT"]),
            str(c["FAIL"]),
            str(sum(c.values())),
        )
    console.print(by)

    if result.err_bucket:
        errs = Table(
            title="[pyne.accent]top errors[/]",
            show_header=True,
            header_style="pyne.accent",
            box=None,
            padding=(0, 1),
        )
        errs.add_column("n", justify="right", style="pyne.fail")
        errs.add_column("message", style="pyne.muted", overflow="fold")
        for msg, n in result.err_bucket.most_common(15):
            errs.add_row(str(n), msg or "(empty)")
        console.print(errs)

    console.print(f"[pyne.muted]csv[/]  {result.out_csv}")
    console.print(f"[pyne.muted]sum[/]  {result.summary_path}")


def _parse_sets(sets_opt: str | None, sets_args: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    if sets_opt:
        parts.extend(s.strip() for s in sets_opt.split(",") if s.strip())
    parts.extend(s.strip() for s in sets_args if s.strip())
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for s in parts:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out or list(DEFAULT_SETS)


@click.group(
    "corpus",
    short_help="Test the Runtime engine against Pine corpus sets (set01-set06).",
    invoke_without_command=True,
)
@click.pass_context
def corpus_group(ctx: click.Context) -> None:
    """Run the open-source Pine corpus through ``Runtime``.

    \b
    Examples:
      pyne corpus list
      pyne corpus run --sets set01,set02 --mode compile
      pyne corpus run set01 set02 --mode interpret --workers 4
      pyne corpus run --sets set01 --mode parse --resume
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@corpus_group.command("list", short_help="Show available corpus sets and script counts.")
@click.option(
    "--data",
    "data_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Corpus root (default: tests/data or $PYNE_CORPUS_DATA).",
)
@click.option("--plain", is_flag=True, help="Disable Rich.")
@click.option("--rich", "force_rich", is_flag=True, help="Force Rich even when stdout is not a TTY.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON array of {set, count}.")
def list_cmd(
    data_root: Path | None,
    plain: bool,
    force_rich: bool,
    as_json: bool,
) -> None:
    """List corpus sets under the data root."""
    data = resolve_data_root(data_root)
    rows = discover_sets(data)
    if as_json:
        import json

        click.echo(json.dumps([{"set": n, "count": c} for n, c in rows], indent=2))
        return

    console = _console(force=force_rich, plain=plain)
    if console is None:
        click.echo(f"data: {data}")
        if not rows:
            click.echo("(no set0N directories found)")
            return
        for name, count in rows:
            mark = "*" if name in KNOWN_SETS else " "
            click.echo(f"  {mark} {name:8}  {count:5} scripts")
        return

    from rich.table import Table

    console.print(f"[pyne.muted]data[/]  {data}")
    table = Table(show_header=True, header_style="pyne.accent", box=None, padding=(0, 1))
    table.add_column("set")
    table.add_column("scripts", justify="right")
    table.add_column("note", style="pyne.muted")
    if not rows:
        console.print("[pyne.warn]no set0N directories found[/]")
        return
    for name, count in rows:
        note = "default" if name in DEFAULT_SETS else ("slow" if name == "set05" else "")
        table.add_row(name, str(count), note)
    console.print(table)


@corpus_group.command("run", short_help="Run corpus sets through Runtime (interpret/compile/auto/parse).")
@click.argument("sets_args", nargs=-1)
@click.option(
    "--sets",
    "sets_opt",
    default=None,
    help="Comma-separated sets (default: set01,set02,set03). Positional set names also work.",
)
@click.option(
    "--mode",
    type=click.Choice(list(MODES), case_sensitive=False),
    default="compile",
    show_default=True,
    help="Runtime mode (`run` is an alias for interpret).",
)
@click.option("--timeout", type=float, default=20.0, show_default=True, help="Per-script seconds.")
@click.option("--bars", type=int, default=50, show_default=True, help="Synthetic OHLCV bar count.")
@click.option("--workers", type=int, default=6, show_default=True, help="Process pool size.")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="CSV output path (default under .cache/).",
)
@click.option("--resume", is_flag=True, help="Skip files already present in --out.")
@click.option("--progress-every", type=int, default=25, show_default=True)
@click.option(
    "--data",
    "data_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Corpus root (default: tests/data or $PYNE_CORPUS_DATA).",
)
@click.option(
    "--cache",
    "cache_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Cache dir for default --out (default: .cache or $PYNE_CORPUS_CACHE).",
)
@click.option("--plain", is_flag=True, help="Disable Rich (plain progress lines).")
@click.option("--rich", "force_rich", is_flag=True, help="Force Rich even when stdout is not a TTY.")
@click.option(
    "--strict/--no-strict",
    default=True,
    show_default=True,
    help="Exit 1 when residual FAIL/PARSE/RUN/TIMEOUT > 0.",
)
def run_cmd(
    sets_args: tuple[str, ...],
    sets_opt: str | None,
    mode: str,
    timeout: float,
    bars: int,
    workers: int,
    out: Path | None,
    resume: bool,
    progress_every: int,
    data_root: Path | None,
    cache_dir: Path | None,
    plain: bool,
    force_rich: bool,
    strict: bool,
) -> None:
    """Test the engine against corpus set0N scripts.

    \b
    Modes:
      interpret  bar-loop AST evaluator
      compile    Numba/object compiled bar loop
      auto       try compile, fall back to interpret
      parse      parse + unparse only
    """
    import multiprocessing as mp

    mp.freeze_support()

    sets = _parse_sets(sets_opt, sets_args)
    data = resolve_data_root(data_root)
    cache = resolve_cache_dir(cache_dir)
    console = _console(force=force_rich, plain=plain)
    mode_label = "interpret" if mode.lower() == "run" else mode.lower()

    # Pre-count for banner
    from pynescript.util.corpus_runtime import collect_files

    total = len(collect_files(sets, data)) if data.is_dir() else 0

    progress_cm: Any = None
    task_id: Any = None

    if console is not None:
        _print_banner(
            console,
            sets=sets,
            mode=mode_label,
            workers=workers,
            bars=bars,
            timeout=timeout,
            data=data,
            total=total,
        )
        from rich.progress import BarColumn
        from rich.progress import MofNCompleteColumn
        from rich.progress import Progress
        from rich.progress import SpinnerColumn
        from rich.progress import TextColumn
        from rich.progress import TimeElapsedColumn
        from rich.progress import TimeRemainingColumn
        from rich.table import Column

        progress_cm = Progress(
            SpinnerColumn(style=f"bold {_ACCENT}"),
            TextColumn("[pyne.accent]corpus[/]"),
            BarColumn(
                bar_width=28,
                style=_BORDER,
                complete_style=_ACCENT,
                finished_style=_OK,
                pulse_style=_ACCENT,
            ),
            MofNCompleteColumn(),
            TextColumn(
                "[pyne.muted]{task.fields[stats]}",
                table_column=Column(no_wrap=True, overflow="ellipsis", min_width=24, ratio=1),
            ),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )

    def on_progress(p: CorpusProgress) -> None:
        stats = (
            f"OK={p.ok} EXP={p.expected_fail} "
            f"P={p.parse_fail} R={p.run_fail} T={p.timeout_n} "
            f"{p.rate:.0f}% {p.status} {p.rel[-40:]}"
        )
        if progress_cm is not None and task_id is not None:
            progress_cm.update(
                task_id,
                completed=p.done_new,
                total=p.total_new,
                stats=stats,
            )
            if p.status not in ("OK", "EXPECTED_FAIL"):
                style = _status_style(p.status)
                console.print(f"  [{style}]{p.status:14}[/] [pyne.muted]{p.ms}ms[/] {p.rel}")
        else:
            click.echo(
                f"  [{p.done_new}/{p.total_new}] OK={p.ok} EXP={p.expected_fail} "
                f"PARSE={p.parse_fail} RUN={p.run_fail} T/O={p.timeout_n} "
                f"{p.rate:.1f}% {p.ms}ms eta={p.eta_s / 60:.1f}m  "
                f"{p.status:14} {p.rel[:50]}",
                err=False,
            )

    def echo_plain(msg: str) -> None:
        if console is None:
            click.echo(msg)

    try:
        if progress_cm is not None:
            with progress_cm as progress:
                task_id = progress.add_task(
                    "corpus",
                    total=max(total, 1),
                    stats="starting…",
                )
                result = run_corpus(
                    sets=sets,
                    mode=mode_label,
                    timeout=timeout,
                    bars=bars,
                    workers=workers,
                    out=out,
                    resume=resume,
                    progress_every=progress_every,
                    data_root=data,
                    cache_dir=cache,
                    on_progress=on_progress,
                    echo=echo_plain,
                )
                done_count = result.ok + result.fail + result.expected_fail
                progress.update(
                    task_id,
                    completed=min(max(total, 1), max(done_count, 1)),
                    stats=f"done OK={result.ok} FAIL={result.fail}",
                )
        else:
            result = run_corpus(
                sets=sets,
                mode=mode_label,
                timeout=timeout,
                bars=bars,
                workers=workers,
                out=out,
                resume=resume,
                progress_every=progress_every,
                data_root=data,
                cache_dir=cache,
                on_progress=on_progress if console is None else None,
                echo=echo_plain if console is None else None,
            )
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if console is not None:
        _print_summary_rich(console, result)
    else:
        click.echo(result.summary_text.rstrip("\n"))
        click.echo(f"Wrote {result.out_csv}")
        click.echo(f"Wrote {result.summary_path}")

    if strict and result.fail > 0:
        raise SystemExit(1)
