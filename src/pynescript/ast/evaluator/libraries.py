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

"""In-process Pine Script library registry for export/import resolution.

TradingView libraries are published as ``username/LibraryName/version``.
pynescript resolves them from an in-process registry populated by:

1. Evaluating a ``library("Title")`` script (auto-registers by title)
2. Explicit ``register_library_source(namespace, name, version, source)``

Exported members (``export const``, ``export f() => ...``, exported types)
are exposed on a :class:`LibraryModule` with attribute access for
``alias.member`` resolution after ``import``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class LibraryModule:
    """A loaded library with its exported members."""

    title: str
    namespace: str | None = None
    version: int | None = None
    exports: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        # dataclass fields use normal access; only fall through for exports
        if name.startswith("_") or name in {"title", "namespace", "version", "exports"}:
            raise AttributeError(name)
        try:
            return self.exports[name]
        except KeyError as exc:
            msg = f"Library '{self.title}' has no exported member '{name}'"
            raise AttributeError(msg) from exc

    def __contains__(self, name: str) -> bool:
        return name in self.exports


class LibraryRegistry:
    """Maps library identity -> :class:`LibraryModule`."""

    def __init__(self) -> None:
        self._by_path: dict[tuple[str, str, int], LibraryModule] = {}
        self._by_title: dict[str, LibraryModule] = {}
        self._sources: dict[tuple[str, str, int], str] = {}

    def register(self, module: LibraryModule) -> None:
        """Register or replace a loaded library module."""
        self._by_title[module.title] = module
        if module.namespace is not None and module.version is not None:
            key = (module.namespace, module.title, int(module.version))
            self._by_path[key] = module

    def register_source(self, namespace: str, name: str, version: int, source: str) -> None:
        """Store Pine source for lazy load on import."""
        self._sources[(namespace, name, int(version))] = source

    def get_source(self, namespace: str, name: str, version: int) -> str | None:
        return self._sources.get((namespace, name, int(version)))

    def lookup(
        self,
        *,
        namespace: str | None = None,
        name: str,
        version: int | None = None,
    ) -> LibraryModule | None:
        """Resolve a library by path and/or title."""
        if namespace is not None and version is not None:
            mod = self._by_path.get((namespace, name, int(version)))
            if mod is not None:
                return mod
        # Title match (local evaluate_script(library(...)) without publisher path)
        return self._by_title.get(name)
