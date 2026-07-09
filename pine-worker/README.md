# pine-worker

TypeScript implementation of the Pine Script evaluator (parser + AST + runtime).

This is an **extra tool** of the main `pynescript` Python repository. It lives in this subdirectory so that:

- Parity fixtures and contracts (`tests/fixtures/parity/`) are co-located and easy to keep in sync.
- The ANTLR grammar remains the single source of truth (regenerate TS parser target from `../src/pynescript/ast/grammar/antlr4/resource/*.g4`).
- Development, testing, and porting can cross language boundaries in one checkout.

## Status

This is the home of **Plan 2** of the strategy-events effort (see `../.opencode/plans/2026-07-05-pine-worker-strategy-events.md`).

Currently a skeleton + partial port of:

- AST Zod schemas + types (mirrors Python ASDL)
- Base evaluator + visitor dispatch
- PineSeries (historical bar access)
- Core NA/loop signal semantics

Full builtins port, parser (ANTLR TS target), runtime loop, and strategy event emission are in progress.

## Quick start (requires Bun)

```bash
cd pine-worker
bun install
bun test
bun run typecheck
```

## Parity with Python reference

The Python side (in `pynescript` + `backend/`) is the source of truth.

Fixtures:

- `../tests/fixtures/parity/pine/*.pine`
- `../tests/fixtures/parity/json/*.json`

Run Python side to (re)generate:

```bash
python ../tests/fixtures/parity/generate_fixtures.py
```

TS parity harness will live under `test/parity/`.

## Converter / porting aid

A Python → TypeScript porting helper (skeleton generator) lives here:

```bash
python pine-worker/scripts/convert-python-to-ts.py \
  src/pynescript/ast/evaluator/builtins/numeric.py
```

It emits a `.ts` file with JSDoc + function signatures + TODO bodies to speed up the manual port while keeping you honest about parity.

It is intended to generate initial TS stubs/skeletons from Python builtin implementations to accelerate manual porting while preserving semantics.

## Relationship to hoox-setup / trade-worker

Once mature, `pine-worker` can be vendored or submoduled into hoox-setup as `workers/pine-worker` for the Cloudflare Worker packaging + service binding to trade-worker (Plan 3).

For now it is developed here as part of the pynescript monorepo-like layout.

## License

Same as parent pynescript project.
