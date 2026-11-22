#!/usr/bin/env python3
"""Aggregate the object-mode forcing-site trace into aggregate.json.

Joins results.jsonl (per file: populations, sha256, outcome) with trace.jsonl
(one line per compilation that recorded a first forcing site; joined on sha256).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROOF = Path(__file__).resolve().parent
REPO = PROOF.parents[2]
DATA = REPO / "tests" / "data"
PRIOR = REPO / ".oo" / "proof" / "numeric-object-error-scan-2026-11-18"

sys.path.insert(0, str(PROOF))
from sites_table import COLOR_SITES, INPUT_STRINGY_SITES, SITES  # noqa: E402

COLOR_RE = re.compile(r"\bcolor\s*\.")


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    results = load_jsonl(PROOF / "results.jsonl")
    trace = load_jsonl(PROOF / "trace.jsonl")
    print(f"results: {len(results)}  trace lines: {len(trace)}")

    # ---- parity vs prior scan ---------------------------------------------
    prior = {}
    for fn in ["details-plotshape.jsonl", "details-input_type_token.jsonl",
               "details-runtime_error.jsonl", "details-assigned_hline.jsonl"]:
        for rec in load_jsonl(PRIOR / fn):
            prior.setdefault(rec["file"], set()).add(rec["outcome"])
    parity_diff = []
    for rec in results:
        old = prior.get(rec["file"])
        if old is None:
            continue
        new = rec["outcome"]
        norm = {"error": "error", "object": "object", "numeric": "numeric"}[new]
        if norm not in old:
            parity_diff.append({"file": rec["file"], "prior": sorted(old), "now": new})

    # ---- index trace by hash ----------------------------------------------
    trace_by_hash: dict[str, list[dict]] = defaultdict(list)
    for t in trace:
        trace_by_hash[t["file"]].append(t)

    files_out = [r for r in results if r["outcome"] == "object"]
    files_err = [r for r in results if r["outcome"] == "error"]
    files_num = [r for r in results if r["outcome"] == "numeric"]
    print(f"object={len(files_out)} numeric={len(files_num)} error={len(files_err)}")

    site_counts: Counter[int] = Counter()
    site_files: dict[int, list[str]] = defaultdict(list)
    site_pops: dict[int, Counter] = defaultdict(Counter)
    site_names: dict[int, str] = {}
    missing_trace: list[str] = []
    per_family: Counter[str] = Counter()
    pop_totals: Counter = Counter()
    pop_color_first: Counter = Counter()
    pop_color_token: Counter = Counter()
    color_first_files: list[str] = []
    has_color_token_files: list[str] = []
    input_site_files: list[str] = []
    error_traced = 0

    for r in files_out:
        h = r.get("sha256")
        tl = trace_by_hash.get(h or "", [])
        if not tl:
            missing_trace.append(r["file"])
            continue
        t = tl[0]  # one line per compile; duplicates only for identical files
        line = t["line"]
        site_counts[line] += 1
        site_files[line].append(r["file"])
        fam = SITES.get(line, ("?", "unknown"))[1]
        site_names[line] = t["site"]
        per_family[fam] += 1
        for p in r["populations"]:
            site_pops[line][p] += 1
            pop_totals[p] += 1
        if line in COLOR_SITES:
            color_first_files.append(r["file"])
            for p in r["populations"]:
                pop_color_first[p] += 1
        if line in INPUT_STRINGY_SITES:
            input_site_files.append(r["file"])

    # error-outcome files: note whether a site was recorded (compile died after forcing)
    for r in files_err:
        h = r.get("sha256")
        if h and trace_by_hash.get(h):
            error_traced += 1

    # color token presence (census comparable, regex identical to census.py)
    for r in files_out:
        try:
            src = (DATA / r["file"]).read_text(errors="ignore")
        except OSError:
            continue
        if COLOR_RE.search(src):
            has_color_token_files.append(r["file"])
            for p in r["populations"]:
                pop_color_token[p] += 1

    total_obj = len(files_out)
    n_traced = total_obj - len(missing_trace)

    def pct(n: int, d: int) -> float:
        return round(100.0 * n / d, 1) if d else 0.0

    sites_ranked = []
    for line, count in site_counts.most_common():
        label, fam = SITES.get(line, ("<unlabeled>", "unknown"))
        sites_ranked.append(
            {
                "line": line,
                "site": site_names.get(line),
                "label": label,
                "family": fam,
                "count": count,
                "pct": pct(count, n_traced),
                "per_population": dict(site_pops[line]),
                "example_files": site_files[line][:5],
            }
        )

    families = [
        {"family": fam, "count": n, "pct": pct(n, n_traced)}
        for fam, n in per_family.most_common()
    ]

    # residual "unknown/unattributed" bucket: explicit catch-alls plus the
    # end-of-visit residual sweep (object state emerged with no earlier forcing site).
    unknown_lines = [3127, 5151, 8077, 1445]
    unknown_files = []
    for ln in unknown_lines:
        unknown_files.extend(site_files.get(ln, []))

    aggregate = {
        "corpus": {
            "unique_object_outcome_files": len({r["file"] for r in results}),
            "results_records": len(results),
            "by_population_records": dict(Counter(p for r in results for p in r["populations"])),
            "population_unique_files": {p: len({r["file"] for r in results if p in r["populations"]}) for p in
                                        sorted({p for r in results for p in r["populations"]})},
        },
        "outcomes": {"object": len(files_out), "numeric": len(files_num), "error": len(files_err)},
        "outcome_parity_vs_2026-11-18": {
            "compared": sum(1 for r in results if r["file"] in prior),
            "changed": parity_diff,
        },
        "traced_object_files": n_traced,
        "missing_trace_for_object_files": missing_trace,
        "error_outcome_files_with_trace": error_traced,
        "unreadable_files": [r["file"] for r in results if r.get("error", "").startswith("read:")],
        "sites": sites_ranked,
        "families": families,
        "color": {
            "first_site_is_color": len(color_first_files),
            "first_site_is_color_pct": pct(len(color_first_files), n_traced),
            "first_site_is_input_stringy": len(input_site_files),
            "first_site_is_input_stringy_pct": pct(len(input_site_files), n_traced),
            "files_containing_color_token": len(has_color_token_files),
            "files_containing_color_token_pct": pct(len(has_color_token_files), len(files_out)),
            "color_first_files": color_first_files,
            "per_population": {
                p: {
                    "traced": pop_totals[p],
                    "color_first": pop_color_first[p],
                    "color_token": pop_color_token[p],
                }
                for p in sorted(pop_totals)
            },
        },
        "unknown_bucket_lines": unknown_lines,
        "unknown_bucket_count": len(unknown_files),
        "unknown_bucket_examples": unknown_files[:10],
        "population_totals_traced": dict(pop_totals),
    }
    with open(PROOF / "aggregate.json", "w") as f:
        json.dump(aggregate, f, indent=2)

    print(f"traced object files: {n_traced}/{total_obj} (missing {len(missing_trace)})")
    print(f"outcome parity: {sum(1 for r in results if r['file'] in prior)} compared, {len(parity_diff)} changed")
    print(f"color first-site: {len(color_first_files)} ({pct(len(color_first_files), n_traced)}%), "
          f"color token present: {len(has_color_token_files)} ({pct(len(has_color_token_files), len(files_out))}%)")
    print("top 15 sites:")
    for s in sites_ranked[:15]:
        print(f"  L{s['line']:5} {s['count']:5} {s['pct']:5.1f}%  {s['label']}")


if __name__ == "__main__":
    main()
