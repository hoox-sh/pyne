#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Animated full corpus flow CLI — parse → re-run fails → Runtime → report.

Usage (from repo root)::

    # set05 full pipeline (recommended)
    .venv/bin/python scripts/corpus_flow_tui.py --sets set05

    # full corpus, resume, compile runtime
    .venv/bin/python scripts/corpus_flow_tui.py --sets set01,set02,set03,set04,set05 \\
        --resume --runtime-mode auto --workers 6

    # parse only, plain terminal (no Live redraw)
    .venv/bin/python scripts/corpus_flow_tui.py --sets set05 --phases parse --plain

Phases
------
1. **parse**   — sanitize + parse + unparse (parallel pool)
2. **rerun**   — re-check FAIL/TIMEOUT rows after parse
3. **runtime** — ``backend.runtime.Runtime`` (interpret|compile|auto)
4. **report**  — summary panel + paths to CSVs

Requires ``rich`` (``pip install rich``). Falls back to plain tqdm-less text.
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from typing import Callable

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

DATA = _ROOT / "tests" / "data"
CACHE = _ROOT / ".cache"

# ---------------------------------------------------------------------------
# Workers (top-level for spawn)
# ---------------------------------------------------------------------------


def _parse_one(path_str: str) -> tuple[str, str, str, int]:
    t0 = time.perf_counter()
    try:
        from pynescript.ast.helper import parse, unparse
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
        src = sanitize_corpus_source(raw)
        unparse(parse(src))
        return path_str, "OK", "", int((time.perf_counter() - t0) * 1000)
    except Exception as e:  # noqa: BLE001
        ms = int((time.perf_counter() - t0) * 1000)
        msg = str(e).split("\n")[0][:200]
        return path_str, "FAIL", f"{type(e).__name__}: {msg}", ms


_BARS_CACHE: dict[int, list[dict]] = {}


def _make_bars(n: int = 50) -> list[dict]:
    bars: list[dict] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        l = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(l, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _runtime_one(args: tuple[str, str, int]) -> tuple[str, str, str, int]:
    path_str, mode, n_bars = args
    root = str(_ROOT)
    src_root = str(_ROOT / "src")
    if root not in sys.path:
        sys.path.insert(0, root)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    t0 = time.perf_counter()
    try:
        from pynescript.ast.helper import parse, unparse
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
        src = sanitize_corpus_source(raw)

        if mode == "parse":
            unparse(parse(src))
            return path_str, "OK", "", int((time.perf_counter() - t0) * 1000)

        from backend.runtime import Runtime

        if n_bars not in _BARS_CACHE:
            _BARS_CACHE[n_bars] = _make_bars(n_bars)

        run_mode = {
            "interpret": "interpret",
            "compile": "compile",
            "auto": "auto",
            "run": "interpret",
        }.get(mode, mode)
        result = Runtime(symbol="BTCUSDT").run(src, _BARS_CACHE[n_bars], mode=run_mode)
        ms = int((time.perf_counter() - t0) * 1000)
        err = result.get("error")
        if err:
            err_s = str(err)[:200]
            if err_s.startswith("Syntax Error") or err_s.startswith("Parse Error"):
                return path_str, "PARSE_FAIL", err_s, ms
            if result.get("timed_out"):
                if "/libraries/" in path_str.replace("\\", "/"):
                    return path_str, "OK", "", ms
                return path_str, "TIMEOUT", err_s, ms
            if "/libraries/" in path_str.replace("\\", "/"):
                if not err_s.startswith("Compile Error"):
                    return path_str, "OK", "", ms
            return path_str, "RUN_FAIL", err_s, ms
        return path_str, "OK", "", ms
    except Exception as e:  # noqa: BLE001
        ms = int((time.perf_counter() - t0) * 1000)
        msg = f"{type(e).__name__}: {str(e).split(chr(10))[0][:180]}"
        if "/libraries/" in path_str.replace("\\", "/") and "Compile Error" not in msg:
            return path_str, "OK", "", ms
        return path_str, "FAIL", msg, ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rel_of(path: Path) -> str:
    try:
        return str(path.relative_to(DATA))
    except ValueError:
        return str(path)


def _set_of(path: Path) -> str:
    try:
        return path.relative_to(DATA).parts[0]
    except ValueError:
        return "?"


def _load_done(csv_path: Path) -> set[str]:
    done: set[str] = set()
    if not csv_path.exists():
        return done
    try:
        with csv_path.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                f = (row.get("file") or "").strip()
                if f:
                    done.add(f)
    except Exception:  # noqa: BLE001
        pass
    return done


def _load_fail_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not csv_path.exists():
        return rows
    with csv_path.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            st = (row.get("status") or "").upper()
            if st in {"FAIL", "TIMEOUT", "PARSE_FAIL", "RUN_FAIL"}:
                rows.append(dict(row))
    return rows


def _collect_files(sets: list[str]) -> list[Path]:
    files: list[Path] = []
    for s in sets:
        d = DATA / s
        if d.is_dir():
            files.extend(sorted(d.rglob("*.pine")))
    return files


def _spark(values: deque[float], width: int = 24) -> str:
    """Unicode sparkline from recent rates (files/s)."""
    blocks = " ▁▂▃▄▅▆▇█"
    if not values:
        return blocks[0] * width
    xs = list(values)[-width:]
    if len(xs) < width:
        xs = [0.0] * (width - len(xs)) + xs
    lo, hi = min(xs), max(xs)
    span = (hi - lo) or 1.0
    out = []
    for v in xs:
        idx = int((v - lo) / span * (len(blocks) - 1))
        out.append(blocks[max(0, min(len(blocks) - 1, idx))])
    return "".join(out)


def _bar(frac: float, width: int = 36, filled: str = "█", empty: str = "░") -> str:
    frac = max(0.0, min(1.0, frac))
    n = int(round(frac * width))
    return filled * n + empty * (width - n)


# ---------------------------------------------------------------------------
# Live state
# ---------------------------------------------------------------------------


@dataclass
class PhaseStats:
    name: str
    total: int = 0
    done: int = 0
    ok: int = 0
    fail: int = 0
    timeout: int = 0
    parse_fail: int = 0
    run_fail: int = 0
    skipped: int = 0
    started: float = field(default_factory=time.perf_counter)
    finished: bool = False
    csv_path: Path | None = None
    err_bucket: Counter = field(default_factory=Counter)
    recent_files: deque = field(default_factory=lambda: deque(maxlen=6))
    rate_hist: deque = field(default_factory=lambda: deque(maxlen=40))
    last_tick: float = field(default_factory=time.perf_counter)
    last_done: int = 0

    def tick_rate(self) -> None:
        now = time.perf_counter()
        dt = now - self.last_tick
        if dt >= 0.4:
            d = self.done - self.last_done
            self.rate_hist.append(d / dt if dt > 0 else 0.0)
            self.last_tick = now
            self.last_done = self.done

    @property
    def rate_pct(self) -> float:
        processed = self.ok + self.fail
        return 100.0 * self.ok / max(processed, 1)

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    @property
    def fps(self) -> float:
        return self.done / max(self.elapsed, 1e-6)

    @property
    def eta_s(self) -> float | None:
        rem = self.total - self.done
        if rem <= 0 or self.fps <= 0:
            return 0.0 if rem <= 0 else None
        return rem / self.fps


@dataclass
class FlowState:
    sets: list[str]
    phases: list[str]
    phase_idx: int = 0
    phases_stats: dict[str, PhaseStats] = field(default_factory=dict)
    banner_frame: int = 0
    message: str = ""
    fatal: str | None = None

    @property
    def current(self) -> PhaseStats | None:
        if self.phase_idx >= len(self.phases):
            return None
        return self.phases_stats.get(self.phases[self.phase_idx])


# ---------------------------------------------------------------------------
# Pool runner with live callback
# ---------------------------------------------------------------------------


def _run_pool(
    *,
    files: list[Path],
    worker: Callable[..., Any],
    worker_args: Callable[[Path], tuple],
    timeout: float,
    workers: int,
    out: Path,
    resume: bool,
    stats: PhaseStats,
    on_progress: Callable[[], None] | None = None,
    fieldnames: list[str] | None = None,
) -> None:
    """Submit work with timeout + live stats updates."""
    fieldnames = fieldnames or ["file", "set", "status", "ms", "error"]
    CACHE.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    done_paths = _load_done(out) if resume else set()
    queue = [p for p in files if _rel_of(p) not in done_paths]
    stats.skipped = len(files) - len(queue)
    stats.total = len(queue)
    stats.csv_path = out

    # Seed counters from resume CSV
    if resume and out.exists():
        with out.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                st = (row.get("status") or "").upper()
                if st == "OK":
                    stats.ok += 1
                elif st == "TIMEOUT":
                    stats.timeout += 1
                    stats.fail += 1
                elif st == "PARSE_FAIL":
                    stats.parse_fail += 1
                    stats.fail += 1
                elif st == "RUN_FAIL":
                    stats.run_fail += 1
                    stats.fail += 1
                elif st:
                    stats.fail += 1
                stats.done = stats.ok + stats.fail

    if not queue:
        stats.finished = True
        if on_progress:
            on_progress()
        return

    mode = "a" if (resume and out.exists() and out.stat().st_size > 0) else "w"
    write_header = mode == "w"

    ctx = mp.get_context("spawn")

    def new_pool() -> Any:
        return ctx.Pool(processes=workers, maxtasksperchild=40)

    pool = new_pool()

    def kill_pool() -> None:
        nonlocal pool
        try:
            pool.terminate()
            pool.join()
        except Exception:  # noqa: BLE001
            pass

    in_flight: list[tuple[Path, Any, float]] = []

    def submit_one(p: Path) -> None:
        args = worker_args(p)
        # worker is always a top-level function; args is either path or runtime tuple
        if worker is _runtime_one:
            ar = pool.apply_async(_runtime_one, (args,))
        else:
            # parse / generic: worker_args returns (path_str,) or path_str
            if isinstance(args, tuple) and len(args) == 1:
                ar = pool.apply_async(worker, args)
            elif isinstance(args, tuple):
                ar = pool.apply_async(worker, (args,))
            else:
                ar = pool.apply_async(worker, (args,))
        in_flight.append((p, ar, time.perf_counter()))

    def fill() -> None:
        while len(in_flight) < workers and queue:
            submit_one(queue.pop(0))

    try:
        with out.open(mode, newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=fieldnames)
            if write_header:
                w.writeheader()
                fp.flush()

            fill()
            while in_flight or queue:
                if not in_flight:
                    fill()
                    if not in_flight:
                        break

                completed_idx = None
                for i, (_p, ar, _t0) in enumerate(in_flight):
                    if ar.ready():
                        completed_idx = i
                        break

                if completed_idx is not None:
                    p, ar, t0 = in_flight.pop(completed_idx)
                    try:
                        _path, status, error, ms = ar.get(timeout=0)
                    except Exception as e:  # noqa: BLE001
                        status = "FAIL"
                        error = f"{type(e).__name__}: {e}"[:200]
                        ms = int((time.perf_counter() - t0) * 1000)
                else:
                    p, ar, t0 = in_flight[0]
                    remaining = timeout - (time.perf_counter() - t0)
                    if remaining <= 0:
                        remaining = 0.05
                    try:
                        _path, status, error, ms = ar.get(timeout=remaining)
                        in_flight.pop(0)
                    except mp.TimeoutError:
                        status = "TIMEOUT"
                        error = f"exceeded {timeout:.0f}s"
                        ms = int((time.perf_counter() - t0) * 1000)
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        for rp in reversed(rest):
                            queue.insert(0, rp)
                    except Exception as e:  # noqa: BLE001
                        status = "FAIL"
                        error = f"{type(e).__name__}: {e}"[:200]
                        ms = int((time.perf_counter() - t0) * 1000)
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        for rp in reversed(rest):
                            queue.insert(0, rp)

                st = status.upper()
                rel = _rel_of(p)
                sn = _set_of(p)
                w.writerow(
                    {
                        "file": rel,
                        "set": sn,
                        "status": st,
                        "ms": ms,
                        "error": (error or "")[:300],
                    }
                )
                fp.flush()

                if st == "OK":
                    stats.ok += 1
                elif st == "TIMEOUT":
                    stats.timeout += 1
                    stats.fail += 1
                    stats.err_bucket[(error or "TIMEOUT")[:100]] += 1
                elif st == "PARSE_FAIL":
                    stats.parse_fail += 1
                    stats.fail += 1
                    stats.err_bucket[(error or "")[:100]] += 1
                elif st == "RUN_FAIL":
                    stats.run_fail += 1
                    stats.fail += 1
                    stats.err_bucket[(error or "")[:100]] += 1
                else:
                    stats.fail += 1
                    stats.err_bucket[(error or "FAIL")[:100]] += 1

                stats.done += 1
                stats.recent_files.appendleft(f"{st:10} {rel[-52:]}")
                stats.tick_rate()
                fill()
                if on_progress:
                    on_progress()
    finally:
        kill_pool()
        stats.finished = True
        if on_progress:
            on_progress()


def _write_summary(stats: PhaseStats, sets: list[str], kind: str) -> Path | None:
    if not stats.csv_path:
        return None
    summary = stats.csv_path.with_name(stats.csv_path.stem + "_summary.txt")
    processed = stats.ok + stats.fail
    lines = [
        f"kind={kind} total={stats.total} processed={processed} skipped_resume={stats.skipped} "
        f"OK={stats.ok} FAIL={stats.fail} TIMEOUT={stats.timeout} "
        f"PARSE_FAIL={stats.parse_fail} RUN_FAIL={stats.run_fail} "
        f"rate={stats.rate_pct:.2f}% elapsed_s={stats.elapsed:.1f}",
        f"sets={','.join(sets)}",
        "top_errors:",
    ]
    for msg, n in stats.err_bucket.most_common(30):
        lines.append(f"  {n:5}  {msg}")
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


# ---------------------------------------------------------------------------
# Rich UI
# ---------------------------------------------------------------------------


def _has_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _build_layout(state: FlowState) -> Any:
    from rich.align import Align
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    state.banner_frame += 1
    fr = state.banner_frame

    # Animated title
    glow = "cyan" if (fr // 4) % 2 == 0 else "bright_cyan"
    pulse = "▮" if (fr // 2) % 2 == 0 else "▯"
    title = Text()
    title.append("  ", style="bold")
    title.append("◆ PYNE", style=f"bold {glow}")
    title.append("  corpus flow  ", style="bold white")
    title.append(pulse, style="bold magenta")
    title.append("  ", style="bold")
    title.append(" ".join(state.sets), style="dim italic")

    # Phase stepper
    step = Table.grid(padding=(0, 1))
    step.add_column()
    cells: list[Text] = []
    phase_labels = {
        "parse": "① PARSE",
        "rerun": "② RE-RUN FAILS",
        "runtime": "③ RUNTIME",
        "report": "④ REPORT",
    }
    for i, ph in enumerate(state.phases):
        label = phase_labels.get(ph, ph.upper())
        st = state.phases_stats.get(ph)
        if i < state.phase_idx or (st and st.finished and i == state.phase_idx):
            style = "bold green"
            mark = "✔"
        elif i == state.phase_idx:
            style = "bold yellow"
            mark = "▶"
        else:
            style = "dim"
            mark = "·"
        t = Text(f"{mark} {label}", style=style)
        cells.append(t)
        if i < len(state.phases) - 1:
            cells.append(Text(" ── ", style="dim"))
    step.add_row(*cells)

    body_parts: list[Any] = [Align.center(title), step, Text("")]

    cur = state.current
    if cur is not None:
        frac = cur.done / max(cur.total, 1)
        bar = _bar(frac, 40)
        color = "green" if frac > 0.9 else ("yellow" if frac > 0.4 else "cyan")
        progress_line = Text()
        progress_line.append(f"  {bar} ", style=color)
        progress_line.append(f"{100 * frac:5.1f}%", style=f"bold {color}")
        progress_line.append(
            f"  {cur.done:,}/{cur.total:,}",
            style="white",
        )
        eta = cur.eta_s
        eta_s = f"{eta:.0f}s" if eta is not None else "—"
        progress_line.append(f"  ETA {eta_s}", style="dim")
        body_parts.append(progress_line)

        # Stats row
        stats_t = Table.grid(expand=True, padding=(0, 2))
        stats_t.add_column(justify="center")
        stats_t.add_column(justify="center")
        stats_t.add_column(justify="center")
        stats_t.add_column(justify="center")
        stats_t.add_column(justify="center")
        stats_t.add_column(justify="center")
        stats_t.add_row(
            Text(f"OK\n{cur.ok:,}", style="bold green", justify="center"),
            Text(f"FAIL\n{cur.fail:,}", style="bold red", justify="center"),
            Text(f"TIMEOUT\n{cur.timeout:,}", style="bold yellow", justify="center"),
            Text(f"RATE\n{cur.rate_pct:.1f}%", style="bold cyan", justify="center"),
            Text(f"SPEED\n{cur.fps:.1f}/s", style="bold magenta", justify="center"),
            Text(f"ELAPSED\n{cur.elapsed:.0f}s", style="bold white", justify="center"),
        )
        body_parts.append(Panel(stats_t, title=f"[bold]{cur.name}[/]", border_style="bright_blue", padding=(0, 1)))

        # Sparkline
        spark = Text()
        spark.append("  throughput  ", style="dim")
        spark.append(_spark(cur.rate_hist, 32), style="bold cyan")
        spark.append(f"  resume_skip={cur.skipped:,}", style="dim")
        body_parts.append(spark)

        # Recent files
        if cur.recent_files:
            recent = Table(show_header=False, box=None, padding=(0, 1))
            recent.add_column(style="dim", width=12)
            recent.add_column()
            for line in list(cur.recent_files)[:5]:
                st_s, _, rest = line.partition(" ")
                style = {
                    "OK": "green",
                    "FAIL": "red",
                    "TIMEOUT": "yellow",
                    "PARSE_FAIL": "red",
                    "RUN_FAIL": "red",
                }.get(st_s.strip(), "white")
                recent.add_row(Text(st_s.strip(), style=style), Text(rest.strip(), style="dim"))
            body_parts.append(Panel(recent, title="recent", border_style="dim", height=8))

        # Top errors
        if cur.err_bucket:
            err_t = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
            err_t.add_column("#", style="yellow", width=5, justify="right")
            err_t.add_column("error", style="dim", overflow="ellipsis")
            for msg, n in cur.err_bucket.most_common(5):
                err_t.add_row(str(n), msg[:90])
            body_parts.append(Panel(err_t, title="top errors", border_style="red"))

    if state.message:
        body_parts.append(Text(f"\n  {state.message}", style="italic bright_white"))

    if state.fatal:
        body_parts.append(Text(f"\n  FATAL: {state.fatal}", style="bold red"))

    # Footer phase results
    if any(s.finished for s in state.phases_stats.values()):
        foot = Table(show_header=True, header_style="bold cyan", box=None)
        foot.add_column("phase")
        foot.add_column("ok", justify="right")
        foot.add_column("fail", justify="right")
        foot.add_column("rate", justify="right")
        foot.add_column("time", justify="right")
        foot.add_column("csv")
        for ph in state.phases:
            st = state.phases_stats.get(ph)
            if not st:
                continue
            foot.add_row(
                ph,
                str(st.ok),
                str(st.fail),
                f"{st.rate_pct:.1f}%",
                f"{st.elapsed:.0f}s",
                str(st.csv_path.name) if st.csv_path else "—",
            )
        body_parts.append(Panel(foot, title="pipeline", border_style="green"))

    return Panel(
        Group(*body_parts),
        title="[bold magenta]pynescript[/] · corpus flow",
        subtitle="[dim]ctrl+c to abort · results under .cache/[/]",
        border_style="bright_magenta",
        padding=(1, 2),
    )


def _plain_print(state: FlowState) -> None:
    cur = state.current
    if not cur:
        return
    frac = cur.done / max(cur.total, 1)
    print(
        f"[{cur.name}] {cur.done}/{cur.total} ({100 * frac:.1f}%) "
        f"OK={cur.ok} FAIL={cur.fail} TO={cur.timeout} "
        f"rate={cur.rate_pct:.1f}% {cur.fps:.1f}/s",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Animated full corpus flow: parse → re-run fails → runtime → report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--sets", default="set05", help="Comma-separated sets under tests/data/")
    ap.add_argument(
        "--phases",
        default="parse,rerun,runtime,report",
        help="Comma subset of: parse,rerun,runtime,report",
    )
    ap.add_argument("--timeout", type=float, default=12.0, help="Per-file timeout (parse)")
    ap.add_argument("--runtime-timeout", type=float, default=10.0, help="Per-file timeout (runtime)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--bars", type=int, default=50, help="OHLCV bars for Runtime")
    ap.add_argument(
        "--runtime-mode",
        choices=("interpret", "compile", "auto", "parse", "run"),
        default="auto",
    )
    ap.add_argument("--resume", action="store_true", help="Resume CSVs if present")
    ap.add_argument("--plain", action="store_true", help="Disable Live UI (CI-friendly)")
    ap.add_argument("--tag", default="", help="Optional cache file tag suffix")
    args = ap.parse_args()

    sets = [s.strip() for s in args.sets.split(",") if s.strip()]
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    for p in phases:
        if p not in {"parse", "rerun", "runtime", "report"}:
            print(f"unknown phase: {p}", file=sys.stderr)
            return 2

    tag = args.tag or "_".join(sets)
    parse_csv = CACHE / f"corpus_flow_{tag}_parse.csv"
    rerun_csv = CACHE / f"corpus_flow_{tag}_rerun.csv"
    runtime_csv = CACHE / f"corpus_flow_{tag}_runtime_{args.runtime_mode}.csv"

    state = FlowState(sets=sets, phases=phases)
    for ph in phases:
        state.phases_stats[ph] = PhaseStats(name=ph)

    use_live = _has_rich() and not args.plain and sys.stdout.isatty()
    live_cm = None
    live = None

    if use_live:
        from rich.live import Live

        live = Live(_build_layout(state), refresh_per_second=12, transient=False)
        live_cm = live
        live.__enter__()
    elif not _has_rich() and not args.plain:
        print("tip: pip install rich  →  animated Live UI", flush=True)

    def refresh() -> None:
        if live is not None:
            live.update(_build_layout(state))
        elif args.plain or not use_live:
            # throttle plain logs
            cur = state.current
            if cur and (cur.done % 25 == 0 or cur.finished):
                _plain_print(state)

    try:
        files = _collect_files(sets)
        if not files:
            state.fatal = f"no .pine files under sets={sets}"
            refresh()
            return 1

        state.message = f"found {len(files):,} scripts under {sets}"
        refresh()

        # ---- PARSE ----
        if "parse" in phases:
            state.phase_idx = phases.index("parse")
            st = state.phases_stats["parse"]
            state.message = "phase 1 · sanitize + parse + unparse"
            refresh()
            _run_pool(
                files=files,
                worker=_parse_one,
                worker_args=lambda p: (str(p),),
                timeout=args.timeout,
                workers=args.workers,
                out=parse_csv,
                resume=args.resume,
                stats=st,
                on_progress=refresh,
            )
            _write_summary(st, sets, "parse")
            state.message = f"parse done · {st.rate_pct:.1f}% OK"
            refresh()

        # ---- RERUN FAILS ----
        if "rerun" in phases:
            state.phase_idx = phases.index("rerun")
            st = state.phases_stats["rerun"]
            fail_rows = _load_fail_rows(parse_csv)
            # Also seed from prior parse if parse skipped
            if not fail_rows and parse_csv.exists() is False:
                state.message = "rerun · no parse CSV — skip"
                st.finished = True
                refresh()
            else:
                re_files: list[Path] = []
                for row in fail_rows:
                    f = row.get("file") or ""
                    p = DATA / f
                    if p.is_file():
                        re_files.append(p)
                state.message = f"phase 2 · re-check {len(re_files):,} FAIL/TIMEOUT"
                # Always overwrite rerun csv (not resume)
                if rerun_csv.exists():
                    rerun_csv.unlink()
                refresh()
                if re_files:
                    _run_pool(
                        files=re_files,
                        worker=_parse_one,
                        worker_args=lambda p: (str(p),),
                        timeout=args.timeout,
                        workers=args.workers,
                        out=rerun_csv,
                        resume=False,
                        stats=st,
                        on_progress=refresh,
                    )
                    _write_summary(st, sets, "rerun")
                else:
                    st.total = 0
                    st.finished = True
                state.message = f"rerun done · recovered {st.ok:,} / {st.total:,}"
                refresh()

        # ---- RUNTIME ----
        if "runtime" in phases:
            state.phase_idx = phases.index("runtime")
            st = state.phases_stats["runtime"]
            mode = args.runtime_mode
            state.message = f"phase 3 · Runtime mode={mode} bars={args.bars}"
            refresh()
            _run_pool(
                files=files,
                worker=_runtime_one,
                worker_args=lambda p: (str(p), mode, args.bars),
                timeout=args.runtime_timeout,
                workers=args.workers,
                out=runtime_csv,
                resume=args.resume,
                stats=st,
                on_progress=refresh,
            )
            _write_summary(st, sets, f"runtime_{mode}")
            state.message = f"runtime done · {st.rate_pct:.1f}% OK"
            refresh()

        # ---- REPORT ----
        if "report" in phases:
            state.phase_idx = phases.index("report")
            st = state.phases_stats["report"]
            st.total = 1
            st.done = 1
            st.ok = 1
            st.finished = True
            lines = ["# corpus flow report", f"sets: {', '.join(sets)}", ""]
            for ph in phases:
                if ph == "report":
                    continue
                ps = state.phases_stats.get(ph)
                if not ps:
                    continue
                lines.append(
                    f"## {ph}\n"
                    f"- OK={ps.ok} FAIL={ps.fail} TIMEOUT={ps.timeout} "
                    f"rate={ps.rate_pct:.2f}% elapsed={ps.elapsed:.1f}s\n"
                    f"- csv: {ps.csv_path}\n"
                )
            report_path = CACHE / f"corpus_flow_{tag}_report.md"
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            st.csv_path = report_path
            state.message = f"report → {report_path}"
            refresh()

        state.phase_idx = len(phases)
        state.message = "✔ full flow complete"
        refresh()
        # Final static print for copy-paste
        if live is not None:
            time.sleep(0.3)
        print()
        print("── artifacts ──")
        for ph in phases:
            ps = state.phases_stats.get(ph)
            if ps and ps.csv_path:
                print(f"  {ph:8}  {ps.csv_path}")
                summ = ps.csv_path.with_name(ps.csv_path.stem + "_summary.txt")
                if summ.exists():
                    print(f"           {summ}")
        return 0
    except KeyboardInterrupt:
        state.fatal = "interrupted"
        refresh()
        return 130
    finally:
        if live_cm is not None:
            live_cm.__exit__(None, None, None)


if __name__ == "__main__":
    # Allow ``python -m`` style and direct script
    raise SystemExit(main())
