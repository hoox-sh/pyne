# Pynescript

[![PyPI](https://img.shields.io/pypi/v/pynescript.svg)][pypi]
[![Python Version](https://img.shields.io/pypi/pyversions/pynescript)][python-version]
[![License](https://img.shields.io/pypi/l/pynescript)][license]
[![Docs](https://img.shields.io/readthedocs/pynescript/latest.svg?label=docs)][docs]

> Parse, analyse, and regenerate TradingView Pine Script with a modern Python toolchain.

After years of experimentation the upstream project stalled. This fork now serves as the primary development home—focused on complete Pine Script compatibility, richer tooling, and open collaboration.

## Why Pynescript?

- End-to-end Pine Script pipeline: parse, inspect, transform, and unparse with a single library.
- Battle-tested fixtures that mirror TradingView's built-in indicators to guarantee regressions surface quickly.
- Batteries-included CLI for quick experimentation plus low-level APIs when you need to hack on the AST.

## Quickstart

### Install

```console
pip install pynescript
```

### CLI

```console
pynescript parse-and-dump path/to/script.pine
```

### Library

```python
from pynescript.ast.helper import parse, dump, unparse

with open("path/to/script.pine", encoding="utf-8") as handle:
    text = handle.read()

tree = parse(text)
print(dump(tree)[:400])  # take a peek at the AST
print(unparse(tree))     # round-trip back to Pine Script
```

## Example Output

Given a Pine Script strategy:

```pinescript
//@version=5
strategy("RSI Strategy", overlay=true)
length = input(14)
overSold = input(30)
overBought = input(70)
price = close
vrsi = ta.rsi(price, length)
co = ta.crossover(vrsi, overSold)
cu = ta.crossunder(vrsi, overBought)
if not na(vrsi)
    if co
        strategy.entry("RsiLE", strategy.long, comment="RsiLE")
    if cu
        strategy.entry("RsiSE", strategy.short, comment="RsiSE")
```

Running `pynescript parse-and-dump rsi_strategy.pine` yields a rich Python AST describing the script, while `pynescript parse-and-unparse` faithfully round-trips it.

## CLI Commands

- `parse-and-dump` — parse Pine Script and print a structured AST.
- `parse-and-unparse` — round-trip Pine Script to normalise style or validate compatibility.
- `download-builtin-scripts` — cache TradingView built-ins locally for testing.

For more automation ideas, see the scripts in `examples/`.

## Project Layout

```text
examples/          # Minimal scripts that demonstrate the library
src/pynescript/    # Core parser, evaluator, transformer, and CLI code
tests/             # Regression fixtures and behavioural tests
docs/              # Sphinx documentation that mirrors the README
```

## Documentation

Extended guides live at [pynescript.readthedocs.io][docs]. Start with `usage` for CLI walkthroughs and `reference` for API details.

## Roadmap

- Ship full Pine Script v5 grammar coverage and keep fixtures synced with TradingView.
- Expand the evaluator to support deterministic execution of more built-in functions.
- Publish architecture notes for contributors and flesh out transformer recipes.

## Contributing

We welcome issues, discussions, and pull requests. Check open tasks in the project board, run `hatch run lint:style` and `hatch run test:test` before submitting, and describe how you validated your changes.

## License

Distributed under the terms of the [LGPL 3.0 license][license].

## Support & Feedback

If you spot a bug or need a feature, please [open an issue][issues]. For real-time chat, join the community discussions once they launch.

[pypi]: https://pypi.org/project/pynescript/
[python-version]: https://pypi.org/project/pynescript
[license]: https://github.com/jango-blockchained/pynescript/blob/main/LICENSE
[docs]: https://pynescript.readthedocs.io/
[issues]: https://github.com/jango-blockchained/pynescript/issues

<!-- github-only -->