# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Transpile-only numeric-mode scan — same method as .oo/proof/bgcolor-2026-11-17.

Counts corpus scripts whose source matches --match (regex), transpiles each once
with pynescript.compiler.engine._transpile_once (no Numba JIT, no bar loop), and
records object_mode / errors. Output JSON schema matches the 2026-11-17 bgcolor
artifact: {total, numeric, object, error, timeout, files: {relpath: {...}}}.

Usage: python scan_numeric_mode.py --sets set05 set06 --match 'bgcolor' --out out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "tests" / "data"
sys.path.insert(0, str(REPO / "src"))

from pynescript.compiler.engine import _transpile_once  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--match", required=True, help="regex; file source must match")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-total", type=int, default=None, help="fail if matched-file count differs")
    args = ap.parse_args()

    rx = re.compile(args.match)
    files: dict[str, dict] = {}
    for s in args.sets:
        for p in sorted((DATA / s).rglob("*.pine")):
            try:
                src = p.read_text(errors="ignore")
            except Exception as exc:  # noqa: BLE001
                files[str(p.relative_to(DATA))] = {"error": f"read: {type(exc).__name__}: {exc}"}
                continue
            if not rx.search(src):
                continue
            rel = str(p.relative_to(DATA))
            try:
                _code, _titles, kinds, om, _attrs = _transpile_once(src)
                files[rel] = {"om": bool(om), "kinds": list(kinds) if kinds is not None else []}
            except Exception as exc:  # noqa: BLE001 - mirror the 2026-11-17 bgcolor scan
                files[rel] = {"error": f"{type(exc).__name__}: {exc}"}

    total = len(files)
    err = sum(1 for v in files.values() if "error" in v)
    obj = sum(1 for v in files.values() if v.get("om") is True)
    num = sum(1 for v in files.values() if v.get("om") is False)
    summary = {
        "scope": f"tests/data/{'+'.join(args.sets)}, scripts matching /{args.match}/",
        "match": args.match,
        "sets": args.sets,
        "total": total,
        "numeric": num,
        "object": obj,
        "error": err,
        "timeout": 0,
        "files": files,
    }
    if args.expect_total is not None and total != args.expect_total:
        print(f"FATAL: matched {total} files, expected {args.expect_total}", file=sys.stderr)
        raise SystemExit(2)
    Path(args.out).write_text(json.dumps(summary, indent=1) + "\n")
    print(f"wrote {args.out}: total={total} numeric={num} object={obj} error={err}")


if __name__ == "__main__":
    main()
