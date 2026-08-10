# Full Repository Code Audit — 2026-08-10

**Mode:** Read-only, 8 parallel agents, shared workspace (no worktrees)  
**Coverage:** Full product surface (AST → dual runtime → compiler → LSP → backend → tests/CI → architecture)  
**Total report volume:** ~3,375 lines across 8 agent reports + this summary  

| Agent | Scope | Report | Score |
|-------|--------|--------|------:|
| 01 | AST / parser / unparser / linter | [AGENT_01](./AGENT_01_ast_parser_unparser.md) | 7.0 |
| 02 | Evaluator core | [AGENT_02](./AGENT_02_evaluator_core.md) | 7.5 |
| 03 | Builtins (TA / strategy / plot / request) | [AGENT_03](./AGENT_03_builtins_ta_strategy.md) | 7.4 |
| 04 | Compiler / Numba | [AGENT_04](./AGENT_04_compiler_numba.md) | 7.0 |
| 05 | Backend / runtime API | [AGENT_05](./AGENT_05_backend_runtime.md) | 6.5 |
| 06 | LSP / util / extensions | [AGENT_06](./AGENT_06_lsp_util_ext.md) | 6.7 |
| 07 | Tests / scripts / CI | [AGENT_07](./AGENT_07_tests_scripts_ci.md) | ~4.5 CI gate |
| 08 | Architecture / quality bar | [AGENT_08](./AGENT_08_architecture_quality.md) | ~5.5 craft |

**Blended craftsmanship (honest):** mid-to-upper alpha toolchain with production-adjacent Pro API — **not** yet “highest professional OSS language-runtime” level. Classifier `Development Status :: 3 - Alpha` is appropriate.

---

## Cross-cutting metrics (orchestrator)

| Metric | Value |
|--------|------:|
| Python LOC (non-generated, approx) | ~64k under `src/pynescript` |
| Modules with docstring | **100%** |
| Classes with docstring | **97%** |
| Functions with docstring | **72%** |
| Hotspots for `except Exception` | `backend/runtime.py` (30), `compiler/engine.py` (16), `datafeed` / `numba_builtins` / `request` / `app` (10 each) |
| Hotspots for `# type: ignore` | `statements.py` (113), `expressions.py` (38), `helper.py` (19) |
| TODO/FIXME density | Very low in production Python (mostly clean) |

**Docs strength:** Module/class docs are strong; function docs and non-obvious Pine-semantics comments are excellent in evaluator/compiler hot paths; weaker on heuristic linter, datafeed edge cases, and some builtins.

---

## P0 — Fix first (Critical across agents)

### Correctness / Pine semantics

| ID | Area | Issue | Where |
|----|------|--------|-------|
| P0-1 | Strategy | `strategy.exit` is an **immediate-close oracle** — fills even when mark is between stop/limit; not a pending bracket | `builtins/strategy.py` ~1268–1294 |
| P0-2 | TA | `ta.atr` is **EMA-of-TR**, not TV **Wilder RMA** — dual-host aligned, wrong vs TradingView | interpret + `numba_atr` |
| P0-3 | Evaluator | **`var` ≡ `varip`** (init-once only; no realtime re-init) | `statements.py:722–735` |
| P0-4 | Evaluator | **`AugAssign` drops series wrappers** → history lost | `statements.py:965–980` |
| P0-5 | Linter | **`C004` always fires** (`source.strip().endswith("\n")` can never succeed) | `linter.py:204–208` |
| P0-6 | Unparser | Typo **`visit_Sipmle`** → `simple` qualifier never unparsed | `unparser.py:1006` |

### Security / multi-tenant backend

| ID | Issue | Where |
|----|--------|-------|
| P0-7 | Unauthenticated free compute DoS (`/run`, batch, prewarm, WS) — no bar/concurrency caps | `backend/app.py` |
| P0-8 | **SSRF** via free-tier `webhook_url` (any http(s), incl. metadata/RFC1918) | free `/run` path |
| P0-9 | Default key store can still persist **raw** API keys | JSON key store |

### CI / false confidence

| ID | Issue |
|----|--------|
| P0-10 | CI only runs linter + evaluator + CLI (+ LSP/backend) — **not** parity, compiler, strategy, series |
| P0-11 | Always-on interp/compile smoke points at empty `tests/data/builtin_scripts/` → all skip |
| P0-12 | Some corpus tests **silent-pass** (`return` instead of skip/fail) when files missing |
| P0-13 | Cloud Build deploys with **no tests**, `--allow-unauthenticated`, version pin drift |

### Datafeed / TS port

| ID | Issue |
|----|--------|
| P0-14 | Alpha Vantage provider calls wrong API methods (`get_daily` / quote endpoint misuse) | `util/data.py` |
| P0-15 | `asyncio.run` in CCXT Pro sync helpers → nested event-loop crash under async hosts |
| P0-16 | pine-worker `PineSeries` lookback polarity **inverted** vs Python/Pine; no real parity CI |

---

## P1 — High priority

### AST / tools

- Linter `W002` uses char offset as line number  
- Linter `C001`/`C003` inverted / wrong for Pine conventions  
- Function/method return types accepted by grammar, **dropped by builder/ASDL**  
- Parse-cache scrub swallows all exceptions  
- `SyntaxError.__str__` crashes if `details` unset  

### Evaluator / builtins

- Tuple unpack writes context raw (history gap like AugAssign)  
- Unbound names → bare strings (type pollution) instead of `na`  
- Mock `bid`/`ask` 100.01/100.02 when host omits quotes  
- Silent 1e6 loop cap (no error)  
- Soft import stubs hide missing libraries  
- `request.security` — no real HTF re-eval; gaps/lookahead unused  
- EMA seed split (incremental SMA seed vs full/MACD first-value seed)  
- Process-global `PlotRegistry` / `DrawingRegistry` vs per-eval strategy state  

### Compiler

- `plot()` does not call `_unique_plot_title` (hline/fill do) → object-mode drop risk  
- `begin_bar` omits `time_arr` → strategy events `bar_time=0`  
- `strategy.risk.*` silent no-op  
- Disk IR invalidation only via manual `_DISK_META_VERSION`  
- Most `opentrades` / `closedtrades` queries return zeros  

### LSP / UX

- Range formatting slices full unparse by line indices (unsafe)  
- Definition/references ranges zero-width at column 0  
- Completion can insert `ta.ta.sma` (no `textEdit`)  
- Parse/lint on every `didChange` with no debounce  
- Capability mismatches (workspace diagnostics, executeCommand, workDoneProgress)  

### Architecture / packaging

- **Runtime host lives in `backend/`**, not installable wheel — package consumers lack first-class bar loop  
- God modules: `compiler.py` ~6.4k, `numba_builtins.py` ~5.2k  
- DESIGN.md still describes dead `NodeEvaluator` vs `NodeLiteralEvaluator`  
- Corpus policy vs tree: docs say no third-party corpus ships; `set01`–`set05` hold ~12k scripts, not gitignored  
- `langserver.__version__ = "0.1.0"` vs package `0.3.3`  
- Preview/backtest: quick backtest can ignore Pine (hardcoded MA cross)  

---

## Documentation audit (inline + product)

| Surface | Assessment |
|---------|------------|
| Module docstrings | Excellent — near-universal |
| Class docstrings | Excellent (~97%) |
| Function docstrings | Good (72%); thinner on large builtins/compiler emit |
| Pine semantics comments | Strong in evaluator/compiler (var, series, NA, dual-host) |
| Linter / type_system | Weak — behavior and docs lag quality of parse stack |
| Architecture docs | Deep MDX under `docs/pyne/`; DESIGN.md partially stale |
| Test intent | Mixed — many TA modules are smoke labeled as indicator tests |

**Recommendation:** Keep module-level contracts; add function docs on every public builtin that differs from TV; fix DESIGN.md dual-evaluator claim; document intentional semantic gaps (`varip`, ATR formula, strategy.exit model) in one “known divergences” page.

---

## Modernization opportunities

1. **Typing:** reduce `# type: ignore` density in statements/expressions; Protocol-typed evaluator mixins; strict mypy on public API only first  
2. **Python 3.11+:** more `match`/structural patterns where visitor dispatch is stringly; `TypeAlias` / PEP 695 where useful  
3. **Compiler structure:** split god-object visitor into emit phases (expr / stmt / strategy / plot); cache invalidation metadata instead of manual version bumps  
4. **Async FastAPI:** lifespan, concurrency semaphores, structured rate limits, SSRF allowlists  
5. **LSP:** debounce `didChange`, proper `textEdit` for completions, honest capabilities  
6. **Testing:** property-based for NA arithmetic; golden vectors for ATR/RMA/Wilder; fail-if-fixture-missing policy  
7. **Architecture H1:** single `Runtime` in `src/pynescript` (see `docs/perf_round7/H1_unify_checklist.md`)  

---

## Quality scorecard (blended)

| Dimension | Score | Note |
|-----------|------:|------|
| Parse → AST → unparse core | 8.0 | Staff-level infrastructure |
| Interpreter hot path | 7.5–8.0 | Perf-hardened; residual semantics |
| Builtins / TA / strategy | 7.0–7.5 | Broad surface; TV gaps remain |
| Compiler / Numba | 7.0 | Strong engine; large visitor |
| Backend runtime host | 8.0 correctness / 4.5 security | Host solid; multi-tenant risk |
| LSP / datafeed | 6–7 | Layout good; protocol/datafeed issues |
| CI as correctness gate | 4.5 | Local harnesses strong; PR gate thin |
| Architecture / packaging unity | 5.5 | Dual host + Runtime outside package |
| Inline documentation | 7.5–8.5 | Strong modules; uneven functions |
| **Overall craftsmanship** | **~6.5–7.0** | Serious alpha, not top-tier OSS runtime yet |

---

## Recommended fix waves

### Wave A — Safety & honesty (1–2 weeks)

1. Backend SSRF lock-down + free-path rate/bar/concurrency limits  
2. Hash-only API keys by default; revoke path  
3. CI `test-core-runtime` job (parity, compiler, strategy, series, TA incremental)  
4. Fix silent-pass / empty `builtin_scripts` smoke (inline fixtures)  
5. Document known TV divergences (ATR, strategy.exit, varip)  

### Wave B — Semantic correctness (2–4 weeks)

1. Pending `strategy.exit` via OHLC / `process_pending_orders`  
2. ATR → RMA (interpret + numba); re-golden Supertrend/KC  
3. `varip` realtime semantics or explicit “historical only” contract  
4. Route all name writes through `_bind_series_name` (AugAssign, unpack)  
5. Compiler plot unique titles + strategy event times  

### Wave C — Tooling polish (parallel)

1. Linter C004/W002/C001 fixes + unparser `visit_Simple`  
2. LSP debounce, textEdit, range fixes  
3. Datafeed Alpha Vantage + asyncio loop bugs  
4. DESIGN.md + version string consistency  

### Wave D — Architecture raise-the-bar (medium term)

1. Package-level single Runtime (H1)  
2. Split compiler god modules  
3. Corpus git policy / license clarity  
4. pine-worker series polarity + real parity or archive skeleton  
5. Strict typing on public boundaries  

---

## Agent report index

1. [AGENT_01_ast_parser_unparser.md](./AGENT_01_ast_parser_unparser.md)  
2. [AGENT_02_evaluator_core.md](./AGENT_02_evaluator_core.md)  
3. [AGENT_03_builtins_ta_strategy.md](./AGENT_03_builtins_ta_strategy.md)  
4. [AGENT_04_compiler_numba.md](./AGENT_04_compiler_numba.md)  
5. [AGENT_05_backend_runtime.md](./AGENT_05_backend_runtime.md)  
6. [AGENT_06_lsp_util_ext.md](./AGENT_06_lsp_util_ext.md)  
7. [AGENT_07_tests_scripts_ci.md](./AGENT_07_tests_scripts_ci.md)  
8. [AGENT_08_architecture_quality.md](./AGENT_08_architecture_quality.md)  

---

*Generated by 8 parallel read-only audit agents on shared workspace (no per-agent worktrees), orchestrated 2026-08-10.*
