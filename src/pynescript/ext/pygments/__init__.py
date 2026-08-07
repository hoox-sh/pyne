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

"""Pygments syntax highlighting for Pine Script.

:class:`~pynescript.ext.pygments.lexers.PinescriptLexer` maps ANTLR4 tokens
to Pygments token types for docs, Sphinx, and code viewers. Import from
:mod:`pynescript.ext.pygments.lexers` or register via Pygments plugin entry
points when packaged.
"""

from __future__ import annotations
