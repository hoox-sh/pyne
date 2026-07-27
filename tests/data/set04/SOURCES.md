# Pine Script corpus sources — set04

Collected: 2026-07-27
Scripts in this set: **1000**

Large batch. Content hashes are **disjoint** from set01, set02, set03
(via `--exclude-manifest` for each prior set).

## Composition

| Kind | Count |
| --- | ---: |
| Librarys | 0 |
| Strategys | 250 |
| Indicators | 750 |

## Pine version mix

| Version | Count |
| --- | ---: |
| v5 | 21 |
| v6 | 979 |

## Used repos

| Repo (pool dir) | URL | Scripts | Notes |
| --- | --- | ---: | --- |
| `pinescript-agents` | [pinescript-agents](https://github.com/TradersPost/pinescript-agents) | 250 | TradersPost agents + strategy templates (v6) |
| `pinescriptv6` | [pinescriptv6](https://github.com/codenamedevan/pinescriptv6) | 250 | v6 reference / sample scripts |
| `mihakralj-pinescript` | [mihakralj-pinescript](https://github.com/mihakralj/pinescript) | 172 | Large MIT indicator suite (v6) |
| `QuanTAlib` | [QuanTAlib](https://github.com/mihakralj/QuanTAlib) | 160 | Quantitative indicator library (Apache) |
| `fmzquant-strategies` | [fmzquant-strategies](https://github.com/fmzquant/strategies) | 128 | Pine fenced in strategy markdown (FMZ bulk dump) |
| `hasnocool-tradingview-pine-scripts` | [hasnocool-tradingview-pine-scripts](https://github.com/hasnocool/tradingview-pine-scripts) | 21 | Scraped TV open-source scripts (cleaned) |
| `mcp-server-pinescript` | [mcp-server-pinescript](https://github.com/iamrichardD/mcp-server-pinescript) | 5 | MCP pine samples |
| `algocode2022-PineScript` | [algocode2022-PineScript](https://github.com/algocode2022/PineScript) | 3 | Personal pine collection |
| `Salikha003-PineScripts` | [Salikha003-PineScripts](https://github.com/Salikha003/PineScripts) | 2 | Personal scripts |
| `ArunKBhaskar-PineScript` | [ArunKBhaskar-PineScript](https://github.com/ArunKBhaskar/PineScript) | 2 | ICT / momentum setups |
| `PineTS` | [PineTS](https://github.com/LuxAlgo/PineTS) | 2 | PineTS fixtures / samples |
| `pinescript-development-workspace` | [pinescript-development-workspace](https://github.com/tradesdontlie/pinescript-development-workspace) | 2 | Dev workspace samples |
| `casoon-pine-scripts` | [casoon-pine-scripts](https://github.com/casoon/pine-scripts) | 1 | Community indicators/strategies |
| `dexcextrade-TradingView-PineScripts` | [dexcextrade-TradingView-PineScripts](https://github.com/dexcextrade/TradingView-PineScripts) | 1 | TV pinescript dump |
| `dgfctr-PineScript` | [dgfctr-PineScript](https://github.com/dgfctr/PineScript) | 1 | Libraries (bands, trend systems) |

## Build command

```bash
python scripts/collect_pine_corpus.py \
  --pool /tmp/pine-new-collect \
  --set set04 \
  --target 1000 \
  --max-per-repo 200 \
  --libraries 80 --strategies 250 --indicators 670 \
  --prefer-version \
  --exclude-manifest tests/data/set01/MANIFEST.json \
  --exclude-manifest tests/data/set02/MANIFEST.json \
  --exclude-manifest tests/data/set03/MANIFEST.json
```

Pool unique candidates at build: **10131**
Skipped: `{'not_pine': 4892, 'unreadable_or_size': 221, 'excluded_manifest': 1499, 'duplicate_hash': 806}`

## Layout

```
tests/data/set04/
  indicators/NNNN_ind_<slug>.pine
  strategies/NNNN_str_<slug>.pine
  libraries/NNNN_lib_<slug>.pine
  MANIFEST.json
  SOURCES.md
  README.md
```

## Related

- [set01](../set01/SOURCES.md) · [set02](../set02/SOURCES.md) · [set03](../set03/SOURCES.md) · [set04](../set04/SOURCES.md)
- Collector: `scripts/collect_pine_corpus.py` (supports MD fence extraction + scrape cleanup)

