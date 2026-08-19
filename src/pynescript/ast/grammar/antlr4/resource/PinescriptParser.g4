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

parser grammar PinescriptParser;

options {
    tokenVocab = PinescriptLexer;
    superClass = PinescriptParserBase;
}

// STARTING RULES

start: start_script;

start_script:     statements? EOF;
start_expression: expression NEWLINE? EOF;

start_comments: comments? EOF;

// STATEMENTS

statements: statement+;
statement:  compound_statement | simple_statements | trailing_structure_statements;

// COMPOUND_STATEMENTS

compound_statement
    : compound_assignment
    | type_declaration
    | enum_declaration
    | structure_statement
    | method_declaration
    | function_declaration;

// SIMPLE STATEMENTS

simple_statements: simple_statement (COMMA simple_statement)* COMMA? NEWLINE;

// Pine multi-statement lines may end with a structure, e.g.:
//   Ex = 0.0, Ey = 0.0, for i=0 to n
//       ...
trailing_structure_statements
    : simple_statement (COMMA simple_statement)* COMMA structure;

simple_statement
    : simple_assignment
    | expression_statement
    | import_statement
    | break_statement
    | continue_statement;

// COMPOUND ASSIGNMENTS

compound_assignment
    : compound_variable_initialization
    | compound_reassignment
    | compound_augassignment;

compound_variable_initialization
    : compound_name_initialization
    | compound_tuple_initialization;

// EXPORT? supports library `export const T name = expr` (June 2025)
compound_name_initialization:  EXPORT? variable_declaration EQUAL structure_expression;
compound_tuple_initialization: tuple_declaration EQUAL structure_expression;

compound_reassignment:  primary_expression COLONEQUAL structure_expression;
compound_augassignment: primary_expression augassign_op structure_expression;

// FUNCTION DECLARATION
// Optional leading type_specification is the return type (Pine v5+/v6 UDFs):
//   int ilog2(int n) => ...
//   void fft_inplace(float[] re, float[] im, int N) => ...

function_declaration
    : EXPORT? type_specification name LPAR parameter_list? RPAR RARROW local_block
    | EXPORT? name LPAR parameter_list? RPAR RARROW local_block
    ;

parameter_list:       parameter_definition (COMMA parameter_definition)* COMMA?;
parameter_definition
    : type_specification name_store (EQUAL expression)?
    | name_store (EQUAL expression)?
    ;

// METHOD DECLARATION

method_declaration
    : EXPORT? METHOD type_specification name LPAR method_parameter_list? RPAR RARROW local_block
    | EXPORT? METHOD name LPAR method_parameter_list? RPAR RARROW local_block
    ;

method_parameter_list: method_parameter_definition (COMMA method_parameter_definition)* COMMA?;
method_parameter_definition: type_specification name_store | parameter_definition;

// TYPE DECLARATION

type_declaration: EXPORT? TYPE name NEWLINE INDENT field_definitions DEDENT;

field_definitions: field_definition+;
field_definition:  VARIP? type_specification name_store (EQUAL expression)? NEWLINE;

// ENUM DECLARATION

enum_declaration: EXPORT? ENUM name NEWLINE INDENT enum_definitions DEDENT;

enum_definitions: enum_definition+;
enum_definition:  name_store (EQUAL expression)? NEWLINE;

// STRUCTURES

structure: if_structure | for_structure | while_structure | switch_structure;

structure_statement:  structure;
structure_expression: structure;

// IF STRUCTURE

if_structure: IF expression local_block if_tail?;
elif_structure: ELSE IF expression local_block if_tail?;
if_tail: elif_structure | else_block;

else_block: ELSE local_block;

// FOR STRUCTURE

for_structure: for_structure_to | for_structure_in;

for_structure_to
    : FOR for_iterator EQUAL expression TO expression (BY expression)? local_block;
for_structure_in: FOR for_iterator IN expression local_block;

// Typed iterators are valid Pine (e.g. `for int i = 0 to n` / `for float x in arr`).
// Prefer the typed alternative first so `int` is not consumed as the loop variable.
for_iterator
    : type_specification name_store
    | name_store
    | tuple_declaration
    ;

// WHILE STRUCTURE

while_structure: WHILE expression local_block;

// SWITCH STRUCTURE

switch_structure: SWITCH expression? NEWLINE INDENT switch_cases DEDENT;

switch_cases: switch_pattern_case+ switch_default_case?;

// Multi-value arms: ``1, 2 => 100`` (OR-match on subject).
switch_pattern_case: switch_patterns RARROW local_block;
switch_patterns: expression (COMMA expression)*;
switch_default_case: RARROW local_block;

// LOCAL BLOCK

local_block: indented_local_block | inline_local_block;

indented_local_block: NEWLINE INDENT statements DEDENT;
inline_local_block:   statement;

// SIMPLE ASSIGNMENTS

simple_assignment
    : simple_variable_initialization
    | simple_reassignment
    | simple_augassignment;

simple_variable_initialization
    : simple_name_initialization
    | simple_tuple_initialization;

// EXPORT? supports library `export const T name = expr` (June 2025)
simple_name_initialization:  EXPORT? variable_declaration EQUAL expression;
simple_tuple_initialization: tuple_declaration EQUAL expression;

// Pine uses := for reassignment. ``=`` on a bare name is initialization
// (simple_name_initialization). ``=`` is only reassignment for attribute /
// subscript targets (e.g. strategy.initial_capital = 50000).
simple_reassignment
    : assignment_target_attribute EQUAL expression
    | assignment_target_subscript EQUAL expression
    | primary_expression COLONEQUAL expression
    ;
simple_augassignment: primary_expression augassign_op expression;

// EXPRESSIONS

expression:           conditional_expression;
expression_statement: expression;

// CONDITIONAL TERNARY EXPRESSION

conditional_expression: disjunction_expression (QUESTION expression COLON expression)?;

// LOGICAL EXPRESSIONS

disjunction_expression: conjunction_expression (OR conjunction_expression)*;

// Logical AND binds less tightly than bitwise OR (C-like / Pine bitwise).
conjunction_expression: bitwise_or_expression (AND bitwise_or_expression)*;

// BITWISE EXPRESSIONS (Pine v5+): |  ^  &  << >>  between logical and compare

bitwise_or_expression
    : bitwise_or_expression PIPE bitwise_xor_expression
    | bitwise_xor_expression;

bitwise_xor_expression
    : bitwise_xor_expression CARET bitwise_and_expression
    | bitwise_and_expression;

bitwise_and_expression
    : bitwise_and_expression AMP equality_expression
    | equality_expression;

// COMPARISON EXPRESSIONS

equality_expression: inequality_expression equality_trailing_pair*;

equality_trailing_pair: equal_trailing_pair | not_equal_trailing_pair;

equal_trailing_pair:     EQEQUAL inequality_expression;
not_equal_trailing_pair: NOTEQUAL inequality_expression;

inequality_expression: shift_expression inequality_trailing_pair*;

inequality_trailing_pair
    : less_than_equal_trailing_pair
    | less_than_trailing_pair
    | greater_than_equal_trailing_pair
    | greater_than_trailing_pair;

less_than_equal_trailing_pair:    LESSEQUAL shift_expression;
less_than_trailing_pair:          LESS shift_expression;
greater_than_equal_trailing_pair: GREATEREQUAL shift_expression;
greater_than_trailing_pair:       GREATER shift_expression;

// SHIFT EXPRESSIONS

shift_expression
    : shift_expression shift_op additive_expression
    | additive_expression;

shift_op: LSHIFT | RSHIFT;

// ARITHMETIC EXPRESSIONS

additive_expression
    : additive_expression additive_op multiplicative_expression
    | multiplicative_expression;

additive_op: PLUS | MINUS;

multiplicative_expression
    : multiplicative_expression multiplicative_op unary_expression
    | unary_expression;

multiplicative_op: STAR | SLASH | PERCENT;

unary_expression: unary_op unary_expression | primary_expression;

// ~ is bitwise NOT (Invert); not/+/ - unchanged
unary_op: NOT | PLUS | MINUS | TILDE;

// PRIMARY EXPRESSIONS

primary_expression
    : primary_expression DOT name_load                                  # primary_expression_attribute
    // template_spec_suffix before LPAR enables array.new<float>(...) form
    | primary_expression template_spec_suffix? LPAR argument_list? RPAR # primary_expression_call
    | primary_expression LSQB subscript_slice RSQB                      # primary_expression_subscript
    | atomic_expression                                                 # primary_expression_fallback;

argument_list:       argument_definition (COMMA argument_definition)* COMMA?;
argument_definition: (name_store EQUAL)? expression;

subscript_slice: expression (COMMA expression)* COMMA?;

// ATOMIC EXPRESSIONS

atomic_expression
    : name_load
    | literal_expression
    | grouped_expression
    | tuple_expression;

literal_expression
    : literal_number
    | literal_string
    | literal_bool
    | literal_color;

literal_number: NUMBER;
literal_string: STRING;
literal_bool:   TRUE | FALSE;
literal_color:  COLOR;

grouped_expression: LPAR expression RPAR;
tuple_expression:   LSQB (expression (COMMA expression)* COMMA?)? RSQB;

// IMPORT

import_statement: IMPORT name SLASH name SLASH literal_number (AS name)?;

// LOOP CONTROLS

break_statement:    BREAK;
continue_statement: CONTINUE;

// VARIABLE DECLARATION AND ASSIGNMENT RELATED SEGMENTS

variable_declaration
    : declaration_mode? type_specification name_store
    | declaration_mode? name_store
    ;
tuple_declaration:    LSQB name_store (COMMA name_store)* COMMA? RSQB;

declaration_mode: VARIP | VAR;

assignment_target
    : assignment_target_attribute
    | assignment_target_subscript
    | assignment_target_name
    | assignment_target_group;

assignment_target_attribute: primary_expression DOT name_store;
assignment_target_subscript: primary_expression LSQB subscript_slice RSQB;
assignment_target_name:      name_store;
assignment_target_group:     LPAR assignment_target RPAR;

augassign_op: STAREQUAL | SLASHEQUAL | PERCENTEQUAL | PLUSEQUAL | MINEQUAL;

// TYPE SPECIFICATION

type_specification
    : type_qualifier? attributed_type_name template_spec_suffix? array_type_suffix?;

type_qualifier:       CONST | INPUT | SIMPLE | SERIES;
attributed_type_name: name_load (DOT name_load)*;

template_spec_suffix: LESS type_argument_list? GREATER;
array_type_suffix:    LSQB RSQB;

type_argument_list: type_specification (COMMA type_specification)* COMMA?;

// NAME WITH SOFT KEYWORDS
// Pine allows many reserved words as identifiers outside their keyword position
// (e.g. `as = input(...)`, `by = 1`). Keep structural keywords (if/for/...) hard.

name
    : NAME
    | TYPE
    | METHOD
    | CONST
    | INPUT
    | SIMPLE
    | SERIES
    | ENUM
    | AS
    | BY
    | TO
    ;

name_load:  name;
name_store: name;

// COMMENTS

comments: comment+;
comment:  COMMENT;