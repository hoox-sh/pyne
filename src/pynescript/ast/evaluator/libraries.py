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

1. Evaluating a ``library("Title")`` script (auto-registers by title via
   :meth:`~.statements.StatementEvaluator.visit_Script`)
2. Explicit ``register_library_source(namespace, name, version, source)``
   on the evaluator (lazy load on first matching ``import``)

Exported members (``export const``, ``export f() => ...``, exported types)
live on :class:`LibraryModule.exports` and resolve as ``alias.member`` after
``import`` binds the module into ``context``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any


def _coerce_stub_int(value: Any) -> int | None:
    """Best-effort int for stub polyfills; ``None`` / non-numeric → ``None``."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        return int(value)
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _merge_stub_args(
    args: tuple[Any, ...] | list[Any],
    kwargs: dict[str, Any],
    order: list[str],
) -> list[Any]:
    """Merge positional + keyword args into a dense list using *order* names."""
    merged: list[Any] = list(args)
    for key, val in kwargs.items():
        if key not in order:
            continue
        idx = order.index(key)
        while len(merged) <= idx:
            merged.append(None)
        if idx < len(args) and args[idx] is not None:
            continue
        merged[idx] = val
    return merged


def _stub_index_2d_to_1d(*args: Any, **kwargs: Any) -> int | None:
    """Row-major flatten: ``index_x * dimension_y + index_y`` (ArrayExtension).

    Matches compiler polyfill and RicardoSantos/ArrayExtension export so
    corpus scripts that ``import …/ArrayExtension`` without a registered
    source still feed valid indices into ``array.get`` / ``array.set``.
    """
    order = ["dimension_x", "dimension_y", "index_x", "index_y"]
    # Accept common aliases used in demos / older libs
    alias = {
        "dim_x": "dimension_x",
        "dim_y": "dimension_y",
        "ix": "index_x",
        "iy": "index_y",
    }
    norm_kw = {alias.get(k, k): v for k, v in kwargs.items()}
    vals = _merge_stub_args(args, norm_kw, order)
    if len(vals) < 4:
        return None
    _dx = _coerce_stub_int(vals[0])
    dy = _coerce_stub_int(vals[1])
    ix = _coerce_stub_int(vals[2])
    iy = _coerce_stub_int(vals[3])
    if dy is None or ix is None or iy is None:
        return None
    return ix * dy + iy


def _stub_index_1d_to_2d(*args: Any, **kwargs: Any) -> tuple[int, int] | None:
    """Inverse of :func:`_stub_index_2d_to_1d` → ``(index_x, index_y)``."""
    order = ["dimension_x", "dimension_y", "index"]
    alias = {"dim_x": "dimension_x", "dim_y": "dimension_y", "i": "index"}
    norm_kw = {alias.get(k, k): v for k, v in kwargs.items()}
    vals = _merge_stub_args(args, norm_kw, order)
    if len(vals) < 3:
        return None
    _dx = _coerce_stub_int(vals[0])
    dy = _coerce_stub_int(vals[1])
    idx = _coerce_stub_int(vals[2])
    if dy is None or idx is None or dy == 0:
        return None
    return idx // dy, idx % dy


# Known export polyfills for unresolved remote libraries (import stubs).
# Name → callable used when ``alias.member(...)`` hits a soft import stub.
STUB_KNOWN_EXPORTS: dict[str, Callable[..., Any]] = {
    "index_2d_to_1d": _stub_index_2d_to_1d,
    "index_1d_to_2d": _stub_index_1d_to_2d,
}


@dataclass
class LibraryModule:
    """A loaded library: title/path identity plus exported callables and values.

    Attribute access (``mod.member``) reads :attr:`exports` only; missing
    members raise :class:`AttributeError`.
    """

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
    """Maps library identity (path and/or title) → :class:`LibraryModule`.

    Also holds raw Pine source for path-keyed lazy loads
    (:meth:`register_source` / :meth:`get_source`).
    """

    def __init__(self) -> None:
        self._by_path: dict[tuple[str, str, int], LibraryModule] = {}
        self._by_title: dict[str, LibraryModule] = {}
        self._sources: dict[tuple[str, str, int], str] = {}

    def register(self, module: LibraryModule) -> None:
        """Register or replace a loaded library (by title and path when known)."""
        self._by_title[module.title] = module
        if module.namespace is not None and module.version is not None:
            key = (module.namespace, module.title, int(module.version))
            self._by_path[key] = module

    def register_source(self, namespace: str, name: str, version: int, source: str) -> None:
        """Store Pine source for lazy load on ``import namespace/name/version``."""
        self._sources[(namespace, name, int(version))] = source

    def get_source(self, namespace: str, name: str, version: int) -> str | None:
        """Return registered source text, or ``None`` if unknown."""
        return self._sources.get((namespace, name, int(version)))

    def lookup(
        self,
        *,
        namespace: str | None = None,
        name: str,
        version: int | None = None,
    ) -> LibraryModule | None:
        """Resolve by ``(namespace, name, version)`` path first, then by title."""
        if namespace is not None and version is not None:
            mod = self._by_path.get((namespace, name, int(version)))
            if mod is not None:
                return mod
        # Title match (local evaluate_script(library(...)) without publisher path)
        return self._by_title.get(name)
