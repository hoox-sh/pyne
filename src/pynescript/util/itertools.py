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

"""Small iteration helpers used by CLI and internal tooling."""

from __future__ import annotations

from itertools import zip_longest


def grouper(iterable, n, *, incomplete="fill", fillvalue=None):
    """Chunk *iterable* into fixed-length tuples of size *n*.

    Args:
        iterable: Source values.
        n: Group size.
        incomplete: How to handle a trailing short group:
            ``"fill"`` (pad with *fillvalue*), ``"strict"`` (raise if uneven),
            or ``"ignore"`` (drop the remainder).
        fillvalue: Padding value when *incomplete* is ``"fill"``.

    Returns:
        An iterator of n-tuples (or shorter when incomplete is ignored).
    """
    args = [iter(iterable)] * n
    match incomplete:
        case "fill":
            return zip_longest(*args, fillvalue=fillvalue)
        case "strict":
            return zip(*args, strict=True)
        case "ignore":
            return zip(*args, strict=False)
        case _:
            msg = "Expected fill, strict, or ignore"
            raise ValueError(msg)
