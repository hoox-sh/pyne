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

"""Backward-compatible re-export of the package Runtime host.

**Source of truth:** :mod:`pynescript.runtime` (implementation in
:mod:`pynescript.runtime.host`).

Prefer new code::

    from pynescript.runtime import Runtime

This module keeps ``from backend.runtime import Runtime`` working for the
Pro API, scripts, and existing tests. The ``sys.modules`` alias preserves
module identity so monkeypatches on ``backend.runtime`` still affect the
live host implementation.
"""

from __future__ import annotations

import sys

from pynescript.runtime import host as _host

# Same module object as pynescript.runtime.host (caches, CustomEvaluator, …).
sys.modules[__name__] = _host
