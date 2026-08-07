# Design

A high-level look at **how pynescript is put together and why**. For *what to
run* read [`AGENTS.md`](./AGENTS.md). For *deep reference* read
[`.opencode/context/`](./.opencode/context/navigation.md). For the LSP
implementation timeline read
[`.opencode/plans/pynescript-lsp-implementation.md`](./.opencode/plans/pynescript-lsp-implementation.md).

---

## 1. Mission

Give Pine Script developers a real, offline toolchain — parser, linter,
evaluator, completion, hover, navigation, and formatting — that works in any
LSP-capable editor (VS Code, Neovim, Zed, Emacs), without depending on
TradingView's browser-only editor.

Pine Script is a small DSL with ~482 builtins. The toolchain goal is to model
it fully enough that scripts can be:

- **Parsed** losslessly (round-trip parse → unparse).
- **Statically analysed** (9+ lint rules, type system, UDT inference).
- **Evaluated** deterministically (literal expressions, full scripts with mock
  data).
- **Edited professionally** (LSP-driven diagnostics, completion, hover,
  formatting, definition, references, document symbols).

A Pro API layer adds live chart previews and backtests on top of the same
evaluation engine, monetizing the work the open toolchain drives.

---

## 2. System Architecture

```
                          ┌──────────────────────────────────────┐
                          │   Editor (VS Code, Neovim, Zed, Emacs)│
                          │   - VS Code ext = Node 22 + bundles LSP binary
                          │   - Others = pip install pynescript[lsp]
                          └────────────────┬─────────────────────┘
                                           │  LSP over STDIO
                                           ▼
        ┌────────────────────────────────────────────────────────────┐
        │  pynescript-lsp  (pygls-based, distributed as Nuitka onefile)
        │  ─────────────────────────────────────────────────────────  │
        │  Workspace  ───►  Parser  ───►  AST  ───►  Linter
        │                                       │
        │                                       ├─►  Completion (482 builtins)
        │                                       ├─►  Hover (signature + doc)
        │                                       ├─►  Formatting (unparse)
        │                                       ├─►  Definition / References
        │                                       └─►  Document Symbols
        └──────────────┬──────────────────────────────────┬──────────┘
                       │                                  │
                       │ (open)                           │ (Pro tier)
                       ▼                                  ▼
       ┌──────────────────────────┐       ┌──────────────────────────────┐
       │  src/pynescript/ast/     │       │  backend/  (Flask, Cloud Run)│
       │   builder + evaluator    │       │   POST /run                  │
       │   linter + type_system   │       │   POST /preview/chart        │
       │   (in-process)           │       │   POST /preview/indicator    │
       └────────────┬─────────────┘       │   POST /backtest/quick       │
                    │                     └──────────────┬───────────────┘
                    │  Pine Script source                  │
                    │  .pine (TradingView editor)          │  chart PNG / equity curve
                    │                                     ▼
                    │                       Editor / Browser / SDK client
                    ▼
       ┌──────────────────────────┐
       │  ANTLR4 grammar (.g4)    │
       │   → generated parser     │
       │  ASDL schema (.asdl)     │
       │   → generated AST nodes  │
       └──────────────────────────┘
```

Two product surfaces share the same AST:

1. **Editor toolchain** (`pynescript-lsp`, the open package, the VS Code ext).
2. **Pro API** (`backend/`, the closed-source-style server).

Both are physically separate but speak the same internal AST, so the Pro API
can run user scripts in a sandboxed `Runtime` against real or mock market
data.

---

## 3. Repository Layout

Top-level intent (full tree in
[`.opencode/context/project-intelligence/lookup/directory-map.md`](./.opencode/context/project-intelligence/lookup/directory-map.md)):

| Path | Role |
| --- | --- |
| `src/pynescript/` | Open package: parser, AST, evaluator, linter, LSP |
| `backend/` | Pro API (Flask, deployed to Cloud Run) |
| `vscode-extension/` | TypeScript extension that bundles the LSP binary |
| `clients/` | Editor config snippets (Neovim, Zed, Emacs, Helix) |
| `scripts/` | Build + utility (Nuitka, metadata regen, copyright) |
| `tests/` | pytest suite, parametrized over a real `.pine` corpus |
| `docs/` | Sphinx docs (re-exports the README + per-phase reports) |
| `examples/` | Sample Pine scripts |
| `.opencode/` | OpenCode workspace + agent context tree (this file lives under it) |

The `src/pynescript/ast/grammar/` subtree is split deliberately:

- `antlr4/resource/*.g4` — **hand-edited** grammar.
- `antlr4/generated/*` — **regenerated** Python parser/lexer (never edit).
- `asdl/resource/Pinescript.asdl` — **hand-edited** AST schema.
- `asdl/generated/PinescriptASTNode.py` — **regenerated** AST node classes.

This split keeps the hand-edited surface area small and machine-verifiable.

---

## 4. Data Flow

### 4.1 Parse and Unparse (round-trip)

```
pine source
   └─► FileStream (utf-8)
        └─► PinescriptLexer         (grammar/antlr4/generated/)
             └─► CommonTokenStream
                  └─► PinescriptParser
                       └─► parse tree
                            └─► PinescriptASTBuilder.visit_*   (ast/builder.py)
                                 └─► AST (ASDL-typed Script, FunctionDef, ...)
                                      └─► _add_annotations()    (helper.py)
                                           └─► Script node with //@version etc.
                                                └─► unparse() (ast/unparser.py)
                                                     └─► pine source
```

The `Script` AST root carries a `body: list[stmt]` plus `annotations: list[str]`
(comments like `//@version=5` and `//@description "..."` get promoted from
free-floating comments onto the nearest following statement or onto the script
itself). This is what makes the round-trip lossless: comment positions and
`@` annotations survive.

### 4.2 Evaluation

```
expression string
   └─► parse() → AST
        └─► NodeLiteralEvaluator (safe) | NodeEvaluator (full)
             └─► mixins (builtins.*) dispatch on namespace + name
                  └─► return Python value
```

Two evaluators differ in capability, not in interface:

- `NodeLiteralEvaluator` — restricted to literal expressions + builtin
  functions; safe to call on untrusted input.
- `NodeEvaluator` — full script execution with assignment, control flow, type
  definitions.

Both compose the same mixins (`BaseEvaluator`, `LiteralEvaluator`,
`ExpressionEvaluator`, `StatementEvaluator`, `NameEvaluator`,
`BuiltinEvaluator`), so adding a new namespace (e.g. a new builtin) is one
file in `evaluator/builtins/`.

### 4.3 LSP Request (e.g. completion)

```
editor: textDocument/completion (uri, position)
   └─► pygls.LanguageServer (server.py)
        └─► @server.feature(TEXT_DOCUMENT_COMPLETION)
             └─► handle_completion(ls, params)
                  ├─► ls.workspace.get_text_document(uri) → TextDocument
                  ├─► parse(source, path) → AST (cached)
                  └─► providers/builtin_metadata.py → CompletionItems
                       └─► lsprotocol.types.CompletionList
```

Diagnostics follow the same pattern but push
`textDocument/publishDiagnostics` to the client; formatting hands off to
`unparse()` over a `DocumentFormattingParams` range.

---

## 5. Pine Script v6 Support & Practical Lessons (2026)

Pine Script v6 (launched late 2024, with monthly updates through 2026) introduced:

- Dynamic `request.*()` (series strings in any scope) — core support landed earlier.
- Strict boolean semantics, integer division → float, removal of `when`/`transp`.
- **April 2026**: Multiline strings (`"""..."""`, `'''...'''` — literal newlines + indentation) and `sort_field` (int index or string name) on `array.sort` / `matrix.sort` for UDT collections.
- Footprint data (`request.footprint`, `footprint.*`, `volume_row.*`).

### Grammar Challenges Encountered

The ANTLR lexer grammar lives in `resource/`. Adding triple-quoted strings exposed:

- Quote parsing fragility in the g4 meta-lexer when mixing `"` and `'` for literal delimiters inside fragments.
- Stale generated artifacts (committed so users need no Java). The committed lexer did not contain the `TRIPLE_*` rules even when the resource file had been edited.
- Interaction with the hand-written `PinescriptLexerBase.py` (indent tracking + `_handle_STRING_token` that must preserve multiline content literally for v6 while still doing legacy line-wrapping stripping for ordinary strings).
- Builder fragility: regenerated `PinescriptParser*.py` sometimes omit or rename context accessors that `ast/builder.py` calls directly.

**Practical process used (July 2026)**:
1. Fix `resource/PinescriptLexer.g4` (safe `TRIPLE_SQ_START` fragment using repeated `'\''`).
2. Run ANTLR in a clean `/tmp` dir (avoids path mirroring when g4 lives under `src/`).
3. Copy only the resulting `PinescriptLexer.py` (and refreshed `LexerBase.py`) into `generated/`. Do **not** overwrite the parser files.
4. Verify with tiny `parse()` + `unparse()` round-trips containing real v6 syntax.
5. Update docs + this file.

The `Matrix` and array UDT sort logic was added in the evaluator layer (mirroring `ObjectInstance.get_field` / `.fields`) without grammar changes.

### Current State (as of 2026-07)

- Multiline strings: fully working (parse, unparse preserves content + indentation, round-trips).
- UDT `sort_field` on matrices: implemented (basic + UDT key extraction).
- Footprint: has mock data generator + method dispatch (already present before this round of work).
- Many other v6 items (dynamic requests, strict bools, new builtins) were already implemented; documentation lagged the code.

Future agents: when touching grammar for new literals or keywords, expect to spend time on quoting experiments + selective artifact refresh + heavy use of the `parse` helper for quick feedback. First-party fixtures under `tests/fixtures/` and unit snippets are the regression gate.

See also:
- `docs/missing_features.md`
- `.opencode/context/project-intelligence/guides/grammar-changes.md`
- `AGENTS.md` (Pine v6 grammar notes)

### 4.4 Pro API Request

```
client: POST /preview/chart { data, options }
   └─► Flask blueprint (backend/api/preview.py)
        └─► require_api_key middleware   (api key tier check)
             └─► Runtime (backend/runtime.py)
                  └─► NodeEvaluator with market data hook
                       └─► chart_renderer → PNG bytes
                            └─► Response (image/png or JSON)
```

The Pro API doesn't ship Pine scripts across the wire; the client sends data
and the server runs its own evaluation engine. This is the same code path
the LSP uses for `literal_eval`, just with a real data backend.

---

## 5. Key Design Decisions

### 5.1 ANTLR4 for the grammar (not a hand-rolled parser)

Pine Script v5 is a moving target (v6 already in the works) and TradingView
publishes reference `.pine` files for every builtin. ANTLR4 gives us:

- A declarative `.g4` grammar that's readable, diffable, and matches how
  TradingView documents the language.
- A generated Python parser we don't have to maintain by hand.
- A visitor/listener split we can choose between per use case (we use the
  visitor).

The cost is a Java + ANTLR4 jar dependency for grammar regen (handled by
the `lint` hatch env). The generated parser is committed so users don't need
Java at install time.

### 5.2 ASDL for AST nodes (not dataclasses)

The AST is described in
[`src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`](./src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl)
— the same schema language CPython uses for its own AST. `pyasdl` turns it
into `PinescriptASTNode.py` (dataclass-like classes with positional fields
plus `lineno`/`col_offset`).

Why not `@dataclass` per node:

- The schema is **one file** that an agent can grep over. Adding a new
  statement form is one place to edit.
- The shape is enforced by code generation — no drift between docs and code.
- Mypy and Ruff exclude the generated module, so the price of using
  untyped `Any` is paid once, in a file agents don't touch.

### 5.3 One Python package, three delivery shapes

The same `src/pynescript/` ships as:

1. **A pip package** (`pynescript`, `pynescript[lsp]`, `pynescript[dev-lsp]`)
   for use as a library and for `python -m pynescript.langserver`.
2. **A Nuitka onefile binary** (`dist/lsp/pynescript-lsp`) for editors that
   prefer a self-contained executable.
3. **A VS Code extension** (`vscode-extension/`) that bundles the binary and
   a thin TypeScript wrapper.

The first two use the same entry point (`pynescript.langserver.__main__`),
which keeps the editor wiring (`clients/*.lua`, `settings.json`, etc.)
identical regardless of distribution channel.

### 5.4 Fernet-encrypted metadata (closed-source strategy)

The "Pro" tier's value is the evaluator + live data, not the language
metadata. To keep the LSP useful without leaking the doc corpus wholesale,
`builtin_metadata.json` is bundled into the binary in **encrypted** form
(`builtin_metadata.json.enc` + `.sha256`):

- Plaintext JSON lives in the repo (used at dev time, ~30KB).
- Encryption is symmetric (Fernet / AES-128-CBC + HMAC-SHA256).
- The Fernet key is **not** in the repo (gitignored) and is supplied as
  `CRYPTO_KEY` in CI to keep the encrypted blob byte-stable.
- The runtime decrypt path lives in
  [`src/pynescript/langserver/providers/metadata_decrypt.py`](./src/pynescript/langserver/providers/metadata_decrypt.py);
  it's a thin loader that runs only inside the compiled binary.

This is "obscurity, not security" — anyone with the binary can re-extract the
plaintext. The point is to prevent casual `strings pynescript-lsp | grep
"documentation"` and to give the project a knob to swap in a paid metadata
endpoint later.

### 5.5 The Pro API is a separate Flask process

The Pro API is intentionally **not** in the LSP server. Reasons:

- Different auth model (per-user API key, rate limits, tier checks).
- Different scaling profile (gunicorn + Cloud Run, not single-user STDIO).
- Different failure surface — taking the API down must not break the
  open-source editor experience.

Both processes consume the same AST + evaluator, which is the only shared
abstraction. The Pro API uses `backend/runtime.py` to wrap the evaluator
with a sandbox + market-data hook; the LSP uses the evaluator directly.

### 5.6 Lint rules as a separate static phase

The linter (`src/pynescript/ast/linter.py`) is a 9-rule static analyser
*orthogonal* to the evaluator. Rules are pure functions of the AST
(plus some text-level regex). This matters because:

- The LSP publishes diagnostics on every keystroke; the evaluator is too
  expensive to run that often.
- Lint findings are stable across Pine Script versions; evaluation semantics
  change.
- A separate linter is easy to test (input source → expected warnings).

### 5.7 Tests parametrized over a real `.pine` corpus

`tests/conftest.py` optionally expands `pinescript_filepath` only when
`--example-scripts-dir` points at a local directory (no third-party corpus is shipped).

This is regression-by-default: any parser change is validated against the
real TradingView corpus, not just synthetic unit tests. The cost is slow
runs; the `pinescript_filepath` fixture exposes
`--example-scripts-dir=...` to scope a run to a single file or subset.

### 5.8 Ruff, not Black + isort + flake8

A single `ruff` configuration in `pyproject.toml` covers lint, format, and
import order. With line length 120, target `py310`, and a wide rule set
(`A ARG B C DTZ E EM F FBT I ICN ISC N PLC PLE PLR PLW Q RUF S T TID UP W
YTT`), the project matches Black's `target-version = py310` for formatting.

The mandatory `from __future__ import annotations` is enforced via ruff
isort's `required-imports` rule — a common cause of "I added a new file and
ruff is mad" is forgetting that one line.

### 5.9 Generated modules are excluded from lint/type

`pyproject.toml` lists `ast.grammar.antlr4.generated.*`,
`ast.grammar.asdl.generated.*`, `ast.grammar.antlr4.resource.*`, and
`evaluator.builtins.*` as mypy overrides, and `generated/` is in
`tool.ruff.extend-exclude`. Generated code is machine-written; linting it
is wasted effort and fixes don't survive regen.

If you find yourself wanting to fix a style issue in `generated/`, the right
fix is upstream: in the `.g4`, the `.asdl`, or the `pyasdl` / `antlr4-cli`
invocation.

---

## 6. Distribution Tiers

| Tier | Open | Deliverable | What you get |
| --- | --- | --- | --- |
| Local | Yes | `pip install pynescript[lsp]` or VS Code ext | Parser, linter, evaluator, LSP features, formatting. **No network calls.** |
| Hobby | Yes (key) | Pro API key (free tier included) | Live chart previews on hover |
| Pro | Yes (key) | Pro API key | + equity curves, backtests, more calls |
| Team | Yes (key) | Pro API key + multi-user | + multi-user, larger quotas |

The local tier is the project's reason to exist; the API tiers exist to fund
ongoing work on the local tier.

---

## 7. Non-Goals

- **Re-implementing TradingView's runtime exactly.** We model enough to
  evaluate scripts with mock data; we do not claim bit-exact match with
  TradingView's own engine (TradingView doesn't publish one).
- **A custom editor UI.** The LSP is the UI. Anything you can do in VS Code
  with the extension, you can do in Neovim with the right plugin and
  `pynescript-lsp` on PATH.
- **v4 Pine Script.** v5 is the current target; v6 is supported as far as the
  reference corpus has been updated. v4 is not in scope.
- **A hosted SaaS playground.** The Pro API is an HTTP API; anyone can build
  a playground on top of it.

---

## 8. Where to Read More

- [`AGENTS.md`](./AGENTS.md) — commands, constraints, entry points.
- [`.opencode/context/navigation.md`](./.opencode/context/navigation.md) —
  full context tree (project + libraries).
- [`.opencode/plans/pynescript-lsp-implementation.md`](./.opencode/plans/pynescript-lsp-implementation.md)
  — 1000+ line LSP design doc (phases, capabilities, closed-source strategy).
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — feature status and what comes next.
- [`docs/reference.md`](./docs/reference.md) — public API reference.
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — official hatch-based dev workflow.
- [`README.md`](./README.md) — project README, also embedded in the docs.
