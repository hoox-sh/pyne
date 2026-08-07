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

# Agent 09 — Collections / strings

| Field | Value |
| --- | --- |
| **Role / ID** | 09 — collections / strings |
| **Verdict** | **win** (goldens landed; soft-na expanded) |
| **Date** | 2026-08-04 |

## Files

| Path | Role |
| --- | --- |
| `builtins/arrays.py` | Negative indices, soft paths |
| `builtins/matrix_evaluator.py` | Region / soft semantics |
| `builtins/map.py` + `map_evaluator.py` | Soft map ops |
| `builtins/strings.py` | match / pos / soft-na |
| `tests/test_corpus_collections_r8.py` | Runtime goldens |
| `tests/test_collections.py` | Expanded unit cases |

## Intentional non-goals

Do **not** soft-suppress library `runtime.error` validation demos (R7 residual 6).

## Tests

`tests/test_corpus_collections_r8.py` + `tests/test_collections.py` (included in
R8 focused suite).
