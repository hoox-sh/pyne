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

"""Color functions for PineScript v6 evaluator."""

from __future__ import annotations


# Hex color string lengths
HEX_COLOR_SHORT_LEN = 6
HEX_COLOR_LONG_LEN = 8


class Color:
    """Represents an RGBA color."""

    def __init__(self, r: int, g: int, b: int, a: int = 255):
        """Initialize a color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            a: Alpha/transparency component (0-255, where 0 is transparent)
        """
        self.r = max(0, min(255, int(r)))
        self.g = max(0, min(255, int(g)))
        self.b = max(0, min(255, int(b)))
        self.a = max(0, min(255, int(a)))

    def to_hex(self) -> str:
        """Convert color to hex string.

        Returns:
            Hex color string (e.g., "#FF0000")
        """
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}{self.a:02X}"

    def to_rgba(self) -> str:
        """Convert color to rgba string.

        Returns:
            RGBA string (e.g., "rgba(255, 0, 0, 1.0)")
        """
        alpha_01 = self.a / 255.0
        return f"rgba({self.r}, {self.g}, {self.b}, {alpha_01})"

    def __repr__(self) -> str:
        """Return string representation."""
        return self.to_hex()

    def __str__(self) -> str:
        """Return string representation."""
        return self.to_hex()

    def __eq__(self, other: object) -> bool:
        """Check equality with another color."""
        if not isinstance(other, Color):
            return NotImplemented
        return (
            self.r == other.r
            and self.g == other.g
            and self.b == other.b
            and self.a == other.a
        )

    def __hash__(self) -> int:
        """Return hash for the color."""
        return hash((self.r, self.g, self.b, self.a))


def color_new(
    color: int | str,
    transp: int | None = None,
) -> Color:
    """Create a new color with optional transparency.

    Args:
        color: Color value as integer or hex string
        transp: Transparency percentage (0-100, where 100 is fully transparent)

    Returns:
        Color object
    """
    if isinstance(color, str):
        # Parse hex color string
        color_str = color.lstrip("#")
        if len(color_str) == HEX_COLOR_SHORT_LEN:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
            a = 255
        elif len(color_str) == HEX_COLOR_LONG_LEN:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
            a = int(color_str[6:8], 16)
        else:
            msg = f"Invalid hex color: {color}"
            raise ValueError(msg)
    else:
        # Parse integer color (RGBA format)
        color_int = int(color)
        r = (color_int >> 24) & 0xFF
        g = (color_int >> 16) & 0xFF
        b = (color_int >> 8) & 0xFF
        a = color_int & 0xFF

    # Apply transparency if specified
    if transp is not None:
        transp_val = max(0, min(100, int(transp)))
        a = int(255 * (1.0 - transp_val / 100.0))

    return Color(r, g, b, a)


def color_r(c: Color) -> int:
    """Get the red component of a color.

    Args:
        c: Color object

    Returns:
        Red component (0-255)
    """
    if not isinstance(c, Color):
        msg = f"Expected Color, got {type(c).__name__}"
        raise TypeError(msg)
    return c.r


def color_g(c: Color) -> int:
    """Get the green component of a color.

    Args:
        c: Color object

    Returns:
        Green component (0-255)
    """
    if not isinstance(c, Color):
        msg = f"Expected Color, got {type(c).__name__}"
        raise TypeError(msg)
    return c.g


def color_b(c: Color) -> int:
    """Get the blue component of a color.

    Args:
        c: Color object

    Returns:
        Blue component (0-255)
    """
    if not isinstance(c, Color):
        msg = f"Expected Color, got {type(c).__name__}"
        raise TypeError(msg)
    return c.b


def color_t(c: Color) -> int:
    """Get the transparency of a color.

    Args:
        c: Color object

    Returns:
        Transparency value (0-100, where 100 is fully transparent)
    """
    if not isinstance(c, Color):
        msg = f"Expected Color, got {type(c).__name__}"
        raise TypeError(msg)
    transp_percent = int((1.0 - c.a / 255.0) * 100)
    return max(0, min(100, transp_percent))


def color_rgb(r: int, g: int, b: int, a: int = 255) -> Color:
    """Create a color from RGB(A) components.

    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        a: Alpha component (0-255, default 255 for opaque)

    Returns:
        Color object
    """
    return Color(r, g, b, a)


def color_from_gradient(
    value: float,
    min_val: float,
    max_val: float,
    color1: Color,
    color2: Color,
) -> Color:
    """Create a color gradient between two colors.

    Interpolates linearly between two colors based on the value position
    between min_val and max_val.

    Args:
        value: The value to interpolate
        min_val: Minimum value (maps to color1)
        max_val: Maximum value (maps to color2)
        color1: Start color
        color2: End color

    Returns:
        Interpolated Color object
    """
    if not isinstance(color1, Color) or not isinstance(color2, Color):
        msg = "color1 and color2 must be Color objects"
        raise TypeError(msg)

    # Normalize value to 0-1 range
    if max_val == min_val:
        ratio = 0.0
    else:
        ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0.0, min(1.0, ratio))

    # Interpolate each component
    r = int(color1.r + (color2.r - color1.r) * ratio)
    g = int(color1.g + (color2.g - color1.g) * ratio)
    b = int(color1.b + (color2.b - color1.b) * ratio)
    a = int(color1.a + (color2.a - color1.a) * ratio)

    return Color(r, g, b, a)


def register_color_functions(namespace: dict) -> None:
    """Register all color functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["color.new"] = color_new
    namespace["color.r"] = color_r
    namespace["color.g"] = color_g
    namespace["color.b"] = color_b
    namespace["color.t"] = color_t
    namespace["color.rgb"] = color_rgb
    namespace["color.from_gradient"] = color_from_gradient
    namespace["color"] = color_new  # color() is an alias for color.new()
