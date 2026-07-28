#!/usr/bin/env python3
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

"""Parse (+ unparse) set01–set05 with per-file timeout, resume, dense progress.

Design goals:
- Survive TIMEOUT / worker death without aborting the corpus
- Resume from an existing CSV (skip already-processed files)
- Stream results so a crash never loses prior rows

Usage:
  python scripts/corpus_parse_sets.py
  python scripts/corpus_parse_sets.py --timeout 12 --workers 4 --resume
  python scripts/corpus_parse_sets.py --sets set03,set04,set05 --resume

Writes:
  .cache/corpus_parse_set01_set05.csv
  .cache/corpus_parse_set01_set05_summary.txt
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
CACHE = ROOT / ".cache"


def _parse_one(path_str: str) -> tuple[str, str, str, int]:
    """Return (path, status, error, ms). Runs in worker process."""
    t0 = time.perf_counter()
    try:
        from pynescript.ast.helper import parse, unparse
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
        src = sanitize_corpus_source(raw)
        tree = parse(src)
        unparse(tree)
        ms = int((time.perf_counter() - t0) * 1000)
        return path_str, "OK", "", ms
    except Exception as e:  # noqa: BLE001 — corpus sweep
        ms = int((time.perf_counter() - t0) * 1000)
        msg = str(e).split("\n")[0][:200]
        return path_str, "FAIL", f"{type(e).__name__}: {msg}", ms


def _set_of(path: Path) -> str:
    try:
        return path.relative_to(DATA).parts[0]
    except ValueError:
        return "?"


def _rel_of(path: Path) -> str:
    try:
        return str(path.relative_to(DATA))
    except ValueError:
        return str(path)


def _load_done(csv_path: Path) -> set[str]:
    """Return set of relative file paths already present in CSV."""
    done: set[str] = set()
    if not csv_path.exists():
        return done
    try:
        with csv_path.open(encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                f = (row.get("file") or "").strip()
                if f:
                    done.add(f)
    except Exception as e:  # noqa: BLE001
        print(f"warning: could not read resume CSV: {e}", flush=True)
    return done


def _write_summary(
    summary_path: Path,
    total_all: int,
    ok: int,
    fail: int,
    timeout_n: int,
    by_set: dict[str, Counter],
    err_bucket: Counter,
    sets: list[str],
    elapsed: float,
    skipped: int,
) -> str:
    processed = ok + fail  # fail includes timeouts
    lines = [
        f"total_corpus={total_all} processed={processed} skipped_resume={skipped} "
        f"OK={ok} FAIL={fail} TIMEOUT={timeout_n} "
        f"rate={100 * ok / max(processed, 1):.2f}% elapsed_s={elapsed:.1f}",
        "by_set:",
    ]
    for s in sets:
        c = by_set.get(s, Counter())
        n = c["OK"] + c["FAIL"] + c["TIMEOUT"]
        lines.append(
            f"  {s}: OK={c['OK']} FAIL={c['FAIL']} TIMEOUT={c['TIMEOUT']} total={n}"
        )
    lines.append("top_errors:")
    for msg, n in err_bucket.most_common(40):
        lines.append(f"  {n:5}  {msg}")
    text = "\n".join(lines) + "\n"
    summary_path.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sets",
        default="set01,set02,set03,set04,set05",
        help="Comma-separated set names under tests/data/",
    )
    ap.add_argument("--timeout", type=float, default=12.0, help="Per-file timeout seconds")
    ap.add_argument("--workers", type=int, default=4, help="Process pool size")
    ap.add_argument("--progress-every", type=int, default=50, help="Log every N completions")
    ap.add_argument(
        "--out",
        type=Path,
        default=CACHE / "corpus_parse_set01_set05.csv",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Skip files already listed in --out CSV and append new rows",
    )
    args = ap.parse_args()
    sets = [s.strip() for s in args.sets.split(",") if s.strip()]

    all_files: list[Path] = []
    for s in sets:
        d = DATA / s
        if not d.is_dir():
            print(f"warning: missing set dir {d}", flush=True)
            continue
        all_files.extend(sorted(d.rglob("*.pine")))
    total_all = len(all_files)

    done_paths = _load_done(args.out) if args.resume else set()
    files = [p for p in all_files if _rel_of(p) not in done_paths]
    skipped = total_all - len(files)

    print(
        f"Parsing {len(files)} scripts "
        f"(corpus={total_all}, resume_skip={skipped}) "
        f"across {sets} (timeout={args.timeout}s/file, workers={args.workers})...",
        flush=True,
    )
    if not files:
        print("Nothing to do.", flush=True)
        return

    CACHE.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Seed counters from existing CSV when resuming
    ok = fail = timeout_n = 0
    by_set: dict[str, Counter] = {s: Counter() for s in sets}
    err_bucket: Counter = Counter()
    if args.resume and args.out.exists():
        with args.out.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                st = row.get("status") or ""
                sn = row.get("set") or "?"
                by_set.setdefault(sn, Counter())[st] += 1
                if st == "OK":
                    ok += 1
                elif st == "TIMEOUT":
                    timeout_n += 1
                    fail += 1
                    err = (row.get("error") or "TIMEOUT")[:100]
                    err_bucket[err] += 1
                else:
                    fail += 1
                    err = (row.get("error") or "FAIL")[:100]
                    err_bucket[err] += 1

    t_all = time.perf_counter()
    mode = "a" if (args.resume and args.out.exists()) else "w"
    write_header = mode == "w" or not args.out.exists() or args.out.stat().st_size == 0

    ctx = mp.get_context("spawn")
    summary_path = args.out.with_name(args.out.stem + "_summary.txt")
    done_new = 0
    total_new = len(files)

    # Work queue as a simple list index for reliable resume after timeouts
    queue = list(files)

    def new_pool() -> mp.pool.Pool:
        return ctx.Pool(processes=args.workers, maxtasksperchild=50)

    pool = new_pool()

    def kill_pool() -> None:
        nonlocal pool
        try:
            pool.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            pool.join()
        except Exception:  # noqa: BLE001
            pass

    try:
        with args.out.open(mode, newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=["file", "set", "status", "ms", "error"])
            if write_header:
                w.writeheader()
                fp.flush()

            # In-flight: list of (Path, AsyncResult, start_time)
            in_flight: list[tuple[Path, mp.pool.AsyncResult, float]] = []

            def submit(p: Path) -> None:
                ar = pool.apply_async(_parse_one, (str(p),))
                in_flight.append((p, ar, time.perf_counter()))

            def fill() -> None:
                while len(in_flight) < args.workers and queue:
                    submit(queue.pop(0))

            fill()

            while in_flight or queue:
                if not in_flight:
                    fill()
                    if not in_flight:
                        break

                # Prefer completed jobs; otherwise wait on the oldest with remaining budget
                completed_idx = None
                for i, (p, ar, t0) in enumerate(in_flight):
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
                    # Wait on oldest job for remaining timeout budget
                    p, ar, t0 = in_flight[0]
                    remaining = args.timeout - (time.perf_counter() - t0)
                    if remaining <= 0:
                        remaining = 0.05
                    try:
                        _path, status, error, ms = ar.get(timeout=remaining)
                        in_flight.pop(0)
                    except mp.TimeoutError:
                        status = "TIMEOUT"
                        error = f"exceeded {args.timeout:.0f}s"
                        ms = int((time.perf_counter() - t0) * 1000)
                        # Drop timed-out job; re-queue other in-flight paths and rebuild pool
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        # put rest back at front of queue (preserve order)
                        for rp in reversed(rest):
                            queue.insert(0, rp)
                    except Exception as e:  # noqa: BLE001
                        # Worker death / broken pipe — rebuild and re-queue others
                        status = "FAIL"
                        error = f"{type(e).__name__}: {e}"[:200]
                        ms = int((time.perf_counter() - t0) * 1000)
                        rest = [x[0] for x in in_flight[1:]]
                        in_flight.clear()
                        kill_pool()
                        pool = new_pool()
                        for rp in reversed(rest):
                            queue.insert(0, rp)

                set_name = _set_of(p)
                rel = _rel_of(p)
                by_set.setdefault(set_name, Counter())[status] += 1
                if status == "OK":
                    ok += 1
                elif status == "TIMEOUT":
                    timeout_n += 1
                    fail += 1
                    err_bucket[error[:100]] += 1
                else:
                    fail += 1
                    err_bucket[error[:100]] += 1

                w.writerow(
                    {"file": rel, "set": set_name, "status": status, "ms": ms, "error": error}
                )
                done_new += 1
                if done_new % 10 == 0:
                    fp.flush()

                fill()

                processed = ok + fail
                if (
                    done_new % args.progress_every == 0
                    or status != "OK"
                    or done_new == 1
                    or done_new == total_new
                ):
                    rate = ok / max(processed, 1) * 100
                    elapsed = time.perf_counter() - t_all
                    left = total_new - done_new
                    eta = (elapsed / max(done_new, 1)) * left
                    print(
                        f"  [{done_new}/{total_new} new | {processed}/{total_all} all] "
                        f"OK={ok} FAIL={fail} (T/O={timeout_n}) "
                        f"{rate:.1f}% {ms}ms eta={eta / 60:.1f}m  {status:7} {rel[:64]}",
                        flush=True,
                    )

                # periodic summary so progress is visible mid-run
                if done_new % 200 == 0:
                    _write_summary(
                        summary_path,
                        total_all,
                        ok,
                        fail,
                        timeout_n,
                        by_set,
                        err_bucket,
                        sets,
                        time.perf_counter() - t_all,
                        skipped,
                    )

    except Exception:
        print("FATAL in main loop (will still write summary):", flush=True)
        traceback.print_exc()
    finally:
        kill_pool()

    elapsed = time.perf_counter() - t_all
    text = _write_summary(
        summary_path,
        total_all,
        ok,
        fail,
        timeout_n,
        by_set,
        err_bucket,
        sets,
        elapsed,
        skipped,
    )
    print(text, flush=True)
    print(f"Wrote {args.out}", flush=True)
    print(f"Wrote {summary_path}", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
