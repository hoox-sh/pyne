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

"""Small on-disk Pine workspace index for ``workspace/symbol``.

Open buffers are always indexed by :class:`~pynescript.langserver.workspace.Workspace`.
This module adds closed files under the client's workspace folders so
``Ctrl+T`` can find functions/types/variables in a project without opening
every script. It is intentionally bounded:

* only Pine extensions,
* ignore VCS/build/dependency directories,
* max files and max file size,
* parse results cached by ``(mtime_ns, size)``.

References/rename still operate on open documents; cross-file semantic edits
need a conflict-aware refactor and are future work.
"""

from __future__ import annotations

import os
import threading
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from lsprotocol import types as lsp

from pynescript.ast.helper import parse
from pynescript.langserver.features.symbols import collect_workspace_symbols


PINE_SUFFIXES = frozenset({".pyne", ".pine", ".pinev5", ".pinev6", ".pinescript"})
_IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".turbo",
    }
)


@dataclass
class _FileEntry:
    path: Path
    mtime_ns: int
    size: int
    symbols: list[lsp.SymbolInformation]


class WorkspaceIndex:
    """Bounded, mtime-cached index of Pine files under workspace roots."""

    def __init__(
        self,
        roots: list[Path] | None = None,
        *,
        max_files: int = 5000,
        max_bytes: int = 1_000_000,
    ) -> None:
        self.roots = roots or []
        self.max_files = max_files
        self.max_bytes = max_bytes
        self._cache: dict[Path, _FileEntry] = {}
        self._lock = threading.Lock()
        self._paths: list[Path] | None = None

    def set_roots(self, roots: list[Path]) -> None:
        """Replace roots and drop the scanned path list."""
        self.roots = roots
        with self._lock:
            self._paths = None

    def invalidate(self, path: Path | None = None) -> None:
        """Drop one cache entry (or all entries) after a file event."""
        with self._lock:
            if path is None:
                self._cache.clear()
            else:
                self._cache.pop(path, None)
            # A create/delete can change the scanned path list; a rename can
            # change a cached path. Rescan lazily on the next search.
            self._paths = None

    def search(
        self,
        query: str,
        *,
        limit: int = 200,
        max_scan_files: int = 400,
        deadline_seconds: float = 2.0,
    ) -> list[lsp.SymbolInformation]:
        """Search closed files for symbols whose name contains *query*.

        A search is an explicit user action, but still bounded: parsing an
        arbitrarily large repository must not freeze the editor for minutes.
        Cached files are cheap; uncached files stop after *max_scan_files* or
        *deadline_seconds*.
        """
        needle = query.lower()
        results: list[lsp.SymbolInformation] = []
        deadline = time.monotonic() + deadline_seconds
        scanned = 0
        for path in self._iter_paths():
            with self._lock:
                cached = self._cache.get(path)
            if cached is None:
                scanned += 1
                if scanned > max_scan_files or time.monotonic() > deadline:
                    break
            entry = self._entry_for(path)
            if entry is None:
                continue
            for symbol in entry.symbols:
                if needle in symbol.name.lower():
                    results.append(symbol)
                    if len(results) >= limit:
                        return results
        return results

    def _iter_paths(self) -> list[Path]:
        with self._lock:
            if self._paths is not None:
                return self._paths
        paths: list[Path] = []
        for root in self.roots:
            if not root.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [
                    name
                    for name in dirnames
                    if name not in _IGNORED_DIRS and not name.startswith(".")
                ]
                for filename in filenames:
                    if Path(filename).suffix.lower() not in PINE_SUFFIXES:
                        continue
                    path = Path(dirpath) / filename
                    try:
                        if path.stat().st_size > self.max_bytes:
                            continue
                    except OSError:
                        continue
                    paths.append(path)
                    if len(paths) >= self.max_files:
                        break
                if len(paths) >= self.max_files:
                    break
            if len(paths) >= self.max_files:
                break
        with self._lock:
            self._paths = paths
        return paths

    def _entry_for(self, path: Path) -> _FileEntry | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        with self._lock:
            cached = self._cache.get(path)
            if cached is not None and cached.mtime_ns == stat.st_mtime_ns and cached.size == stat.st_size:
                return cached
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        try:
            tree = parse(source, filename=str(path))
        except Exception:
            # Cache the failure by mtime so a search does not reparse the same
            # broken file on every query.
            entry = _FileEntry(path=path, mtime_ns=stat.st_mtime_ns, size=stat.st_size, symbols=[])
            with self._lock:
                self._cache[path] = entry
            return entry
        symbols = _symbols_for(tree, source, path)
        entry = _FileEntry(path=path, mtime_ns=stat.st_mtime_ns, size=stat.st_size, symbols=symbols)
        with self._lock:
            self._cache[path] = entry
        return entry


def _symbols_for(tree: Any, source: str, path: Path) -> list[lsp.SymbolInformation]:
    uri = _path_to_uri(path)
    doc = type("_IndexedDoc", (), {"valid_ast": tree, "source": source})()
    return collect_workspace_symbols(doc, uri)


def _path_to_uri(path: Path) -> str:
    try:
        return path.as_uri()
    except ValueError:
        return "file://" + quote(str(path))


__all__ = ["PINE_SUFFIXES", "WorkspaceIndex"]
