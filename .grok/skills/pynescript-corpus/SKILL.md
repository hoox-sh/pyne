---
name: pynescript-corpus
description: >
  Parse and harden the pynescript open-source Pine corpus (set01–set05), fix
  ANTLR4 grammar/lexer failures, sanitize scraped sources, and re-run fail buckets.
  Use when the user mentions corpus parse, set01/set02/set03/set04/set05, Pine
  Script grammar, ANTLR4 regeneration, corpus_sanitize, or runs /pynescript-corpus.
---

# pynescript-corpus

Agent workflow for **parser regression** against the open-source Pine corpus under
`tests/data/set0{1..5}/`, plus **ANTLR4 grammar** fixes in this repo.

## Hard constraints (never violate)

1. **Edit grammar only under**
   `src/pynescript/ast/grammar/antlr4/resource/`
   (`PinescriptLexer.g4`, `PinescriptParser.g4`, `*Base.py`).
2. **Regenerate** into `.../antlr4/generated/` — do not hand-edit generated ATNs
   except by re-running antlr4. Same for ASDL: edit
   `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`, regenerate nodes.
3. After parser rule changes, update **hand-written** `src/pynescript/ast/builder.py`
   visitors to match new context accessors.
4. `from __future__ import annotations` on every new Python file.
5. Prefer **minimal snippets + unit tests** before full corpus sweeps.

## Corpus layout

| Set | Role | Approx size |
| --- | --- | ---: |
| set01 | curated | ~250 |
| set02 | curated | ~250 |
| set03 | curated | ~1000 |
| set04 | curated | ~1000 |
| set05 | remainder dump | ~9k (slow; skip unless asked) |

Sources are scraped (GitHub, FMZ, docs). Many files include markdown chrome or are
**truncated mid-block** (`if cond` then EOF). Prefer grammar fixes only for real
Pine syntax gaps; use `corpus_sanitize` for page chrome.

## Commands

```bash
# Full sets (sanitize applied inside worker)
python scripts/corpus_parse_sets.py \
  --sets set01,set02,set03,set04 \
  --timeout 12 --workers 4 \
  --out .cache/corpus_parse_set01_set04.csv

# Resume after interrupt
python scripts/corpus_parse_sets.py --sets set01,set02,set03,set04 \
  --resume --out .cache/corpus_parse_set01_set04.csv

# Re-parse only FAIL/TIMEOUT rows after a code fix
python scripts/corpus_rerun_fails.py \
  --base .cache/corpus_parse_set01_set04.csv \
  --out .cache/corpus_parse_set01_set04_rerun_fails.csv

# Focused unit tests for corpus grammar fixes
.venv/bin/python -m pytest tests/test_lexer_corpus_fixes.py tests/test_corpus_sanitize.py -q

# Same corpus through pyne-worker Runtime (sibling repo)
cd /home/jango/Git/pyne-worker
.venv/bin/python scripts/corpus_run_sets.py \
  --sets set01,set02,set03,set04 --mode run --timeout 10 --workers 4
# Outputs: .cache/pyne_corpus_set01_set04.csv (+ _summary.txt)
# Modes: run (Runtime.eval) | parse (parse+unparse only)
```

Outputs:

- `.cache/corpus_parse_set01_set04.csv` — per-file status
- `.cache/corpus_parse_*_summary.txt` — rates + top error buckets

## ANTLR4 regeneration (reliable recipe)

`hatch run lint:gen-parser` is a thin wrapper; prefer a **flat temp dir** so paths
do not mirror `src/` into the output:

```bash
OUT=/tmp/pynescript-antlr-$$
mkdir -p "$OUT"
cp src/pynescript/ast/grammar/antlr4/resource/Pinescript{Lexer,Parser}.g4 "$OUT/"
cp src/pynescript/ast/grammar/antlr4/resource/Pinescript{Lexer,Parser}Base.py "$OUT/"
cd "$OUT"
antlr4 -Dlanguage=Python3 -visitor -listener PinescriptLexer.g4   # produces .tokens
antlr4 -Dlanguage=Python3 -visitor -listener PinescriptParser.g4
GEN=/path/to/repo/src/pynescript/ast/grammar/antlr4/generated
cp PinescriptLexer.py PinescriptParser.py \
   PinescriptParserVisitor.py PinescriptParserListener.py \
   PinescriptLexer.tokens PinescriptParser.tokens \
   PinescriptLexer.interp PinescriptParser.interp \
   PinescriptLexerBase.py PinescriptParserBase.py "$GEN/"
```

Lexer-only changes (tokens, fragments): you may copy only `PinescriptLexer.py` +
`LexerBase.py` if the parser ATN is unchanged — safer when builder is fragile.

ASDL (new operator/statement shapes):

```bash
.venv/bin/pip install 'pyasdl>=0.3.1'   # if needed
.venv/bin/python src/pynescript/ast/grammar/asdl/tool/asdlgen.py \
  src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl \
  -o src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py
```

## LexerBase behaviors (`PinescriptLexerBase.py`)

- Hides `NEWLINE` inside open `(`/`[` (`_numOpens`) and after **operator** tokens
  (line-join). Keep new binary/unary ops in `self._operators`.
- Emits `INDENT`/`DEDENT` only when indent width is a multiple of 4.
- `#` line comments via `HASH_COMMENT` (must not steal `#RRGGBB` colors).
- Markdown backticks → COMMENT channel; unicode paste noise → HIDDEN.

## Soft keywords

Parser `name` rule allows selected keywords as identifiers outside keyword
position (`TYPE`, `METHOD`, `CONST`, `AS`, `BY`, `TO`, …). Add corpus keywords
here when `mismatched input 'kw'` appears on valid Pine IDs.

## Fix triage (after a corpus run)

1. Bucket errors with a small Python/csv script (see summary `top_errors`).
2. Classify each bucket:
   - **Real grammar gap** → resource g4 + builder (+ ASDL/unparser if new ops)
   - **Scrape chrome** → `src/pynescript/util/corpus_sanitize.py` + unit test
   - **Truncated/stub file** (ends with `if x`, `foo(`, empty `=`) → leave; not a parser bug
   - **TIMEOUT** → large scripts / exponential ambiguity; raise timeout only for
     diagnosis, then profile; do not paper over with 60s defaults
3. Add a **minimal** case to `tests/test_lexer_corpus_fixes.py` or
   `tests/test_corpus_sanitize.py`.
4. Re-run fails only via `scripts/corpus_rerun_fails.py`.
5. Only then full set01–04 if projected rate moved.

## Known real gaps already addressed (2026-07)

- Operator line-join with trailing WS after `?`
- `#` comments vs color literals; backticks; unicode IDs
- `=` reassignment on attributes/subscripts (`strategy.initial_capital = …`)
- Soft keyword `as` / `by` / `to` as identifiers
- Bitwise: `& | ^ ~ << >>` (ASDL ops + builder + unparser)
- Typed UDF returns: `int f(int n) => …`
- Sanitize: fences, FMZ footers, Expand stubs, missing commas between `var` decls

## Key files

| Path | Role |
| --- | --- |
| `scripts/corpus_parse_sets.py` | Parallel parse+unparse with timeout/resume |
| `scripts/corpus_rerun_fails.py` | Re-check FAIL rows after a fix |
| `src/pynescript/util/corpus_sanitize.py` | Scrape chrome strip |
| `src/pynescript/ast/helper.py` | `parse` / `unparse` |
| `src/pynescript/ast/builder.py` | ANTLR visitor → ASDL AST |
| `src/pynescript/ast/unparser.py` | AST → source |
| `.../antlr4/resource/*.g4` | Grammar source of truth |
| `.opencode/context/project-intelligence/guides/grammar-changes.md` | Longer case studies |

## Smoke checklist before claiming done

```bash
python -c "from pynescript.ast.helper import parse, unparse; print(unparse(parse('''//@version=5
indicator(\"t\")
as = (1 << 2) | (3 & 1)
int f(int n) => n
plot(f(as))
''')))"
.venv/bin/python -m pytest tests/test_lexer_corpus_fixes.py tests/test_corpus_sanitize.py -q
```
