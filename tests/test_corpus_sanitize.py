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

import re

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


def test_strips_trailing_comma_on_switch_arms() -> None:
    """Python-style trailing commas after switch arms appear in community scrapes."""
    raw = """//@version=6
indicator("t")
atrValue = ta.atr(14)
atrSL = switch syminfo.ticker
    "EURUSD" => 3.0 * atrValue,
    "USDJPY" => 2.5 * atrValue,
    => 2.0 * atrValue
plot(atrSL)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "atrValue," not in cleaned
    assert '"EURUSD" => 3.0 * atrValue' in cleaned
    _roundtrip(cleaned)


def test_strips_docs_ellipsis_and_nav_chrome() -> None:
    raw = """//@version=6
strategy("My Strategy", process_orders_on_close = true, ...)
//-------------------------------------------
...
//-------------------------------------------
label.new(bar_index, high, "Pivot High")          Next
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "..." not in cleaned
    assert "Next" not in cleaned
    assert 'strategy("My Strategy", process_orders_on_close = true)' in cleaned
    _roundtrip(cleaned)


def test_repairs_trailing_binop_and_empty_arrow_body() -> None:
    raw = """//@version=6
indicator("t")
bool isTargetHour = timeframe.isdwm or
upDownColor(float source) =>
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    # ``or`` at EOL with no indented continuation → append na; empty ``=>`` body too.
    assert "or na" in cleaned or "isdwm or na" in cleaned
    assert "upDownColor(float source) => na" in cleaned
    _roundtrip(cleaned)


def test_preserves_same_indent_and_or_chains() -> None:
    """Multi-line ``and``/``or`` at same indent must not get ``na`` injected mid-chain."""
    raw = """//@version=6
indicator("t")
gaps = td == mo and yd != su or
         td == tu and yd != mo or
         td == we and yd != tu
plot(gaps ? 1 : 0)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "or na" not in cleaned
    assert "and na" not in cleaned
    assert "td == we" in cleaned
    _roundtrip(cleaned)


def test_preserves_digit_start_arithmetic_continuation() -> None:
    """``… +`` / next ``2 * …`` (digit start) is a real continuation."""
    raw = """//@version=6
indicator("t")
var float filter = 0.0
filter :=
     pow(alpha, 2) * close +
     2 * (1 - alpha) * filter -
     pow(1 - alpha, 2) * filter
plot(filter)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "+ na" not in cleaned
    assert "- na" not in cleaned
    assert "2 * (1 - alpha)" in cleaned
    _roundtrip(cleaned)


def test_strips_docs_previous_nav_trail() -> None:
    raw = """//@version=6
indicator("t")
plot(c)         Previous       Methods      Next   Matrices
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Previous" not in cleaned
    assert "plot(c)" in cleaned
    _roundtrip(cleaned)


def test_strips_trademark_and_hair_space() -> None:
    raw = """//@version=6
strategy("x")
import foo/bar/1\u200aas lib
// Pine Script™ strategy
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "™" not in cleaned
    assert "\u200a" not in cleaned
    assert "import foo/bar/1 as lib" in cleaned or "as lib" in cleaned
    _roundtrip(cleaned)


def test_dedents_leading_indented_script() -> None:
    raw = """//@version=4
    study("My Script")
    plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert not cleaned.lstrip("/@version=4\n").startswith(" ")
    assert 'study("My Script")' in cleaned
    # first code line at column 0
    for ln in cleaned.splitlines():
        if ln.strip() and not ln.lstrip().startswith("//"):
            assert not ln[0].isspace(), repr(ln)
            break
    _roundtrip(cleaned)


def test_empty_method_body_with_annotation_gets_na() -> None:
    raw = """//@version=6
indicator("t")
method rowWiseAvg(matrix<float> this) =>
    //@variable An array of averages.
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "=>" in cleaned
    assert "na" in cleaned
    _roundtrip(cleaned)


def test_promotes_same_indent_if_else_body_from_docs() -> None:
    """Docs scrapes often omit indent under if/else — promote sibling lines."""
    raw = """//@version=6
indicator("t", "", true)
if barstate.isfirst
table.cell(t, 0, 0, "a")
else if barstate.islast
table.cell_set_text(t, 0, 0, "b")
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "    table.cell(t, 0, 0, \"a\")" in cleaned or "\ttable.cell" in cleaned
    assert "else if barstate.islast" in cleaned
    _roundtrip(cleaned)


def test_docs_nav_does_not_cut_tooltip_next_to() -> None:
    """English ``next to`` inside tooltips must not match docs ``Next`` chrome."""
    raw = """//@version=6
indicator("t")
showQ = input.bool(false, "Show Q",
     tooltip="Adds a 0-100 quality score next to each marker.")
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "next to each marker" in cleaned
    assert 'tooltip="Adds a 0-100 quality score' in cleaned
    # must not truncate mid-sentence
    assert "quality score\n" not in cleaned.split("tooltip=")[-1][:80]
    _roundtrip(cleaned)


def test_preserves_multiline_ternary_same_indent_arms() -> None:
    """Same-indent nested ternary arms must not get ``: na`` injected."""
    raw = """//@version=6
indicator("t")
ma(src, len, maType) =>
    maType == "EMA" ? ta.ema(src, len) :
    maType == "SMA" ? ta.sma(src, len) :
    maType == "WMA" ? ta.wma(src, len) : na
plot(ma(close, 14, "EMA"))
"""
    cleaned = sanitize_corpus_source(raw)
    assert ": na\n    maType" not in cleaned  # no false injection between arms
    assert 'maType == "WMA"' in cleaned
    _roundtrip(cleaned)


def test_repairs_dangling_plus_before_closer() -> None:
    """Docs scrapes cut mid-concat: ``str.tostring(a) +)``."""
    raw = """//@version=6
indicator("t")
if barstate.islast
    label.new(bar_index, 0, "a: " + str.tostring(close) +)
plot(1)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "+)" not in cleaned
    assert "str.tostring(close)" in cleaned
    _roundtrip(cleaned)


def test_repairs_truncated_typed_function_header() -> None:
    """Docs scrapes often cut after parameter list with no ``=>`` body."""
    raw = """//@version=6
strategy("t")
timeWithinAllowedRange(
     int    startTime, int endTime,
     bool   useDateFilter = true,
     string timeZone      = "GMT-0"
"""
    cleaned = sanitize_corpus_source(raw)
    assert "=> na" in cleaned
    assert "timeWithinAllowedRange(" in cleaned
    _roundtrip(cleaned)


def test_strips_expand_ui_stub_incomplete_paren() -> None:
    """Scrape cut mid-``Expand (N lines`` must not leave a bare call for the lexer."""
    raw = """//@version=6
indicator("T")
plot(close)
Expand (152 lines
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Expand" not in cleaned
    _roundtrip(cleaned)


def test_expand_after_pine_stops_trailing_chrome() -> None:
    """``Expand (N lines)`` after real code ends the script (collapsed UI residual)."""
    raw = """//@version=5
indicator("AI SuperTrend Clustering Oscillator")
hline(0, linestyle = hline.style_solid)
//-----------------------------------------------------------------------------}
Expand (152 lines)
> Detail
https://www.fmz.com/strategy/1
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Expand" not in cleaned
    assert "Detail" not in cleaned
    assert "fmz.com" not in cleaned
    assert "hline(0" in cleaned
    _roundtrip(cleaned)


def test_fmz_else_if_strategy_entry_with_fence() -> None:
    """FMZ scrapes: ``if cond`` / ``else if`` + strategy.entry + closing fence + footer."""
    raw = """//@version=5
indicator("Fukuiz Octa-EMA")
buy2 = close > open
sell2 = close < open
if buy2
    strategy.entry("Enter Long", strategy.long)
else if sell2
    strategy.entry("Enter Short", strategy.short)




```

> Detail

https://www.fmz.com/strategy/363588

> Last Modified

2022-05-16 18:21:00
"""
    cleaned = sanitize_corpus_source(raw)
    assert "```" not in cleaned
    assert "Detail" not in cleaned
    assert "Last Modified" not in cleaned
    assert 'strategy.entry("Enter Long"' in cleaned
    assert "else if sell2" in cleaned
    # body under else if must remain indented
    assert re.search(r"else if sell2\n\s+strategy\.entry", cleaned)
    _roundtrip(cleaned)


def test_fmz_else_if_pivot_strategy_entry() -> None:
    """Same FMZ pattern with ``else if ph`` (pivot trailing maxima scrape)."""
    raw = """//@version=5
indicator("Pivot Based Trailing Maxima", overlay=true)
ph = ta.pivothigh(14, 14)
pl = ta.pivotlow(14, 14)
if pl
    strategy.entry("Enter Long", strategy.long)
else if ph
    strategy.entry("Enter Short", strategy.short)
```

> Detail

https://www.fmz.com/strategy/365719
"""
    cleaned = sanitize_corpus_source(raw)
    assert "```" not in cleaned
    assert "else if ph" in cleaned
    assert 'strategy.entry("Enter Short"' in cleaned
    _roundtrip(cleaned)


def test_empty_if_under_for_in_expression_assignment() -> None:
    """Truncated loops.md demo: ``x = for …`` / empty ``if`` → collapse to ``x = na``.

    Empty-body injection alone yields a for-expression that parses but cannot be
    emitted as Python (``x = for …``). Collapse na-only control RHS to ``na``.
    """
    raw = """//@version=5
indicator("Loop keywords and variable assignment demo")
var array<int> randomArray = array.from(1, 5, 2, -3, 14, 7, 9, 8, 15, 12)
if barstate.islastconfirmedhistory
    string tempString = ""
    string finalLabelText = for number in randomArray
        // Stop the current iteration if number is 8.
        if number == 8
"""
    cleaned = sanitize_corpus_source(raw)
    assert "Expand" not in cleaned
    assert "finalLabelText = na" in cleaned
    assert "for number in randomArray" not in cleaned
    _roundtrip(cleaned)


def test_injects_na_for_empty_for_while_if_statements() -> None:
    """Bare empty for/while/if statement demos need an INDENT body (DEDENT fix)."""
    raw = """//@version=5
indicator("t")
for i = 0 to 10
while true
if close > open
plot(1)
"""
    cleaned = sanitize_corpus_source(raw)
    # empty for/while get ``na``; same-indent ``plot(1)`` is promoted under ``if``
    assert "for i = 0 to 10\n    na" in cleaned or "for i = 0 to 10\n\tna" in cleaned
    assert "while true\n    na" in cleaned or "while true\n\tna" in cleaned
    assert "plot(1)" in cleaned
    _roundtrip(cleaned)


def test_injects_na_for_empty_if_at_eof() -> None:
    """Trailing empty ``if`` / ``for`` at EOF (DEDENT expecting INDENT)."""
    raw = """//@version=5
indicator("t")
if barstate.islast
    for number in array.from(1, 2, 8)
        if number == 8
"""
    cleaned = sanitize_corpus_source(raw)
    assert "na" in cleaned
    _roundtrip(cleaned)


def test_preserves_real_for_in_expression_with_body() -> None:
    """Non-truncated expression-for with a real leaf must not collapse to na."""
    raw = """//@version=5
indicator("t")
arr = array.from(1, 2, 3)
total = for v in arr
    v + 1
plot(total)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "for v in arr" in cleaned
    assert "v + 1" in cleaned
    assert "total = na" not in cleaned
    _roundtrip(cleaned)


def test_preserves_multiline_signature_arrow_body() -> None:
    """Closing ``) =>`` deeper than body indent must not get ``=> na`` injected.

    Multi-line UDF headers commonly wrap parameters so the arrow line is indented
    further than the function body (QuanTAlib / library scrapes).
    """
    raw = """//@version=6
indicator("t")
sarext(simple float start_value = 0.0, simple float offset_on_reverse = 0.0,
       simple float af_init_long = 0.02, simple float af_long = 0.02) =>
    if af_init_long <= 0
        runtime.error("bad")
    start_value
plot(sarext(0.0, 0.0, 0.02, 0.02))
"""
    cleaned = sanitize_corpus_source(raw)
    assert ") => na" not in cleaned
    assert "=> na" not in cleaned
    assert "runtime.error" in cleaned
    _roundtrip(cleaned)


def test_preserves_export_multiline_arrow_with_region_comment() -> None:
    """``) => //{`` multi-line export with real body must not become ``=> na``."""
    raw = """//@version=5
library("NN")
export network (
     float[] inputs, float[] targets, float[] weights,
     int[] layer_sizes
     ) => //{
    // TODO: notes
    int n = array.size(inputs)
    n
//}
"""
    cleaned = sanitize_corpus_source(raw)
    assert ") => na" not in cleaned
    assert "array.size(inputs)" in cleaned
    _roundtrip(cleaned)


def test_preserves_zero_indent_call_args_inside_parens() -> None:
    """Line-wrapped ``plot(`` with zero-indent args must not become ``plot(na)``.

    TV release-notes demos intentionally show free indent inside parentheses.
    """
    raw = """//@version=6
indicator("Line wrap demo", overlay = true)
plot(
median,              // No indentation.
  "Median",          // Indented by two spaces.
   chart.fg_color,   // Indented by three spaces.
    3                // Indented by four spaces.
)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "plot(na)" not in cleaned
    assert "plot(" in cleaned
    assert "chart.fg_color" in cleaned
    _roundtrip(cleaned)


def test_preserves_multiline_string_english_content() -> None:
    """Prose-stop heuristics must not cut mid-``\"\"\"`` string (false positive).

    Content lines like ``We do not have to…`` match English-prose patterns that
    formerly ended the script and left an unclosed triple-quoted string.
    """
    raw = '''//@version=6
indicator("Multiline string demo")
string multilineStr = """This is a multiline string.
Each of these code lines literally represents a separate line of text.
The newline character is automatically included before each new line.
We do not have to manually add the `\\\\n` escape sequence to separate the lines."""
if barstate.isfirst
    log.info(multilineStr)
'''
    cleaned = sanitize_corpus_source(raw)
    assert '"""' in cleaned
    assert cleaned.count('"""') >= 2
    assert "We do not have to manually" in cleaned
    assert "log.info(multilineStr)" in cleaned
    _roundtrip(cleaned)


def test_still_injects_na_for_empty_arrow_at_eof() -> None:
    """Empty ``f() =>`` at EOF (truncated) still gets ``na`` body."""
    raw = """//@version=6
indicator("t")
upDownColor(float source) =>
"""
    cleaned = sanitize_corpus_source(raw)
    assert "upDownColor(float source) =>" in cleaned
    assert re.search(r"=>\s*(na|\n\s+na)", cleaned)
    _roundtrip(cleaned)
