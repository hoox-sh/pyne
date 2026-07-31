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

"""Pine Script → Numba / object-mode compile pipeline.

This package is the **compile** path alternative to the AST evaluator
(``mode="interpret"``). It lowers Pine to a bar-loop Python module, optionally
JITs with Numba nopython, and runs over full OHLCV arrays.

Public surface
--------------
- :func:`compile_script` / :func:`transpile` / :func:`run_script` — entry points
  (implemented in :mod:`pynescript.compiler.engine`).
- :class:`CompiledScript` — handle with ``.run(open, high, low, close, volume?)``
  returning a plot-title → series dict (plus object-mode extras).
- :class:`CompilerVisitor` — AST → source emitter (numeric or object backend).
- :func:`has_numba` / :func:`clear_compile_cache` — capability and cache control.

Interpret vs compile
--------------------
- **Interpret** (evaluator): walks the AST per bar with full Pine semantics
  (UDT, map, drawing, strategy, libraries). Flexible; slower.
- **Compile**: one-shot transpile → ``execute_script_compiled(...)``. Pure
  numeric scripts use ``@numba.njit``; UDT/map/drawing/strategy force a pure-
  Python bar loop (object mode). nopython warm-up failures automatically
  re-emit object mode so ``mode="compile"`` still runs.

Supporting modules (not re-exported here)
-----------------------------------------
- :mod:`pynescript.compiler.numba_builtins` — star-imported runtime helpers
  (njit TA kernels, object-mode ``safe_*`` / matrix / ``na_num``).
- :mod:`pynescript.compiler.strategy_broker` — :class:`CompileStrategyBroker`
  used only by object-mode strategy emission.
"""

from __future__ import annotations

from .compiler import CompilerVisitor
from .engine import CompileEmitError
from .engine import CompileError
from .engine import CompileLoadError
from .engine import CompileNumbaRequiredError
from .engine import CompiledScript
from .engine import clear_compile_cache
from .engine import clear_disk_compile_cache
from .engine import compile_cache_stats
from .engine import compile_script
from .engine import has_numba
from .engine import prewarm_numba_builtins
from .engine import run_script
from .engine import transpile

__all__ = [
    "CompileEmitError",
    "CompileError",
    "CompileLoadError",
    "CompileNumbaRequiredError",
    "CompiledScript",
    "CompilerVisitor",
    "clear_compile_cache",
    "clear_disk_compile_cache",
    "compile_cache_stats",
    "compile_script",
    "has_numba",
    "prewarm_numba_builtins",
    "run_script",
    "transpile",
]
