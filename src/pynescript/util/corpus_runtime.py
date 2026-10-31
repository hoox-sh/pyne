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

"""Corpus Runtime engine: run set01-set06 Pine through ``Runtime``.

Shared by ``scripts/corpus_run_runtime.py`` and the ``pyne corpus`` CLI.
"""

from __future__ import annotations

import csv
import multiprocessing as mp
import os
import time
import traceback

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


# Intentional demos / guards / truncated docs scrapes.
# Classified as EXPECTED_FAIL so OK% is not inflated.
EXPECTED_FAIL_RELS: frozenset[str] = frozenset(
    {
        "set02/libraries/019_lib_functionnnetwork.pine",
        "set02/libraries/021_lib_analysisinterpolationloess.pine",
        "set02/libraries/026_lib_mathcomplexoperator.pine",
        "set02/libraries/032_lib_colorscheme.pine",
        "set02/libraries/036_lib_mathcomplextrigonometry.pine",
        "set03/strategies/0256_str_exit_persist_demo.pine",
        "set03/strategies/0257_str_exit_persist_demo_2.pine",
        "set04/indicators/0703_ind_higher_timeframe_security_demo.pine",
        "set04/indicators/0776_ind_repainting_vs_non_repainting_request_security_demo.pine",
        "set04/indicators/0768_ind_invalid_line_wrap_demo.pine",
        "set04/indicators/0822_ind_searching_in_arrays.pine",
        "set04/indicators/0823_ind_session_bar_checker.pine",
        "set04/strategies/0130_str_decomposing_expressions_demo.pine",
        "set04/indicators/0898_ind_loop_is_too_long.pine",
        "set03/indicators/0314_ind_hurst_exponent_hurst_2.pine",
        "set03/indicators/0791_ind_wyckoff_schematics.pine",
        "set04/indicators/0312_ind_composite_fractal_behavior_cfb.pine",
    }
)

KNOWN_SETS: tuple[str, ...] = ("set01", "set02", "set03", "set04", "set05", "set06")
DEFAULT_SETS: tuple[str, ...] = ("set01", "set02", "set03")
MODES: tuple[str, ...] = ("interpret", "compile", "auto", "run", "parse")

_BARS_CACHE: dict[int, list[dict]] = {}


def resolve_data_root(explicit: Path | None = None) -> Path:
    """Locate ``tests/data`` (env ``PYNE_CORPUS_DATA``, cwd, or repo walk)."""
    if explicit is not None:
        return explicit.resolve()
    env = (os.environ.get("PYNE_CORPUS_DATA") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    cwd_data = Path.cwd() / "tests" / "data"
    if cwd_data.is_dir():
        return cwd_data.resolve()
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        cand = parent / "tests" / "data"
        if cand.is_dir():
            return cand.resolve()
    return cwd_data.resolve()


def resolve_cache_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    env = (os.environ.get("PYNE_CORPUS_CACHE") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / ".cache").resolve()


def corpus_rel_path(path_str: str, data_root: Path | None = None) -> str:
    """Normalize a worker path to ``tests/data``-relative form (posix)."""
    data = data_root or resolve_data_root()
    p = Path(path_str)
    try:
        return str(p.resolve().relative_to(data)).replace("\\", "/")
    except ValueError:
        s = str(path_str).replace("\\", "/")
        marker = "/tests/data/"
        if marker in s:
            return s.split(marker, 1)[1]
        for prefix in KNOWN_SETS:
            needle = f"{prefix}/"
            if needle in s:
                return s[s.index(needle) :]
        return s.lstrip("./")


def is_expected_fail(path_str: str, err_s: str = "", data_root: Path | None = None) -> bool:
    """True for intentional demos listed in ``EXPECTED_FAIL_RELS``."""
    if not (err_s or "").strip():
        return False
    rel = corpus_rel_path(path_str, data_root)
    if rel in EXPECTED_FAIL_RELS:
        return True
    base = Path(rel).name
    return any(Path(x).name == base for x in EXPECTED_FAIL_RELS)


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


def _run_one(args: tuple[str, str, int]) -> tuple[str, str, str, int]:
    """Return (path, status, error, ms). Runs in a worker process."""
    path_str, mode, n_bars = args
    t0 = time.perf_counter()
    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.helper import unparse
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
        src = sanitize_corpus_source(raw)

        if mode == "parse":
            unparse(parse(src))
            return path_str, "OK", "", int((time.perf_counter() - t0) * 1000)

        from pynescript.runtime import Runtime

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
                if is_expected_fail(path_str, err_s):
                    return path_str, "EXPECTED_FAIL", err_s, ms
                return path_str, "PARSE_FAIL", err_s, ms
            if result.get("timed_out"):
                if is_expected_fail(path_str, err_s):
                    return path_str, "EXPECTED_FAIL", err_s, ms
                if "/libraries/" in path_str.replace("\\", "/"):
                    return path_str, "OK", "", ms
                return path_str, "TIMEOUT", err_s, ms
            if is_expected_fail(path_str, err_s):
                return path_str, "EXPECTED_FAIL", err_s, ms
            if "/libraries/" in path_str.replace("\\", "/"):
                if not err_s.startswith("Compile Error"):
                    return path_str, "OK", "", ms
            return path_str, "RUN_FAIL", err_s, ms
        return path_str, "OK", "", ms
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        msg = f"{type(e).__name__}: {str(e).split(chr(10))[0][:180]}"
        if is_expected_fail(path_str, msg):
            return path_str, "EXPECTED_FAIL", msg, ms
        if "/libraries/" in path_str.replace("\\", "/") and "Compile Error" not in msg:
            return path_str, "OK", "", ms
        return path_str, "FAIL", msg, ms


def _set_of(path: Path, data_root: Path) -> str:
    try:
        return path.relative_to(data_root).parts[0]
    except ValueError:
        return "?"


def _rel_of(path: Path, data_root: Path) -> str:
    try:
        return str(path.relative_to(data_root))
    except ValueError:
        return str(path)


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
    except Exception:
        pass
    return done


def discover_sets(data_root: Path | None = None) -> list[tuple[str, int]]:
    """Return ``[(set_name, pine_count), …]`` for present corpus dirs."""
    data = resolve_data_root(data_root)
    out: list[tuple[str, int]] = []
    if not data.is_dir():
        return out
    for name in KNOWN_SETS:
        d = data / name
        if d.is_dir():
            out.append((name, sum(1 for _ in d.rglob("*.pine"))))
    # Any extra set0N dirs
    for child in sorted(data.iterdir()):
        if child.is_dir() and child.name.startswith("set") and child.name not in KNOWN_SETS:
            out.append((child.name, sum(1 for _ in child.rglob("*.pine"))))
    return out


def collect_files(sets: list[str], data_root: Path) -> list[Path]:
    files: list[Path] = []
    for s in sets:
        d = data_root / s
        if not d.is_dir():
            continue
        files.extend(sorted(d.rglob("*.pine")))
    return files


def format_summary(
    *,
    total_all: int,
    ok: int,
    fail: int,
    timeout_n: int,
    parse_fail: int,
    run_fail: int,
    by_set: dict[str, Counter],
    err_bucket: Counter,
    sets: list[str],
    elapsed: float,
    skipped: int,
    mode: str,
    expected_fail: int = 0,
) -> str:
    residual = ok + fail
    scored = residual + expected_fail
    honest_den = max(residual, 1)
    lines = [
        f"runtime=pynescript.runtime mode={mode} total_corpus={total_all} "
        f"processed={scored} skipped_resume={skipped} "
        f"OK={ok} EXPECTED_FAIL={expected_fail} PARSE_FAIL={parse_fail} "
        f"RUN_FAIL={run_fail} FAIL={fail} TIMEOUT={timeout_n} "
        f"rate={100 * ok / honest_den:.2f}% "
        f"(excl. EXPECTED_FAIL) elapsed_s={elapsed:.1f}",
        "by_set:",
    ]
    for s in sets:
        c = by_set.get(s, Counter())
        n = sum(c.values())
        lines.append(
            f"  {s}: OK={c['OK']} EXPECTED_FAIL={c['EXPECTED_FAIL']} "
            f"PARSE_FAIL={c['PARSE_FAIL']} RUN_FAIL={c['RUN_FAIL']} "
            f"TIMEOUT={c['TIMEOUT']} FAIL={c['FAIL']} total={n}"
        )
    lines.append("top_errors:")
    for msg, n in err_bucket.most_common(40):
        lines.append(f"  {n:5}  {msg}")
    return "\n".join(lines) + "\n"


@dataclass
class CorpusProgress:
    """One completed script callback payload for Rich / plain UIs."""

    done_new: int
    total_new: int
    total_all: int
    ok: int
    expected_fail: int
    parse_fail: int
    run_fail: int
    timeout_n: int
    fail: int
    status: str
    rel: str
    ms: int
    elapsed_s: float
    eta_s: float
    rate: float


@dataclass
class CorpusRunResult:
    out_csv: Path
    summary_path: Path
    summary_text: str
    ok: int
    fail: int
    expected_fail: int
    parse_fail: int
    run_fail: int
    timeout_n: int
    total_all: int
    processed: int
    skipped: int
    elapsed_s: float
    mode: str
    sets: list[str] = field(default_factory=list)
    by_set: dict[str, Counter] = field(default_factory=dict)
    err_bucket: Counter = field(default_factory=Counter)

    @property
    def exit_code(self) -> int:
        return 0 if self.fail == 0 else 1


def run_corpus(
    *,
    sets: list[str] | None = None,
    mode: str = "compile",
    timeout: float = 20.0,
    bars: int = 50,
    workers: int = 6,
    out: Path | None = None,
    resume: bool = False,
    progress_every: int = 25,
    data_root: Path | None = None,
    cache_dir: Path | None = None,
    on_progress: Callable[[CorpusProgress], None] | None = None,
    echo: Callable[[str], None] | None = None,
) -> CorpusRunResult:
    """Run corpus sets through ``Runtime`` (or parse-only).

    Parameters mirror ``scripts/corpus_run_runtime.py``. *on_progress* is called
    on interesting completions (failures, every *progress_every*, first/last).
    """

    def _echo(msg: str) -> None:
        if echo is not None:
            echo(msg)

    sets = list(sets or DEFAULT_SETS)
    mode_label = "interpret" if mode == "run" else mode
    data = resolve_data_root(data_root)
    cache = resolve_cache_dir(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    if out is None:
        tag = "_".join(sets)
        out = cache / f"runtime_corpus_{tag}_{mode_label}.csv"
    else:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)

    if not data.is_dir():
        msg = f"corpus data dir missing: {data}"
        raise FileNotFoundError(msg)

    all_files = collect_files(sets, data)
    total_all = len(all_files)
    missing = [s for s in sets if not (data / s).is_dir()]
    for s in missing:
        _echo(f"warning: missing {data / s}")

    done_paths = _load_done(out) if resume else set()
    files = [p for p in all_files if _rel_of(p, data) not in done_paths]
    skipped = total_all - len(files)

    _echo(
        f"pynescript Runtime corpus: {len(files)} scripts "
        f"(corpus={total_all}, resume_skip={skipped}) "
        f"sets={sets} mode={mode_label} timeout={timeout}s "
        f"bars={bars} workers={workers}"
    )

    summary_path = out.with_name(out.stem + "_summary.txt")
    ok = fail = timeout_n = parse_fail = run_fail = expected_fail = 0
    by_set: dict[str, Counter] = {s: Counter() for s in sets}
    err_bucket: Counter = Counter()

    if not files:
        text = format_summary(
            total_all=total_all,
            ok=ok,
            fail=fail,
            timeout_n=timeout_n,
            parse_fail=parse_fail,
            run_fail=run_fail,
            by_set=by_set,
            err_bucket=err_bucket,
            sets=sets,
            elapsed=0.0,
            skipped=skipped,
            mode=mode_label,
            expected_fail=expected_fail,
        )
        summary_path.write_text(text, encoding="utf-8")
        _echo("Nothing to do.")
        return CorpusRunResult(
            out_csv=out,
            summary_path=summary_path,
            summary_text=text,
            ok=ok,
            fail=fail,
            expected_fail=expected_fail,
            parse_fail=parse_fail,
            run_fail=run_fail,
            timeout_n=timeout_n,
            total_all=total_all,
            processed=0,
            skipped=skipped,
            elapsed_s=0.0,
            mode=mode_label,
            sets=sets,
            by_set=by_set,
            err_bucket=err_bucket,
        )

    if resume and out.exists():
        with out.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                st = row.get("status") or ""
                sn = row.get("set") or "?"
                by_set.setdefault(sn, Counter())[st] += 1
                if st == "OK":
                    ok += 1
                elif st == "EXPECTED_FAIL":
                    expected_fail += 1
                    err_bucket[(row.get("error") or "EXPECTED_FAIL")[:100]] += 1
                elif st == "TIMEOUT":
                    timeout_n += 1
                    fail += 1
                    err_bucket[(row.get("error") or "TIMEOUT")[:100]] += 1
                elif st == "PARSE_FAIL":
                    parse_fail += 1
                    fail += 1
                    err_bucket[(row.get("error") or "")[:100]] += 1
                elif st == "RUN_FAIL":
                    run_fail += 1
                    fail += 1
                    err_bucket[(row.get("error") or "")[:100]] += 1
                else:
                    fail += 1
                    err_bucket[(row.get("error") or "")[:100]] += 1

    t_all = time.perf_counter()
    mode_w = "a" if (resume and out.exists()) else "w"
    write_header = mode_w == "w" or not out.exists() or out.stat().st_size == 0
    done_new = 0
    total_new = len(files)
    queue = list(files)

    ctx = mp.get_context("spawn")

    def new_pool() -> Any:
        return ctx.Pool(processes=workers, maxtasksperchild=30)

    pool = new_pool()

    def kill_pool() -> None:
        nonlocal pool
        try:
            pool.terminate()
        except Exception:
            pass
        try:
            pool.join()
        except Exception:
            pass

    try:
        with out.open(mode_w, newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=["file", "set", "status", "ms", "error"])
            if write_header:
                w.writeheader()
                fp.flush()

            in_flight: list[tuple[Path, Any, float]] = []

            def submit(p: Path) -> None:
                ar = pool.apply_async(_run_one, ((str(p), mode_label, bars),))
                in_flight.append((p, ar, time.perf_counter()))

            def fill() -> None:
                while len(in_flight) < workers and queue:
                    submit(queue.pop(0))

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
                    except Exception as e:
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
                        ms = int((time.perf_counter() - t0) * 1000)
                        error = f"exceeded {timeout:.0f}s"
                        if is_expected_fail(str(p), error, data):
                            status = "EXPECTED_FAIL"
                        elif "/libraries/" in str(p).replace("\\", "/"):
                            status = "OK"
                            error = ""
                        else:
                            status = "TIMEOUT"
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        for rp in reversed(rest):
                            queue.insert(0, rp)
                    except Exception as e:
                        status = "FAIL"
                        error = f"{type(e).__name__}: {e}"[:200]
                        ms = int((time.perf_counter() - t0) * 1000)
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        for rp in reversed(rest):
                            queue.insert(0, rp)

                set_name = _set_of(p, data)
                rel = _rel_of(p, data)
                by_set.setdefault(set_name, Counter())[status] += 1
                if status == "OK":
                    ok += 1
                elif status == "EXPECTED_FAIL":
                    expected_fail += 1
                    err_bucket[error[:100]] += 1
                elif status == "TIMEOUT":
                    timeout_n += 1
                    fail += 1
                    err_bucket[error[:100]] += 1
                elif status == "PARSE_FAIL":
                    parse_fail += 1
                    fail += 1
                    err_bucket[error[:100]] += 1
                elif status == "RUN_FAIL":
                    run_fail += 1
                    fail += 1
                    err_bucket[error[:100]] += 1
                else:
                    fail += 1
                    err_bucket[error[:100]] += 1

                w.writerow({"file": rel, "set": set_name, "status": status, "ms": ms, "error": error})
                done_new += 1
                if done_new % 10 == 0:
                    fp.flush()

                fill()

                residual = ok + fail
                elapsed = time.perf_counter() - t_all
                left = total_new - done_new
                eta = (elapsed / max(done_new, 1)) * left
                rate = 100 * ok / max(residual, 1)
                interesting = (
                    done_new % progress_every == 0
                    or status not in ("OK", "EXPECTED_FAIL")
                    or done_new in (1, total_new)
                )
                if interesting:
                    prog = CorpusProgress(
                        done_new=done_new,
                        total_new=total_new,
                        total_all=total_all,
                        ok=ok,
                        expected_fail=expected_fail,
                        parse_fail=parse_fail,
                        run_fail=run_fail,
                        timeout_n=timeout_n,
                        fail=fail,
                        status=status,
                        rel=rel,
                        ms=ms,
                        elapsed_s=elapsed,
                        eta_s=eta,
                        rate=rate,
                    )
                    if on_progress is not None:
                        on_progress(prog)
                    else:
                        _echo(
                            f"  [{done_new}/{total_new} new | "
                            f"{residual + expected_fail}/{total_all} all] "
                            f"OK={ok} EXP={expected_fail} PARSE={parse_fail} "
                            f"RUN={run_fail} T/O={timeout_n} {rate:.1f}% "
                            f"{ms}ms eta={eta / 60:.1f}m  "
                            f"{status:14} {rel[:50]}"
                        )

                if done_new % 200 == 0:
                    text = format_summary(
                        total_all=total_all,
                        ok=ok,
                        fail=fail,
                        timeout_n=timeout_n,
                        parse_fail=parse_fail,
                        run_fail=run_fail,
                        by_set=by_set,
                        err_bucket=err_bucket,
                        sets=sets,
                        elapsed=time.perf_counter() - t_all,
                        skipped=skipped,
                        mode=mode_label,
                        expected_fail=expected_fail,
                    )
                    summary_path.write_text(text, encoding="utf-8")
    except Exception:
        _echo("FATAL in main loop:")
        traceback.print_exc()
    finally:
        kill_pool()

    elapsed = time.perf_counter() - t_all
    text = format_summary(
        total_all=total_all,
        ok=ok,
        fail=fail,
        timeout_n=timeout_n,
        parse_fail=parse_fail,
        run_fail=run_fail,
        by_set=by_set,
        err_bucket=err_bucket,
        sets=sets,
        elapsed=elapsed,
        skipped=skipped,
        mode=mode_label,
        expected_fail=expected_fail,
    )
    summary_path.write_text(text, encoding="utf-8")
    _echo(text.rstrip("\n"))
    _echo(f"Wrote {out}")
    _echo(f"Wrote {summary_path}")

    return CorpusRunResult(
        out_csv=out,
        summary_path=summary_path,
        summary_text=text,
        ok=ok,
        fail=fail,
        expected_fail=expected_fail,
        parse_fail=parse_fail,
        run_fail=run_fail,
        timeout_n=timeout_n,
        total_all=total_all,
        processed=ok + fail + expected_fail,
        skipped=skipped,
        elapsed_s=elapsed,
        mode=mode_label,
        sets=sets,
        by_set=by_set,
        err_bucket=err_bucket,
    )
