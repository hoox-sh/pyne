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

"""Unit tests for scraped-corpus source sanitization."""

from __future__ import annotations

from pynescript.ast.helper import parse, unparse
from pynescript.util.corpus_sanitize import sanitize_corpus_source


def _roundtrip(src: str) -> None:
    tree = parse(src)
    unparse(tree)


def test_strips_trailing_fmz_footer_after_fence() -> None:
    raw = """//@version=6
strategy("X", overlay=true)
plot(close)
```

> Detail

https://www.fmz.com/strategy/123

> Last Modified

2024-12-27 14:12:50
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Detail" not in cleaned
    assert "fmz.com" not in cleaned
    assert "Last Modified" not in cleaned
    assert "```" not in cleaned
    _roundtrip(cleaned)


def test_extracts_fenced_body_from_fmz_prose_wrapper() -> None:
    raw = """// set02 corpus entry
// source_repo: fmzquant-strategies
// collected: 2026-07-27

> Name

Some Strategy Title

> Author

someone

> Strategy Description

#### Overview
Lots of Chinese/English prose that is not Pine.

> Source (PineScript)

``` pinescript
//@version=6
strategy("Gold Trading RSI", overlay=true)
rsi = ta.rsi(close, 14)
plot(rsi)
```

> Detail

https://www.fmz.com/strategy/482895

> Last Modified

2025-02-27 17:28:19
"""
    cleaned = sanitize_corpus_source(raw)
    assert "strategy(\"Gold Trading RSI\"" in cleaned
    assert "ta.rsi" in cleaned
    assert "Overview" not in cleaned
    assert "Last Modified" not in cleaned
    assert "```" not in cleaned
    _roundtrip(cleaned)


def test_drops_expand_ui_stub() -> None:
    raw = """//@version=6
indicator("T")
Expand (29 lines)
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Expand" not in cleaned
    _roundtrip(cleaned)


def test_unwraps_blockquote_code_lines() -> None:
    raw = """//@version=6
indicator("T")
> plot(close)
> a = ta.sma(close, 14)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "> plot" not in cleaned
    assert "plot(close)" in cleaned
    assert "ta.sma" in cleaned
    _roundtrip(cleaned)


def test_inserts_missing_comma_between_var_decls() -> None:
    raw = """//@version=5
indicator("t")
var float a = na var float b = na, var float c = 1.0
plot(1)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "var float a = na, var float b = na" in cleaned
    _roundtrip(cleaned)


def test_preserves_annotation_markdown_inside_comments() -> None:
    """Markdown in //@function comments must stay (hover docs only)."""
    raw = """//@version=6
indicator("T")
//@function **Bold** and `code` with > quote text
//@param x The **source** series
f(x) => x + 1
plot(f(close))
"""
    cleaned = sanitize_corpus_source(raw)
    assert "**Bold**" in cleaned
    assert "`code`" in cleaned
    assert "> quote" in cleaned
    _roundtrip(cleaned)


def test_extracts_example_from_reference_docs_page() -> None:
    raw = """// source_path: TradingView/Pinescript Syntax/strategy.exit.md

> strategy.exit(id, from_entry, qty)

- It is a command to exit.

```
//@version=5
strategy(title = "simple strategy exit example")
strategy.entry("long", strategy.long, 1, when = open > high[1])
strategy.exit("exit", "long", profit = 10, loss = 5)
```
"""
    cleaned = sanitize_corpus_source(raw)
    assert "strategy.exit(\"exit\"" in cleaned
    assert "It is a command" not in cleaned
    _roundtrip(cleaned)


def test_stubs_shell_script_without_extractable_pine() -> None:
    raw = """// set03 corpus entry
// source_path: hooks/before-write.sh
#!/bin/bash
FILE_PATH="$1"
if [ -f "$FILE_PATH" ]; then
    echo "ok"
    exit 0
fi
"""
    cleaned = sanitize_corpus_source(raw)
    assert 'indicator("x")' in cleaned
    assert "#!/bin" not in cleaned
    assert "echo" not in cleaned
    _roundtrip(cleaned)


def test_stubs_pytest_module() -> None:
    raw = '''// set03 corpus entry
// source_path: tests/test_process.py
"""Tests for process_docs."""
import pytest

@pytest.fixture
def tmp_docs(tmp_path):
    return tmp_path

def test_x(tmp_docs):
    assert tmp_docs is not None
'''
    cleaned = sanitize_corpus_source(raw)
    assert 'indicator("x")' in cleaned
    assert "@pytest" not in cleaned
    _roundtrip(cleaned)


def test_extracts_pine_from_shell_heredoc() -> None:
    raw = """// set03 corpus entry
// source_path: hooks/startup.sh
#!/bin/bash
if [ ! -f projects/blank.pine ]; then
    cat > projects/blank.pine << 'EOF'
//@version=6
indicator("Blank Template", overlay=true)
plot(close)
EOF
fi
echo "done"
"""
    cleaned = sanitize_corpus_source(raw)
    assert 'indicator("Blank Template"' in cleaned
    assert "plot(close)" in cleaned
    assert "#!/bin" not in cleaned
    assert "EOF" not in cleaned
    _roundtrip(cleaned)


def test_strips_tv_docs_trademark_and_prose() -> None:
    raw = """//@version=6
indicator("Single-color candles")
plotcandle(open, high, low, close)
image

To color them green or red, we can use the following code:

Pine Script®
Copied
//@version=6
indicator("Example 2")
paletteColor = close >= open ? color.lime : color.red
plotbar(open, high, low, close, color = paletteColor)
image

Note that the color parameter accepts series color arguments.
"""
    cleaned = sanitize_corpus_source(raw)
    assert "®" not in cleaned
    assert "Pine Script" not in cleaned or "indicator(" in cleaned
    assert "Copied" not in cleaned
    assert "Note that" not in cleaned
    assert "paletteColor" in cleaned or "plotcandle" in cleaned
    _roundtrip(cleaned)


def test_strips_html_comments_and_checklist_markdown() -> None:
    raw = """//@version=6`
// set03 corpus entry
- [ ] Single line function calls
- [ ] Proper variable assignment

## Testing
<!-- Add screenshots of the indicator -->
- [ ] Code compiles without errors
"""
    cleaned = sanitize_corpus_source(raw)
    assert "<!--" not in cleaned
    assert "- [ ]" not in cleaned
    assert 'indicator("x")' in cleaned or "indicator(" in cleaned
    _roundtrip(cleaned)


def test_repairs_empty_switch_body() -> None:
    raw = """//@version=5
indicator("Inputs", overlay=true)
ma(series float source, simple int length, simple string maType) =>
    switch maType
"""
    cleaned = sanitize_corpus_source(raw)
    assert "switch maType" not in cleaned or "=>" in cleaned
    # Incomplete switch replaced with na so the function body parses
    assert "ma(" in cleaned
    _roundtrip(cleaned)


def test_preserves_real_pine_without_stubbing() -> None:
    raw = """//@version=5
indicator("RSI", overlay=false)
len = input.int(14)
plot(ta.rsi(close, len))
"""
    cleaned = sanitize_corpus_source(raw)
    assert 'indicator("x")' not in cleaned
    assert "ta.rsi" in cleaned
    _roundtrip(cleaned)


def test_closes_truncated_call_at_eof() -> None:
    """Docs scrapes often cut mid-call: ``log.info(`` / ``label.new(`` at EOF."""
    raw = """//@version=6
indicator("t")
if barstate.isconfirmed
    log.info(
"""
    cleaned = sanitize_corpus_source(raw)
    assert "log.info(na)" in cleaned
    _roundtrip(cleaned)

def test_closes_truncated_call_in_switch_arm() -> None:
    raw = """//@version=6
indicator("t")
switch
    true => label.new(
"""
    cleaned = sanitize_corpus_source(raw)
    assert "label.new(na)" in cleaned
    _roundtrip(cleaned)

def test_closes_truncated_nested_open_parens() -> None:
    raw = """//@version=6
indicator("t")
plot(math.max(
"""
    cleaned = sanitize_corpus_source(raw)
    assert "math.max(na)" in cleaned
    _roundtrip(cleaned)

def test_closes_truncated_method_definition() -> None:
    raw = """//@version=6
indicator("t")
method debugLabel(
"""
    cleaned = sanitize_corpus_source(raw)
    assert "method debugLabel() => na" in cleaned
    assert "debugLabel(na)" not in cleaned
    _roundtrip(cleaned)
