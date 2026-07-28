#!/usr/bin/env python3
"""Re-parse FAIL/TIMEOUT rows from a corpus CSV with the current parser.

Uses a single-worker Process + hard kill so timeouts cannot freeze the run
(ProcessPoolExecutor.fut.result(timeout) leaves hung workers and can stall).
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"


def _parse_one(path_str: str, q: mp.Queue) -> None:
    """Worker entry: put (status, error, ms) on queue."""
    t0 = time.perf_counter()
    try:
        from pynescript.ast.helper import parse, unparse
        from pynescript.util.corpus_sanitize import sanitize_corpus_source

        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
        src = sanitize_corpus_source(raw)
        unparse(parse(src))
        q.put(("OK", "", int((time.perf_counter() - t0) * 1000)))
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {str(e).split(chr(10))[0][:200]}"
        q.put(("FAIL", msg, int((time.perf_counter() - t0) * 1000)))


def parse_with_timeout(path: Path, timeout: float) -> tuple[str, str, int]:
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue(1)
    proc = ctx.Process(target=_parse_one, args=(str(path), q))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        if proc.is_alive():
            proc.kill()
            proc.join(1)
        return "TIMEOUT", f"exceeded {timeout:.0f}s", int(timeout * 1000)
    if not q.empty():
        return q.get()
    return "FAIL", "worker exited without result", 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--base",
        type=Path,
        default=ROOT / ".cache" / "corpus_parse_set01_set04.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / ".cache" / "corpus_parse_set01_set04_rerun_fails.csv",
    )
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()

    fails: list[str] = []
    base_ok = 0
    base_total = 0
    with args.base.open(encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            base_total += 1
            if row["status"] == "OK":
                base_ok += 1
            else:
                fails.append(row["file"])

    print(f"re-parsing {len(fails)} previously failed files (hard timeout)…", flush=True)
    rows: list[dict[str, object]] = []
    ok = fail = timeout_n = 0
    err_bucket: Counter[str] = Counter()
    by_set: Counter[tuple[str, str]] = Counter()
    t_all = time.perf_counter()

    for i, rel in enumerate(fails, 1):
        status, error, ms = parse_with_timeout(DATA / rel, args.timeout)
        set_name = rel.split("/")[0]
        if status == "OK":
            ok += 1
        elif status == "TIMEOUT":
            timeout_n += 1
            fail += 1
            err_bucket[error[:100]] += 1
        else:
            fail += 1
            err_bucket[error[:100]] += 1
        by_set[(set_name, status)] += 1
        rows.append({"file": rel, "set": set_name, "status": status, "ms": ms, "error": error})

        if i % 10 == 0 or status != "OK" or i == 1 or i == len(fails):
            print(
                f"  [{i}/{len(fails)}] OK={ok} FAIL={fail - timeout_n} T/O={timeout_n}  "
                f"{status:7} {ms}ms  {rel[:58]}",
                flush=True,
            )

    elapsed = time.perf_counter() - t_all
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["file", "set", "status", "ms", "error"])
        w.writeheader()
        w.writerows(rows)

    new_ok = base_ok + ok
    rate = 100 * new_ok / max(base_total, 1)
    lines = [
        f"rerun_fails={len(fails)} now_OK={ok} still_FAIL={fail - timeout_n} "
        f"TIMEOUT={timeout_n} elapsed_s={elapsed:.1f}",
        f"projected_overall OK={new_ok}/{base_total} rate={rate:.2f}% "
        f"(base OK={base_ok} rate={100 * base_ok / max(base_total, 1):.2f}%)",
        "by_set_status:",
    ]
    for (s, st), n in sorted(by_set.items()):
        lines.append(f"  {s} {st}: {n}")
    lines.append("top_errors:")
    for msg, n in err_bucket.most_common(30):
        lines.append(f"  {n:5}  {msg}")
    text = "\n".join(lines) + "\n"
    summary = args.out.with_name(args.out.stem + "_summary.txt")
    summary.write_text(text, encoding="utf-8")
    print(text, flush=True)
    print(f"Wrote {args.out}", flush=True)
    print(f"Wrote {summary}", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
