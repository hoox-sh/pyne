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

"""Package version (single source of truth).

:data:`__version__` is read by Hatch (``[tool.hatch.version]``), re-exported
from :mod:`pynescript`, and used as the Language Server ``version`` string in
:class:`~pynescript.langserver.server.PynescriptLanguageServer`.

Bump this string when releasing; do not hardcode versions elsewhere for the
package identity.
"""

from __future__ import annotations


__version__ = "0.3.14"
