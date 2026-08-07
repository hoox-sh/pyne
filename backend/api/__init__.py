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

"""HTTP API blueprints for the Pro API (beyond core ``/run`` routes).

Submodules:

- :mod:`backend.api.preview` — chart thumbnails and quick backtests (keyed)
- :mod:`backend.api.lsp_http` — free completion/hover for AXIS (browser LSP)
- :mod:`backend.api.git_oauth` — GitHub/GitLab device OAuth proxy for AXIS Connect
"""

from __future__ import annotations
