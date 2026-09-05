// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

lexer grammar PinescriptLexer;

options {
    superClass = PinescriptLexerBase;
}

tokens {
    INDENT,
    DEDENT
}

channels {
    COMMENT_CHANNEL
}

// KEYWORDS

AND:      'and';
AS:       'as';
BREAK:    'break';
BY:       'by';
CONST:    'const';
CONTINUE: 'continue';
ELSE:     'else';
ENUM:     'enum';
EXPORT:   'export';
FALSE:    'false';
FOR:      'for';
IF:       'if';
IMPORT:   'import';
IN:       'in';
INPUT:    'input';
METHOD:   'method';
NOT:      'not';
ONCE:     'once';
OR:       'or';
SERIES:   'series';
SIMPLE:   'simple';
SWITCH:   'switch';
TO:       'to';
TYPE:     'type';
TRUE:     'true';
VAR:      'var';
VARIP:    'varip';
WHILE:    'while';

// PUNCTUATIONS AND OPERATORS

LPAR: '(';
RPAR: ')';
LSQB: '[';
RSQB: ']';

// Multi-char ops first so ANTLR longest-match prefers them over '<' / '>'.
LSHIFT:       '<<';
RSHIFT:       '>>';
LESSEQUAL:    '<=';
GREATEREQUAL: '>=';
EQEQUAL:      '==';
NOTEQUAL:     '!=';
LESS:         '<';
GREATER:      '>';
EQUAL:        '=';

RARROW: '=>';

DOT:      '.';
COMMA:    ',';
COLON:    ':';
QUESTION: '?';

// Bitwise (Pine v5+): ~ unary, & | ^ binary, << >> shifts (above).
TILDE:  '~';
AMP:    '&';
PIPE:   '|';
CARET:  '^';

PLUS:    '+';
MINUS:   '-';
STAR:    '*';
SLASH:   '/';
PERCENT: '%';

PLUSEQUAL:    '+=';
MINEQUAL:     '-=';
STAREQUAL:    '*=';
SLASHEQUAL:   '/=';
PERCENTEQUAL: '%=';

COLONEQUAL: ':=';

// COMMON TOKENS

NAME:    ID_START ID_CONTINUE*;
NUMBER:  NUMBER_LITERAL;
STRING:  STRING_LITERAL;
COLOR:   COLOR_LITERAL;
NEWLINE: OS_INDEPENDENT_NL;

// WHITE SPACES, COMMENTS, MISCS

WS:          [ \t\f]+      -> channel(HIDDEN);
// TradingView uses // comments; also accept # line comments (markdown/python scrapes)
// and ignore markdown fence backticks. Emit as COMMENT so LexerBase newline
// joining treats them like //.
// IMPORTANT: HASH_COMMENT must NOT match #RRGGBB colors — only when '#' is
// followed by whitespace or a non-hex character.
COMMENT: '//' ~[\r\n]* -> channel(COMMENT_CHANNEL);
// Pine / C-style block comments (/* ... */), including newlines.
BLOCK_COMMENT: '/*' .*? '*/' -> type(COMMENT), channel(COMMENT_CHANNEL);
HASH_COMMENT: '#' ( [ \t\f] ~[\r\n]* | ~[0-9a-fA-F\r\n] ~[\r\n]* )
    -> type(COMMENT), channel(COMMENT_CHANNEL);
BACKTICKS: '`'+ -> type(COMMENT), channel(COMMENT_CHANNEL);
// Common paste noise (unicode arrows / bullets / curly quotes) — ignore
UNICODE_NOISE
    : [\u2190-\u2193\u21d0-\u21d3\u2022\u00b7\u2013\u2014\u2018\u2019\u201c\u201d]
    -> channel(HIDDEN)
    ;
ERROR_TOKEN: .;

// FRAGMENTS

// v6 multiline triple-quoted strings (explicit rules so lexer matches """...""" as STRING)
TRIPLE_DQ_STRING : '"""' ( ~'"' | '"' ~'"' | '""' ~'"' )* '"""' -> type(STRING) ;
TRIPLE_SQ_STRING : '\'\'\'' ( ~'\'' | '\'' ~'\'' | '\'\'' ~'\'' )* '\'\'\'' -> type(STRING) ;

fragment STRING_LITERAL: SINGLE_QUOTED_STRING | DOUBLE_QUOTED_STRING;

fragment SINGLE_QUOTED_STRING: '\'' STRING_ITEM_FOR_SINGLE_QUOTE* '\'';
fragment DOUBLE_QUOTED_STRING: '"' STRING_ITEM_FOR_DOUBLE_QUOTE* '"';

fragment STRING_ITEM_FOR_SINGLE_QUOTE
    : STRING_CHAR_NO_SINGLE_QUOTE
    | STRING_ESCAPE_SEQ;
fragment STRING_ITEM_FOR_DOUBLE_QUOTE
    : STRING_CHAR_NO_DOUBLE_QUOTE
    | STRING_ESCAPE_SEQ;

fragment STRING_CHAR_NO_SINGLE_QUOTE: ~[\\'];
fragment STRING_CHAR_NO_DOUBLE_QUOTE: ~[\\"];

fragment STRING_ESCAPE_SEQ: '\\' .;

fragment COLOR_LITERAL: COLOR_LITERAL_RGBA | COLOR_LITERAL_RGB;

fragment COLOR_LITERAL_RGBA
    : '#' HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT;
fragment COLOR_LITERAL_RGB
    : '#' HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT;

fragment NUMBER_LITERAL: INTEGER | FLOAT_NUMBER | IMAG_NUMBER;

fragment INTEGER:        DEC_INTEGER | BIN_INTEGER | OCT_INTEGER | HEX_INTEGER;
fragment DEC_INTEGER:    NON_ZERO_DIGIT ('_'? DIGIT)* | '0' ('_'? DIGIT)*;
fragment BIN_INTEGER:    '0' ('b' | 'B') ('_'? BIN_DIGIT)+;
fragment OCT_INTEGER:    '0' ('o' | 'O') ('_'? OCT_DIGIT)+;
fragment HEX_INTEGER:    '0' ('x' | 'X') ('_'? HEX_DIGIT)+;
fragment NON_ZERO_DIGIT: [1-9];
fragment DIGIT:          [0-9];
fragment BIN_DIGIT:      '0' | '1';
fragment OCT_DIGIT:      [0-7];
fragment HEX_DIGIT:      DIGIT | [a-f] | [A-F];

fragment FLOAT_NUMBER:   POINT_FLOAT | EXPONENT_FLOAT;
fragment POINT_FLOAT:    DIGIT_PART? FRACTION | DIGIT_PART '.';
fragment EXPONENT_FLOAT: (DIGIT_PART | POINT_FLOAT) EXPONENT;
fragment DIGIT_PART:     DIGIT ('_'? DIGIT)*;
fragment FRACTION:       '.' DIGIT_PART;
fragment EXPONENT:       ('e' | 'E') ('+' | '-')? DIGIT_PART;

fragment IMAG_NUMBER: (FLOAT_NUMBER | DIGIT_PART) ('j' | 'J');

fragment OS_INDEPENDENT_NL: '\r'? '\n';

// Allow Unicode letters in identifiers (common in non-English scripts/titles used as names)
fragment ID_START:    [\p{L}_];
fragment ID_CONTINUE: [\p{L}\p{Nd}_];