#!/usr/bin/env python
"""Simple test runner without pytest plugin conflicts."""

from __future__ import annotations

import subprocess
import sys

# Run tests directly with Python's unittest discovery
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
    ],
    check=False,
)
sys.exit(result.returncode)
