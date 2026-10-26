# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pynescript.util import corpus_sanitize as cs
from pynescript.util.corpus_sanitize import sanitize_corpus_source


def test_normalize_chrome_and_html_comments() -> None:
    raw = "a <!-- hide --> b® c™"
    out = cs._normalize_chrome(raw)
    assert "<!--" not in out
    assert "®" not in out
    assert "™" not in out
    assert "a" in out and "b" in out


def test_strip_line_chrome_drops_ui_noise() -> None:
    assert cs._strip_line_chrome("Expand (12 lines)") is None
    assert cs._strip_line_chrome("---") is None
    assert cs._strip_line_chrome("https://example.com/x") is None
    assert cs._strip_line_chrome("![img](https://x)") is None
    assert cs._strip_line_chrome("[link](https://x)") is None
    assert cs._strip_line_chrome("Pine Script®") is None or cs._strip_line_chrome("Pine Script") is None
    assert cs._strip_line_chrome("Copied") is None
    assert cs._strip_line_chrome("12") is None
    assert cs._strip_line_chrome("...") is None
    assert cs._strip_line_chrome("Detail") is None
    assert cs._strip_line_chrome("Last Modified") is None
    assert cs._strip_line_chrome("- [x] done") is None
    assert cs._strip_line_chrome("{{< highlight pine >}}") is None
    assert cs._strip_line_chrome(".. image:: x.png") is None
    assert cs._strip_line_chrome("====") is None
    assert cs._strip_line_chrome("at https://docs") is None
    assert cs._strip_line_chrome("<Steps>") is None
    assert cs._strip_line_chrome("## Heading") is None
    assert cs._strip_line_chrome("`") is None


def test_strip_line_chrome_unwraps_blockquote_code() -> None:
    assert cs._strip_line_chrome("> plot(close)") == "plot(close)"
    assert cs._strip_line_chrome("> > a = 1") == "a = 1"
    assert cs._strip_line_chrome("> Detail") is None
    assert cs._strip_line_chrome(">") is None
    assert cs._strip_line_chrome("  //@version=6`") == "  //@version=6"


def test_polish_and_semicolon_and_unicode_ops() -> None:
    polished = cs._polish_code_line('plot(close)          Next Strategies')
    assert "Next" not in polished
    assert polished.startswith("plot(close)")
    assert cs._polish_code_line("plot(close)`").endswith(")")
    assert cs._polish_code_line("f(..., )").count("(") >= 1 or "f()" in cs._polish_code_line("f(...)")
    assert cs._strip_trailing_semicolon("a = 1;") == "a = 1"
    assert cs._strip_trailing_semicolon('msg = "a;b"') == 'msg = "a;b"'
    assert cs._strip_trailing_semicolon("// keep;") == "// keep;"
    assert cs._normalize_unicode_ops("x = 1") == "x = 1"
    assert "+/-" in cs._normalize_unicode_ops("\u00b11")
    assert cs._normalize_unicode_ops('s = "\u00b1"') == 's = "\u00b1"'


def test_mustache_replacements() -> None:
    assert cs._mustache_sub_for_span("AS_OF_DATE", 'title="', in_string=True) == "na"
    assert cs._mustache_sub_for_span("LENGTH", "x =", in_string=False) == "0"
    assert cs._mustache_sub_for_span("FOO", "x +", in_string=False) == "0"
    assert cs._mustache_sub_for_span("FOO", "call(", in_string=False) == "na"
    line = 'title="{{AS_OF_DATE}}" len={{LENGTH}} other={{FOO}}'
    out = cs._replace_mustache_in_line(line)
    assert "{{" not in out
    assert "na" in out
    assert "0" in out
    assert cs._replace_mustache_in_line("// {{KEEP}}") == "// {{KEEP}}"
    assert "{{" not in cs._replace_mustache_placeholders('x={{LEN}}\n')


def test_score_and_foreign_detection() -> None:
    pine = '//@version=5\nindicator("x")\nplot(close)\n'
    assert cs._score_pine_block(pine) >= 40
    assert cs._has_usable_pine(pine) is True
    assert cs._has_usable_pine("`indicator(x)`") is False
    assert cs._has_usable_pine("- indicator(x)") is False

    shell = "#!/bin/bash\necho hi\nexit 1\n"
    assert cs._looks_like_foreign(shell) is True
    assert cs._looks_like_foreign(pine) is False

    js = "const x = 1\nif (x) {\n  plot(close)\n}\n"
    assert cs._looks_like_js_block(js) is True
    assert cs._looks_like_js_block(pine) is False

    mdx = 'import { Steps } from "nextra"\n<Steps>\n'
    assert cs._looks_like_mdx(mdx) is True
    assert cs._looks_like_jinja("{% for x in y %}\n{{ x }}\n") is True


def test_extract_fenced_heredoc_and_tv_blocks() -> None:
    lines = [
        "prose",
        "```pine",
        '//@version=5',
        'indicator("x")',
        "plot(close)",
        "```",
        "more",
    ]
    tagged = cs._extract_fenced_blocks_tagged(lines)
    assert tagged and tagged[0][0] == "pine"
    assert "indicator" in tagged[0][1]
    assert cs._extract_fenced_blocks(lines)[0].startswith("//@version")

    tv = [
        "Pine Script",
        "Copied",
        "",
        '//@version=5',
        'indicator("t")',
        "plot(close)",
        "Note that: more prose",
    ]
    blocks = cs._extract_tv_copied_blocks(tv)
    assert blocks and "indicator" in blocks[0]

    heredoc = [
        "cat <<'EOF'",
        '//@version=5',
        'indicator("h")',
        "plot(close)",
        "EOF",
    ]
    hblocks = cs._extract_heredoc_blocks(heredoc)
    assert hblocks and "indicator" in hblocks[0]


def test_provenance_split_and_compose() -> None:
    lines = [
        "// set05 corpus",
        "// source_repo: example",
        "",
        '//@version=5',
        'indicator("x")',
    ]
    prov, body = cs._split_provenance(lines)
    assert any("set05" in p for p in prov)
    assert body[0].startswith("//@version") or body[0] == ""
    assert cs._is_provenance("// collected: 2026")
    assert cs._is_provenance("")
    assert not cs._is_provenance("plot(close)")
    composed = cs._compose(["// set05"], 'indicator("x")\n', True)
    assert composed.startswith("// set05")
    assert "indicator" in composed


def test_block_comment_and_string_state() -> None:
    assert cs._block_comment_open_after_line("/* start", False) is True
    assert cs._block_comment_open_after_line("still", True) is True
    assert cs._block_comment_open_after_line("end */ code", True) is False
    assert cs._block_comment_open_after_line('s = "/*"', False) is False
    assert cs._string_state_after_line('x = "open', None) == '"'
    assert cs._string_state_after_line('closed"', '"') is None
    assert cs._string_state_after_line('x = """', None) == '"""'


def test_var_comma_and_paren_helpers() -> None:
    fixed = cs._insert_var_commas("var float a = na var float b = na")
    assert ", var float b" in fixed
    assert cs._has_var_keyword("var float x = 1")
    assert cs._count_var_keywords("var float a = 1, var float b = 2") >= 2
    assert cs._code_ends_with_semicolon("a = 1;") is True
    assert cs._code_ends_with_semicolon('a = "x;"') is False
    depth = cs._code_paren_bracket_depth("plot(close")
    assert depth[0] > 0
    closed = cs._append_missing_closers("plot(close")
    assert closed.count(")") >= closed.count("(")


def test_looks_like_prose_and_pine_start() -> None:
    assert cs._is_pine_start_line("plot(close)")
    assert cs._is_pine_start_line("indicator(\"x\")")
    assert not cs._is_pine_start_line("if [ -f x ]")
    assert cs._looks_like_prose_line("Note that: this is docs")
    assert cs._looks_like_prose_line("You can also use")


def test_sanitize_tiny_strings_many_branches() -> None:
    assert "indicator" in sanitize_corpus_source("")
    fenced = "```pine\n//@version=5\nindicator(\"x\")\nplot(close)\n```\n"
    cleaned = sanitize_corpus_source(fenced)
    assert "```" not in cleaned
    assert "indicator" in cleaned

    foreign = "#!/usr/bin/env python3\nimport pytest\ndef test_x():\n    pass\n"
    stub = sanitize_corpus_source(foreign)
    assert 'indicator("x")' in stub

    mdx = '---\ntitle: x\n---\nimport { Steps } from "x"\n<Steps>\nok\n</Steps>\n'
    assert 'indicator("x")' in sanitize_corpus_source(mdx)

    mustache = '//@version=5\nindicator("{{TITLE}}")\nlen = {{LENGTH}}\nplot(close)\n'
    out = sanitize_corpus_source(mustache)
    assert "{{" not in out

    # Expand after a live declaration truncates trailing chrome (incl. later plot).
    chrome_trunc = '//@version=5\nindicator("t")\nExpand (3 lines)\nplot(close)\n'
    out_trunc = sanitize_corpus_source(chrome_trunc)
    assert "Expand" not in out_trunc
    assert "plot(close)" not in out_trunc

    chrome = '//@version=5\nindicator("t")\nplot(close)\nhttps://example.com\n'
    out2 = sanitize_corpus_source(chrome)
    assert "https://" not in out2
    assert "plot(close)" in out2


def test_dedent_rst_literal_and_docs_nav() -> None:
    rst = 'study("fill")\n    p1 = plot(close)\n    fill(p1, p1)\n\n.. image:: x.png\n'
    dedented = cs._dedent_rst_literal_body(rst)
    assert "p1 = plot" in dedented
    # leading indent under study should shrink when stop line present
    body_line = [ln for ln in dedented.splitlines() if "p1 =" in ln][0]
    assert not body_line.startswith("    p1")

    nav = cs._polish_code_line("label.new(bar_index, high, 'x')          Previous On this page junk")
    assert "Previous" not in nav
    assert "label.new" in nav


def test_fix_truncated_and_empty_script_helpers() -> None:
    assert cs._is_effectively_empty_script("// only comments\n\n") is True
    assert cs._is_effectively_empty_script('indicator("x")\n') is False
    fixed = cs._fix_truncated_syntax("plot(close")
    assert ")" in fixed
    joined = cs._join_column1_ternary_continuations("x = cond\n  ? 1\n  : 2\n")
    assert "?" in joined
