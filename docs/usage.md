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

# Usage

## Installation

Install the latest release from PyPI:

```console
pip install pynescript
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
