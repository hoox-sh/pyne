#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Transpile-only numeric/object/error scan for re-sourced populations.

Same method as .oo/proof/bgcolor-2026-11-17 and .oo/proof/numeric-mode-remeasure-2026-11-17:
for every ``tests/data/setXX/**/*.pine`` whose source matches the population
regex, call ``pynescript.compiler.engine._transpile_once(source)`` (parse +
CompilerVisitor only — no JIT, no bar loop, no disk index) and record
``object_mode`` / raised exception.

Classification (identical to the 2026-11-17 scan):
  * ``om is True``  -> "object"
  * ``om is False`` -> "numeric"
  * exception       -> "error"   (reported separately, NEVER folded into
    object/numeric; errors are expected on the scraped-doc sets)

Populations (patterns embedded, self-describing; regexes verified against
.oo/proof/numeric-mode-remeasure-2026-11-17/{re-source.md,file_counts.json}):

  plotshape        pattern: ``plotshape``            (files containing the token)
                   expected file counts: set01-04=359, set05+06=2875, all=3234
  input_type_token pattern: ``type\\s*=\\s*input\\s*\\.`` (verbatim from the
                   2026-11-14 proof PATS["input_type"])
                   expected: 115 / 1878 / 1993
  runtime_error    pattern: ``runtime\\.error`` flags=IGNORECASE (task-specified;
                   re-source.md verified case-insensitive == case-sensitive on counts)
                   expected: 553 / 199 / 752
  assigned_hline   pattern: ``=\\s*hline\\s*\\(`` (multiline: ``\\s`` matches \\n;
                   verbatim from 2026-11-14 proof PATS["hline"])
                   expected: 48 / 479 / 527

Usage:
  python scan_numeric_object_error.py --population plotshape --out out.json --details d.jsonl [--sets set01 set02 ...] [--workers N] [--count-only]
  python scan_numeric_object_error.py --population assigned_hline --src /tmp/opencode/oo-base-x/src --data <repo>/tests/data --sets set01 set02 set03 set04 ...

``--src`` / ``--data`` exist so the same scanner can run against a baseline
``git archive`` extract of ``src/`` (before/after comparison) while keeping the
corpus (tests/data) identical — the corpus has not changed since 2026-11-11.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

POPULATIONS = {
    "plotshape": {
        "pattern": r"plotshape",
        "flags": 0,
        "origin": "files containing substring 'plotshape' (2026-11-17 re-source)",
        "expect": {"set01_04": 359, "set05_06": 2875, "all_six": 3234},
    },
    "input_type_token": {
        "pattern": r"type\s*=\s*input\s*\.",
        "flags": 0,
        "origin": "2026-11-14 proof PATS['input_type'] (re-verified 2026-11-17)",
        "expect": {"set01_04": 115, "set05_06": 1878, "all_six": 1993},
    },
    "runtime_error": {
        "pattern": r"runtime\.error",
        "flags": re.IGNORECASE,
        "origin": "task-specified, case-insensitive; 2026-11-17 re-source verified identical counts case-insensitively",
        "expect": {"set01_04": 553, "set05_06": 199, "all_six": 752},
    },
    "assigned_hline": {
        "pattern": r"=\s*hline\s*\(",
        "flags": 0,
        "origin": "2026-11-14 proof PATS['hline'] (multiline; \\s spans newlines)",
        "expect": {"set01_04": 48, "set05_06": 479, "all_six": 527},
    },
}
ALL_SETS = [f"set0{i}" for i in range(1, 7)]

# worker globals (set in _init_worker)
_SRC: str | None = None
_POP: dict | None = None
_pop_rx = None


def _init_worker(src: str, pattern: str, flags: int) -> None:
    global _SRC, _pop_rx
    _SRC = src
    if src not in sys.path:
        sys.path.insert(0, src)
    _pop_rx = re.compile(pattern, flags)


def _scan_one(task: tuple[str, str]) -> dict:
    """Transpile one matched file. Returns the JSONL record."""
    rel, data_root = task
    path = Path(data_root) / rel
    rec: dict = {"file": rel, "set": rel.split("/", 1)[0]}
    try:
        src = path.read_text(errors="ignore")
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "error"
        rec["error"] = f"read: {type(exc).__name__}: {exc}"[:500]
        return rec
    if not _pop_rx.search(src):
        # Should not happen (matched in phase 1); keep honest.
        rec["outcome"] = "error"
        rec["error"] = "internal: file no longer matches population regex"
        return rec
    try:
        from pynescript.compiler.engine import _transpile_once

        t0 = time.perf_counter()
        _code, _titles, kinds, om, _attrs = _transpile_once(src)
        rec["outcome"] = "object" if om else "numeric"
        rec["kinds"] = list(kinds) if kinds is not None else []
        rec["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:  # noqa: BLE001 - mirror the 2026-11-17 bgcolor scan
        rec["outcome"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population", required=True, choices=sorted(POPULATIONS))
    ap.add_argument("--sets", nargs="+", default=ALL_SETS)
    ap.add_argument("--root", default=None, help="repo root (default: derived from this file)")
    ap.add_argument("--src", default=None, help="path to src/ to import pynescript from (default: <root>/src)")
    ap.add_argument("--data", default=None, help="path to tests/data (default: <root>/tests/data)")
    ap.add_argument("--out", default=None, help="write run summary JSON here")
    ap.add_argument("--details", default=None, help="write per-file JSONL here")
    ap.add_argument("--log", default=None, help="append progress lines here (flushed)")
    ap.add_argument("--workers", type=int, default=1, help="parallel worker processes (default 1 = sequential, like the 2026-11-17 scan)")
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--count-only", action="store_true", help="only count matched files, no transpile")
    ap.add_argument("--label", default=None, help="free-form label recorded in the run summary (e.g. baseline SHA)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[3]
    src_dir = Path(args.src).resolve() if args.src else root / "src"
    data_dir = Path(args.data).resolve() if args.data else root / "tests" / "data"
    pop = POPULATIONS[args.population]
    rx = re.compile(pop["pattern"], pop["flags"])

    log_f = open(args.log, "a", buffering=1) if args.log else sys.stdout

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {args.population}: {msg}"
        print(line, file=log_f, flush=True)

    t_start = time.time()
    log_enabled = args.log is not None

    # Phase 1: select matching files (fast; read-only)
    matched: list[str] = []
    per_set_matched: dict[str, int] = {}
    for s in args.sets:
        s_dir = data_dir / s
        if not s_dir.is_dir():
            print(f"FATAL: missing data dir {s_dir}", file=sys.stderr)
            raise SystemExit(2)
        n = 0
        for p in sorted(s_dir.rglob("*.pine")):
            try:
                text = p.read_text(errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            if rx.search(text):
                matched.append(str(p.relative_to(data_dir)))
                n += 1
        per_set_matched[s] = n
    total = len(matched)
    log(f"phase1 match: total={total} per_set={per_set_matched} flags={pop['flags']} pattern={pop['pattern']!r}")

    if args.count_only:
        summary = {
            "population": args.population,
            "pattern": pop["pattern"],
            "flags": pop["flags"],
            "sets": args.sets,
            "matched": total,
            "per_set": per_set_matched,
            "expect": pop["expect"],
        }
        print(json.dumps(summary, indent=2))
        if log_enabled:
            log_f.close()
        return

    # Phase 2: transpile
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    details_f = open(args.details, "w", encoding="utf-8") if args.details else None
    counts: dict[str, dict[str, int]] = {s: {"total": 0, "numeric": 0, "object": 0, "error": 0} for s in args.sets}
    done = 0

    def handle(rec: dict) -> None:
        nonlocal done
        s = rec["set"]
        bucket = counts.setdefault(s, {"total": 0, "numeric": 0, "object": 0, "error": 0})
        bucket["total"] += 1
        bucket[rec["outcome"]] += 1
        if details_f:
            details_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        done += 1
        if done % args.progress_every == 0 or done == total:
            el = time.time() - t_start
            log(f"progress {done}/{total} elapsed={el:.0f}s ({done / el:.2f} files/s)")

    if args.workers > 1:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_init_worker,
            initargs=(str(src_dir), pop["pattern"], pop["flags"]),
        ) as pool:
            for rec in pool.map(_scan_one, [(rel, str(data_dir)) for rel in matched], chunksize=max(1, total // (args.workers * 20) or 1)):
                handle(rec)
    else:
        _init_worker(str(src_dir), pop["pattern"], pop["flags"])
        for rel in matched:
            handle(_scan_one((rel, str(data_dir))))

    if details_f:
        details_f.close()
    dur = time.time() - t_start
    for s in args.sets:
        c = counts[s]
        log(f"set {s}: total={c['total']} numeric={c['numeric']} object={c['object']} error={c['error']}")

    tot_numeric = sum(c["numeric"] for c in counts.values())
    tot_object = sum(c["object"] for c in counts.values())
    tot_error = sum(c["error"] for c in counts.values())
    summary = {
        "population": args.population,
        "pattern": pop["pattern"],
        "flags": pop["flags"],
        "pattern_origin": pop["origin"],
        "label": args.label,
        "src": str(src_dir),
        "data": str(data_dir),
        "sets": args.sets,
        "match": pop["pattern"],
        "total": total,
        "numeric": tot_numeric,
        "object": tot_object,
        "error": tot_error,
        "timeout": 0,
        "per_set": counts,
        "duration_s": round(dur, 1),
        "workers": args.workers,
        "repo_head": os.environ.get("OO_SCAN_HEAD", None),
    }
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2) + "\n")
    log(f"DONE total={total} numeric={tot_numeric} object={tot_object} error={tot_error} duration={dur:.0f}s")
    if log_enabled:
        log_f.close()


if __name__ == "__main__":
    main()
