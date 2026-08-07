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

"""Pine ``log.*`` and ``runtime.error`` builtins for the evaluator.

Buffers log records on a process-local :class:`Logger` for hosts and tests
to inspect after a run. ``runtime.error`` raises so bar evaluation aborts
with a clear message.

Registration
------------
:func:`register_logging_functions` injects handlers into the evaluator
dispatch map from :class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`.
"""

from __future__ import annotations

from typing import Any


class Logger:
    """In-memory log buffer for ``log.*`` builtins (ERROR / INFO / WARNING)."""

    def __init__(self):
        """Initialize logger."""
        self.logs = []

    def error(self, message: str) -> None:
        """Log an error message."""
        self.logs.append(("ERROR", str(message)))

    def info(self, message: str) -> None:
        """Log an info message."""
        self.logs.append(("INFO", str(message)))

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.logs.append(("WARNING", str(message)))

    def get_logs(self) -> list[tuple[str, str]]:
        """Get all logged messages as ``(level, message)`` tuples."""
        return self.logs.copy()

    def clear(self) -> None:
        """Clear all logged messages."""
        self.logs.clear()


# Global logger instance
_logger = Logger()


def _pine_log_arg(value: Any) -> Any:
    """Coerce a Pine value for string formatting (``na`` → ``\"na\"``)."""
    if value is None:
        return "na"
    return value


def format_log_message(*parts: Any) -> str:
    """Format a Pine ``log.*`` / ``runtime.error`` message.

    Supports:
    - single arg: ``log.info("hello")``
    - ``str.format`` style: ``log.info("x={0}", close)``
    - printf ``%`` style: ``log.info("x=%s", close)``
    - multi-arg fallback: join with spaces

    Note: bare ``str.format(*args)`` succeeds even when the template has no
    ``{…}`` placeholders (leaving ``%s`` / extra args unused). Only apply
    ``.format`` when braces are present so printf templates still work.
    """
    if not parts:
        return ""
    if len(parts) == 1:
        return str(parts[0] if parts[0] is not None else "na")
    fmt = str(parts[0] if parts[0] is not None else "")
    args = [_pine_log_arg(p) for p in parts[1:]]
    # TV primary path: str.format placeholders
    if "{" in fmt:
        try:
            return fmt.format(*args)
        except (IndexError, KeyError, ValueError):
            pass
    # printf-style (common in corpus / older scripts)
    if "%" in fmt:
        try:
            return fmt % tuple(args)
        except (TypeError, ValueError):
            pass
    # No recognized placeholders — join all parts
    return " ".join(str(a) for a in (_pine_log_arg(p) for p in parts))


def log_error(*parts: Any) -> None:
    """Log an error message (printf / format varargs supported)."""
    _logger.error(format_log_message(*parts))


def log_info(*parts: Any) -> None:
    """Log an info message (printf / format varargs supported)."""
    _logger.info(format_log_message(*parts))


def log_warning(*parts: Any) -> None:
    """Log a warning message (printf / format varargs supported)."""
    _logger.warning(format_log_message(*parts))


def get_logger() -> Logger:
    """Get the global logger instance."""
    return _logger


def runtime_error(*parts: Any) -> None:
    """Halt script execution with an error message (Pine ``runtime.error``)."""
    msg = format_log_message(*parts)
    _logger.error(msg)
    raise RuntimeError(msg)


def register_logging_functions(namespace: dict) -> None:
    """Register all logging functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    from .declarations import _as_builtin_handler

    namespace["log.error"] = _as_builtin_handler(log_error)
    namespace["log.info"] = _as_builtin_handler(log_info)
    namespace["log.warning"] = _as_builtin_handler(log_warning)
    namespace["runtime.error"] = _as_builtin_handler(runtime_error)
