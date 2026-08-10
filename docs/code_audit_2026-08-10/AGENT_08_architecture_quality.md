# Agent 08 — Cross-cutting Architecture & Quality Bar

**Date:** 2026-08-10 
**Scope:** Public API, dual host (interpret vs compile), docs honesty, typing, packaging, duplication, corpus/privacy, craftsmanship bar 
**Method:** Read-only sampling of entry points, greps for anti-patterns, docs-vs-code comparison. No source changes.

---

## Executive summary

This repository is an ambitious, multi-surface language runtime (parser → AST → dual-engine bar loop → LSP → Pro API → optional TS worker) with **serious engineering investment** visible in hot-path comments, parity harnesses, structured host errors, and extensive product docs under `docs/pyne/`.

It does **not** currently clear a “highest professional open-source language-runtime” bar. The gap is not “missing features” — it is **architectural unity, API honesty, god-module size, soft typing, dual-host drift, and documentation that sometimes contradicts the tree**.

**Top three structural truths:**

1. **The bar-loop Runtime host lives outside the installable package** (`backend/runtime.py` ~2k lines) while the PyPI wheel only ships `src/pynescript`. Interpret/compile parity, CLI/showcase tools, and tests all import that host; package consumers get AST + evaluator + compiler pieces, not one first-class `Runtime`.
2. **Interpret and compile are dual implementations**, not a cleanly factored single IR. Compiler surface is concentrated in enormous modules (`compiler.py` ~6.4k LOC, `numba_builtins.py` ~5.2k LOC) with process-global caches and many `except Exception` recovery paths. Parity is actively pursued (good) but residual MISMATCH is acknowledged as open work.
3. **Docs and packaging claims lag or contradict reality** in several high-visibility places: DESIGN.md still describes two evaluator classes; root/`tests/data` messaging claims no third-party corpus ships while `tests/data/set01`–`set05` hold ~12k scraped `.pine` files and are **not** covered by `.gitignore`; `langserver.__version__` is hard-coded `0.1.0` vs package `0.3.3`.

**Craftsmanship verdict (honest):** Strong mid-to-upper tier for a solo/small-team alpha toolchain with production-adjacent Pro API; **not** yet CPython-stdlib / Rust-compiler-grade OSS runtime craftsmanship. Classifier correctly says Alpha (`Development Status :: 3 - Alpha`).

---

## Architecture assessment

### What is cleanly designed

| Layer | Location | Assessment |
| --- | --- | --- |
| Grammar / AST generation | `src/pynescript/ast/grammar/{antlr4,asdl}/` | Clear hand-edit vs generated split; AGENTS.md constraints are real and enforced by culture |
| Parse public face | `ast/helper.py` | CPython-`ast`-like contracts, parse LRU, documented mutability risk |
| Error model (parse) | `ast/error.py` + docs/pyne/core/error-model.mdx | Structured location + caret; intentional name shadowing documented |
| Evaluator composition | `NodeLiteralEvaluator` + mixins | MRO composition is intentional; NA/`var`/`series` conventions documented in package docstrings |
| Compiler package surface | `compiler/__init__.py` | Explicit `__all__`, typed exception family (`CompileError` hierarchy) |
| Pro API auth | `backend/middleware/auth.py` | Hash-only stores, admin fail-closed, tier quotas — ops-conscious |
| Product docs | `docs/pyne/**`, `docs/WRITING.md` | Page skeleton and voice standards exist; architecture MDX is unusually deep for OSS |

### Dual-engine (interpret vs compile)

```
 ┌─────────────────────────────┐
 Pine source ──► │ parse (helper, cached AST) │
 └─────────────┬───────────────┘
 │
 ┌───────────────────┴───────────────────┐
 ▼ ▼
 backend.Runtime (host) pynescript.compiler
 interpret: bar loop + transpile → exec(module)
 NodeLiteralEvaluator / Numba nopython OR object mode
 CustomEvaluator plot capture strategy_broker / numba_builtins
 │ │
 └───────────────────┬───────────────────┘
 ▼
 JSON-ish result dict (plots, events, errors)
```

**Factoring quality:**

- **Shared:** parse, AST, some plotting merge helpers, compile cache knobs, NA policy comments, parity tests/scripts.
- **Not shared:** the interpret bar loop, PineSeries host, LazyCalendarContext, error_kind packaging, series cap policy — all SoT in `backend/`, with a **separate** worker tree called out in `docs/perf_round7/H1_unify_checklist.md` (`pyne-worker` outside this repo).
- H1 residual is correctly named: “Single Runtime implementation / package owns bar loop” remains open. Dual-host is **not** cleanly factored; it is **intentionally duplicated with a checklist**, which is honest engineering but not professional-grade cohesion.

**DESIGN.md staleness (evidence):** §4.2 claims `NodeLiteralEvaluator` (safe) **vs** `NodeEvaluator` (full). Code and `ast/evaluator/__init__.py` state explicitly: *“There is **no** separate `NodeEvaluator` class. The public composed type is `NodeLiteralEvaluator`.”* Safe literal_eval vs full script is a usage mode of one type, not two classes. Architecture docs oversell isolation.

### Package vs monorepo

| Path | In PyPI wheel? | Role |
| --- | --- | --- |
| `src/pynescript/` | Yes | Open library |
| `backend/` | No | Pro API + **canonical Runtime host** |
| `pine-worker/` | No | Incomplete TS port (skeleton/partial) |
| `vscode-extension/` | Separate | Bundles LSP |
| `tests/data/set*` | Not package | Local/third-party corpus (~12k scripts) |

This monorepo layout is fine for a product stack; the **problem** is that the semantic “language runtime” (bar loop + series host) is not in the library, so “install hoox-pyne and run Pine like reference” is architecturally incomplete without vendoring `backend` or reimplementing the host.

### pine-worker / backend / package triangle

- **Python package:** AST + evaluator builtins + compiler.
- **backend:** host Runtime + Flask + plot packaging.
- **pine-worker (TS):** partial series/evaluator; README admits incomplete builtins; converter stubs accelerate port.
- **COMPATIBILITY.md:** three-way matrix including `pyne-worker` (~750 LOC thin wrapper elsewhere). Matrix language is useful but “100% compatibility” framing at the top is marketing-adjacent relative to partial TS coverage.

Duplication cost: NA/series semantics must stay aligned across **three** implementations (interpret Python, compile Python, TS port) plus a worker copy of host. That is a classic multi-runtime maintenance tax.

---

## Critical / High / Medium / Low findings

### Critical

| ID | Finding | Evidence |
| --- | --- | --- |
| C1 | **Runtime host not part of public package architecture** — dual engine is marketed as product core, but SoT bar loop is `backend/runtime.py`, outside hatch wheel packages. | `pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/pynescript"]`; tests/scripts `from backend.runtime import Runtime`; H1 checklist still open |
| C2 | **Third-party corpus present and not gitignored; docs claim it is not shipped** — licensing, redistributability, and privacy/ToS risk. | README L39 + `tests/data/README.md` + AGENTS.md claim no third-party corpus; `tests/data/set01`–`set05` exist with SOURCES.md (GitHub scrapes), set05 alone ~9k scripts; list_dir shows tree (not gitignored) |
| C3 | **Compile path `exec`s generated Python** from user-adjacent script input — expected for this architecture but **not** a sandbox. Pro API that accepts arbitrary Pine → compile is code-generation then execute. | `compiler/engine.py` `exec(code, namespace)` / `exec(code_disk, namespace)` with `# noqa: S102` |

### High

| ID | Finding | Evidence |
| --- | --- | --- |
| H1 | **God modules in compiler path** — maintenance, review, and type-checking choke points. | `compiler/compiler.py` ends ~6400+ LOC single `CompilerVisitor`; `numba_builtins.py` ~5216 LOC; `backend/runtime.py` ~2k+ |
| H2 | **Broad `except Exception` culture remains after “hardened error handling”** | Grep: dozens of hits in `engine.py`, `numba_builtins.py`, `runtime.py` soft-fail sites for drawings/logger/request wiring; intentional soft-fails mixed with recovery — hard to audit fail-closed guarantees |
| H3 | **mypy is configured as non-strict with large escape hatches** — `Typing :: Typed` + empty `py.typed` signal typed package, but evaluator builtins disable many error codes; `disallow_untyped_defs = false` | `pyproject.toml` `[tool.mypy]` + overrides for `pynescript.ast.evaluator.builtins.*` |
| H4 | **Stale architecture docs** undercut trust in the quality bar the project advertises | DESIGN.md NodeEvaluator dual class; `docs/rating.md` still says plotting stubbed / older test counts; COMPATIBILITY.md “100%” intro vs partial ports |
| H5 | **Dual-host package unify open** while surface claims “same pipeline” across Pro/edge/Pyodide | ROADMAP H1 residual; H1 checklist P0 call-site on shared AST; README “same pipeline” language |
| H6 | **Version identity split** | `pynescript.__about__.__version__ = "0.3.3"` vs `langserver/__init__.py` `__version__ = "0.1.0"` (docstring claims server uses package version — partial/confusing) |

### Medium

| ID | Finding | Evidence |
| --- | --- | --- |
| M1 | **Root package public API is only `__version__`** — fine if intentional, but forces every consumer to know deep import paths; no stable “runtime” re-export | `src/pynescript/__init__.py` `__all__ = ["__version__"]` |
| M2 | **`ast/__init__.py` star-exports** via `from .helper import *` etc. — convenient, risk of surface sprawl / namespace pollution | `ast/__init__.py` `# ruff: noqa: F403` |
| M3 | **Process-global mutable caches** without a unified cache policy API across parse/compile/host | `_PARSE_CACHE`, `_COMPILE_CACHE`, `_HOST_COMPILE_*` in backend, Numba disk caches; env flags proliferate (`PYNE_*`) |
| M4 | **Parse-cache mutability footgun** documented but easy to misuse with transformers | `helper.py` module docs: shared identity on hit |
| M5 | **Call-site binding on AST** called out as H1 P0 residual — multi-run correctness hazard | H1_unify_checklist.md |
| M6 | **pine-worker incomplete but co-located** — noise for contributors; COMPATIBILITY matrix overstates readiness | pine-worker README “skeleton + partial port” |
| M7 | **Dependencies: unpinned `requests`, `tqdm`** in core install; compile/numba optional — OK for alpha, weak for reproducible runtime deploys (backend has separate requirements) | `pyproject.toml` dependencies |
| M8 | **No pyright/basedpyright config** — only mypy hatch env | grep across config files |
| M9 | **Security story is basic** — SECURITY.md exists; Fernet metadata encryption for Nuitka is product DRM-ish, not sandboxing; API keys solid; user script execution trust model underexplained for Pro | SECURITY.md, engine exec, auth middleware |

### Low

| ID | Finding | Evidence |
| --- | --- | --- |
| L1 | Print debugging only in intentional CLI/Jupyter paths (acceptable); data module doc examples use `print` | jupyter/__main__/data docstrings |
| L2 | Emotion-heavy internal docs (`docs/REFACTORING_EXECUTIVE_SUMMARY.md` emoji trophy language) vs WRITING.md academic voice | contrast with `docs/WRITING.md` |
| L3 | Massive agent round documentation tree (`perf_round*`, `parity_round*`) is valuable history but crowds “current truth” | `docs/` layout |
| L4 | Black + ruff both present (ruff format preferred in AGENTS) — mild tool redundancy | `pyproject.toml` |
| L5 | `util/__init__.py` does not re-export submodules (fine) but util is a grab bag (data, sanitize, time) | util package |

---

## Documentation & inline docs standard

### Project-level docs

| Artifact | Role | Quality vs reality |
| --- | --- | --- |
| `AGENTS.md` | Agent ops bible | High practical value; corpus “not shipped” claim is inconsistent with tree |
| `DESIGN.md` | Architecture | Good diagrams; **stale** on evaluator dual-class and Pro API “same as literal_eval” oversimplification |
| `COMPATIBILITY.md` | Multi-impl matrix | Useful; top “100%” framing oversells |
| `docs/ROADMAP.md` / `missing_features.md` | Status | Relatively honest about residual parity/host work; dense checkmarks can read as complete when host unify is open |
| `docs/WRITING.md` | MDX standards | Professional; product docs under `docs/pyne/` often meet it |
| `docs/pyne/**` | User/dev manuals | Strong for OSS; better than many mature projects |
| `docs/rating.md` | Value rating | **Stale** (plotting stubbed claim vs current drawing/plot work) |
| Agent round reports | Perf/parity archaeology | Excellent for agents; poor as public “read me first” |

### Inline documentation (sampled)

**Above average for alpha OSS:**

- Module docstrings on `helper.py`, `evaluator/__init__.py`, `expressions.py`, `compiler/__init__.py`, `backend/series.py`, `backend/runtime.py` document NA semantics, flags, and host contracts.
- Cross-cutting rules (na = `None`, series index conventions, var init) are repeated at the right layers — good for multi-agent maintenance.

**Below highest bar:**

- Giant methods in `CompilerVisitor` / host `run()` cannot be fully understood from docs alone; comments are tactical (“Agent 07”, “Phase 1.4”) more than conceptual API design.
- Many handlers remain `Any`-heavy with sparse param typing.
- No consistent Google/NumPy docstring enforcement via tooling (docstrings exist by culture, not CI gate).
- Historical name `NodeLiteralEvaluator` for full interpreter is itself a documentation debt (called out in code — good — but never renamed).

---

## Public API & typing

### Public API surface

```
pynescript
├── __version__ # only root export
├── ast. # de-facto stable: parse, unparse, dump, walk, SyntaxError, nodes
├── compiler. # explicit __all__: compile_script, run_script, CompiledScript, errors
├── langserver. # LSP types; requires [lsp]
├── ext. # pygments, jupyter, nautilus
└── util. # data providers, sanitize, time_parts
```

**Strengths:**

- Root package correctly avoids dumping the entire tree into `__init__`.
- `compiler` and `ast.helper` document contracts (modes, errors, cache).
- Console scripts dual-named (`pyne` / `pynescript`) with clear aliases.

**Weaknesses:**

- No versioned stability policy (what is public vs private? leading underscore only partially used).
- No single import for “run this script on OHLCV” in the package — that is `backend.Runtime`.
- `literal_eval` docstring still says “restricted / not general script executor” while composition uses the full evaluator stack with optional data feeds — **safer-than-exec but not a capability sandbox**.
- Star-import package (`ast`) vs explicit `__all__` modules (`compiler`) inconsistency.

### Typing

| Signal | Reality |
| --- | --- |
| `py.typed` present | Empty marker — correct form |
| Classifier `Typing :: Typed` | Aspirational relative to mypy strictness |
| `from __future__ import annotations` | Enforced via ruff isort required-imports — good |
| mypy | `check_untyped_defs = true` but **not** `disallow_untyped_defs`; builtins overrides disable arg-type, assignment, attr-defined, etc. |
| pyright | Not configured |
| Runtime types | Widespread `Any`, `dict`, untyped `run()` return in host |

For a language runtime, **typed public boundaries + gradual internal Any** is acceptable; today the **public** boundaries (Runtime result dict, evaluator context, series wrappers) are still largely untyped dictionaries/protocols-by-convention.

### Packaging / dependency hygiene

**Good:**

- hatchling src layout, dynamic version from `__about__.py`
- Optional extras: `lsp`, `compile`, `pro`, `data` — sensible
- AGPL-3.0-or-later SPDX headers ubiquitous
- sdist excludes brand noise / node_modules

**Weak:**

- Distribution name `hoox-pyne` vs import `pynescript` vs brand `pyne` — documented, still cognitively expensive
- Core deps unpinned ranges; Pro stack split between extra and `backend/requirements.txt`
- Alpha classifier correct; marketing README sometimes reads post-alpha
- Wheel does not ship backend; Docker/Pro path is the real “full stack” deliverable

---

## Consistency & craftsmanship scorecard (honest 1–10)

| Category | Score | Notes |
| --- | --- | --- |
| Architectural clarity (layers, ownership) | **6** | Front-end clean; runtime ownership split package/backend/worker |
| Dual-engine factoring (interpret/compile) | **5** | Works; shared IR missing; parity as after-the-fact discipline |
| Public API design | **6** | Thoughtful root minimalism; missing host in package; star-exports |
| Error model consistency | **7** | Parse strong; host error_kind good; compile typed; still many soft fails |
| Typing discipline | **4** | py.typed signal > enforcement; huge Any islands |
| Docs honesty & currency | **5** | Deep docs + stale DESIGN/rating/corpus claims |
| Inline docs standard | **7** | Best modules excellent; god-files uneven |
| Dependency & packaging | **6** | Modern hatch/extras; naming and pin policy middling |
| Duplication control | **4** | Dual host + TS port + external worker checklist |
| Security / trust boundaries | **5** | Auth keys solid; script exec/sandbox underexplained; corpus license risk |
| Test / parity culture | **8** | Large suite, corpus scripts, interp↔compile harness — strong |
| Code size / modularity | **4** | technical_submodules improved; compiler reverse of that |
| Consistency of conventions (NA/series) | **7** | Documented and mostly coherent; host/worker residual drift |
| Overall craftsmanship | **5.5** | Capable alpha product-engineering; not top-tier language runtime OSS |

---

## Gap vs “highest professional level”

A highest-professional open-source language runtime typically exhibits:

| Expectation | This repo |
| --- | --- |
| One installable library owns the full execution model | Split: package language core, backend host |
| Dual backends share a single IR or bytecode | Dual emit/walk with convergence tests |
| Strict typed public API + stability guarantees | Loose Any dict contracts; alpha, no stability RFC |
| Fail-closed by default; soft-fail enumerated | Soft-fail common and only partially enumerated |
| Docs as verified contract (doctest/CI drift checks) | Docs rich; some high-level docs wrong |
| God-files avoided or generated | Multi-kLOC hand-maintained compiler visitor |
| Third-party fixtures legally scrubbed / clearly optional | Large scraped corpus on disk; docs deny shipping |
| Sandbox story for untrusted scripts | None for compile `exec` path |
| Single source of version/truth | Package 0.3.3; langserver constant 0.1.0 |
| Contributor-facing map shorter than archaeology | Agent round noise + excellent AGENTS.md |

**What already approaches the bar:** parse/unparse contracts, mixin evaluator design, structured parse errors, compile exception hierarchy, series-cap/env policy docs, auth middleware, parity tooling, copyright/SPDX hygiene, future-annotations enforcement.

**What keeps it off the podium:** architectural split of Runtime, god modules, typing softness, dual-host drift, corpus/doc contradictions, and marketing-complete language while classifier and residuals say alpha.

---

## Prioritized recommendations for raising the bar

### P0 — Correctness & honesty (do first)

1. **Move or re-export a single package-level Runtime** 
 - Target: `pynescript.runtime` (or `pynescript.host`) owns bar loop + series + error_payload. 
 - `backend` becomes Flask adapters only; worker vendors package Runtime. 
 - Close H1 checklist DoD items with goldens (multi-run, inputs, auto caches).

2. **Reconcile corpus policy with the tree** 
 - Either: gitignore + document local-only collection (and ensure not in sdist), **or** ship a **small** first-party fixture set with clear licenses and provenance. 
 - Align README, AGENTS.md, `tests/data/README.md`. 
 - Scan set* for license headers / non-OSS; do not redistribute ambiguous community scrapes.

3. **Fix stale architecture statements** 
 - DESIGN.md evaluator section; rating.md plotting claims; dual-version langserver constant; any “100% compatibility” superlatives in COMPATIBILITY.md intro.

### P1 — Architecture & fail-closed

4. **Carve compiler.py / numba_builtins.py** into domain modules (emit expressions, strategy, plots, TA kernels, collections) with a thin CompilerVisitor facade — mirror the technical_submodules success story.

5. **Enumerate soft-fail sites** in one `docs/pyne/runtime/soft-fail-policy.mdx` (request mocks, color serialize, drawing GC, resolve_request_sources) and ban new bare `except Exception` without kind + comment in review.

6. **Sandbox / trust document for Pro API** 
 - State clearly: interpret is Python-side AST walk (still not reference Pine sandbox); compile is `exec` of generated code — only trusted tenants / resource limits / no filesystem builtins. 
 - Consider object-mode-only for multi-tenant until resource limits exist.

7. **AST call-site cache hygiene** (H1 P0) — never bind evaluator instance methods onto shared parse-cache trees without generation keys.

### P2 — API & typing

8. Publish a short **API stability table** (stable: `parse`/`unparse`/`SyntaxError`; provisional: compiler; internal: evaluator mixins).

9. Raise mypy on **public modules only** (`helper`, `error`, `compiler.engine` public functions, future `runtime`) with `disallow_untyped_defs = true`; leave builtins gradual.

10. Add TypedDict / dataclass for Runtime result (`series`, `error_kind`, `events`, …) shared by backend and tests.

11. Align `langserver.__version__` with `__about__` or remove the duplicate.

### P3 — Hygiene & craftsmanship

12. Pin or lower-bound thoughtfully for release reproducibility; document backend requirements vs extras.

13. Archive or index perf/parity agent rounds under `docs/archive/` so “current truth” is ROADMAP + DESIGN + pyne MDX only.

14. Deprecate or quarantine pine-worker until parity harness is green, or move to separate repo to reduce monorepo cognitive load.

15. Add a CI “docs drift” job for critical claims (version string, “no corpus”, Runtime import path).

---

## Evidence index (paths)

| Topic | Paths |
| --- | --- |
| Root API | `/mnt/data/home/jango/Git/pynescript/src/pynescript/__init__.py` |
| Version | `.../src/pynescript/__about__.py`, `.../src/pynescript/langserver/__init__.py` |
| Parse / cache | `.../src/pynescript/ast/helper.py` |
| Evaluator composition | `.../src/pynescript/ast/evaluator/__init__.py` |
| NA / expressions | `.../src/pynescript/ast/evaluator/expressions.py` |
| Compile surface | `.../src/pynescript/compiler/__init__.py`, `engine.py`, `compiler.py` |
| Host Runtime | `.../backend/runtime.py`, `evaluator.py`, `series.py` |
| H1 unify | `.../docs/perf_round7/H1_unify_checklist.md` |
| Packaging | `.../pyproject.toml` |
| Design stale | `.../DESIGN.md` §4.2 |
| Corpus | `.../tests/data/README.md` vs `set01`–`set05/`, `SOURCES.md` |
| Auth | `.../backend/middleware/auth.py` |
| pine-worker | `.../pine-worker/README.md` |

---

## Bottom line

**pynescript / hoox-pyne is a dense, serious alpha toolchain** with real dual-engine work, parity discipline, and above-average module-level documentation in the core language layers. It is **not** yet at the highest professional bar for an open-source language runtime: the execution host is architecturally homeless relative to the package, the compiler is a pair of megafiles, typing is mostly ceremonial on hot paths, dual hosts remain a known residual, and high-visibility docs partially deny a large third-party corpus that exists on disk.

Raising the bar is primarily a **unification and honesty program** (package Runtime, corpus policy, doc drift, fail-closed enumeration), not another feature sprint.
