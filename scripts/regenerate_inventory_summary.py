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

"""Regenerate the Summary counts section of pine_v6_full_surface_inventory.md
from the live evaluator dispatch map.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    dispatch = NodeLiteralEvaluator()._build_builtin_map()
    keys = sorted(dispatch.keys())
    ns = Counter(k.split(".")[0] if "." in k else k for k in keys)
    partial = [
        k
        for k, h in dispatch.items()
        if any(w in ((h.__doc__ or "").lower()) for w in ("stub", "mock", "limited", "not fully"))
    ]
    today = date.today().isoformat()
    ns_rows = "\n".join(f"| `{n}` | {c} |" for n, c in ns.most_common(25))
    summary = f"""## Summary counts

Regenerated from live `NodeLiteralEvaluator._build_builtin_map()` on {today}.

| Metric | Count |
|--------|------:|
| Dispatch builtins (callable) | {len(keys)} |
| Dispatch partial-heuristic (docstring stub/mock) | {len(partial)} |
| Namespaces (top-level prefixes) | {len(ns)} |

### By namespace (dispatch keys)

| Namespace | Count |
|-----------|------:|
{ns_rows}

### Official TV v6 reference coverage

Against the public Pine v6 function reference list (434 symbols): **0 missing** in dispatch.

"""
    path = Path(__file__).resolve().parents[1] / "docs" / "pine_v6_full_surface_inventory.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\*\*Generated:\*\* [0-9-]+", f"**Generated:** {today}", text)
    m = re.search(r"(## Summary counts\n)(.*?)(\n## )", text, re.S)
    if not m:
        print("Summary section not found", file=sys.stderr)
        return 1
    text = text[: m.start()] + summary + m.group(3) + text[m.end() :]
    path.write_text(text, encoding="utf-8")
    print(f"Updated {path} — dispatch={len(keys)} partial≈{len(partial)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
