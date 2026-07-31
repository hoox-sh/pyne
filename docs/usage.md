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

# Usage

## Installation

Install the latest release from PyPI:

```console
pip install hoox-pyne
```

To work from a local checkout, install Hatch and activate the project environment with `hatch shell`.

## Command-Line Interface

Pynescript ships a CLI that mirrors the helper functions in `pynescript.ast.helper`:

- `parse-and-dump` prints a formatted AST for a Pine Script™ input.
- `parse-and-unparse` round-trips a script to verify formatting stability.
- `download-builtin-scripts` downloads TradingView® reference scripts used in tests.

```console
pynescript parse-and-dump path/to/script.pine
```

```{eval-rst}
.. click:: pynescript.__main__:cli
    :prog: pynescript
    :nested: full
```

## Library Quickstart

```{literalinclude} ../examples/parse_dump_unparse.py
---
language: python
---
```

## Walking The AST

```{literalinclude} ../examples/execute_script.py
---
language: python
---
```

For more worked examples check the `examples/` directory and the regression tests under `tests/`.

````
