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

"""Logging functions for PineScript v6 evaluator."""

from __future__ import annotations


class Logger:
    """Simple logger for PineScript logging functions."""

    def __init__(self):
        """Initialize logger."""
        self.logs = []

    def error(self, message: str) -> None:
        """Log an error message.

        Args:
            message: The error message to log
        """
        self.logs.append(("ERROR", str(message)))

    def info(self, message: str) -> None:
        """Log an info message.

        Args:
            message: The info message to log
        """
        self.logs.append(("INFO", str(message)))

    def warning(self, message: str) -> None:
        """Log a warning message.

        Args:
            message: The warning message to log
        """
        self.logs.append(("WARNING", str(message)))

    def get_logs(self) -> list[tuple[str, str]]:
        """Get all logged messages.

        Returns:
            List of (level, message) tuples
        """
        return self.logs.copy()

    def clear(self) -> None:
        """Clear all logged messages."""
        self.logs.clear()


# Global logger instance
_logger = Logger()


def log_error(message: str) -> None:
    """Log an error message.

    In PineScript, errors are logged to the console and script execution may halt.

    Args:
        message: The error message to log
    """
    _logger.error(message)


def log_info(message: str) -> None:
    """Log an info message.

    In PineScript, info messages are logged to the console.

    Args:
        message: The info message to log
    """
    _logger.info(message)


def log_warning(message: str) -> None:
    """Log a warning message.

    In PineScript, warnings are logged to the console.

    Args:
        message: The warning message to log
    """
    _logger.warning(message)


def get_logger() -> Logger:
    """Get the global logger instance.

    Returns:
        The Logger instance
    """
    return _logger


def runtime_error(message: str) -> None:
    """Halt script execution with an error message (Pine ``runtime.error``)."""
    _logger.error(message)
    raise RuntimeError(str(message))


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
