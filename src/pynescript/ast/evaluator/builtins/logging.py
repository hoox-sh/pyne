# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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


def register_logging_functions(namespace: dict) -> None:
    """Register all logging functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["log.error"] = log_error
    namespace["log.info"] = log_info
    namespace["log.warning"] = log_warning
