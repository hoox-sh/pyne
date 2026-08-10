# AGENT 07 — Tests, Scripts, CI/CD, Packaging, pine-worker

**Date:** 2026-08-10  
**Scope:** `tests/`, `scripts/`, packaging/CI configs, `pine-worker/`, `examples/`  
**Mode:** Read-only audit (no product code changes)  
**Auditor role:** Senior code audit of confidence gates (do tests prove correctness or only smoke?)

---

## Executive summary

The repository has a **large local test surface** (~70 Python test modules, multi-thousand-script corpus tooling, interpret↔compile harness, strategy/order-fill suites) but **CI exercises only a thin slice**: linter + evaluator + CLI + LSP + backend + package/Docker smoke. That gap is intentional and documented, yet it creates **systemic false confidence**: green CI does not protect strategy runtime, compiler/Numba, interp/compile parity, series buffers, TA correctness, or pine-worker.

**Critical themes:**

1. **CI omits the highest-value correctness tests** (parity, compiler, strategy, series, corpus residuals).
2. **Interpret↔compile “always-on” smoke is inert** when `tests/data/builtin_scripts/` is empty (all cases `pytest.skip`).
3. **Several corpus-dependent tests silent-pass** (`return` without `pytest.skip`) when files are missing.
4. **TA indicator test modules are parse/unparse smoke**, not numerical correctness.
5. **pine-worker TS port is a skeleton**: series index polarity disagrees with Python Pine offsets; parity harness is a no-op; no CI job.
6. **Cloud Build deploys Pro API without running tests** and with `--allow-unauthenticated`.
7. **Version/label drift** across `__about__.py` (0.3.3), root `package.json` / cloudbuild pin (0.3.0), compose defaults (0.2.0).

Local harness quality for interpret↔compile (`scripts/compare_interp_compile.py` + unit tests of the harness itself) is **strong**. Strategy unit tests and backend API tests are **solid when run**. The main risk is **what never runs on PR**, and **tests that look green while asserting almost nothing**.

---

## Critical

### C1. CI core job omits parity, compiler, strategy, series, and runtime residual suites

**Evidence:** [`.github/workflows/ci.yml:69-77`](.github/workflows/ci.yml) runs only:

```text
tests/test_linter.py
tests/test_evaluator.py
tests/test_cli.py
```

plus LSP and `tests/test_backend.py`. Explicit comment at `:70-71` says corpus-parametrized tests are omitted for speed.

**Impact:** A PR can break:

- interpret↔compile value parity (`test_interp_compile_parity.py`, `test_compiler_numba.py`)
- strategy broker / fills / risk (`test_strategy_runtime.py`, `test_order_fills.py`, `test_parity.py`)
- series cap/ring (`test_series_cap.py`, `test_series_ring_buffer.py`)
- TA incremental vs full (`test_ta_incremental.py`)
- compiler object mode / strategy compile (`test_compiler_objects.py`, `test_compiler_strategy.py`)

…and CI stays green. Documented in [`docs/pyne/devops/ci.mdx:75-79`](docs/pyne/devops/ci.mdx) but still a **product risk**, not just a process note.

**Recommendation:** Add a `test-core-runtime` job (single Python version, ~5–10 min budget) with:

```text
tests/test_parity.py
tests/test_interp_compile_parity.py
tests/test_compiler_numba.py
tests/test_compiler_strategy.py
tests/test_strategy_runtime.py
tests/test_order_fills.py
tests/test_series_cap.py
tests/test_series_ring_buffer.py
tests/test_ta_incremental.py
tests/test_expr_parity_r8.py
```

Keep full corpus out of PR CI; keep first-party inline/fixture tests in.

---

### C2. Always-on interp/compile smoke depends on empty `builtin_scripts/`

**Evidence:**

- Smoke list expects files under `tests/data/builtin_scripts/` — [`tests/test_interp_compile_parity.py:48-72`](tests/test_interp_compile_parity.py), `:263-268` (`pytest.skip` if missing).
- `tests/data/builtin_scripts/` is **empty** in the tree (directory present, no `*.pine`).
- AGENTS / data README state third-party corpora are not shipped ([`AGENTS.md:64-66`](AGENTS.md), [`tests/data/README.md:3-13`](tests/data/README.md)).

**Impact:** The 17-script “always-on” smoke that CI would rely on **never asserts value parity** in a clean clone; every case skips. Harness unit tests (allclose, ignore flags) still run, so the module can look “mostly green” while proving no script-level correctness.

**Recommendation:** Point `_ALWAYS_SCRIPTS` at **shipped** assets:

- first-party `tests/fixtures/parity/pine/*.pine`, and/or
- **inline** mini indicators (SMA/RSI/ATR) embedded in the test module (as `SCRIPTS` does in `scripts/bench_pipeline.py`).

Fail hard if a listed always-on asset is missing (`pytest.fail`), do not skip.

---

### C3. Silent pass on missing corpus paths in R9 kernel tests

**Evidence:** [`tests/test_parity_r9_kernels.py:94-95`](tests/test_parity_r9_kernels.py), `:114-115`, `:259-260`, `:276-277`, `:291-292`:

```python
if not path.is_file():
    return
```

Contrast with proper skips in [`tests/test_corpus_runtime_residuals.py:232-233`](tests/test_corpus_runtime_residuals.py) and [`tests/test_corpus_collections_r8.py:176-177`](tests/test_corpus_collections_r8.py).

**Impact:** Without local set01/set02 trees, five “corpus residual parity” tests **pass with zero assertions**. Worse than skip: no yellow count in CI summary.

**Recommendation:** Replace bare `return` with `pytest.skip(...)` or mark `@pytest.mark.corpus` and exclude from default CI while failing under a `corpus` job when the path is expected.

---

### C4. Cloud Build deploys without test gate; public unauthenticated service

**Evidence:** [`cloudbuild.yaml`](cloudbuild.yaml)

- Steps: `docker build` → `push` → `gcloud run deploy` → optional Nuitka LSP (`:13-73`).
- **No pytest / no image smoke** before deploy.
- Deploy uses `--allow-unauthenticated` (`:50`).
- Version pin `_PYNESCRIPT_VERSION: "0.3.0"` (`:11`) vs package [`src/pynescript/__about__.py:33`](src/pynescript/__about__.py) `__version__ = "0.3.3"`.

**Impact:** Broken API image can ship to Cloud Run; image labels/version may disagree with source; unauthenticated surface relies entirely on app-level auth (partially tested only in GitHub CI Docker smoke).

**Recommendation:** Add a Cloud Build step that runs container health + minimal `/run` smoke (and/or reuses GitHub CI artifacts). Sync `_PYNESCRIPT_VERSION` from `__about__.py`. Revisit unauthenticated exposure separately (security).

---

### C5. pine-worker series offset convention contradicts Python/Pine

**Evidence:**

| Side | Convention | Source |
| --- | --- | --- |
| Python | Pine offset **n ≥ 0**: `0` = current, `1` = previous; negative → na | [`src/pynescript/ast/evaluator/series_buffer.py:157-163`](src/pynescript/ast/evaluator/series_buffer.py) |
| TypeScript | `get(offset)`: **negative** = past, **positive** = future | [`pine-worker/src/evaluator/series.ts:46-60`](pine-worker/src/evaluator/series.ts) |
| TS tests encode inverted model | `get(-1, 5)` historical | [`pine-worker/test/series.test.ts:40-45`](pine-worker/test/series.test.ts) |

README claims co-located parity with Python oracle ([`pine-worker/README.md:33-48`](pine-worker/README.md)), but **no TS test consumes** `tests/fixtures/parity/json/*.json`. `package.json` parity script is a soft-fail placeholder:

```text
"parity": "bun test test/parity ... || echo 'parity harness not yet wired'"
```

([`pine-worker/package.json:13`](pine-worker/package.json))

**Impact:** Any port that reuses TS `PineSeries.get` for `close[1]`-style semantics will invert history vs future. Unit tests **lock in the wrong polarity**. Cross-language strategy event parity is currently **Python-only** ([`tests/test_parity.py:20-34`](tests/test_parity.py) documents TS plan; TS harness not present).

**Recommendation:** Align TS API to Pine positive lookback; add golden tests against shared OHLCV + JSON fixtures; make `bun run parity` fail CI when harness missing or failing; add GitHub job for `pine-worker` `bun test` + `tsc`.

---

## High

### H1. “TA indicator” modules mostly prove parse/unparse, not values

**Evidence:** [`tests/test_ta_indicators_1.py:40-50`](tests/test_ta_indicators_1.py) — parse → unparse → assert name string present. Same pattern in `test_ta_indicators_2..8.py` and [`tests/test_indicators.py:40-56`](tests/test_indicators.py) (docstrings claim “basic calculation” / zero-range behavior but only parse).

**Impact:** Large test surface and class names imply numerical coverage for kama/dema/cmf/etc.; a broken TA implementation that still parses would pass.

**Recommendation:** For each claimed indicator, add Runtime or builtin-call tests with fixed series and golden last values (as `test_compiler_numba.py` does for SMA at `:56-71`, and `test_ta_incremental.py` does for incremental vs full).

---

### H2. Fixture generator can silently skip failures and bake stale goldens

**Evidence:** [`tests/fixtures/parity/generate_fixtures.py:62-66`](tests/fixtures/parity/generate_fixtures.py):

```python
if "error" in result:
    print(f"SKIP: {sname} ({result['error'][:80]})")
    continue
```

**Impact:** Regenerating after a regression leaves old JSON in place while printing SKIP; reviewers may assume fixtures refreshed. Oracle is **current Python Runtime**, not TradingView — correct for Python↔TS parity, but regenerating after a bug **encodes the bug**.

**Recommendation:** Exit non-zero if any script errors; require explicit `--force` to overwrite; optionally hash bar input into JSON metadata.

---

### H3. Interp/compile smoke skips runtime errors as non-failures

**Evidence:** [`tests/test_interp_compile_parity.py:74-83`](tests/test_interp_compile_parity.py), `:278-283` — statuses in `_SKIP_STATUSES` (`interp_error`, `compile_error`, `both_error`, …) call `pytest.skip`. Harness CLI treats `both_error_same` / `expected_error` as non-fatal by default ([`scripts/compare_interp_compile.py:744-747`](scripts/compare_interp_compile.py)).

**Impact:** Shared regressions (both backends break the same way) can look “OK” under soft policy. Appropriate for exploratory corpus sweeps; **dangerous for always-on CI smoke** if smoke scripts ever exist.

**Recommendation:** For always-on list, only allow `OK` / optional `fill_background_only`. Use skip only for documented environment gaps (no numba).

---

### H4. Version / packaging identity drift

| Location | Value |
| --- | --- |
| `src/pynescript/__about__.py` | `0.3.3` |
| root `package.json` | `0.3.0` |
| `cloudbuild.yaml` `_PYNESCRIPT_VERSION` | `0.3.0` |
| `docker-compose.yml` / prod default `PYNESCRIPT_VERSION` | `0.2.0` |
| PyPI name | `hoox-pyne` ([`pyproject.toml:9`](pyproject.toml)) |
| Hatch test matrix | 3.10–3.12 only ([`pyproject.toml:149-150`](pyproject.toml)); CI also 3.13 |

**Impact:** Misleading image labels, support confusion, hatch envs not covering CI’s 3.13.

---

### H5. Wheel package does not include `backend/`; Pro path is Docker/source only

**Evidence:** `[tool.hatch.build.targets.wheel] packages = ["src/pynescript"]` ([`pyproject.toml:113-114`](pyproject.toml)). Dockerfile copies `backend/` separately ([`Dockerfile:82-83`](Dockerfile)).

**Impact:** `pip install hoox-pyne` does not install the Flask Pro API. Fine if intentional, but `make install-pro` / docs must stay clear. Wheel smoke only imports CLI (`ci.yml:120-128`) — no Pro API import check.

---

### H6. Lint/type gates are soft

**Evidence:**

- Ruff CI selects only `E,F,W` with several ignores ([`ci.yml:35-42`](ci.yml)); full `make lint` not enforced.
- mypy: `mypy src/ --ignore-missing-imports || true` (`:46`) — **always green**.
- Tests excluded from mypy errors entirely ([`pyproject.toml:296-301`](pyproject.toml)).

**Impact:** Style/type debt can grow without PR signal.

---

### H7. `test_parity` strategy corpus depends on empty `builtin_scripts`

**Evidence:** [`tests/test_parity.py:123-172`](tests/test_parity.py) parametrizes `rsi_strategy`, `macd_strategy`, `greedy_strategy` under `tests/data/builtin_scripts/`. With empty dir, `path.exists()` fails → **hard fail** if module is collected. Not in CI today (C1). When added to CI without shipping files, suite fails immediately.

**Recommendation:** Move those three scripts into `tests/fixtures/` or inline them.

---

## Medium

### M1. `conftest.py` optional corpus; parse/unparse suite is dead in CI

**Evidence:** [`tests/conftest.py:49-69`](tests/conftest.py) — if no `*.pine` under example dir, parametrizes a single **skipped** case. [`tests/test_parse_and_unparse.py`](tests/test_parse_and_unparse.py) is therefore a no-op without local corpus. Copilot instructions still claim broad corpus parse/unparse ([`.github/copilot-instructions.md:17`](.github/copilot-instructions.md)) — **stale**.

### M2. OHLCV fixture inconsistencies

- Parity OHLCV: no `volume` key ([`tests/fixtures/parity/ohlcv.py:63-71`](tests/fixtures/parity/ohlcv.py)); host defaults volume to `1.0` ([`backend/runtime.py:453-481`](backend/runtime.py)).
- Harness `make_bars` includes volume ([`scripts/compare_interp_compile.py:128-136`](scripts/compare_interp_compile.py)).
- Multiple ad-hoc bar generators in tests (`test_parity_r9_kernels`, `test_corpus_runtime_residuals`, compiler tests) with different noise/structure.

**Impact:** OBV/MFI/volume-sensitive scripts diverge across harnesses; harder to reproduce failures.

### M3. Stub / smoke assertions that always pass

- `assert True` after “should not raise” ([`tests/test_evaluator.py:2343-2344`](tests/test_evaluator.py)).
- Timeframe stubs return fixed False/str ([`:2320-2327`](tests/test_evaluator.py)).
- xfail open on bar-mode SMA ([`tests/test_strategy_risk_enforcement.py:65-76`](tests/test_strategy_risk_enforcement.py)) — documented, but shows bar-mode TA still incomplete.

### M4. pine-worker tooling gaps

- `lint` script is `echo 'add eslint or biome here'` ([`pine-worker/package.json:12`](pine-worker/package.json)).
- `tsconfig` excludes `test/` from typecheck (`include: src only` — [`pine-worker/tsconfig.json:19-20`](pine-worker/tsconfig.json)).
- Root CI has no Bun/Node job for pine-worker (VS Code extension only).
- Converter emits TODO stubs only ([`pine-worker/scripts/convert-python-to-ts.py:39-40`](pine-worker/scripts/convert-python-to-ts.py)) — fine as a tool; risk is treating stubs as complete.

### M5. Examples are educational, not CI-gated

[`examples/`](examples/) includes scripts that import pandas (`execute_script.py`) and custom mini interpreters — not executed in CI. No `examples` smoke job. Fine for demos; do not treat as regression suite.

### M6. Corpus tooling quality high, CI coupling low

Scripts `corpus_run_runtime.py`, `showcase.py`, `compare_interp_compile.py` have thoughtful EXPECTED_FAIL lists and bucket summaries (R8 harness work). They **are not** PR gates. Local OK% claims in README can diverge from main if corpus data is only local.

### M7. Nuitka release matrix soft-fails binaries

[`release.yml:384-391`](release.yml) creates releases if package+vscode succeed even when LSP/CLI matrix cells fail (`fail-fast: false`, binary_count can be 0 with a warning). Acceptable for flake tolerance; risk of shipping incomplete release assets without hard signal.

### M8. Coverage reporting only on backend job

Codecov upload from `test_backend.py` run only (`ci.yml:86-99`). Core package coverage from evaluator/linter is not uploaded. `fail_ci_if_error: false`.

---

## Low

### L1. Duplicate version / label defaults in compose

`docker-compose.yml` / `docker-compose.prod.yml` default `PYNESCRIPT_VERSION` to `0.2.0` while package is 0.3.x.

### L2. Hatch `test-cov` uses xdist + cov

[`pyproject.toml:139-141`](pyproject.toml) — fine if configured; can flake under heavy numba compile if workers share cache (not CI issue today).

### L3. Property-based testing unused

`.hypothesis/` is gitignored; no `hypothesis` dependency. Good candidate for NA arithmetic, series lookback, sanitize edge cases.

### L4. Markers underused

Only `interp_compile_full` registered ([`pyproject.toml:185-187`](pyproject.toml)). No `slow`, `corpus`, `numba`, `pine_worker`, `network` markers for selective CI tiers.

### L5. Dockerfile duplicate copyright header block

Cosmetic: lines 1–6 repeat license/comment block ([`Dockerfile:1-6`](Dockerfile)).

### L6. `test_parse_and_unparse` uses `repr` equality

Structural round-trip via `repr(ast)` ([`tests/test_parse_and_unparse.py:39`](tests/test_parse_and_unparse.py)) is fragile if `repr` changes without semantic change.

---

## Coverage gaps (critical paths)

| Critical path | Local tests exist? | In PR CI? | Quality of proof |
| --- | --- | --- | --- |
| Parse / lint | Yes (`test_linter`, lexer fixes) | Partial (linter only) | Good for linter |
| Evaluator expressions / builtins | Large `test_evaluator.py` | Yes | Mixed: deep + stubs |
| Strategy events / position | `test_parity`, `test_strategy_*`, fills | **No** | Good when run |
| Interpret ↔ compile series | harness + smoke + numba tests | **No** | Strong harness; smoke inert without files |
| Numba transpile/run | `test_compiler_*` | **No** | Good numerical checks in places |
| Series cap / ring buffer | dedicated modules | **No** | Good isolation with monkeypatch |
| TA incremental | `test_ta_incremental.py` | **No** | Strong A/B vs disabled |
| TA surface inventory | `test_ta_indicators_*` | **No** | **Smoke only** (parse) |
| Corpus sanitize | extensive | **No** | High quality unit tests |
| Backend HTTP / auth | `test_backend.py` | Yes | Good Flask client fixtures |
| CLI | `test_cli.py` | Yes | Good tmp_path isolation |
| LSP | langserver + features | Yes | Solid unit coverage |
| pine-worker TS | unit only | **No** | Foundation only; parity unwired |
| Docker api/cli | smoke in CI | Yes | Health + auth + `check` only |
| Cloud Run deploy | cloudbuild | N/A | **No test step** |
| PyPI package | build + import | Yes | CLI only |

**Corpus sets set01–set05:** present in this workspace for local measurement; policy says not part of shipped product confidence. Tests that soft-skip/silent-return on missing files blur that boundary.

---

## Documentation of test intent / fixtures

| Asset | Assessment |
| --- | --- |
| `tests/conftest.py` docstring | Clear: optional local corpus |
| `tests/fixtures/parity/*` | Excellent module docs + generate script |
| `tests/test_parity.py` header | Clear Python oracle / TS plan |
| `tests/test_interp_compile_parity.py` | Clear always-on vs full mark |
| `scripts/compare_interp_compile.py` | Excellent CLI/docs, cache notes |
| `docs/pyne/runtime/compiler/parity.mdx` | Good contract for interpret/compile |
| `docs/pyne/pine-worker/testing.mdx` | Honest about unwired parity |
| `docs/pyne/devops/ci.mdx` | Accurate about thin CI |
| `tests/data/README.md` | Accurate “no third-party ship” |
| `test_ta_indicators_*` docstrings | **Misleading** (claim calculation, do parse) |
| `.github/copilot-instructions.md` | **Stale** on corpus parse suite |

---

## Modernization opportunities

1. **Markers + tiers:** `fast` (CI), `runtime` (parity/compiler/strategy), `corpus` (local/nightly), `numba`.
2. **Shared bar fixture** in `conftest.py` (`ohlcv_bars(n, seed, volume=True)`) replacing N copies.
3. **Parametrize goldens** for TA: `@pytest.mark.parametrize("fn,args,expected", ...)` against known closed forms.
4. **Hypothesis** for: NA propagation, series lookback bounds, sanitize idempotence, allclose edge cases.
5. **Snapshot testing** (optional) for strategy event streams — already JSON fixtures; could use syrupy for series tails.
6. **Strict CI subset** that fails on skip-count thresholds (e.g. fail if >0 skips in always-on parity).
7. **pine-worker:** add `test/parity/*.test.ts` reading `../tests/fixtures/parity/json`; run under Bun in CI.
8. **Coverage gates** on `pynescript.compiler` + `ast.evaluator` for the runtime job (not only backend).
9. **Replace silent `return`** with skip/xfail API consistently.
10. **Nightly workflow** for `scripts/compare_interp_compile.py --limit 50` and corpus residual CSV diff when corpus present.

---

## Scorecard (1–10)

| Dimension | Score | Notes |
| --- | --- | --- |
| Test design quality (when intentional) | **7** | Strong fixtures, monkeypatch isolation, harness unit tests, strategy depth |
| False-confidence risk | **3** | Thin CI, empty smoke corpus, silent passes, parse-as-TA |
| CI/CD effectiveness | **5** | Good packaging/Docker smoke; weak product correctness gate; soft mypy |
| Packaging / release | **7** | Solid hatch/sdist/wheel/publish OIDC; version drift; backend not in wheel (OK if clear) |
| Scripts quality | **8** | compare_interp_compile, corpus_run_runtime, showcase, build scripts are mature |
| Documentation of tests | **7** | Parity/docs excellent; some modules mislabeled |
| pine-worker TS readiness | **3** | Skeleton + inverted series semantics + no parity harness/CI |
| Modern testing techniques | **5** | Parametrize/xdist/monkeypatch used; little property-based; markers sparse |
| **Overall confidence gate** | **4.5** | Local experts can validate deeply; PR CI does not |

**Test helpers / scripts code quality:** **8/10** for harnesses; **6/10** for test-module consistency (silent return vs skip, bar generators).

---

## Prioritized recommendations

| Priority | Action | Effort | Pays off |
| --- | --- | --- | --- |
| P0 | CI job: first-party runtime/compiler/strategy/parity subset (C1) | M | Stops silent main breakage |
| P0 | Fix always-on smoke to use shipped fixtures/inline scripts (C2) | S | Makes “always-on” real |
| P0 | Replace silent `return` with skip/fail in R9 tests (C3) | S | Honest suite |
| P0 | Align pine-worker series offsets with Pine/Python (C5) | M | Avoids permanent port rot |
| P1 | Wire TS parity harness + CI `bun test` (C5/H) | M | Python↔TS contract |
| P1 | Cloud Build: test/smoke before deploy; sync version (C4/H4) | S–M | Prod safety |
| P1 | Upgrade TA modules from parse smoke to value goldens (H1) | L | Real indicator confidence |
| P2 | Fixture generator fail-closed (H2) | S | Oracle hygiene |
| P2 | Markers + nightly corpus job (M4/M6) | M | Scale without PR timeout |
| P2 | Single shared OHLCV factory (M2) | S | Repro consistency |
| P3 | Hypothesis for NA/series; harden mypy over time (L3/H6) | L | Long-term quality |
| P3 | Version single-source across package.json / compose / cloudbuild (H4) | S | Ops hygiene |

---

## Evidence index (key paths)

| Path | Role in audit |
| --- | --- |
| [`tests/conftest.py`](tests/conftest.py) | Optional corpus parametrization |
| [`tests/test_interp_compile_parity.py`](tests/test_interp_compile_parity.py) | Always-on smoke + skip policy |
| [`tests/test_parity.py`](tests/test_parity.py) | Strategy event oracle |
| [`tests/test_parity_r9_kernels.py`](tests/test_parity_r9_kernels.py) | Silent pass pattern |
| [`tests/fixtures/parity/`](tests/fixtures/parity/) | First-party goldens |
| [`scripts/compare_interp_compile.py`](scripts/compare_interp_compile.py) | Interp/compile harness |
| [`scripts/corpus_run_runtime.py`](scripts/corpus_run_runtime.py) | Corpus EXPECTED_FAIL |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Thin test matrix |
| [`cloudbuild.yaml`](cloudbuild.yaml) | Deploy without tests |
| [`pyproject.toml`](pyproject.toml) | Packaging, pytest markers, hatch envs |
| [`pine-worker/src/evaluator/series.ts`](pine-worker/src/evaluator/series.ts) | Offset polarity risk |
| [`pine-worker/package.json`](pine-worker/package.json) | Unwired parity |
| [`src/pynescript/ast/evaluator/series_buffer.py`](src/pynescript/ast/evaluator/series_buffer.py) | Python lookback truth |
| [`Makefile`](Makefile) | Local `make test` runs full tree |

---

## Bottom line

**Scripts and local harnesses are a strength.** **CI and “always-on” packaging of confidence are a weakness.** The project can measure deep correctness on a developer machine with corpus + harnesses, but a green GitHub Actions run today primarily proves: lint subset, evaluator/linter unit suite, CLI smoke, LSP units, Flask backend, wheel import, and Docker health—not the dual-engine runtime that defines product fidelity.

Treat **P0 items (C1–C3, C5)** as the minimum to turn the large local investment into a trustworthy gate.
