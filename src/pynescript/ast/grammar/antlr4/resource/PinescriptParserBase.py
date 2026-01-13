# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import sys

from typing import TextIO

from antlr4 import Parser
from antlr4 import TokenStream


class PinescriptParserBase(Parser):
    # ruff: noqa: N802, N803, A002

    def __init__(self, input: TokenStream, output: TextIO = sys.stdout):
        super().__init__(input, output)

    def isEqualToCurrentTokenText(self, tokenText: str) -> bool:
        return self.getCurrentToken().text == tokenText

    def isNotEqualToCurrentTokenText(self, tokenText: str) -> bool:
        return not self.isEqualToCurrentTokenText(tokenText)
