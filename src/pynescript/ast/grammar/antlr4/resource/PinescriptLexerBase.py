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

"""Hand-maintained ANTLR lexer base helpers for Pine Script."""

from __future__ import annotations


import re
import sys

from collections import deque
from typing import TextIO

from antlr4 import InputStream
from antlr4 import Lexer
from antlr4 import Token
from antlr4.Token import CommonToken

from pynescript.ast.error import IndentationError as PinescriptIndentationError
from pynescript.ast.error import SyntaxError as PinescriptSyntaxError

# Precompiled once — only applied to line-wrapped single/double-quoted strings.
_STRING_COLLAPSE_NL = re.compile(r"(\r?\n)+")
_STRING_STRIP_WRAP_INDENT = re.compile(r"(\r?\n)(\s)+")


class PinescriptLexerBase(Lexer):
    # ruff: noqa: N802, N806, A002

    """
    - ignore possible leading newlines
    - ignore excessive trailing newlines except a single newline
    - ensure that script ends with a newline if none
    - ignore consecutive newlines except the last one
    - ignore newlines inside open parentheses, brackets
    - ignore newlines after operators
    - ignore newlines for line wraping (lines whose indentation width is not a multiple of four)
    - track indentation level, push INDENT or DEDENT token respectfully
    - handle multiline string literal correctly (ignore <newline + indentation for line wrapping>)
    """

    # Built lazily on first lexer instance of each concrete subclass (token ids differ by grammar).
    _operator_types: frozenset[int] | None = None

    def __init__(self, input: InputStream, output: TextIO = sys.stdout):
        super().__init__(input, output)

        cls = type(self)
        ops = cls._operator_types
        if ops is None:
            ops = frozenset(
                {
                    self.AND,
                    self.COLON,
                    self.COLONEQUAL,
                    self.COMMA,
                    self.EQEQUAL,
                    self.EQUAL,
                    self.GREATER,
                    self.GREATEREQUAL,
                    self.LESS,
                    self.LESSEQUAL,
                    self.MINEQUAL,
                    self.MINUS,
                    self.NOTEQUAL,
                    self.OR,
                    self.PERCENT,
                    self.PERCENTEQUAL,
                    self.PLUS,
                    self.PLUSEQUAL,
                    self.QUESTION,
                    self.SLASH,
                    self.SLASHEQUAL,
                    self.STAR,
                    self.STAREQUAL,
                    # bitwise / shift (Pine v5+)
                    self.AMP,
                    self.PIPE,
                    self.CARET,
                    self.LSHIFT,
                    self.RSHIFT,
                    self.TILDE,
                }
            )
            cls._operator_types = ops
        self._operators = ops

        # indent specific parameters
        self._tabLength: int = 4
        self._indentLength: int = 4

        # track internal tokens
        self._currentToken: CommonToken | None = None
        self._followingToken: CommonToken | None = None

        # keep pending tokens (deque: O(1) popleft vs list.pop(0))
        self._pendingTokens: deque[CommonToken] = deque()

        # track last pending token types
        self._lastPendingTokenType: int = 0
        self._lastPendingTokenTypeFromDefaultChannel: int = 0

        # track number of opens
        self._numOpens: int = 0

        # track indentations
        self._indentLengthStack: deque[int] = deque()

        # True after start-of-input indent bootstrap has run
        self._inputStarted: bool = False

    def _resetInternalStates(self):
        self._currentToken = None
        self._followingToken = None
        self._pendingTokens = deque()
        self._lastPendingTokenType = 0
        self._lastPendingTokenTypeFromDefaultChannel = 0
        self._numOpens = 0
        self._indentLengthStack = deque()
        self._inputStarted = False

    def nextToken(self) -> CommonToken:
        self._checkNextToken()
        return self._popPendingToken()

    def _checkNextToken(self) -> None:
        if self._lastPendingTokenType == Token.EOF:
            return

        self._setNextInternalTokens()
        if not self._inputStarted:
            self._handleStartOfInputIfNecessary()

        tok_type = self._currentToken.type
        # Hot path: most tokens are identifiers / keywords / numbers / ops.
        # if/elif is slightly cheaper than match for dense integer dispatch.
        if tok_type == self.LPAR or tok_type == self.LSQB:
            self._numOpens += 1
            self._addPendingToken(self._currentToken)
        elif tok_type == self.RPAR or tok_type == self.RSQB:
            self._numOpens -= 1
            self._addPendingToken(self._currentToken)
        elif tok_type == self.NEWLINE:
            self._handle_NEWLINE_token()
        elif tok_type == self.STRING:
            self._handle_STRING_token()
        elif tok_type == self.ERROR_TOKEN:
            message = "token recognition error at: '" + self._currentToken.text + "'"
            self._reportLexerError(message, self._currentToken, PinescriptSyntaxError)
            self._addPendingToken(self._currentToken)
        elif tok_type == Token.EOF:
            self._handle_EOF_token()
        else:
            self._addPendingToken(self._currentToken)

    def _reachedEndOfFile(self) -> bool:
        return self._lastPendingTokenType == Token.EOF

    def _setNextInternalTokens(self) -> None:
        self._currentToken = super().nextToken() if self._followingToken is None else self._followingToken
        self._followingToken = self._currentToken if self._currentToken.type == Token.EOF else super().nextToken()

    def _handleStartOfInputIfNecessary(self):
        if self._inputStarted:
            return
        self._inputStarted = True
        self._indentLengthStack.append(0)
        while self._currentToken.type != Token.EOF:
            if self._currentToken.channel == Token.DEFAULT_CHANNEL:
                if self._currentToken.type == self.NEWLINE:
                    self._hideAndAddPendingToken(self._currentToken)
                else:
                    self._checkLeadingIndentIfAny()
                    return
            else:
                self._addPendingToken(self._currentToken)
            self._setNextInternalTokens()

    def _checkLeadingIndentIfAny(self):
        if self._lastPendingTokenType == self.WS:
            prev_token: CommonToken = self._pendingTokens[-1]
            if self._getIndentationLength(prev_token.text) != 0:
                message = "first statement indented"
                self._reportLexerError(message, self._currentToken, PinescriptIndentationError)
                self._createAndAddPendingToken(self.INDENT, Token.DEFAULT_CHANNEL, message, self._currentToken)

    def _getIndentationLength(self, text: str) -> int:
        length = 0
        tab = self._tabLength
        for ch in text:
            if ch == " ":
                length += 1
            elif ch == "\t":
                length += tab
            elif ch == "\f":
                length = 0
        return length

    def _createAndAddPendingToken(self, type: int, channel: int, text: str | None, base_token: CommonToken):
        token: CommonToken = base_token.clone()
        token.type = type
        token.channel = channel
        token.stop = base_token.start - 1
        token.text = "<" + self.symbolicNames[type] + ">" if text is None else text
        self._addPendingToken(token)

    def _addPendingToken(self, token: CommonToken):
        self._lastPendingTokenType = token.type
        if token.channel == Token.DEFAULT_CHANNEL:
            self._lastPendingTokenTypeFromDefaultChannel = self._lastPendingTokenType
        self._pendingTokens.append(token)

    def _hideAndAddPendingToken(self, token: CommonToken):
        token.channel = Token.HIDDEN_CHANNEL
        self._addPendingToken(token)

    def _popPendingToken(self) -> CommonToken:
        return self._pendingTokens.popleft()

    def _handle_NEWLINE_token(self):
        # Use last *default-channel* token so trailing spaces after operators
        # (e.g. `x = cond ? <spaces>\n  cont`) still line-join. Hidden WS must
        # not clear the operator-continuation state.
        if self._numOpens > 0 or self._lastPendingTokenTypeFromDefaultChannel in self._operators:
            self._hideAndAddPendingToken(self._currentToken)
            return

        nl_token: CommonToken = self._currentToken
        following_type = self._followingToken.type
        is_looking_ahead: bool = following_type == self.WS

        if is_looking_ahead:
            self._setNextInternalTokens()
            following_type = self._followingToken.type

        if following_type == self.NEWLINE or following_type == self.COMMENT:
            self._hideAndAddPendingToken(nl_token)
            if is_looking_ahead:
                self._addPendingToken(self._currentToken)
        elif is_looking_ahead:
            indentation_length: int = (
                0 if following_type == Token.EOF else self._getIndentationLength(self._currentToken.text)
            )
            if indentation_length % self._indentLength == 0:
                self._addPendingToken(nl_token)
                self._addPendingToken(self._currentToken)
                self._insertIndentOrDedentToken(indentation_length)
            else:
                self._hideAndAddPendingToken(nl_token)
                self._addPendingToken(self._currentToken)
        else:
            self._addPendingToken(nl_token)
            self._insertIndentOrDedentToken(0)

    def _isValidIndent(self, indent_length: int):
        return indent_length % self._indentLength == 0

    def _insertIndentOrDedentToken(self, indent_length: int):
        prev_indent_length: int = self._indentLengthStack[-1]
        if indent_length > prev_indent_length:
            self._createAndAddPendingToken(self.INDENT, Token.DEFAULT_CHANNEL, None, self._followingToken)
            self._indentLengthStack.append(indent_length)
        else:
            while indent_length < prev_indent_length:
                self._indentLengthStack.pop()
                prev_indent_length = self._indentLengthStack[-1]
                if indent_length <= prev_indent_length:
                    self._createAndAddPendingToken(self.DEDENT, Token.DEFAULT_CHANNEL, None, self._followingToken)
                else:
                    message = "inconsistent dedent"
                    self._reportLexerError(message, self._followingToken, PinescriptIndentationError)
                    self._createAndAddPendingToken(
                        self.ERROR_TOKEN, Token.DEFAULT_CHANNEL, message, self._followingToken
                    )

    def _handle_STRING_token(self):
        # Pine v6 triple-quoted multiline strings keep *all* newlines and
        # indentation literally. Only single/double-quoted strings that are
        # line-wrapped across physical source lines strip wrap-indent.
        text = self._currentToken.text
        if text.startswith('"""') or text.startswith("'''"):
            self._addPendingToken(self._currentToken)
            return

        # Fast path: ordinary single-line strings (vast majority) need no rewrite.
        if "\n" not in text and "\r" not in text:
            self._addPendingToken(self._currentToken)
            return

        replacedText = _STRING_COLLAPSE_NL.sub(r"\1", text)
        replacedText = _STRING_STRIP_WRAP_INDENT.sub("", replacedText)
        if len(text) == len(replacedText):
            self._addPendingToken(self._currentToken)
        else:
            originalToken: CommonToken = self._currentToken.clone()
            self._currentToken.text = replacedText
            self._addPendingToken(self._currentToken)
            self._hideAndAddPendingToken(originalToken)

    def _insertTrailingTokens(self):
        last = self._lastPendingTokenTypeFromDefaultChannel
        if last != self.NEWLINE and last != self.DEDENT:
            self._createAndAddPendingToken(self.NEWLINE, Token.DEFAULT_CHANNEL, None, self._followingToken)
        self._insertIndentOrDedentToken(0)

    def _handle_EOF_token(self):
        if self._lastPendingTokenTypeFromDefaultChannel > 0:
            self._insertTrailingTokens()
        self._addPendingToken(self._currentToken)

    def _reportLexerError(self, message, token, errcls):
        lineno = token.line
        offset = token.column
        error = errcls(message) if errcls else None
        self.getErrorListenerDispatch().syntaxError(
            self,
            token,
            lineno,
            offset,
            message,
            error,
        )

    def reset(self):
        self._resetInternalStates()
        super().reset()
