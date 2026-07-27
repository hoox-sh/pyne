# Pine Script corpus sets

Collected open-source Pine for parser / evaluator / linter regression.

| Set | Scripts | Indicators | Strategies | Libraries | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| [set01](./set01/) | 250 | 145 | 80 | 25 | v3:25, v4:122, v5:96, v6:7 |
| [set02](./set02/) | 250 | 140 | 70 | 40 | v5:33, v6:217 |
| [set03](./set03/) | 1000 | 717 | 251 | 32 | v5:6, v6:985, vNone:9 |
| [set04](./set04/) | 1000 | 750 | 250 | 0 | v5:21, v6:979 |
| [set05](./set05/) | 9131 | 2363 | 6768 | 0 | full remainder · v1:11, v2:487, v3:671, v4:2978, v5:4133, v6:520, vNone:331 |

**Total: 11631 unique scripts** (no content-hash overlap across sets).

| Path | Role |
| --- | --- |
| `set01/` … `set04/` | Curated batches (250 / 250 / 1000 / 1000) |
| `set05/` | Full drain of remaining pool uniques |
| `builtin_scripts/` | Official TradingView builtins (separate) |
| `library/` | Existing local reference stash (not re-imported) |

Rebuild / expand: `scripts/collect_pine_corpus.py`  
Per-set provenance: each set’s `SOURCES.md` + `MANIFEST.json`.
