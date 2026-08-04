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

Install the latest release from PyPI. The **distribution name is `pyne`**; the import package and CLIs remain `pynescript` / `pynescript-lsp`:

```console
pip install pyne
pip install "pyne[lsp]"    # language server
pip install "pyne[data]"   # ccxt market data
```

Do not install `hoox-pyne` or the unrelated upstream PyPI package named `pynescript` for this stack.

To work from a local checkout, install Hatch and activate the project environment with `hatch shell`, or `pip install -e ".[lsp]"`.

Prefer **`.pyne`** for HOOX / PYNE stack sources (`.pine` still works).

## Command-Line Interface

Pynescript ships a CLI that mirrors the helper functions in `pynescript.ast.helper`:

- `parse-and-dump` prints a formatted AST for a Pine Script™ input.
- `parse-and-unparse` round-trips a script to verify formatting stability.
- `lint` runs the static linter.
- `data` fetches sample OHLCV via providers (`mock`, `yahoo`, `ccxt`, …).
- `download-builtin-scripts` downloads TradingView® reference scripts used in tests.

```console
pynescript parse-and-dump path/to/script.pyne
pynescript lint path/to/script.pyne
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

## Evaluate (bar loop)

Expression evaluation:

```python
from pynescript.ast.helper import literal_eval

literal_eval("ta.sma([1,2,3,4,5], 3)")
```

Multi-bar evaluate (monorepo / Pro API host) uses `backend.runtime.Runtime` or `POST /run` with `mode` ∈ `auto` | `interpret` | `compile`. HTTP defaults to **`auto`**. Responses may include `series`, `plot_meta`, `events`, `drawings`, and `alerts` (plus optional L2 webhooks via `webhook_url` / `ALERT_WEBHOOK_URL`). See product docs under `docs/pyne/enduser/`.

Interpret ↔ compile plot parity harness:

```console
python scripts/compare_interp_compile.py --bars 1000 --limit 50
```

For more worked examples check the `examples/` directory and the regression tests under `tests/`.
