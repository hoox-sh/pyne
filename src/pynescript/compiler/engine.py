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

"""Pine → Numba compile-and-run engine.

Pipeline:
  source  →  parse  →  CompilerVisitor.transpile  →  exec  →  njit callable

Use :func:`compile_script` then :meth:`CompiledScript.run` with OHLCV arrays.
Falls back with a clear error if ``numba`` is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable

import numpy as np

from pynescript.ast.helper import parse
from pynescript.compiler.compiler import CompilerVisitor

try:
    import numba  # noqa: F401

    _HAS_NUMBA = True
except ImportError:  # pragma: no cover
    _HAS_NUMBA = False


def has_numba() -> bool:
    return _HAS_NUMBA


def transpile(source: str) -> str:
    """Parse Pine source and return generated Python/Numba source string."""
    tree = parse(source, mode="exec")
    visitor = CompilerVisitor()
    code = visitor.visit(tree)
    if not isinstance(code, str) or not code.strip():
        msg = "CompilerVisitor produced empty code"
        raise RuntimeError(msg)
    return code


@dataclass
class CompiledScript:
    """A compiled Pine script ready to run over OHLCV arrays."""

    source: str
    generated_code: str
    execute: Callable[..., Any]
    plot_titles: list[str] = field(default_factory=list)

    def run(
        self,
        open_: np.ndarray | list[float],
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
        volume: np.ndarray | list[float] | None = None,
    ) -> dict[str, np.ndarray]:
        """Execute over full series; returns plot title → float64 array."""
        o = np.asarray(open_, dtype=np.float64)
        h = np.asarray(high, dtype=np.float64)
        l = np.asarray(low, dtype=np.float64)
        c = np.asarray(close, dtype=np.float64)
        if volume is None:
            v = np.ones(len(c), dtype=np.float64)
        else:
            v = np.asarray(volume, dtype=np.float64)
        n = len(c)
        if not (len(o) == len(h) == len(l) == n == len(v)):
            msg = "OHLCV arrays must have the same length"
            raise ValueError(msg)
        raw = self.execute(o, h, l, c, v)
        return _normalize_result(raw)


def _normalize_result(raw: Any) -> dict[str, np.ndarray]:
    """Convert numba typed dict / mapping / None into plain {str: ndarray}."""
    if raw is None:
        return {}
    # numba.typed.Dict or Python dict
    out: dict[str, np.ndarray] = {}
    try:
        items = raw.items()
    except Exception:
        # single array
        return {"plot": np.asarray(raw, dtype=np.float64)}
    for k, v in items:
        key = str(k)
        out[key] = np.asarray(v, dtype=np.float64)
    return out


def compile_script(source: str) -> CompiledScript:
    """Transpile Pine source and load the Numba-compiled entry point."""
    if not _HAS_NUMBA:
        msg = "numba is required for compile mode (pip install numba)"
        raise RuntimeError(msg)

    code = transpile(source)
    # Extract plot titles from visitor by re-running visitor (cheap vs parse)
    tree = parse(source, mode="exec")
    visitor = CompilerVisitor()
    _ = visitor.visit(tree)
    titles = [p.get("title", f"Plot {i}") for i, p in enumerate(visitor.plots)]

    namespace: dict[str, Any] = {"__name__": "pynescript_compiled"}
    exec(code, namespace)  # noqa: S102 — intentional compile pipeline
    fn = namespace.get("execute_script_compiled")
    if fn is None or not callable(fn):
        msg = "generated code missing execute_script_compiled()"
        raise RuntimeError(msg)

    # Trigger JIT compile with tiny dummy data (optional warm-up)
    dummy = np.arange(5, dtype=np.float64)
    try:
        fn(dummy, dummy, dummy, dummy, dummy)
    except Exception:
        # Some scripts need longer series; ignore warm-up failures
        pass

    return CompiledScript(source=source, generated_code=code, execute=fn, plot_titles=titles)


def run_script(
    source: str,
    open_: np.ndarray | list[float],
    high: np.ndarray | list[float],
    low: np.ndarray | list[float],
    close: np.ndarray | list[float],
    volume: np.ndarray | list[float] | None = None,
) -> dict[str, np.ndarray]:
    """One-shot compile + run (re-compiles every call — prefer :func:`compile_script`)."""
    return compile_script(source).run(open_, high, low, close, volume)
