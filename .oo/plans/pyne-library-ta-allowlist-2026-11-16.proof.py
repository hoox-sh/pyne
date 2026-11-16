# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: ta.sma/ta.ema work inside inlined library bodies; ta.rsi stays closed."""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_compiler_library_inline as t  # noqa: E402


def _run_src(src: str, lib_source: str, mode: str) -> dict[str, object]:
    return Runtime(symbol="TEST").run(
        src,
        t._bars(8),
        mode=mode,
        libraries=t._ta_libraries(lib_source),
    )


def _run(lib_source: str, mode: str) -> dict[str, object]:
    return _run_src(t._SRC_TA_LIB, lib_source, mode)


def main() -> None:
    for lib_source in (t._LIB_TA_SMA, t._LIB_TA_EMA):
        interp = _run(lib_source, "interpret")
        compiled = _run(lib_source, "compile")
        assert "error" not in interp, interp.get("error")
        assert "error" not in compiled, compiled.get("error")
        t._assert_ta_series(compiled["series"]["x"], interp["series"]["x"])  # type: ignore[index]

    closed = _run(t._LIB_TA_RSI, "compile")
    assert closed.get("error_kind") == "compile", closed
    assert "unsupported ta function ta.rsi" in str(closed.get("error") or "").lower()

    missing = _run_src(t._SRC_LIB_MISSING, t._LIB_MISSING_REQUIRED, "compile")
    assert missing.get("error_kind") == "runtime", missing
    missing_msg = str(missing.get("error") or "")
    assert "missing 1 required positional argument" in missing_msg, missing_msg
    assert "'k'" in missing_msg, missing_msg

    required_first = _run_src(t._SRC_LIB_MISSING, t._LIB_REQUIRED_BEFORE_DEFAULT, "compile")
    assert required_first.get("error_kind") == "runtime", required_first
    required_msg = str(required_first.get("error") or "")
    assert "missing 2 required positional arguments" in required_msg, required_msg
    assert "'b'" in required_msg and "'k'" in required_msg, required_msg

    print(
        "LIB_TA_OK sma=1 ema=1 unknown=fail_closed "
        "missing=typeerror required_before_default=typeerror"
    )


if __name__ == "__main__":
    main()
