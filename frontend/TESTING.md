# AXIS testing guide

## Quick commands

```bash
cd frontend

bun run test                 # unit + worker tests
bun run test:unit            # frontend/tests only
bun run test:coverage        # lcov + text under coverage/
bun run test:coverage:gate   # coverage + scoped line gate
bun run test:security        # tests/security/
bun run test:e2e:smoke       # Playwright @smoke (builds + preview)
bun run test:all             # coverage gate + security
```

From repo root:

```bash
bun run test:frontend
bun run test:frontend:coverage
```

## Layout

```
frontend/tests/
  setup.ts                 # localStorage / document stubs
  fixtures/                # bars, plugin modules
  helpers/                 # mock-fetch, mock-ws
  *.test.ts                # unit suites
  integration/             # run-pipeline, load-symbol, library-service
  security/                # (Phase D)
frontend/scripts/check-coverage.mjs
frontend/e2e/
  smoke.spec.ts            # @smoke Playwright
frontend/playwright.config.ts
frontend/worker/tests/     # auth, keys, runtime, scripts
```

## E2E (Playwright)

```bash
cd frontend
bun install
bunx playwright install chromium
bun run test:e2e:smoke       # @smoke only (PR CI)
bun run test:e2e:critical    # @smoke + @critical
bun run test:e2e             # all specs
```

- Mocks `/run` and Binance so smoke does not need a live Pro API.
- Selectors use `data-testid` on topbar / manager (`axis-btn-load`, `axis-manager`, …).
- CI: `axis-e2e` smoke on PR; **AXIS nightly** runs full e2e (`.github/workflows/axis-nightly.yml`).

## Security

```bash
bun run test:security
```

Covers plugin URL schemes, storage-via-URL reject, poisoned localStorage, worker partition isolation, If-Match 409, admin keys.

## Coverage policy

- **Gate:** **95%** lines on scoped core (ratchet: 70 → 80 → 83 → 87 → 90 → **95**).
- **Include:** plugins, storage (minus idb), store, results, sources, streams, data, chart pure helpers + series-factory/manager-access, worker auth/keys/runtime/scripts.
- **Excluded from gate:** `drawing-layer.ts`, `pane-manager` (unit-tested), `runner` chart apply, pyodide boot, legacy JS, Solid UI `.tsx`.
- Full unscoped report: `bun test --coverage`.

### Soft spots to raise for 90%

| Module | Notes |
| --- | --- |
| `storage/local.ts`, `cloud.ts`, `git*.ts` | Error paths, migration edges |
| `results/strategy.ts` | Multi-id, formatters, CSV |
| `chart/pine-drawings.ts` | polyline / aliases |

## Integration suites

| File | Covers |
| --- | --- |
| `tests/integration/run-pipeline.test.ts` | server engine mock `/run` |
| `tests/integration/load-symbol.test.ts` | mock-walk → store.bars |
| `tests/integration/library-service.test.ts` | storage façade |
| `tests/integration/live-rerun.test.ts` | multiplex start/stop |
| `tests/integration/plugin-install.test.ts` | fixture URL → registry |
| `tests/integration/persist.test.ts` | AXIS key shape (debounced) |

## Conventions

1. Import `./setup` first when tests touch store/plugins/storage.
2. No real network (mock `fetch` / WebSocket).
3. Prefer table-driven tests for catalog built-ins.
4. Plugin fixtures live in `tests/fixtures/plugins/`.

## Adding a unit test

1. Create `tests/<area>.test.ts`.
2. `import './setup'` if needed.
3. Use fixtures from `tests/fixtures/`.
4. Run `bun run test:unit` and `bun run test:coverage:gate`.

See the session testing plan for Phases B–D (streams, chart, e2e, security).
