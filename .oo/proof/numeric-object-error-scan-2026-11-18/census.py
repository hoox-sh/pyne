#!/usr/bin/env python3
"""Census of likely object-mode forcers inside a population's object-mode files.

Read-only analysis. For every file recorded as outcome=object in a details-*.jsonl,
count occurrences of regexes for major object-mode-forcing construct families.
A file matching a family means the family is PRESENT, not necessarily that it
forced object mode (attribution per file would require compiler bisection).
Also reports how many object-mode files match NONE of the known families
(residual class worth manual inspection).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA = Path("/mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript/tests/data")

FAMILIES = {
    "strategy_call": r"\bstrategy\s*\(",
    "library_import": r"(?m)^\s*import\s+\S+",
    "udt_type": r"(?m)^\s*type\s+[A-Za-z_]\w*",
    "varip": r"\bvarip\b",
    "array_map_matrix": r"\b(array|map|matrix)\s*\.",
    "stringy_input": r"type\s*=\s*input\s*\.\s*(string|text_area|color|symbol|timeframe|session)\b",
    "string_ops": r"\bstr\s*\.\s*(tostring|format|format_time|repeat|replace|lower|upper|trim)",
    "color_token": r"\bcolor\s*\.",
    "drawing": r"\b(label|line|box|table|polyline|linefill)\s*\.\s*new\b",
    "multi_arg_runtime_error": None,  # handled specially (balanced parens)
    "nonliteral_or_multiarg_error": None,
    "security": r"\brequest\.security",
    "iff_dynamic": r"\biff\s*\(",
    "switch": r"\bswitch\b",
    "table": r"\btable\s*\.",
    "runtime_error_any": r"runtime\s*\.\s*error",
}

def runtime_error_shape(src: str) -> str:
    """Classify the runtime.error call(s) in src: 'none' | 'literal_single' | 'other'."""
    found = False
    for m in re.finditer(r"runtime\s*\.\s*error\s*\(", src, re.IGNORECASE):
        depth, i = 1, m.end()
        start = i
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        inner = src[start:i - 1]
        # top-level comma?
        d, comma = 0, False
        for ch in inner:
            if ch in "([{": d += 1
            elif ch in ")]}": d -= 1
            elif ch == "," and d == 0: comma = True
        found = True
        if comma:
            return "other"
        s = inner.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            continue  # literal single-arg: OK
        if s == "":
            continue
        return "other"
    return "literal_single" if found else "none"

def main() -> None:
    details = Path(sys.argv[1])
    scope = sys.argv[2]  # e.g. 'set01,set02,set03,set04' or 'all'
    want = None if scope == "all" else set(scope.split(","))
    files = []
    with details.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["outcome"] != "object":
                continue
            if want and rec["set"] not in want:
                continue
            files.append(rec["file"])
    fam_counts: Counter = Counter()
    err_shapes: Counter = Counter()
    zero_family = []
    comp = {k: re.compile(v) for k, v in FAMILIES.items() if v}
    for rel in files:
        src = (DATA / rel).read_text(errors="ignore")
        hit = False
        for name, rx in comp.items():
            if rx.search(src):
                fam_counts[name] += 1
                hit = True
        shape = runtime_error_shape(src)
        err_shapes[shape] += 1
        if shape == "other":
            hit = True
        if not hit:
            zero_family.append(rel)
    print(f"object-mode files examined: {len(files)}")
    for k, v in fam_counts.most_common():
        print(f"  contains {k}: {v} ({100*v/len(files):.1f}%)" if files else "")
    print(f"runtime.error call shape among object-mode files: {dict(err_shapes)}")
    print(f"object-mode files matching NO known family: {len(zero_family)}")
    for f in zero_family[:40]:
        print(f"    residual: {f}")

if __name__ == "__main__":
    main()
