# AGENT 06 — Langserver, Util, Extensions, CLI Entrypoints

**Date:** 2026-08-10 
**Scope:** `src/pynescript/langserver/`, `src/pynescript/util/`, `src/pynescript/ext/`, package entrypoints (`__init__.py`, `__main__.py`, `__about__.py`), `clients/`, `vscode-extension/src/extension.ts` (brief) 
**Mode:** Read-only audit (no code changes)

---

## Executive summary

The LSP stack is a coherent pygls server with solid packaging: workspace parse/lint cache, capability advertisement that mostly matches handlers, rich builtin metadata for completion/hover, and a polished VS Code client with auto-discovery. Recent perf work (workspace AST reuse, incremental edit padding, symbols flush fix) is visible in code and tests and substantially improves feature latency.

Residual risk clusters into three areas:

1. **LSP protocol / UX correctness** — zero-width definition/reference ranges, broken range formatting semantics, completion insert text without `textEdit`, dual diagnostic converters (workspace path weaker than `features/diagnostics`), capability mismatches (`workspace_diagnostics=False` while a workspace pull handler is registered; `executeCommand` handler with no advertised commands; `work_done_progress=True` with no progress reporting).
2. **Util data path hazards** — Alpha Vantage provider almost certainly broken (wrong client class / methods), `asyncio.run` nested-loop hazard in CCXT Pro sync helpers, infinite reconnect loops with weak backoff, dead `data_source="ccxt"` historical branch in `resolve_request_sources`.
3. **Extensions as stubs** — Jupyter magic only parse/lint/unparse; Nautilus strategy is subscription shell with empty `on_bar`; corpus sanitize and time_parts are higher quality.

CLI (`__main__.py`) is mature for a toolchain (check/format/lint/compile/run/data/info/prewarm). Package version is centralized in `__about__.py` (`0.3.3`); langserver subpackage still exports a stale `__version__ = "0.1.0"`.

**Overall score (this surface): ~6.5–7.0 / 10** — usable product path, not yet “IDE-grade” language intelligence or production-hardened market data.

---

## Critical

### C1. Alpha Vantage provider uses wrong API surface

**Evidence:** `src/pynescript/util/data.py:376–441`

```python
self._client = {
 "fx": ForeignExchange(key=self._api_key),
 "ti": TechIndicators(key=self._api_key),
}
# ...
data, meta = client["ti"].get_daily(...) # TechIndicators has no get_daily
data, _ = client["ti"].get_quote_endpoint(...) # quote lives on TimeSeries
```

`get_daily` / `get_quote_endpoint` belong to `alpha_vantage.timeseries.TimeSeries`, not `TechIndicators`. Any `pynescript data … --provider alphavantage` or `get_provider("alphavantage")` path will fail at runtime (or succeed only if the library coincidentally exposes aliases — it does not in the standard package).

**Impact:** CLI and any runtime wiring that selects Alpha Vantage is non-functional.

**Fix:** Use `TimeSeries` for OHLCV/quotes; keep FX on `ForeignExchange` if needed; add a unit test with a mocked client.

---

### C2. `asyncio.run` in CCXT Pro sync helpers (nested event-loop crash)

**Evidence:** `src/pynescript/util/datafeed.py:296–323`

```python
def fetch_latest_ohlcv(...):
 return asyncio.run(self._fetch_latest_ohlcv_async(...))

def fetch_latest_ticker(...):
 return asyncio.run(self._fetch_latest_ticker_async(...))
```

These helpers are documented for use from “mostly-sync” evaluator / `request.*` paths. Calling `asyncio.run` from an already-running event loop (async runtime, Jupyter, Nautilus, FastAPI worker) raises `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Impact:** Live / hybrid evaluation paths that touch `fetch_latest_*` under an async host will hard-fail.

**Fix:** Detect running loop and use `asyncio.get_event_loop().create_task` / a dedicated thread loop / require async API only; never nest `asyncio.run`.

---

## High

### H1. Range formatting is not true range formatting

**Evidence:** `src/pynescript/langserver/features/formatting.py:78–120`

Handler parses **the whole document**, unparses **the whole tree**, then slices **line ranges** of the fully formatted text and replaces only that span. Line indices of unparsed output need not align with the original selection (comments moved, blank lines collapsed, multi-line expressions reshaped). Result can corrupt surrounding code or produce a no-op / wrong patch.

**Impact:** `textDocument/rangeFormatting` is unsafe for partial selections; clients that default to range format on save-of-selection will mis-edit.

**Fix:** Either (a) unparse only a reconstructed subtree for the selection, (b) fall back to full-document format when ranges differ in structure, or (c) stop advertising `document_range_formatting_provider` until correct.

---

### H2. Definition / references / workspace-symbol ranges are zero-width at column 0

**Evidence:**

- `definitions.py:173–178` — `start`/`end` both `(lineno-1, 0)`
- `references.py:152–157` — same
- `server.py:_collect_workspace_symbols` lines 351–386 — same

Editors “go to definition” land at line start, not on the identifier. Multiple same-line symbols are indistinguishable. Selection highlighting is broken.

**Impact:** Navigation UX is degraded; some clients treat zero-width ranges poorly.

**Fix:** Use `col_offset` / name length (as `symbols.py:_name_to_range` already does at lines 233–241).

---

### H3. Completion insert text can double module prefixes

**Evidence:** `completion_items.py:112–128`, `completion.py:82–95`

`build_completion_item` sets `insert_text` to full label (`ta.sma`) or snippet without a `textEdit` range. After `ta.` trigger, clients that insert at cursor append full label → `ta.ta.sma`. Category header items (`--- Technical Analysis ---`) are selectable with empty `insert_text` (lines 161–179).

**Impact:** Everyday autocomplete friction; fake “headers” pollute the list.

**Fix:** Emit `textEdit` covering the partial identifier; use `CompletionItemTag` / `labelDetails` instead of folder-kind headers; insert only the leaf name for module completions.

---

### H4. Sync parse/lint on every `didChange` (no debounce / off-thread)

**Evidence:** `server.py:110–120`, `workspace.py:147–159`

Every incremental change re-parses and re-lints on the LSP request thread, then publishes diagnostics. Large Pine files (corpus scripts, multi-kLOC strategies) will stall completion/hover/didChange processing. There is no cancellation token, debounce, or version-check discard of stale results.

**Impact:** Editor jank under load; potential “stale diagnostic race” if future async is added without version guards (today serial, so correct but slow).

**Fix:** Debounce publish (e.g. 150–300 ms), parse in a worker, discard results when `doc.version` advanced; optionally use pull diagnostics as primary and push as secondary.

---

### H5. `resolve_request_sources`: `data_source="ccxt"` never becomes historical CCXT

**Evidence:** `data.py:663–684`

```python
if src in {"mock", "ccxtpro", "ccxt", "pro"} and feed is None:
 ...
 feed = get_datafeed("ccxtpro", ...) # "ccxt" always here
elif src in {"yahoo", "alphavantage", "ccxt"} and provider is None:
 # "ccxt" branch is unreachable when feed path matched
```

`"ccxt"` is in the first branch and always constructs a **Pro** feed. The historical `CCXTProvider` path for the same name is dead.

**Impact:** Callers expecting REST historical OHLCV from `data_source="ccxt"` get a WebSocket feed instead (or fail if Pro unavailable).

**Fix:** Split names: `"ccxt"` → historical provider; `"ccxtpro"` / `"pro"` → feed only.

---

### H6. Capability / handler mismatches

| Issue | Evidence |
| --- | --- |
| `workspace_diagnostics=False` but `WORKSPACE_DIAGNOSTIC` handler registered | `config.py:53–57`, `server.py:196–214` |
| `WORKSPACE_EXECUTE_COMMAND` handler returns `None`; no `execute_command_provider` / command list in capabilities | `server.py:233–237`, `config.py` (absent) |
| `work_done_progress=True` for document/workspace symbol with no progress tokens | `config.py:65–70` |
| Clients pass `--stdio`; server ignores argv (usually harmless) | `langserver/__main__.py:41–44`, `clients/zed.json:23`, `clients/README.md` |

**Impact:** Protocol-strict clients may not call workspace diagnostics; clients that discover executeCommand via method table may send unknown commands; progress capability is a lie.

**Fix:** Align advertisement with implementation (enable workspace diagnostics *or* remove handler; advertise commands or drop feature; set progress false until implemented). Optionally accept/ignore `--stdio` explicitly.

---

### H7. Dual diagnostic conversion (drift)

**Evidence:**

- Live path: `workspace._lint_warning_to_diagnostic` (`workspace.py:215–252`) — no tags, no `codeDescription`
- Helper path: `features/diagnostics.py:59–95` — tags for W001/W002, codeDescription hrefs

Server always uses workspace conversion (`server.py:105–106`, `119–120`, `188`). The richer module is effectively unused for publish/pull.

**Impact:** Tags (Unnecessary/Deprecated) and doc links never reach the editor; future fixes risk diverging further.

**Fix:** Single shared converter; delete or re-export one implementation.

---

## Medium

### M1. `file://` path parsing is naive

**Evidence:** `workspace.py:71–75`

```python
if self.uri.startswith("file://"):
 return Path(self.uri[7:])
```

Does not use `urllib.parse.urlparse` / `unquote`; fails for `file:///c%3A/...`, spaces, and non-ASCII paths. Currently mostly unused for parse (filename is the URI string), but any future disk I/O via `.path` is wrong on Windows and encoded URIs.

---

### M2. Definition finder incomplete / wrong ctx checks

**Evidence:** `definitions.py:130–157`

- `visit_Name` checks `node.ctx` for Load then also `node._ctx` for Store — inconsistent attributes; Store via Name is largely handled in `visit_Assign` instead
- No function parameters, method defs, import aliases, or tuple destructure beyond partial field walk
- Same-document only; no builtin → virtual location

Go-to-def works for simple assigns and function/type names only.

---

### M3. References finder misses attribute / keyword / multi-decl patterns

**Evidence:** `references.py:107–145`

Only `Name` Load/Store, FunctionDef/TypeDef names, and Call of bare `Name`. `ta.sma` as Attribute is not treated as a reference to a user symbol (OK for builtins) but also won’t find method-style uses. No cross-file / multi-workspace search despite `workspace/symbol` existing for open docs only.

---

### M4. Hover is builtins-only

**Evidence:** `hover.py:35–90`

No hover for user variables, function signatures from AST, or UDT fields. Hard-coded example map for a few `ta.*` / strategy functions (lines 157–164). Empty `_build_docs_link` (lines 194–201).

---

### M5. Diagnostics docs URLs look placeholder / wrong domain

**Evidence:** `features/diagnostics.py:125–128` → `https://docs.pynescript.ai/errors` 
Package docs elsewhere point at `https://hoox.sh/pyne`. Dead links confuse users if tags/codeDescription ever wire up.

---

### M6. CCXT Pro watch loops: broad `except Exception`, weak backoff

**Evidence:** `datafeed.py:218–277`

On connection-ish errors: `sleep(1)` and continue forever. Non-connection errors raise (good). No max retries, jitter, or circuit breaker. `CompositeDataFeed` silently falls through with bare `except Exception` (lines 472–478). Broker fill logic (`DataFeedBroker`) ignores partial fills / short sells / multi-symbol.

---

### M7. Initialization options from VS Code ignored

**Evidence:** `vscode-extension/src/extension.ts:183–187` sends `formattingEnabled`, `snippetsEnabled`, `diagnosticsEnabled`; server never reads `InitializeParams.initialization_options` (`server.py:142–159`). Toggles only affect client-side expectations partially (diagnostics still published server-side).

---

### M8. `didSave` does not apply `params.text` despite `include_text=True`

**Evidence:** `config.py:51`, `server.py:132–140`

Save re-lints cached buffer only. Clients that rely on save-text without prior change events (rare with incremental sync) stay stale.

---

### M9. Langserver package version drift

**Evidence:** `langserver/__init__.py:56` → `__version__ = "0.1.0"`; package `__about__.py:33` → `0.3.3`. Server identity correctly uses package version (`server.py:56, 84`). The subpackage constant misleads importers.

---

### M10. Jupyter / Nautilus integrations are thin

| Module | Issue |
| --- | --- |
| `ext/jupyter.py` | Magic only lint + parse + unparse; `evaluate_indicator` uses `NodeLiteralEvaluator` once (not bar-series Runtime); bare `except Exception` |
| `ext/nautilus_trader/strategy.py` | Empty `on_bar` / `on_trade_tick`; no Pine evaluation or order mapping |
| `ext/pygments/lexers.py` | Solid ANTLR-backed lexer; duplicate map keys (`WS`, `COMMENT` twice) are harmless but noisy |

---

### M11. Corpus sanitize stub-on-failure can hide bad inputs

**Evidence:** `corpus_sanitize.py:34–35, 42–43` — minimal parseable stub when chrome strip yields nothing. Appropriate for corpus pipelines; dangerous if reused as a general “user input cleaner” without flagging that content was replaced.

---

### M12. Semantic tokens incomplete vs legend

**Evidence:** `semantic_tokens.py:127–146` emits function/class/variable/namespace/method/property only. Legend also lists keyword, string, number, operator, comment (`config.py:91–105`) but those are never emitted — clients may expect richer coloring; TextMate still covers syntax.

Attribute column for `_emit_attr` is approximate (`end_col_offset` heuristic) — possible misaligned tokens on multi-line attributes.

---

## Low

### L1. Broad `except Exception` swallows in feature handlers

**Evidence:** definitions/formatting/references/semantic_tokens/symbols/inlay — parse failures return empty/None (acceptable for LSP), but other bugs are also hidden. Prefer `except SyntaxError` / project parse error type.

### L2. Category headers & sort hacks in completion

`sort_text="\x00" + category` (completion_items.py:178) is clever but non-portable across clients.

### L3. `get_filter_options` unused

`config.py:118–133` document selector never attached to capabilities (fine if clients own selectors; dead API).

### L4. Code actions defined but not wired

`create_quick_fix` / `create_diagnostic_related_info` in `features/diagnostics.py` are never registered; `codeAction` correctly not advertised (good), but dead code accumulates.

### L5. `pine_facade.py` downloads remote Pine builtin sources

Network scraping utility; thread-local sessions OK. No rate limiting beyond ThreadPoolExecutor; depends on public facade stability. Not on hot LSP path.

### L6. Mock providers use global `random` / unseeded walks in places

`jupyter.create_sample_data`, `MockDataFeed` — fine for demos; not reproducible without seeds.

### L7. Clients README / Helix / Sublime configs

Helpful; `--stdio` args unnecessary for current `main()`. Neovim sample still says `lspconfig.pynescript` — verify upstream name.

### L8. VS Code extension quality is high

`extension.ts`: serialized client ops, status bar, discovery chain `pyne-lsp` → `pynescript-lsp` → `python -m pynescript.langserver`, config restart — good. Sync `execFileSync` on activate for PATH probes can stall briefly (acceptable).

### L9. CLI surface (`__main__.py`)

Well-structured Click group with aliases, Rich theming, CI-friendly `check`/`format --check`/`lint --fail-on`. Synthetic OHLCV for `run` is deterministic. `compile`/`run` catch broad Exception (OK for CLI UX). Not part of LSP critical path.

### L10. No TODO/FIXME in langserver tree

Grep found none — good hygiene; issues live as silent fallbacks instead.

---

## Documentation quality

| Area | Assessment |
| --- | --- |
| Package / CLI / langserver package docstrings | **Strong** — entrypoints, layout, console scripts documented |
| Feature module module-docs | **Strong** — public handlers listed, capability notes |
| Workspace incremental-edit comment | **Good** — documents prior stale-buffer bug |
| Function-level docs | **Mixed** — handlers documented; several private helpers sparse |
| Hover / diagnostics external links | **Weak** — placeholders or wrong domain |
| Util `datafeed` / `data` | **Good** usage docs; Alpha Vantage implementation contradicts docs |
| Nautilus / Jupyter | **Honest** about experimental/stub status in places |
| Clients README | **Good** multi-editor guide |

**Score (docs):** 7.5/10 for this surface.

---

## Modernization opportunities

1. **LSP 3.17+ polish**
 - Pull diagnostics as primary with `result_id` / unchanged reports (partially present for document diagnostic)
 - `textDocument/semanticTokens/range` optional
 - `textDocument/prepareCallHierarchy`, signature help, rename, code actions (when ready)
 - Position encoding negotiation (`utf-16` default awareness for multi-byte identifiers)

2. **Async / worker architecture**
 - Off-thread parse+lint with version tokens
 - Debounced `publishDiagnostics`
 - Optional incremental parsing if ANTLR pipeline allows

3. **Semantic model**
 - Shared symbol index (defs/refs/hover/completion of locals)
 - Scope-aware resolution (params, nested functions, imports)
 - Type inference beyond inlay’s RHS shapes

4. **Completion**
 - `textEdit` + `insertTextFormat`
 - Item defaults / `completionList.itemDefaults` (LSP 3.17)
 - Snippet toggle honored from init options

5. **Data layer**
 - Async-native providers; deprecate `asyncio.run` bridges
 - Typed OHLCV dataclass / Protocol instead of bare dicts
 - Circuit breakers, metrics, structured logging on feeds

6. **VS Code**
 - Honor server-side init options for diagnostics/snippets
 - Language status item API instead of only status bar
 - Telemetry-free crash reporting channel already present — keep

7. **Extensions**
 - Jupyter: bar-loop evaluate via Runtime/compile pipeline
 - Nautilus: map `Bar` → OHLCV push into Pine runtime + order events

---

## Scorecard

| Dimension | Score (1–10) | Notes |
| --- | --- | --- |
| Correctness / bugs | **5.5** | Alpha Vantage broken; range format unsafe; def ranges; data_source ccxt dead branch |
| LSP protocol fidelity | **6.5** | Core methods work; capability mismatches; no cancel/progress |
| Design quality | **7.0** | Clean feature modules + workspace cache; dual diag converters; thin symbol model |
| Modern techniques | **6.0** | AST reuse good; missing debounce/async, incomplete semantic model |
| Code quality | **7.0** | Typed, structured, tested paths; broad excepts; dead code |
| Inline documentation | **7.5** | Excellent package/feature docs; some stale links/version |
| Util datafeed safety | **5.0** | Nested loop hazard; reconnector; Alpha Vantage; broker toy |
| Extensions maturity | **4.0** | Pygments good; Jupyter/Nautilus stubs |
| CLI entrypoints | **8.0** | Polished Click UX; clear separation from LSP |
| VS Code client | **8.0** | Discovery, lifecycle lock, UX messages |
| **Weighted overall** | **~6.7** | Ship-worthy editor baseline; not production market-data or full IDE |

---

## Prioritized recommendations

### P0 (fix correctness)

1. **Rewrite Alpha Vantage provider** on `TimeSeries` (+ tests with mocks). 
2. **Remove or guard `asyncio.run`** in `CCXTProDataFeed.fetch_latest_*`; document async-only contract if needed. 
3. **Disable or rewrite range formatting** until line-aligned unparse is proven safe.

### P1 (LSP UX)

4. **Identifier-accurate ranges** for definition, references, workspace symbols (reuse `_name_to_range` pattern). 
5. **Completion `textEdit`** + leaf insert for module members; drop selectable category headers. 
6. **Unify diagnostic conversion** on the richer `features/diagnostics` path (tags + single implementation). 
7. **Align capabilities** with handlers (workspace diagnostics flag, executeCommand, workDoneProgress). 
8. **Debounce + versioned diagnostics** after `didChange`.

### P2 (data + wiring)

9. **Fix `resolve_request_sources` name matrix** (`ccxt` vs `ccxtpro`). 
10. **Backoff / max-retry** on feed reconnect; structured logging instead of silent continue. 
11. **Honor init options** from VS Code (or stop sending unused flags). 
12. **URI path helper** for `file://` (urlparse + unquote).

### P3 (product depth)

13. User-symbol hover + signature help from AST. 
14. Wire code actions (W001 version pragma) and advertise `codeActionProvider`. 
15. Jupyter magic → Runtime evaluate; Nautilus `on_bar` → real Pine host. 
16. Drop or alias langserver `__version__` to package version. 
17. Fix docs links (`hoox.sh/pyne` or real error catalog).

---

## Evidence index (file:line)

| Topic | Location |
| --- | --- |
| Server handlers / lifecycle | `src/pynescript/langserver/server.py:91–336` |
| Workspace parse/lint + incremental edit | `src/pynescript/langserver/workspace.py:117–286` |
| Capabilities | `src/pynescript/langserver/config.py:39–86` |
| Completion | `.../features/completion.py`, `.../providers/completion_items.py` |
| Definition zero-width range | `.../features/definitions.py:173–178` |
| References | `.../features/references.py:147–160` |
| Formatting / range | `.../features/formatting.py:35–123` |
| Hover builtins-only | `.../features/hover.py:35–90` |
| Diagnostics dual path | `workspace.py:184–252` vs `features/diagnostics.py:38–95` |
| Semantic tokens | `.../features/semantic_tokens.py:83–204` |
| Inlay hints | `.../features/inlay_hints.py:69–225` |
| Metadata load | `.../providers/builtin_metadata.py:66–102` |
| Datafeed asyncio.run | `src/pynescript/util/datafeed.py:296–323` |
| Datafeed reconnect | `src/pynescript/util/datafeed.py:218–277` |
| Alpha Vantage bug | `src/pynescript/util/data.py:376–441` |
| resolve_request_sources ccxt | `src/pynescript/util/data.py:663–684` |
| Corpus sanitize | `src/pynescript/util/corpus_sanitize.py` |
| time_parts | `src/pynescript/util/time_parts.py` |
| Jupyter | `src/pynescript/ext/jupyter.py` |
| Nautilus stub | `src/pynescript/ext/nautilus_trader/strategy.py` |
| Pygments | `src/pynescript/ext/pygments/lexers.py` |
| CLI | `src/pynescript/__main__.py` |
| Package version | `src/pynescript/__about__.py:33` |
| Langserver stale version | `src/pynescript/langserver/__init__.py:56` |
| VS Code client | `vscode-extension/src/extension.ts` |
| Prior LSP perf notes | `docs/perf_round5/AGENT_11_lsp.md` |

---

## Test coverage notes (existing)

- `tests/test_langserver.py` — workspace, incremental edit EOF, stale parse diagnostics 
- `tests/test_lsp_features.py` — metadata, completion, handlers 
- `tests/test_datafeed.py` / `test_datafeed_wiring.py` — feed wiring 
- `tests/test_corpus_sanitize.py`, `tests/test_time_parts.py` 
- Gaps: Alpha Vantage, range formatting correctness, completion insert prefix, nested asyncio, capability advertisement snapshot, init options

---

## Closing

This surface is **architecturally sound for a first-party Pine LSP**: clear separation of server / workspace / features / providers, good editor packaging, and recent correctness fixes for symbols, references, and incremental edits. The highest-ROI work is **protocol-faithful ranges and completion inserts**, **safe formatting**, **honest capabilities**, **debounced diagnostics**, and **repairing the market-data utilities** that sit under CLI and live evaluation. Extensions should be labeled experimental until they call the real Runtime/compiler path.
