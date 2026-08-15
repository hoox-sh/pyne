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

"""Parse, dump, walk, and unparse Pine Script ASTs.

Primary public surface of :mod:`pynescript.ast` (also re-exported from the
package ``__init__``):

* :func:`parse` — source string → AST (``Script`` or ``Expression``)
* :func:`unparse` — AST → Pine source (semantic round-trip; not byte-identical)
* :func:`dump` — debug string of an AST tree
* :func:`literal_eval` — evaluate literal-only expressions
* :func:`walk`, :func:`iter_fields`, :func:`iter_child_nodes` — tree traversal
* :func:`copy_location`, :func:`fix_missing_locations`, :func:`increment_lineno`
* :func:`get_source_segment` — slice original source by node location
* :func:`clear_parse_cache`, :func:`parse_cache_info` — process-local AST LRU

Contracts
---------
* **Input encoding**: :func:`parse` takes a Unicode ``str`` (decoded source).
  File paths are not accepted here; callers that read disk should open with
  ``utf-8`` (or use the internal file-stream path with the same default).
* **Parse modes**: ``"exec"`` → full script (root :class:`~pynescript.ast.node.Script`);
  ``"eval"`` → single expression (root :class:`~pynescript.ast.node.Expression`).
* **Errors**: invalid ``mode`` → :class:`ValueError`; syntax failures →
  :class:`pynescript.ast.error.SyntaxError` (with location when available).
* **Annotations**: in ``exec`` mode, ``//@…`` comments are attached as
  ``annotations`` on the script / function / type / assign nodes when present.
* **Round-trip**: ``parse`` → ``unparse`` preserves structure and meaning;
  whitespace, comment layout (except ``//@`` annotations on supported nodes),
  and some formatting may differ from the original source.
* **Parse cache**: by default successful :func:`parse` results are cached by
  ``sha256(source)`` + ``mode`` (bounded LRU, thread-safe). Disable with
  ``PYNE_PARSE_CACHE=0``. Cached trees are shared by identity — treat as
  read-only (see module-level cache docs).
"""

from __future__ import annotations

import hashlib
import itertools
import os
import re
import threading

from collections import OrderedDict
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from antlr4 import CommonTokenStream
from antlr4 import FileStream
from antlr4 import InputStream
from antlr4.atn.PredictionMode import PredictionMode
from antlr4.error.Errors import ParseCancellationException
from antlr4.error.ErrorStrategy import BailErrorStrategy
from antlr4.error.ErrorStrategy import DefaultErrorStrategy

from pynescript.ast import node as ast
from pynescript.ast.builder import PinescriptASTBuilder
from pynescript.ast.grammar.antlr4.error_listener import PinescriptErrorListener
from pynescript.ast.grammar.antlr4.lexer import PinescriptLexer
from pynescript.ast.grammar.antlr4.parser import PinescriptParser
from pynescript.ast.node import AST
from pynescript.ast.node import Expression
from pynescript.util.itertools import grouper


# Deeply nested Pine expressions (e.g. long ternary chains) need a higher
# recursion limit during ANTLR walk + AST builder visits.
_PARSE_RECURSION_LIMIT = 5000

# Reuse strategy instances: BailErrorStrategy holds no cross-parse state of
# interest after parser.reset(); DefaultErrorStrategy is only used on the
# uncommon LL fallback path (and reset() clears recovery flags).
_BAIL_ERROR_STRATEGY = BailErrorStrategy()
_DEFAULT_ERROR_STRATEGY = DefaultErrorStrategy()

# Builder is stateless across visits — reuse one instance to skip alloc.
_SHARED_BUILDER = PinescriptASTBuilder()

# Per-thread ANTLR engine: keeps SLL DFA warm across *distinct* sources.
# Shared process-wide lexer/parser is unsafe (indent / token-stream bleed).
_PARSE_TLS = threading.local()


class _ThreadParseEngine:
    """Reuse Lexer + CommonTokenStream + Parser on one thread.

    ``bind`` retargets the input and clears indent/token/parser state via
    ANTLR ``reset`` / ``setTokenSource`` so consecutive scripts cannot leak
    ``_numOpens`` or leftover tokens.
    """

    __slots__ = ("lexer", "tokens", "parser")

    def __init__(self) -> None:
        self.lexer = PinescriptLexer(InputStream(""))
        self.tokens = CommonTokenStream(self.lexer)
        self.parser = PinescriptParser(self.tokens)
        listener = PinescriptErrorListener.INSTANCE
        self.lexer.removeErrorListeners()
        self.parser.removeErrorListeners()
        self.lexer.addErrorListener(listener)
        self.parser.addErrorListener(listener)

    def bind(self, stream: InputStream) -> tuple[PinescriptLexer, CommonTokenStream, PinescriptParser]:
        """Point the reused engine at *stream* and return (lexer, tokens, parser)."""
        self.lexer.inputStream = stream
        self.tokens.setTokenSource(self.lexer)
        self.parser.setTokenStream(self.tokens)
        return self.lexer, self.tokens, self.parser


def _thread_parse_engine() -> _ThreadParseEngine:
    eng = getattr(_PARSE_TLS, "engine", None)
    if eng is None:
        eng = _ThreadParseEngine()
        _PARSE_TLS.engine = eng
    return eng

# Cached after first annotation pass (avoids circular import at module load).
_StatementCollector = None

# ---------------------------------------------------------------------------
# Parse / AST cache (Phase 1.6) — multi-run warm path
# ---------------------------------------------------------------------------
# Keyed by sha256(source) + mode. Shared AST identity is returned on hit.
#
# Mutability risk: the evaluator / Runtime treat trees as read-only. Callers
# that mutate a returned node (e.g. NodeTransformer, increment_lineno) also
# mutate the cached entry for all subsequent hits. Prefer clear_parse_cache()
# after intentional mutation, or set PYNE_PARSE_CACHE=0 for isolation.
#
# Env:
#   PYNE_PARSE_CACHE=0|false|off|no  — disable (default: ON)
#   PYNE_PARSE_CACHE_MAX=<int>       — max entries (default: 128)
# ---------------------------------------------------------------------------
_PARSE_CACHE: OrderedDict[tuple[str, str], AST] = OrderedDict()
_PARSE_CACHE_LOCK = threading.RLock()
_PARSE_CACHE_MAX_DEFAULT = 128
_PARSE_CACHE_HITS = 0
_PARSE_CACHE_MISSES = 0


def _env_flag_enabled(name: str, *, default: bool = True) -> bool:
    """Truthiness for ``PYNE_*`` toggles (``0``/``false``/``off``/``no`` → off)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _parse_cache_enabled() -> bool:
    return _env_flag_enabled("PYNE_PARSE_CACHE", default=True)


def _parse_cache_max() -> int:
    raw = os.environ.get("PYNE_PARSE_CACHE_MAX", "").strip()
    if raw:
        try:
            n = int(raw)
            if n >= 1:
                return n
        except ValueError:
            pass
    return _PARSE_CACHE_MAX_DEFAULT


def _parse_cache_key(source: str, mode: str) -> tuple[str, str]:
    """Return ``(sha256_hex, mode)`` for *source* (UTF-8)."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return (digest, mode)


def clear_parse_cache() -> None:
    """Drop all cached parse trees (tests, hot-reload, post-mutation).

    Thread-safe. Does not change enable/max env settings.
    """
    global _PARSE_CACHE_HITS, _PARSE_CACHE_MISSES
    with _PARSE_CACHE_LOCK:
        _PARSE_CACHE.clear()
        _PARSE_CACHE_HITS = 0
        _PARSE_CACHE_MISSES = 0


def _scrub_pine_call_sites(tree: AST) -> AST:
    """Drop ``_pine_call_site`` attrs on a shared AST (parse-cache hit).

    ``visit_Call`` may cache bound handlers stamped with evaluator generation.
    A later evaluator ignores a mismatched generation, but scrubbing still
    drops dead instance-method refs so cached trees do not pin evaluators.
    """
    try:
        for node in walk(tree):
            if getattr(node, "_pine_call_site", None) is not None:
                try:
                    delattr(node, "_pine_call_site")
                except Exception:
                    try:
                        object.__setattr__(node, "_pine_call_site", None)
                    except Exception:
                        pass
    except Exception:
        pass
    return tree


def parse_cache_info() -> dict[str, Any]:
    """Return cache stats for diagnostics and tests.

    Keys: ``enabled``, ``size``, ``maxsize``, ``hits``, ``misses``.
    """
    with _PARSE_CACHE_LOCK:
        return {
            "enabled": _parse_cache_enabled(),
            "size": len(_PARSE_CACHE),
            "maxsize": _parse_cache_max(),
            "hits": _PARSE_CACHE_HITS,
            "misses": _PARSE_CACHE_MISSES,
        }


def _parse_cache_get(key: tuple[str, str]) -> AST | None:
    global _PARSE_CACHE_HITS, _PARSE_CACHE_MISSES
    with _PARSE_CACHE_LOCK:
        hit = _PARSE_CACHE.get(key)
        if hit is not None:
            _PARSE_CACHE.move_to_end(key)
            _PARSE_CACHE_HITS += 1
            return hit
        _PARSE_CACHE_MISSES += 1
        return None


def _parse_cache_put(key: tuple[str, str], tree: AST) -> AST:
    """Insert *tree*; return existing entry if another thread raced the put."""
    with _PARSE_CACHE_LOCK:
        existing = _PARSE_CACHE.get(key)
        if existing is not None:
            _PARSE_CACHE.move_to_end(key)
            return existing
        maxsize = _parse_cache_max()
        while len(_PARSE_CACHE) >= maxsize:
            try:
                _PARSE_CACHE.popitem(last=False)
            except KeyError:
                break
        _PARSE_CACHE[key] = tree
        return tree


def _get_statement_collector_cls():
    global _StatementCollector
    if _StatementCollector is None:
        from pynescript.ast.collector import StatementCollector as _SC

        _StatementCollector = _SC
    return _StatementCollector


def _add_annotations(script, statements, comments):
    """Attach annotation comments to AST nodes.

    Processes special comments (those starting with @) and attaches them to the nearest
    following statement as annotations. Supports script-level, function, type, and variable annotations.

    Examples:
        //@version 5  -> added to script.annotations
        //@description "My Strategy"  -> added to function.annotations
        //@type input  -> added to type.annotations

    Args:
        script: The root Script node
        statements: List of statement nodes
        comments: List of Comment nodes with metadata (lineno, col_offset, kind, value)
    """
    # Optimize: early exit if no comments
    if not comments:
        return

    # Combine comments and statements, then sort by position (line, column)
    comments_and_statements_iter = itertools.chain(comments, statements)
    sorted_items = sorted(comments_and_statements_iter, key=lambda item: (item.lineno, item.col_offset))

    # Group consecutive items by whether they are comments or statements
    grouped = itertools.groupby(sorted_items, lambda item: isinstance(item, ast.Comment))
    comments_and_statements = [(k, list(g)) for k, g in grouped]

    # Ensure first group is comments (or empty if it starts with statements)
    if not comments_and_statements[0][0]:
        comments_and_statements.insert(0, (True, []))

    # Extract annotation comments (those starting with @) and pair with following statements
    grouped_annotations_and_statements = [
        [c for c in group if c.kind.startswith("@")] if comment else group[0]
        for comment, group in comments_and_statements
    ]

    # Process script-level annotations (marked with @...S suffix)
    first_group = grouped_annotations_and_statements[0]
    if first_group:
        # Extract annotations for script (kind ends with 'S')
        annotations = [c.value for c in first_group if c.kind.endswith("S")]
        if annotations:
            script.annotations = annotations

    # Pair annotation groups with statements, stepping by 2 (annotation group, statement)
    grouped_annotations_and_statement_pairs = grouper(grouped_annotations_and_statements, n=2, incomplete="ignore")

    # Attach annotations to specific statement types
    for comments, statement in grouped_annotations_and_statement_pairs:
        # Optimize: skip if no comments
        if not comments:
            continue

        if isinstance(statement, ast.FunctionDef):
            # Extract function-specific annotations (kind ends with 'F')
            annotations = [c.value for c in comments if c.kind.endswith("F")]
            if annotations:
                statement.annotations = annotations
        elif isinstance(statement, ast.TypeDef):
            # Extract type-specific annotations (kind ends with 'T')
            annotations = [c.value for c in comments if c.kind.endswith("T")]
            if annotations:
                statement.annotations = annotations
        elif isinstance(statement, ast.Assign):
            # Extract variable-specific annotations (kind ends with 'V')
            annotations = [c.value for c in comments if c.kind.endswith("V")]
            if annotations:
                statement.annotations = annotations


def _collect_comment_nodes(builder: PinescriptASTBuilder, token_stream: CommonTokenStream) -> list[ast.Comment]:
    """Extract annotation-relevant comment nodes from the token stream.

    Only comments containing ``@`` can become annotations (``//@version``,
    ``//@description``, …). Plain ``//`` comments and ``//# region`` markers
    are skipped — ``_add_annotations`` would ignore them anyway.

    Args:
        builder: PinescriptASTBuilder instance with comment parsing capability
        token_stream: ANTLR token stream containing all tokens from parsing

    Returns:
        List of Comment AST nodes with position information and parsed kind/value
    """
    # Ensure all tokens have been generated by the lexer
    token_stream.fill()
    comments: list[ast.Comment] = []

    comment_type = PinescriptLexer.COMMENT
    parse_comment = builder._parseComment

    for token in token_stream.tokens:
        if token is None or token.type != comment_type:
            continue

        text = token.text
        if not text or "@" not in text:
            continue

        kind, _parts = parse_comment(text)
        # Only @-annotations are attached; skip if pattern did not match.
        if not kind.startswith("@"):
            continue

        comment = ast.Comment(
            value=text,
            kind=kind,
        )
        text_len = len(text)
        comment.lineno = token.line  # type: ignore[attr-defined]
        comment.col_offset = token.column  # type: ignore[attr-defined]
        comment.end_lineno = token.line  # type: ignore[attr-defined]
        comment.end_col_offset = token.column + text_len  # type: ignore[attr-defined]

        comments.append(comment)

    return comments


def _parse_rule(parser: PinescriptParser, mode: str):
    """Invoke the start rule for the given parse mode."""
    if mode == "exec":
        return parser.start_script()
    return parser.start_expression()


def _parse(
    stream: InputStream,
    mode: str = "exec",
) -> AST:
    """Core parse pipeline: lex → SLL/LL parse → AST build → annotations.

    Raises:
        ValueError: Invalid *mode*.
        pynescript.ast.error.SyntaxError: Lexer/parser failure.
    """
    import sys

    # Validate mode argument
    if mode not in {"exec", "eval"}:
        msg = f"invalid argument mode: {mode}"
        raise ValueError(msg)

    # Temporarily increase recursion limit for deeply nested expressions
    # (e.g., hundreds of nested ternary operators)
    old_limit = sys.getrecursionlimit()
    if old_limit < _PARSE_RECURSION_LIMIT:
        sys.setrecursionlimit(_PARSE_RECURSION_LIMIT)
        restore_recursion = True
    else:
        restore_recursion = False

    try:
        _lexer, token_stream, parser = _thread_parse_engine().bind(stream)

        # Two-stage parse: SLL is much faster on unambiguous input; on SLL
        # failure (BailErrorStrategy → ParseCancellationException) reset and
        # re-parse with full LL. Produces identical trees to pure-LL on success.
        parser._interp.predictionMode = PredictionMode.SLL
        parser._errHandler = _BAIL_ERROR_STRATEGY
        try:
            rule = _parse_rule(parser, mode)
        except ParseCancellationException:
            token_stream.seek(0)
            parser.reset()
            parser._errHandler = _DEFAULT_ERROR_STRATEGY
            parser._interp.predictionMode = PredictionMode.LL
            rule = _parse_rule(parser, mode)

        builder = _SHARED_BUILDER
        node = builder.visit(rule)

        if mode == "exec":
            # Annotation comments always contain '@' (e.g. //@version=5).
            # Skip statement/comment collection when none can exist.
            src_text = getattr(stream, "strdata", None)
            if src_text is not None and "@" not in src_text:
                return node

            statements = list(_get_statement_collector_cls()().visit(node))

            if not statements:
                return node

            comments = _collect_comment_nodes(builder, token_stream)

            if not comments:
                return node

            _add_annotations(node, statements, comments)

        return node
    finally:
        if restore_recursion:
            sys.setrecursionlimit(old_limit)


def _get_absolute_path(filename: str) -> str:
    """Convert a filename to an absolute path if the file exists.

    Handles special filenames like "<unknown>" and validates path existence.

    Args:
        filename: The input filename (may be relative or absolute)

    Returns:
        Absolute path if file exists, otherwise the original filename unchanged
    """
    # Special case for placeholder filenames
    if filename in {"<unknown>"}:
        return filename
    # Convert to Path object for manipulation
    filename_path = Path(filename)
    # Only convert to absolute path if the file actually exists
    if not filename_path.exists():
        return filename
    # Return absolute path as string
    filename = str(filename_path.absolute())
    return filename


def _parse_inputstream(
    source: str,
    filename: str = "<unknown>",
    mode: str = "exec",
) -> AST:
    """Parse source code from a string into an AST.

    Wrapper around _parse() that creates an InputStream from source text.

    Args:
        source: The Pine Script source code as a string
        filename: Optional filename for error reporting
        mode: "exec" for statements or "eval" for expressions

    Returns:
        Root AST node (Script for exec, Expression for eval)
    """
    # Normalize filename to absolute path if possible
    filename = _get_absolute_path(filename)
    # Create ANTLR InputStream from source text
    stream = InputStream(source)
    # Attach filename for error reporting
    stream.name = filename
    # Delegate to core parsing function
    return _parse(stream, mode)


def _parse_filestream(
    filename: str,
    encoding: str = "utf-8",
    mode: str = "exec",
) -> AST:
    """Parse a Pine Script file directly from disk into an AST.

    Wrapper around _parse() that creates a FileStream from a file path.

    Args:
        filename: Path to the Pine Script file to parse
        encoding: File encoding (default: utf-8)
        mode: "exec" for statements or "eval" for expressions

    Returns:
        Root AST node (Script for exec, Expression for eval)
    """
    # Normalize filename to absolute path if possible
    filename = _get_absolute_path(filename)
    # Create ANTLR FileStream (reads file from disk)
    stream = FileStream(filename, encoding=encoding)
    # Delegate to core parsing function
    return _parse(stream, mode)


def parse(
    source: str,
    filename: str = "<unknown>",
    mode: str = "exec",
) -> AST:
    """Parse Pine Script source into an AST.

    Primary public entry point. ``source`` must be a decoded Unicode string
    (not bytes). ``filename`` is used only in error messages and is normalized
    to an absolute path when the path exists.

    **Caching (default ON):** successful trees are stored in a process-local
    LRU keyed by ``sha256(source)`` and ``mode`` (see :func:`clear_parse_cache`,
    :func:`parse_cache_info`). Warm multi-run hosts (API batch, re-eval same
    script) skip ANTLR re-parse. Disable with ``PYNE_PARSE_CACHE=0``. Cached
    trees are shared by identity and must be treated as **read-only**.

    Args:
        source: Pine Script source (``str``, typically UTF-8-decoded).
        filename: Path or label for diagnostics (default ``"<unknown>"``).
            Not part of the cache key (only affects error messages).
        mode: ``"exec"`` (full script) or ``"eval"`` (single expression).

    Returns:
        :class:`~pynescript.ast.node.Script` for ``mode="exec"``, or
        :class:`~pynescript.ast.node.Expression` for ``mode="eval"``.

    Raises:
        ValueError: If ``mode`` is not ``"exec"`` or ``"eval"``.
        pynescript.ast.error.SyntaxError: On lexer/parser syntax errors.

    Examples:
        >>> tree = parse("plot(close)")
        >>> expr = parse("close > open", mode="eval")
    """
    if not _parse_cache_enabled():
        return _parse_inputstream(source, filename, mode)

    key = _parse_cache_key(source, mode)
    hit = _parse_cache_get(key)
    if hit is not None:
        return _scrub_pine_call_sites(hit)

    tree = _parse_inputstream(source, filename, mode)
    return _parse_cache_put(key, tree)


def literal_eval(
    node_or_string: AST | str,
    context: dict[str, Any] | None = None,
    data_feed: Any = None,
    data_provider: Any = None,
) -> Any:
    """Evaluate a literal-only expression (AST node or source string).

    Accepts numbers, strings, booleans, tuples, and a restricted set of
    built-in calls. Strings are parsed with :func:`parse` in ``"eval"`` mode.
    Not a general script executor — non-literal constructs raise.

    Args:
        node_or_string: Expression AST, :class:`~pynescript.ast.node.Expression`
            wrapper, or source string.
        context: Optional name/function lookup dict for the evaluator.
        data_feed: Optional realtime data feed for ``request.*`` in literal contexts.
        data_provider: Optional historical data provider.

    Returns:
        Python value (``int``, ``str``, ``bool``, sequence, etc.).

    Raises:
        ValueError: Non-literal or unsafe construct.
        pynescript.ast.error.SyntaxError: If a string input fails to parse.

    Examples:
        >>> literal_eval("42")
        42
        >>> literal_eval("'hello'")
        'hello'
    """
    # If input is a string, parse it as an expression first
    if isinstance(node_or_string, str):
        node_or_string = parse(node_or_string.lstrip(" \t"), mode="eval")
    # Unwrap Expression wrapper to get the actual expression node
    if isinstance(node_or_string, Expression):
        node_or_string = node_or_string.body

    # Import here to avoid circular dependency
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    # Create evaluator with optional context and visit the node
    # Support data_feed / data_provider for request.* integration in literal contexts too
    evaluator = NodeLiteralEvaluator(context, data_feed=data_feed, data_provider=data_provider)
    return evaluator.visit(node_or_string)


def dump(
    node: AST,
    *,
    annotate_fields: bool = True,
    include_attributes: bool = False,
    indent: int | str | None = None,
) -> str:
    """Return a debug string for an AST tree (Python-``ast.dump`` style).

    Args:
        node: Root AST node.
        annotate_fields: Include field names (e.g. ``name='x'``).
        include_attributes: Include location attrs (``lineno``, ``col_offset``, …).
        indent: Pretty-print: ``int`` spaces per level, or an indent string;
            ``None`` for a single line.

    Returns:
        Structural string such as ``Script(body=[Assign(...)])``.

    Raises:
        TypeError: If ``node`` is not an :class:`~pynescript.ast.node.AST`.
    """
    def _format(node, level=0):  # noqa: PLR0912
        # Prepare indentation and separator based on indent parameter
        if indent is not None:
            level += 1
            # Newline with indentation for readability
            prefix = "\n" + indent * level
            # Separator includes indentation for multi-line output
            sep = ",\n" + indent * level
        else:
            # Single-line output
            prefix = ""
            sep = ", "

        if isinstance(node, AST):
            # Format AST node: collect all field and attribute values
            cls = type(node)
            args = []
            allsimple = True  # Track if all sub-elements are simple (one-liners)
            keywords = annotate_fields  # Use field names as keywords

            # Iterate through all fields defined in the node's schema
            for name in node._fields:
                try:
                    value = getattr(node, name)
                except AttributeError:
                    # Field not set - force keyword format for clarity
                    keywords = True
                    continue
                # Skip None values that have None as default
                if value is None and getattr(cls, name, ...) is None:
                    keywords = True
                    continue
                # Recursively format the field value
                value, simple = _format(value, level)
                # Track complexity for smart formatting
                allsimple = allsimple and simple
                # Add to args list (with or without field name)
                if keywords:
                    args.append(f"{name}={value}")
                else:
                    args.append(value)

            # Include attributes (position, etc.) if requested
            if include_attributes and node._attributes:
                for name in node._attributes:
                    try:
                        value = getattr(node, name)
                    except AttributeError:
                        continue
                    # Skip None values that have None as default
                    if value is None and getattr(cls, name, ...) is None:
                        continue
                    # Recursively format the attribute value
                    value, simple = _format(value, level)
                    allsimple = allsimple and simple
                    args.append(f"{name}={value}")

            # Smart formatting: single-line for simple, short outputs
            if allsimple and len(args) <= 3:  # noqa: PLR2004
                return "{}({})".format(node.__class__.__name__, ", ".join(args)), not args
            # Multi-line formatting for complex structures
            return f"{node.__class__.__name__}({prefix}{sep.join(args)})", False

        elif isinstance(node, list):
            # Format list of nodes
            if not node:
                return "[]", True  # Empty list is simple
            # Format list elements with separators and indentation
            return f"[{prefix}{sep.join(_format(x, level)[0] for x in node)}]", False

        # Fallback: format as Python repr (strings, numbers, etc.)
        return repr(node), True

    # Validate input is an AST node
    if not isinstance(node, AST):
        msg = f"expected AST, got {node.__class__.__name__!r}"
        raise TypeError(msg)

    # Normalize indent parameter: convert int to string of spaces
    if indent is not None and not isinstance(indent, str):
        indent = " " * indent

    # Start formatting from the root node
    return _format(node)[0]


def copy_location(new_node: AST, old_node: AST) -> AST:
    """Copy source location attributes from *old_node* onto *new_node*.

    Copies ``lineno``, ``col_offset``, ``end_lineno``, and ``end_col_offset``
    when both nodes declare them in ``_attributes``. Mutates *new_node* in place.

    Returns:
        *new_node* (same object).
    """
    # Iterate through all position attributes
    for attr in "lineno", "col_offset", "end_lineno", "end_col_offset":
        # Check if both nodes support this attribute
        if attr in old_node._attributes and attr in new_node._attributes:
            value = getattr(old_node, attr, None)
            # Copy value if it exists, or for end_* attributes always try to copy
            if value is not None or (hasattr(old_node, attr) and attr.startswith("end_")):
                setattr(new_node, attr, value)
    return new_node


def iter_fields(node: AST) -> Iterator[tuple[str, Any]]:
    """Yield ``(field_name, value)`` for each name in ``node._fields``.

    Skips fields that raise :class:`AttributeError` (unset on the instance).
    """
    # Iterate through fields defined in the node's schema
    for field in node._fields:
        try:
            # Yield field name and its value
            yield field, getattr(node, field)
        except AttributeError:
            # Skip fields not set on this node
            pass


def iter_child_nodes(node: AST) -> Iterator[AST]:
    """Yield direct child AST nodes (one level only).

    Field values that are AST instances or lists of ASTs are yielded;
    non-AST field values are ignored. Does not walk grandchildren — use
    :func:`walk` for a full traversal.
    """
    # Iterate over all fields and extract child nodes
    for _name, field in iter_fields(node):
        # Single child node
        if isinstance(field, AST):
            yield field
        # List of child nodes
        elif isinstance(field, list):
            for item in field:
                # Each list element might be an AST node
                if isinstance(item, AST):
                    yield item


def _fix_locations(  # noqa: PLR0912
    node: AST,
    lineno: int,
    col_offset: int,
    end_lineno: int,
    end_col_offset: int,
) -> None:
    """Recursively fill in missing location attributes on AST nodes.

    Propagates line and column information from parent to child nodes,
    ensuring all nodes have consistent position metadata for error reporting.

    Args:
        node: The AST node to process
        lineno: Default line number to use
        col_offset: Default column offset to use
        end_lineno: Default end line number to use
        end_col_offset: Default end column offset to use
    """
    # Set lineno if not already set
    if "lineno" in node._attributes:
        if not hasattr(node, "lineno"):
            node.lineno = lineno  # type: ignore[attr-defined]
        else:
            # Use this node's lineno as the default for children
            lineno = node.lineno  # type: ignore[attr-defined]

    # Set end_lineno if not already set
    if "end_lineno" in node._attributes:
        if getattr(node, "end_lineno", None) is None:
            node.end_lineno = end_lineno  # type: ignore[attr-defined]
        else:
            # Use this node's end_lineno as the default for children
            end_lineno = node.end_lineno  # type: ignore[attr-defined]

    # Set col_offset if not already set
    if "col_offset" in node._attributes:
        if not hasattr(node, "col_offset"):
            node.col_offset = col_offset  # type: ignore[attr-defined]
        else:
            # Use this node's col_offset as the default for children
            col_offset = node.col_offset  # type: ignore[attr-defined]

    # Set end_col_offset if not already set
    if "end_col_offset" in node._attributes:
        if getattr(node, "end_col_offset", None) is None:
            node.end_col_offset = end_col_offset  # type: ignore[attr-defined]
        else:
            # Use this node's end_col_offset as the default for children
            end_col_offset = node.end_col_offset  # type: ignore[attr-defined]

    # Recursively process all child nodes with the propagated defaults
    for child in iter_child_nodes(node):
        _fix_locations(child, lineno, col_offset, end_lineno, end_col_offset)


def fix_missing_locations(node: AST) -> AST:
    """Fill missing location attributes on *node* and descendants in place.

    Defaults for the root are line ``1``, column ``0``; children inherit
    from the nearest parent that has a value. Useful after building or
    transforming nodes without a full parse.

    Returns:
        *node* (same object).
    """
    # Start recursion with default line 1, column 0
    _fix_locations(node, 1, 0, 1, 0)
    return node


def increment_lineno(node: AST, n: int = 1) -> AST:
    """Add *n* to ``lineno`` / ``end_lineno`` on every node in the tree.

    Mutates in place. Useful when splicing nodes into a different source
    region.

    Returns:
        *node* (same object).
    """
    # Walk through all nodes in the tree and increment their line numbers
    for child in walk(node):
        # Increment lineno if the node has one
        if "lineno" in child._attributes:
            child.lineno = getattr(child, "lineno", 0) + n  # type: ignore[attr-defined]
        # Increment end_lineno if the node has one
        if "end_lineno" in child._attributes and (end_lineno := getattr(child, "end_lineno", 0)) is not None:
            child.end_lineno = end_lineno + n  # type: ignore[attr-defined]
    return node


_line_pattern = re.compile(r"(.*?(?:\r\n|\n|\r|$))")


def _splitlines_no_ff(source: str, maxlines: int | None = None) -> list[str]:
    """Split *source* into lines, keeping terminators; stop after *maxlines*."""
    lines = []
    for lineno, match in enumerate(_line_pattern.finditer(source), 1):
        if maxlines is not None and lineno > maxlines:
            break
        lines.append(match[0])
    return lines


def _pad_whitespace(source: str) -> str:
    """Replace non-tab/form-feed characters with spaces (preserve width)."""
    result = ""
    for c in source:
        if c in "\f\t":
            result += c
        else:
            result += " "
    return result


def get_source_segment(source: str, node: AST, *, padded: bool = False) -> str | None:
    """Extract the original source slice corresponding to *node*.

    Requires the node to have complete location attributes (``lineno``,
    ``col_offset``, ``end_lineno``, ``end_col_offset``). Offsets are byte
    offsets within the line (UTF-8), matching the parser.

    Args:
        source: Full source string that was parsed to produce *node*.
        node: AST node with location attributes.
        padded: If True, multi-line segments pad the first line so that
            leading indentation aligns with the original column.

    Returns:
        The source segment, or ``None`` if location data is missing/incomplete.
    """
    try:
        if node.end_lineno is None or node.end_col_offset is None:  # type: ignore[attr-defined]
            return None
        lineno = node.lineno - 1  # type: ignore[attr-defined]
        end_lineno = node.end_lineno - 1  # type: ignore[attr-defined]
        col_offset = node.col_offset  # type: ignore[attr-defined]
        end_col_offset = node.end_col_offset  # type: ignore[attr-defined]
    except AttributeError:
        return None

    lines = _splitlines_no_ff(source, maxlines=end_lineno + 1)
    if end_lineno == lineno:
        return lines[lineno].encode()[col_offset:end_col_offset].decode()

    if padded:
        padding = _pad_whitespace(lines[lineno].encode()[:col_offset].decode())
    else:
        padding = ""

    first = padding + lines[lineno].encode()[col_offset:].decode()
    last = lines[end_lineno].encode()[:end_col_offset].decode()
    lines = lines[lineno + 1 : end_lineno]

    lines.insert(0, first)
    lines.append(last)
    return "".join(lines)


def walk(node: AST) -> Iterator[AST]:
    """Breadth-first walk of *node* and all descendants (includes *node*).

    Yields each AST node once. Safe for mutation of child links after a
    node has been yielded (children are queued before yield returns).
    """
    todo = deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


def unparse(node: AST) -> str:
    """Convert an AST back to Pine Script source text.

    Semantic round-trip with :func:`parse` is supported for well-formed trees
    (structure and meaning preserved). Exact whitespace, non-annotation
    comments, and original formatting are not guaranteed.

    Returns:
        Pine Script source as a ``str``.
    """
    # Reuse a per-thread NodeUnparser (warm visitor cache). Public API unchanged.
    from pynescript.ast.unparser import unparse_node

    return unparse_node(node)


__all__ = [
    "clear_parse_cache",
    "copy_location",
    "dump",
    "fix_missing_locations",
    "get_source_segment",
    "increment_lineno",
    "iter_child_nodes",
    "iter_fields",
    "literal_eval",
    "parse",
    "parse_cache_info",
    "unparse",
    "walk",
]
