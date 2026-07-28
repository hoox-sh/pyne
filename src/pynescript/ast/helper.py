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

from __future__ import annotations

import itertools
import re

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
    """Extract comment nodes from the token stream.

    Parses all COMMENT tokens and creates Comment AST nodes with metadata.
    Uses PinescriptASTBuilder to parse comment syntax (extracts kind from format like //@version).

    Args:
        builder: PinescriptASTBuilder instance with comment parsing capability
        token_stream: ANTLR token stream containing all tokens from parsing

    Returns:
        List of Comment AST nodes with position information and parsed kind/value
    """
    # Ensure all tokens have been generated by the lexer
    token_stream.fill()
    comments: list[ast.Comment] = []

    # Optimize: cache COMMENT type lookup to avoid repeated attribute access
    comment_type = PinescriptLexer.COMMENT

    # Iterate through all tokens looking for COMMENT type tokens
    for token in token_stream.tokens:
        if token is None or token.type != comment_type:
            continue

        # Extract comment text from token
        text = token.text or ""
        # Parse comment syntax to extract kind (e.g., "version" from //@version)
        kind, _parts = builder._parseComment(text)
        # Create Comment node with parsed metadata
        comment = ast.Comment(
            value=text,
            kind=kind,
        )

        # Attach position information from token metadata
        # Optimize: cache text length to calculate end_col_offset
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
    """Core parsing function: tokenize, parse, and build AST from input stream.

    Orchestrates the ANTLR lexer/parser pipeline and AST construction:
    1. Lexes the input stream into tokens
    2. Parses tokens according to Pinescript grammar (SLL first, LL fallback)
    3. Builds AST nodes from parse tree
    4. Collects annotations from comments (in exec mode)

    Args:
        stream: ANTLR InputStream or FileStream to parse
        mode: "exec" for statements (Script/Module), "eval" for single expressions

    Returns:
        Root AST node (Script for exec mode, Expression for eval mode)

    Raises:
        ValueError: If mode is invalid
        SyntaxError: If parsing fails (from PinescriptErrorListener)
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
        lexer = PinescriptLexer(stream)
        token_stream = CommonTokenStream(lexer)
        parser = PinescriptParser(token_stream)
        error_listener = PinescriptErrorListener.INSTANCE

        lexer.removeErrorListeners()
        parser.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        parser.addErrorListener(error_listener)

        # Two-stage parse: SLL is much faster on unambiguous input; on SLL
        # failure (BailErrorStrategy → ParseCancellationException) reset and
        # re-parse with full LL. Produces identical trees to pure-LL on success.
        parser._interp.predictionMode = PredictionMode.SLL
        parser._errHandler = BailErrorStrategy()
        try:
            rule = _parse_rule(parser, mode)
        except ParseCancellationException:
            token_stream.seek(0)
            parser.reset()
            parser._errHandler = DefaultErrorStrategy()
            parser._interp.predictionMode = PredictionMode.LL
            rule = _parse_rule(parser, mode)

        builder = PinescriptASTBuilder()
        node = builder.visit(rule)

        if mode == "exec":
            # Annotation comments always contain '@' (e.g. //@version=5).
            # Skip statement/comment collection when none can exist.
            src_text = getattr(stream, "strdata", None)
            if src_text is not None and "@" not in src_text:
                return node

            # Deferred import: collector → visitor → helper (circular at module load)
            from pynescript.ast.collector import StatementCollector

            statements = list(StatementCollector().visit(node))

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
    """Parse Pine Script source code into an AST.

    PUBLIC API: Primary entry point for parsing Pine Script code.

    Args:
        source: The Pine Script source code as a string
        filename: Optional filename for error reporting and debugging
        mode: "exec" (default) for full script with statements, or "eval" for expression-only

    Returns:
        Root AST node:
        - Script node for mode="exec" containing list of statements
        - Expression node for mode="eval" containing a single expression

    Raises:
        ValueError: If mode is not "exec" or "eval"
        SyntaxError: If the source code has syntax errors

    Examples:
        >>> ast = parse("plot(close)")
        >>> ast = parse("close > open", mode="eval")
    """
    # Delegate to stream-based parser
    return _parse_inputstream(source, filename, mode)


def literal_eval(
    node_or_string: AST | str,
    context: dict[str, Any] | None = None,
    data_feed: Any = None,
    data_provider: Any = None,
) -> Any:
    """Safely evaluate an AST node or string containing only literal values.

    Evaluates constant expressions (numbers, strings, booleans, tuples) and some built-in functions.
    Does NOT execute arbitrary code - raises NotImplementedError for non-literal expressions.

    Args:
        node_or_string: An AST node or string to evaluate
        context: Optional context dict for variable/function lookups
        data_feed: Optional realtime DataFeed (for request.* live data integration)
        data_provider: Optional historical DataProvider

    Returns:
        The evaluated Python value (int, str, bool, list, etc.)

    Raises:
        ValueError: If the expression contains non-literal/unsafe operations

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
    """Generate a string representation of an AST node tree.

    Converts an AST into a human-readable format showing the node structure.
    Can optionally include field names, position attributes, and indentation.

    Args:
        node: The root AST node to dump
        annotate_fields: If True, include field names in output (e.g., "name='x'")
        include_attributes: If True, include position metadata (lineno, col_offset, etc.)
        indent: Optional indentation for pretty-printing (int for spaces or string)

    Returns:
        String representation of the AST tree

    Raises:
        TypeError: If node is not an AST node

    Examples:
        >>> ast = parse("x = 1")
        >>> print(dump(ast))
        Script(body=[Assign(...)])
        >>> print(dump(ast, indent=2))  # Pretty-printed with indentation
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
    """Copy position metadata from one node to another.

    Copies lineno, col_offset, end_lineno, and end_col_offset attributes
    from old_node to new_node where they are defined.

    Args:
        new_node: The target node to copy location info into
        old_node: The source node to copy location info from

    Returns:
        The modified new_node with location info copied from old_node
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
    """Iterate over all fields in an AST node.

    Yields (fieldname, value) tuples for each field defined in the node's schema.
    Skips fields that are not set on the node.

    Args:
        node: The AST node to iterate over

    Yields:
        Tuples of (field_name, field_value) for each defined field
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
    """Iterate over all direct child AST nodes.

    Recursively yields child nodes, handling both single nodes and lists of nodes.

    Args:
        node: The parent AST node

    Yields:
        Direct child AST nodes
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
    """Fill in missing location information for an AST tree.

    Ensures all nodes have lineno and col_offset attributes set,
    using defaults (1, 0) for the root and propagating from parents.

    Args:
        node: The root AST node to process

    Returns:
        The modified node with location info filled in
    """
    # Start recursion with default line 1, column 0
    _fix_locations(node, 1, 0, 1, 0)
    return node


def increment_lineno(node: AST, n: int = 1) -> AST:
    """Increment line numbers for all nodes in the tree.

    Useful for adjusting AST nodes when inserting code or adjusting to different contexts.

    Args:
        node: The root AST node to modify
        n: Number of lines to increment (default: 1)

    Returns:
        The modified node tree with incremented line numbers
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
    lines = []
    for lineno, match in enumerate(_line_pattern.finditer(source), 1):
        if maxlines is not None and lineno > maxlines:
            break
        lines.append(match[0])
    return lines


def _pad_whitespace(source: str) -> str:
    result = ""
    for c in source:
        if c in "\f\t":
            result += c
        else:
            result += " "
    return result


def get_source_segment(source: str, node: AST, *, padded: bool = False) -> str | None:
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
    todo = deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


def unparse(node: AST):
    # Reuse a per-thread NodeUnparser (warm visitor cache). Public API unchanged.
    from pynescript.ast.unparser import unparse_node

    return unparse_node(node)


__all__ = [
    "copy_location",
    "dump",
    "fix_missing_locations",
    "get_source_segment",
    "increment_lineno",
    "iter_child_nodes",
    "iter_fields",
    "literal_eval",
    "parse",
    "unparse",
    "walk",
]
