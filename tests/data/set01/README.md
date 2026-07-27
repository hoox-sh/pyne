# set01 — Pine Script corpus (batch 1)

Public open-source Pine Script indicators, strategies, and libraries collected
for parser / evaluator / linter regression coverage.

| | |
| --- | ---: |
| Scripts | 250 |
| Indicators | 145 |
| Strategies | 80 |
| Libraries | 25 |
| Collected | 2026-07-27 |

See [SOURCES.md](./SOURCES.md) for repositories and expansion notes, and
[MANIFEST.json](./MANIFEST.json) for per-file provenance.

## Layout

- `indicators/` — `NNN_ind_<slug>.pine`
- `strategies/` — `NNN_str_<slug>.pine`
- `libraries/` — `NNN_lib_<slug>.pine`

Each file includes a short provenance header (`source_repo`, `source_path`,
`content_hash`) after the `//@version` line when present.
