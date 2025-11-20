# Copyright 2024-2025 jango_blockchained
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

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class PlottingFunctionsMixin(BuiltinDispatchMixin):
    """Plotting function stubs for Pine Script compatibility."""

    def _plotting_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "plot": self._builtin_plot,
            "plotarrow": self._builtin_plotarrow,
            "plotbar": self._builtin_plotbar,
            "plotcandle": self._builtin_plotcandle,
            "plotchar": self._builtin_plotchar,
            "plotshape": self._builtin_plotshape,
            "fill": self._builtin_fill,
            "bgcolor": self._builtin_bgcolor,
            "barcolor": self._builtin_barcolor,
            "hline": self._builtin_hline,
        }

    def _builtin_plot(self, _args: list[Any]) -> None:
        """Stub: plot(series, title, color, linewidth, style, trackprice)."""
        # In Pine Script, plot() returns None and has side effects on the chart
        # This is a stub that accepts the arguments but does nothing
        return None

    def _builtin_plotarrow(self, _args: list[Any]) -> None:
        """Stub: plotarrow(series, title, colorup, colordown, offset,
        minHeight, maxHeight)."""
        return None

    def _builtin_plotbar(self, _args: list[Any]) -> None:
        """Stub: plotbar(open, high, low, close, title, color,
        editable, show_last)."""
        return None

    def _builtin_plotcandle(self, _args: list[Any]) -> None:
        """Stub: plotcandle(open, high, low, close, title, color,
        editable, show_last, wickcolor, bordercolor)."""
        return None

    def _builtin_plotchar(self, _args: list[Any]) -> None:
        """Stub: plotchar(series, title, char, location, color, offset,
        size, editable, show_last)."""
        return None

    def _builtin_plotshape(self, _args: list[Any]) -> None:
        """Stub: plotshape(series, title, style, location, color,
        offset, text, editable, show_last)."""
        return None

    def _builtin_fill(self, _args: list[Any]) -> None:
        """Stub: fill(plot1, plot2, color, title, editable, show_last)."""
        return None

    def _builtin_bgcolor(self, _args: list[Any]) -> None:
        """Stub: bgcolor(color, title, editable, show_last)."""
        return None

    def _builtin_barcolor(self, _args: list[Any]) -> None:
        """Stub: barcolor(color, offset, editable, show_last)."""
        return None

    def _builtin_hline(self, _args: list[Any]) -> None:
        """Stub: hline(price, title, color, linestyle, linewidth)."""
        return None
