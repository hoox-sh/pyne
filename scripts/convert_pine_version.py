#!/usr/bin/env python3
"""Pine Script v5 <-> v6 converter stub (plan §6 / roadmap D1).

Minimal starting point. Expand with real diff rules as needed.
"""

from __future__ import annotations

import sys
from pathlib import Path


def convert_v5_to_v6(source: str) -> str:
    """Very basic v5 to v6 adjustments (examples only)."""
    out = source
    # Example: some v5 things that changed
    # (real ones would be more; this is placeholder per plan)
    out = out.replace("study(", "indicator(")
    return out


def convert_v6_to_v5(source: str) -> str:
    """Reverse (placeholder)."""
    out = source
    out = out.replace("indicator(", "study(")
    return out


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/convert_pine_version.py <v5|v6> <file.pine>")
        sys.exit(1)
    direction = sys.argv[1]
    path = Path(sys.argv[2])
    src = path.read_text(encoding="utf-8")
    if direction == "v5":
        dst = convert_v6_to_v5(src)
    else:
        dst = convert_v5_to_v6(src)
    print(dst)


if __name__ == "__main__":
    main()
