#!/usr/bin/env python3
"""Aggregate scan runs into summary.json (populations x set scopes, before/after flips)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
POPULATIONS = ["plotshape", "input_type_token", "runtime_error", "assigned_hline"]
SET_GROUPS = {
    "set01": ["set01"], "set02": ["set02"], "set03": ["set03"], "set04": ["set04"],
    "set05": ["set05"], "set06": ["set06"],
    "set01_04": ["set01", "set02", "set03", "set04"],
    "set05_06": ["set05", "set06"],
    "all_six": [f"set0{i}" for i in range(1, 7)],
}

def load_details(path: Path) -> dict[str, dict]:
    out = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["file"]] = rec
    return out

def scope_counts(per_set: dict, sets: list[str]) -> dict:
    tot = {"total": 0, "numeric": 0, "object": 0, "error": 0}
    for s in sets:
        c = per_set[s]
        for k in tot:
            tot[k] += c[k]
    return tot

summary: dict = {
    "card": "pyne-numeric-object-error-transp-fa4960d2",
    "date": "2026-11-18",
    "method": (
        "transpile-only via pynescript.compiler.engine._transpile_once on every "
        "tests/data/setXX/**/*.pine matching the population regex; object_mode flag "
        "from CompilerVisitor; exceptions classified as 'error' (never folded into "
        "object/numeric); timeout=0 (no per-file timeout, same as 2026-11-17 scans)."
    ),
    "populations": {},
    "before_after": {},
}

for pop in POPULATIONS:
    run = json.loads((HERE / f"run-{pop}.json").read_text())
    per_set = run["per_set"]
    entry = {
        "pattern": run["pattern"],
        "pattern_origin": run["pattern_origin"],
        "flags": run["flags"],
        "match": run["match"],
        "per_set": per_set,
        "scopes": {name: scope_counts(per_set, sets) for name, sets in SET_GROUPS.items()},
        "total": run["total"],
        "numeric": run["numeric"],
        "object": run["object"],
        "error": run["error"],
        "duration_s": run["duration_s"],
        "workers": run["workers"],
        "details": f"details-{pop}.jsonl",
    }
    summary["populations"][pop] = entry

    before_path = HERE / f"before-{pop}.json"
    if before_path.exists():
        before = json.loads(before_path.read_text())
        bdet = load_details(HERE / f"details-{pop}-before.jsonl")
        ade = load_details(HERE / f"details-{pop}.jsonl")
        # restrict HEAD details to set01-04 for comparability
        flips = Counter()
        changed = []
        for f, arec in ade.items():
            if not arec["set"] in ("set01", "set02", "set03", "set04"):
                continue
            brec = bdet.get(f)
            if brec is None:
                continue
            b_out, a_out = brec["outcome"], arec["outcome"]
            if b_out != a_out:
                flips[f"{b_out}->{a_out}"] += 1
                changed.append({"file": f, "before": b_out, "after": a_out})
        bset01_04 = scope_counts(before["per_set"], ["set01", "set02", "set03", "set04"])
        aset01_04 = scope_counts(per_set, ["set01", "set02", "set03", "set04"])
        summary["before_after"][pop] = {
            "baseline_sha": (before.get("label") or "").split(":", 1)[-1],
            "baseline_full": before,
            "set01_04_before": bset01_04,
            "set01_04_after": aset01_04,
            "delta": {k: aset01_04[k] - bset01_04[k] for k in ("total", "numeric", "object", "error")},
            "flips": dict(flips),
            "changed_files": sorted(changed, key=lambda c: c["file"]),
        }

(HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({p: summary["populations"][p]["scopes"] for p in POPULATIONS}, indent=2))
if summary["before_after"]:
    print(json.dumps({p: {"before": v["set01_04_before"], "after": v["set01_04_after"], "flips": v["flips"]} for p, v in summary["before_after"].items()}, indent=2))
