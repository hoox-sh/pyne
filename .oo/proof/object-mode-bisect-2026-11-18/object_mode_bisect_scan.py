#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bisect forcing sites for object mode across the four scanned populations.

Reads the object-outcome records from the 2026-11-18 numeric/object error scan
(.oo/proof/numeric-object-error-scan-2026-11-18/details-*.jsonl), dedupes the
file list, and re-transpiles each file with ``PYNE_OBJECT_MODE_TRACE`` set so
the instrumented compiler (see compiler.py ``_om_trace``) appends one line per
file to the trace JSONL.

Per-file results are written to ``results.jsonl`` (relative path, sha256 of the
exact source string passed to the transpiler, outcome, error, populations).
The trace lines carry the same sha256, so both join on ``file``.

Usage:
  PYNE_OBJECT_MODE_TRACE=<proof>/trace.jsonl python3 object_mode_bisect_scan.py \
      --repo <repo-root> --out-results results.jsonl --log scan.log [--workers 7]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

POP_FILES = {
    "plotshape": "details-plotshape.jsonl",
    "input_type_token": "details-input_type_token.jsonl",
    "runtime_error": "details-runtime_error.jsonl",
    "assigned_hline": "details-assigned_hline.jsonl",
}
PRIOR_DIR = Path(".oo/proof/numeric-object-error-scan-2026-11-18")

# worker globals
_DATA: Path | None = None
_POP: dict[str, list[str]] = {}


def _init_worker(data_dir: str, pop_map: dict[str, list[str]]) -> None:
    global _DATA, _POP
    src = str(Path(data_dir).parent.parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    _DATA = Path(data_dir)
    _POP = pop_map


def _scan_one(rel: str) -> dict:
    path = _DATA / rel
    rec: dict = {"file": rel, "populations": _POP.get(rel, [])}
    try:
        src = path.read_text(errors="ignore")
    except Exception as exc:  # noqa: BLE001
        rec.update(outcome="error", error=f"read: {type(exc).__name__}: {exc}"[:300], sha256=None)
        return rec
    rec["sha256"] = hashlib.sha256(src.encode("utf-8", errors="ignore")).hexdigest()
    try:
        from pynescript.compiler.engine import _transpile_once

        t0 = time.perf_counter()
        _code, _titles, _kinds, om, _attrs = _transpile_once(src)
        rec["outcome"] = "object" if om else "numeric"
        rec["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return rec


def load_corpus(repo: Path) -> dict[str, list[str]]:
    """rel path -> sorted list of populations it belongs to (object outcome only)."""
    pop: dict[str, set[str]] = {}
    for name, fname in POP_FILES.items():
        with open(repo / PRIOR_DIR / fname) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("outcome") != "object":
                    continue
                pop.setdefault(rec["file"], set()).add(name)
    return {k: sorted(v) for k, v in sorted(pop.items())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out-results", required=True)
    ap.add_argument("--log", default=None)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--progress-every", type=int, default=50)
    ap.add_argument("--limit", type=int, default=None, help="debug: only scan first N files")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    data_dir = repo / "tests" / "data"
    corpus = load_corpus(repo)
    files = sorted(corpus)
    if args.limit:
        files = files[: args.limit]

    trace = os.environ.get("PYNE_OBJECT_MODE_TRACE")
    log_f = open(args.log, "a", buffering=1) if args.log else sys.stdout

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        print(line, file=log_f, flush=True)

    log(f"corpus: {len(corpus)} unique object-outcome files; scanning {len(files)}; trace={trace}")
    t_start = time.time()
    counts = {"object": 0, "numeric": 0, "error": 0}
    missing = 0
    done = 0
    with open(args.out_results, "w", encoding="utf-8") as out_f:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_init_worker,
            initargs=(str(data_dir), corpus),
        ) as pool:
            for rec in pool.map(_scan_one, files, chunksize=8):
                if rec["outcome"] == "error" and rec.get("error", "").startswith("read:"):
                    missing += 1
                counts[rec["outcome"]] = counts.get(rec["outcome"], 0) + 1
                out_f.write(json.dumps(rec) + "\n")
                done += 1
                if done % args.progress_every == 0 or done == len(files):
                    el = time.time() - t_start
                    log(f"progress {done}/{len(files)} elapsed={el:.0f}s ({done / el:.2f} files/s)")
    dur = time.time() - t_start
    log(f"DONE total={len(files)} object={counts['object']} numeric={counts['numeric']} "
        f"error={counts['error']} unreadable={missing} duration={dur:.0f}s")
    if args.log:
        log_f.close()


if __name__ == "__main__":
    main()
