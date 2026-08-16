# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 02 — Language Core

**Track:** Language Core (`docs/pyne/core/*`)  
**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-118a-7e01-b58e-371b945f1c90`  
**Package:** `hoox-pyne` 0.3.10 (`src/pynescript/__about__.py`)  
**Verdict:** **updated**

## Pages read

- `docs/pyne/core/index.mdx`
- `docs/pyne/core/grammar-antlr4.mdx`
- `docs/pyne/core/asdl-schema.mdx`
- `docs/pyne/core/builder.mdx`
- `docs/pyne/core/helper-api.mdx`
- `docs/pyne/core/unparser.mdx`
- `docs/pyne/core/visitor-transformer.mdx`
- `docs/pyne/core/type-system.mdx`
- `docs/pyne/core/linter.mdx`
- `docs/pyne/core/error-model.mdx`
- `docs/WRITING.md`, `docs/docs_audit_2026-08-16/PROMPT.md`

## Pages edited

All ten exclusive pages above (no deletes, no new pages, `docs.json` untouched).

## Pages added / deleted

None. No `docs.json` insertion needed.

## Code checked

| Path | What was verified |
| --- | --- |
| `src/pynescript/__about__.py` | Version **0.3.10** |
| `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4` | Triple strings, `HASH_COMMENT`/`BACKTICKS`, bitwise tokens, `COMMENT_CHANNEL` |
| `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4` | Left-factored `variable_declaration` / `for_iterator` / params; `=` vs `:=`; UDF return type; bitwise layers; trailing structures; soft `name` |
| `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexerBase.py` | INDENT/DEDENT, indent=4, `IndentationError` |
| `src/pynescript/ast/grammar/antlr4/tool/generate.py` | Project-aware regen + copy of `*Base.py` |
| `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl` | `FunctionDef.returns`, bitwise ops, `Invert` |
| `src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py` | Generated `FunctionDef.returns` field |
| `src/pynescript/ast/grammar/asdl/tool/generate.py` + `asdlgen.py` | Writes **file** `PinescriptASTNode.py`, not a directory |
| `src/pynescript/ast/builder.py` | `_setLocations` direct attrs; `_getLocations` unused dict helper; `FunctionDef.returns`; Assign vs ReAssign |
| `src/pynescript/ast/helper.py` | sha256 LRU (`PYNE_PARSE_CACHE`, max 128); SLL→LL; TLS engine; shared builder; `__all__` |
| `src/pynescript/ast/unparser.py` | Full `Precedence` enum; bitwise maps; `visit_FunctionDef` emits `returns`; `unparse_node` TLS |
| `src/pynescript/ast/visitor.py` / `transformer.py` / `collector.py` | Type-object visitor cache; transformer list splice; collector `Structure` tuple |
| `src/pynescript/ast/type_system.py` | Qualifiers, builtins, collections, UDT, registry, resolver |
| `src/pynescript/ast/linter.py` | E001–C004 codes; E001 now copies `details` line/column |
| `src/pynescript/ast/error.py` + `grammar/antlr4/error_listener.py` | `SyntaxErrorDetails`, caret `__str__`, singleton listener |
| `src/pynescript/ast/node.py` | Re-export; documents `FunctionDef.returns` |
| `pyproject.toml` | `hatch run lint:gen-parser` is only `antlr4 {args}` |

## Fixes applied (must-fix + missing surface)

- **Generated-path rule kept:** resource-only edits; `generated/` is never presented as hand-edited.
- **`FunctionDef.returns`:** added to ASDL schema, builder visit table + example, unparser emission, core invariants.
- **Builder locations:** `_setLocations` documented as **direct attribute writes**; `_getLocations` marked unused dict helper (not the live path).
- **Unparser precedence list** now matches `IntEnum` (`BITOR`/`BITXOR`/`BITAND`/`SHIFT`/`EXPR`/`Invert`).
- **Linter catalog** still matches code (`E001`, `W001`/`W002`, `W101`–`W103`, `C001`–`C004`); E001 location extraction updated; error-model no longer claims details are discarded.
- **Helper parse cache:** sha256 + mode LRU, `PYNE_PARSE_CACHE` / `PYNE_PARSE_CACHE_MAX`, `clear_parse_cache` / `parse_cache_info`, identity/mutability warning, `__all__`.
- **0.3.9 grammar:** left-factored typed names; `Assign` (`name =`) vs `ReAssign` (`:=` or attr/subscript `=`); UDF return types; bitwise expression layers; `HASH_COMMENT`.
- **Regen commands:** ANTLR via `python -m pynescript.ast.grammar.antlr4.tool.generate` (hatch script is just the CLI); ASDL via `…asdl.tool.generate` (not bare `pyasdl -o generated/`).
- **Visitor cache:** type-object keys, not class-name strings; unparser has a second `_type_visitor_cache`.

## Remaining holes

- Type system is still a modeling vocabulary, not a checker (`is_compatible_with` is shallow). Bar-loop coercion lives in the evaluator (agent 03).
- Linter rules remain regex heuristics (`C001` camelCase, `C003` any indented `if`).
- `_getLocations` is dead on the visit path; left in code, documented as unused.
- `Precedence.EXPR` exists in the enum but is unused by current op tables.
- `hatch run lint:gen-parser` without flags does **not** point at `resource/` / `generated/` — easy footgun; documented, not a hatch change (out of this track).
- Public `pynescript.ast` module docstring still omits `clear_parse_cache` / `parse_cache_info` (code, not this page set).
- Evaluator/LSP consumption of `FunctionDef.returns` is out of this track.

## Verdict

**updated** — exclusive core pages now match 0.3.10 language-core code. No nav change.
