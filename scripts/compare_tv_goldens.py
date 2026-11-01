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

"""Compare PYNE against real TradingView exports.

The fixtures under ``tests/fixtures/tv_goldens/`` come from OpenPineScript's
``conformance/v5/golden`` directory: a Pine harness plus the Pine Logs export
TradingView produced when that harness ran on ``BINANCE:BTCUSDT`` ``1D``.
The harness IS the test program.  We run the same ``.pine`` file through
``pynescript.runtime.Runtime`` on the OHLCV bars carried by the export and
compare its ``OPS|`` rows column-by-column with TradingView's rows.

The comparison mirrors OpenPineScript's ``tradingview_golden.test.ts``:

* compare only the intersection of exported columns and columns the harness
  emits, with ``MIN_COLUMNS`` stopping a degraded harness from passing;
* skip a warm-up window so seeded recursive indicators can converge;
* skip bars where TradingView has ``na``, but fail when PYNE invents a value
  where TradingView has none;
* require the first non-``na`` bar to agree when TradingView's starts after
  bar 0 (an indicator that starts one bar early/late is a parity bug);
* reject all-``na`` and constant columns as vacuous evidence.

Known divergences live in ``tests/fixtures/tv_goldens/baseline.json`` so the
suite can stay green while a remaining gap is explicit.  The current red set
is empty (112 / 112).  ``--strict`` ignores the baseline and fails on any
difference; ``--update-baseline`` refreshes it.

Usage::

    python scripts/compare_tv_goldens.py
    python scripts/compare_tv_goldens.py --strict
    python scripts/compare_tv_goldens.py --json
    python scripts/compare_tv_goldens.py --only harness_core,harness_state
    python scripts/compare_tv_goldens.py --update-baseline
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURES = _ROOT / "tests" / "fixtures" / "tv_goldens"
_DEFAULT_BASELINE = _DEFAULT_FIXTURES / "baseline.json"

OHLCV = frozenset({"time", "open", "high", "low", "close", "volume"})
DEFAULT_WARMUP = 300
REL_TOL = 1e-6
ABS_TOL = 1e-9
MIN_COLUMNS = 5
MIN_POINTS = 50

# Path-dependent harnesses never converge: compare from the first exported bar.
WARMUP_BY_HARNESS: dict[str, int] = {
    "harness_control": 0,
    "harness_exits": 0,
    "harness_state": 0,
    "harness_strategy": 0,
}

# Columns that are constant BY CONSTRUCTION; matching them proves nothing but
# the probe is still meaningful.  Keyed by ``<harness>::<column>``.
CONSTANT_BY_CONSTRUCTION: frozenset[str] = frozenset({"harness_loops::nested_loops"})


def _out(message: str = "") -> None:
    """Write one report line (ruff T201 is about bare ``print``)."""
    sys.stdout.write(message + "\n")


# Why a known divergence is still red.  Used when (re)writing the baseline so
# the reason travels with the fixture instead of living in someone's head.
KNOWN_REASONS: dict[str, str] = {}


@dataclass(slots=True)
class Export:
    """One TradingView export plus the harness that produced it."""

    path: Path
    harness: Path
    header: list[str]
    bars: list[dict[str, float]]
    columns: dict[str, list[float]]
    kind: str


@dataclass(slots=True)
class ColumnResult:
    """Outcome for one exported column."""

    column: str
    status: str
    compared: int = 0
    mismatches: int = 0
    nan_mismatches: int = 0
    first_tv: int = -1
    first_ours: int = -1
    worst_rel: float = 0.0
    first_diff: str | None = None
    problems: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(slots=True)
class HarnessResult:
    """Outcome for one export/harness pair."""

    export: Export
    columns: list[ColumnResult] = field(default_factory=list)
    error: str | None = None


def _split_payload(line: str, marker: str) -> str | None:
    """Return the payload after ``marker`` inside a CSV or prefixed log line."""
    try:
        fields = next(csv.reader([line]))
    except csv.Error:
        fields = [line]
    for field_text in fields:
        idx = field_text.find(marker)
        if idx >= 0:
            return field_text[idx + len(marker) :]
    return None


def _cells(payload: str) -> list[str]:
    try:
        return next(csv.reader([payload]))
    except csv.Error:
        return payload.split(",")


def _parse_cell(raw: str) -> float:
    text = raw.strip()
    if text == "" or text.lower() in {"na", "nan", "n/a", "null"}:
        return math.nan
    try:
        value = float(text)
    except ValueError:
        return math.nan
    return value


def _parse_time(raw: str) -> float:
    text = raw.strip()
    if text == "":
        return math.nan
    try:
        numeric = float(text)
    except ValueError:
        numeric = math.nan
    if math.isfinite(numeric):
        # Seconds vs milliseconds: anything below ~1e12 is seconds.
        return numeric * 1000.0 if abs(numeric) < 1e12 else numeric
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000.0
    except ValueError:
        return math.nan


def _read_log(text: str) -> tuple[list[str], list[list[str]]]:
    header: list[str] | None = None
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        head = _split_payload(line, "OPSHEAD|")
        if head is not None:
            header = [cell.strip() for cell in _cells(head)]
            continue
        body = _split_payload(line, "OPS|")
        if body is not None:
            cells = _cells(body)
            if cells:
                rows[cells[0].strip()] = cells
    if not header:
        raise ValueError("no OPSHEAD| line found; copy the whole Pine Logs pane")
    ordered = [rows[key] for key in sorted(rows, key=_parse_time)]
    return header, ordered


def _read_csv(text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("empty CSV export")
    header = [cell.strip() for cell in rows[0]]
    return header, rows[1:]


def _load_export(path: Path) -> Export:
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if "OPSHEAD|" in text or "OPS|" in text:
        header, rows = _read_log(text)
        kind = "log"
    else:
        header, rows = _read_csv(text)
        kind = "csv"

    lowered = [name.lower() for name in header]
    required = ("time", "open", "high", "low", "close")
    missing = [name for name in required if name not in lowered]
    if missing:
        raise ValueError(f"header is missing {missing}; export the main series too")
    index = {name: lowered.index(name) for name in required}
    i_volume = lowered.index("volume") if "volume" in lowered else -1

    plot_indices = [(name, idx) for idx, name in enumerate(header) if name and name.lower() not in OHLCV]
    bars: list[dict[str, float]] = []
    columns: dict[str, list[float]] = {name: [] for name, _ in plot_indices}
    for row in rows:
        cells = row if len(row) >= len(header) else [*row, *([""] * (len(header) - len(row)))]
        time_value = _parse_time(cells[index["time"]])
        close_value = _parse_cell(cells[index["close"]])
        if not math.isfinite(time_value) or not math.isfinite(close_value):
            continue
        bars.append(
            {
                "time": int(time_value),
                "open": _parse_cell(cells[index["open"]]),
                "high": _parse_cell(cells[index["high"]]),
                "low": _parse_cell(cells[index["low"]]),
                "close": close_value,
                "volume": _parse_cell(cells[i_volume]) if i_volume >= 0 else 0.0,
            }
        )
        for name, idx in plot_indices:
            columns[name].append(_parse_cell(cells[idx]))

    harness = path.with_name(path.name.split(".")[0] + ".pine")
    if not harness.exists():
        raise ValueError(f"no sibling harness {harness.name!r} for {path.name!r}")
    return Export(path=path, harness=harness, header=header, bars=bars, columns=columns, kind=kind)


def _symbol_from_filename(name: str) -> str:
    parts = name.split(".")
    return parts[1] if len(parts) >= 3 else "CHART"


def _timeframe_from_filename(name: str) -> str:
    parts = name.split(".")
    if len(parts) < 3:
        return "D"
    raw = parts[2].upper()
    return {"1D": "D", "1W": "W", "1M": "M"}.get(raw, raw)


def _harness_name(path: Path) -> str:
    return path.name.split(".")[0]


def _warmup_for(export: Export) -> int:
    return WARMUP_BY_HARNESS.get(_harness_name(export.path), DEFAULT_WARMUP)


def _number(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _read_pyne_logs(logs: list[dict[str, Any]]) -> tuple[list[str], list[list[str]]]:
    header: list[str] | None = None
    rows: dict[str, list[str]] = {}
    for entry in logs:
        message = str(entry.get("message", ""))
        if message.startswith("OPSHEAD|"):
            header = [cell.strip() for cell in _cells(message[len("OPSHEAD|") :])]
        elif message.startswith("OPS|"):
            cells = _cells(message[len("OPS|") :])
            if cells:
                rows[cells[0].strip()] = cells
    if not header:
        raise ValueError("PYNE logged no OPSHEAD| row")
    ordered = [rows[key] for key in sorted(rows, key=_parse_time)]
    return header, ordered


def _run_harness(export: Export, mode: str) -> dict[str, list[float]]:
    from pynescript.runtime.host import Runtime

    source = export.harness.read_text(encoding="utf-8")
    runtime = Runtime(
        symbol=_symbol_from_filename(export.path.name),
        timeframe=_timeframe_from_filename(export.path.name),
    )
    result = runtime.run(source, export.bars, mode=mode)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))

    if "OPSHEAD|" in source:
        header, rows = _read_pyne_logs(list(result.get("logs") or []))
        columns: dict[str, list[float]] = {}
        for idx, name in enumerate(header):
            if not name or name.lower() in OHLCV or name == "time":
                continue
            columns[name] = [_parse_cell(row[idx]) if idx < len(row) else math.nan for row in rows]
        return columns

    series = result.get("series") or {}
    return {name: [_number(value) for value in values] for name, values in series.items()}


def _close(theirs: float, ours: float) -> bool:
    diff = abs(theirs - ours)
    return diff <= ABS_TOL or diff <= REL_TOL * max(abs(theirs), abs(ours))


def _compare_column(
    name: str,
    theirs: list[float],
    ours: list[float],
    *,
    warmup: int,
    times: list[int],
    key: str,
) -> ColumnResult:
    result = ColumnResult(column=name, status="pass")
    limit = min(len(theirs), len(ours))
    if len(theirs) != len(ours):
        result.problems.append(f"length mismatch tradingview={len(theirs)} ours={len(ours)}")
    if limit == 0:
        result.problems.append("no samples")
        result.status = "fail"
        return result

    result.first_tv = next((i for i in range(limit) if not math.isnan(theirs[i])), -1)
    result.first_ours = next((i for i in range(limit) if not math.isnan(ours[i])), -1)
    if result.first_tv < 0:
        result.status = "skip"
        result.problems.append("TradingView exported no values")
        return result

    seen: set[float] = set()
    for i in range(warmup, limit):
        theirs_value = theirs[i]
        ours_value = ours[i]
        if math.isnan(theirs_value):
            if not math.isnan(ours_value):
                result.nan_mismatches += 1
                if result.first_diff is None:
                    result.first_diff = _diff_text(i, times, "na", ours_value)
            continue
        result.compared += 1
        seen.add(theirs_value)
        if math.isnan(ours_value) or not _close(theirs_value, ours_value):
            result.mismatches += 1
            if math.isnan(ours_value):
                result.worst_rel = math.inf
            else:
                result.worst_rel = max(
                    result.worst_rel,
                    abs(theirs_value - ours_value) / max(abs(theirs_value), abs(ours_value), 1e-12),
                )
            if result.first_diff is None:
                result.first_diff = _diff_text(i, times, theirs_value, ours_value)

    if result.compared < MIN_POINTS:
        result.problems.append(
            f"TradingView reported a value on only {result.compared} bars after the {warmup}-bar warm-up"
        )
    if len(seen) <= 1 and key not in CONSTANT_BY_CONSTRUCTION:
        result.problems.append("TradingView column is constant; matching it proves nothing")
    if result.first_tv > 0 and result.first_ours != result.first_tv:
        result.problems.append(f"first non-na bar differs: tradingview={result.first_tv} ours={result.first_ours}")
    if result.mismatches:
        result.problems.append(
            f"{result.mismatches} of {result.compared} bars disagree (worst rel {result.worst_rel:.2e})"
        )
    if result.nan_mismatches:
        result.problems.append(f"PYNE produced {result.nan_mismatches} values where TradingView has na")
    if result.problems:
        result.status = "fail"
    return result


def _diff_text(index: int, times: list[int], theirs: float, ours: float) -> str:
    when = ""
    if index < len(times):
        try:
            when = datetime.fromtimestamp(times[index] / 1000.0, tz=UTC).date().isoformat() + " "
        except (OverflowError, OSError, ValueError):
            when = ""
    return f"bar {index} ({when}): tradingview={theirs!r} ours={ours!r}"


def _baseline_key(export: Export, column: str, fixtures: Path) -> str:
    return f"{export.path.relative_to(fixtures).as_posix()}::{column}"


def _load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonable(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _write_baseline(path: Path, results: list[HarnessResult], fixtures: Path, previous: dict[str, Any]) -> None:
    old_columns = previous.get("columns") or {}
    columns: dict[str, Any] = {}
    for harness in results:
        for column in harness.columns:
            if column.status not in {"fail", "known", "new"}:
                continue
            key = _baseline_key(harness.export, column.column, fixtures)
            short_key = f"{_harness_name(harness.export.path)}::{column.column}"
            old = old_columns.get(key) or {}
            columns[key] = {
                "reason": old.get("reason") or KNOWN_REASONS.get(short_key) or "TODO: triage",
                "compared": column.compared,
                "mismatches": column.mismatches,
                "nan_mismatches": column.nan_mismatches,
                "first_tv": column.first_tv,
                "first_ours": column.first_ours,
                "worst_rel": _jsonable(column.worst_rel),
                "first_diff": column.first_diff,
            }
    payload = {
        "schema": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "tolerance": {"rel": REL_TOL, "abs": ABS_TOL},
        "warmup": {"default": DEFAULT_WARMUP, **WARMUP_BY_HARNESS},
        "columns": dict(sorted(columns.items())),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def find_exports(fixtures: Path, glob: str | None = None, only: set[str] | None = None) -> list[Export]:
    paths: list[Path] = []
    for suffix in ("*.log", "*.csv"):
        paths.extend(fixtures.rglob(suffix))
    exports: list[Export] = []
    for path in sorted(paths):
        relative = path.relative_to(fixtures).as_posix()
        if glob and not Path(relative).match(glob):
            continue
        if only and _harness_name(path) not in only:
            continue
        exports.append(_load_export(path))
    return exports


def compare_all(
    fixtures: Path = _DEFAULT_FIXTURES,
    baseline: Path = _DEFAULT_BASELINE,
    *,
    mode: str = "interpret",
    glob: str | None = None,
    only: set[str] | None = None,
) -> list[HarnessResult]:
    previous = _load_baseline(baseline)
    known = previous.get("columns") or {}
    results: list[HarnessResult] = []
    for export in find_exports(fixtures, glob=glob, only=only):
        harness = HarnessResult(export=export)
        try:
            ours = _run_harness(export, mode)
        except Exception as exc:
            harness.error = f"{type(exc).__name__}: {exc}"
            results.append(harness)
            continue
        warmup = _warmup_for(export)
        for name, theirs in export.columns.items():
            key = _baseline_key(export, name, fixtures)
            if name not in ours:
                column = ColumnResult(
                    column=name,
                    status="fail",
                    problems=["harness did not emit this column"],
                )
            else:
                column = _compare_column(
                    name,
                    theirs,
                    ours[name],
                    warmup=warmup,
                    times=[int(bar["time"]) for bar in export.bars],
                    key=f"{_harness_name(export.path)}::{name}",
                )
            if column.status == "fail":
                entry = known.get(key)
                if entry:
                    column.status = "known"
                    column.reason = str(entry.get("reason") or "")
                else:
                    column.status = "new"
            harness.columns.append(column)
        matched = [column for column in harness.columns if column.status != "skip"]
        if len(matched) < MIN_COLUMNS:
            for column in harness.columns:
                if column.status == "pass":
                    column.status = "new"
                column.problems.append(f"only {len(matched)} columns matched; minimum is {MIN_COLUMNS}")
        results.append(harness)
    return results


def _summarize(results: list[HarnessResult]) -> dict[str, int]:
    counts = {"pass": 0, "known": 0, "new": 0, "skip": 0, "fixed": 0}
    for harness in results:
        for column in harness.columns:
            counts[column.status] = counts.get(column.status, 0) + 1
    return counts


def _report_dict(results: list[HarnessResult], fixtures: Path) -> dict[str, Any]:
    harnesses = []
    for harness in results:
        harnesses.append(
            {
                "export": harness.export.path.relative_to(fixtures).as_posix(),
                "harness": harness.export.harness.name,
                "bars": len(harness.export.bars),
                "error": harness.error,
                "columns": [
                    {
                        "column": column.column,
                        "status": column.status,
                        "compared": column.compared,
                        "mismatches": column.mismatches,
                        "nan_mismatches": column.nan_mismatches,
                        "first_tv": column.first_tv,
                        "first_ours": column.first_ours,
                        "worst_rel": _jsonable(column.worst_rel),
                        "first_diff": column.first_diff,
                        "problems": column.problems,
                        "reason": column.reason,
                    }
                    for column in harness.columns
                ],
            }
        )
    return {
        "fixtures": str(fixtures),
        "summary": _summarize(results),
        "harnesses": harnesses,
    }


def _print_report(results: list[HarnessResult], fixtures: Path, *, verbose: bool) -> None:
    counts = _summarize(results)
    total = sum(counts.values())
    _out(
        f"TradingView goldens: {len(results)} exports, {total} columns  "
        f"pass={counts['pass']} known={counts['known']} new={counts['new']} "
        f"skip={counts['skip']}"
    )
    for harness in results:
        relative = harness.export.path.relative_to(fixtures).as_posix()
        failed = [column for column in harness.columns if column.status in {"known", "new"}]
        status = "ERROR" if harness.error else ("FAIL" if failed else "PASS")
        _out(f"\n== {relative}  [{status}]  bars={len(harness.export.bars)}  columns={len(harness.columns)}")
        if harness.error:
            _out(f"   {harness.error}")
            continue
        for column in harness.columns:
            if column.status == "pass" and not verbose:
                continue
            if column.status == "skip" and not verbose:
                continue
            detail = (
                f"compared={column.compared} bad={column.mismatches} nan={column.nan_mismatches} "
                f"first={column.first_tv}/{column.first_ours} worst={column.worst_rel:.2e}"
            )
            _out(f"   {column.status.upper():5} {column.column:20} {detail}")
            if column.first_diff:
                _out(f"         {column.first_diff}")
            for problem in column.problems:
                _out(f"         - {problem}")
            if column.reason:
                _out(f"         reason: {column.reason}")


def _parse_only(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    names = {part.strip() for part in raw.split(",") if part.strip()}
    return names or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--fixtures", type=Path, default=_DEFAULT_FIXTURES, help="Fixture root (default: tests/fixtures/tv_goldens)"
    )
    parser.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE, help="Known-divergence baseline JSON")
    parser.add_argument(
        "--mode", choices=("interpret", "compile", "auto"), default="interpret", help="PYNE runtime mode"
    )
    parser.add_argument("--glob", help="Only exports whose relative path matches this glob")
    parser.add_argument("--only", help="Comma-separated harness basenames (e.g. harness_core,harness_state)")
    parser.add_argument("--strict", action="store_true", help="Fail on known divergences too")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    parser.add_argument("--verbose", action="store_true", help="Print passing columns too")
    parser.add_argument("--update-baseline", action="store_true", help="Rewrite the baseline from this run")
    args = parser.parse_args(argv)

    results = compare_all(
        args.fixtures,
        args.baseline,
        mode=args.mode,
        glob=args.glob,
        only=_parse_only(args.only),
    )
    if args.update_baseline:
        previous = _load_baseline(args.baseline)
        _write_baseline(args.baseline, results, args.fixtures, previous)
        failures = sum(
            1 for harness in results for column in harness.columns if column.status in {"fail", "known", "new"}
        )
        _out(f"wrote {args.baseline} ({failures} known divergences)")

    if args.json:
        _out(json.dumps(_report_dict(results, args.fixtures), indent=2))
    else:
        _print_report(results, args.fixtures, verbose=args.verbose)

    counts = _summarize(results)
    errors = [harness for harness in results if harness.error]
    if errors:
        return 1
    if args.strict:
        return 0 if counts["new"] == 0 and counts["known"] == 0 and counts["pass"] > 0 else 1
    return 0 if counts["new"] == 0 and counts["pass"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
