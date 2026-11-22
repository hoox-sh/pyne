# Deploy proof — P0 `/ws/live` script `full.count` splice

- Date: 2026-11-11 (rev. 2)
- Seat: oo-spec-2 (Head of Deploy)
- Approval: `4781b066-3d40-42c2-9bca-ee928b86dc9e` — `deploy` / `production/pro-api`, approved by `operator`, 2026-11-11
- Card: `deploy-patched-pro-api-build-aga-a6c4e05d`

## Revision note — superseded values

Rev. 1 of this file cited image `8c3f52e5…`, `live_ws.py` sha `137d2e14…`, and AXIS build
`08f472a2`. **All three are superseded.** A newer API image was deployed by another actor
(built `2026-11-11T19:01:58Z`, started `19:02:35Z`) and AXIS now serves `db4840fa`
(`buildTime 2026-11-11T18:14:50Z`). Rev. 1 also summarized frames rather than storing them;
the raw capture is now `p0-live-frames-2026-11-11.jsonl` (below).

## Verdict

**P0 closed.** The running API serves the fixed contract: `full.count == len(bar_times) ==
len(plots) == len(series[k])`, deltas numbered from that count. Raw frames replayed through
AXIS's **currently deployed** applier (`db4840fa`) splice 37/37 with `needsFull: 0`.

## 1. Deployed identity — current running process

Container env labels are stale (`PYNESCRIPT_VERSION=0.6.11`, `GIT_SHA=dev`) and are **not**
used as evidence.

| Check | Command | Result |
|---|---|---|
| Local pyne HEAD | `git rev-parse --short HEAD` | `8bd2e883` — "fix(live): carry the tail axis and timeframe on /ws/live frames" |
| Fix ancestor | `git merge-base --is-ancestor 6ea1d35d HEAD` | yes |
| Local `live_ws.py` | `sha256sum backend/api/live_ws.py` | `17f1e8b7682b75d416d5465aff23358122233f315956a1500f864fdbec2b37e2` |
| Container `live_ws.py` | `docker exec pynescript-api-1 sha256sum /app/backend/api/live_ws.py` | identical `17f1e8b7…` |
| Package version | `python -c "import pynescript;print(pynescript.__version__)"` | `0.6.35` |
| Module resolution | `import backend.api.live_ws as m` | `/app/backend/api/live_ws.py` (`PYTHONPATH=/app/src:/app`) |
| Running image | `docker inspect pynescript-api-1 --format '{{.Image}}'` | `sha256:4537c056431d…` |
| Image built | `docker image inspect pynescript-api:latest` | `2026-11-11T19:01:58Z` |
| Container started | `docker inspect … .State.StartedAt` | `2026-11-11T19:02:35Z`, restarts `0` |
| Bind mounts | `docker inspect … .Mounts` | only `volume:/data` — no host source shadowing |

Note: `8bd2e883` also adds the tail axis (`times`) and `interval` to delta frames — visible
in the raw capture below.

## 2. Raw JSONL capture (audit-grade)

- Path: `.oo/proof/p0-live-frames-2026-11-11.jsonl`
- 43 lines, one JSON object per line: `{"ts": <unix seconds>, "frame": <verbatim frame>}`
- Script subscribe, `history_bars=10100`, `binance|spot|BTC/USDT|1m`, script `sma(20)/sma(50)`
- 37 deltas, **2 bar boundaries crossed**, elapsed 75.8 s
- No key material present (`grep -c pyn_` → 0)

Arithmetic re-checked on the raw lines:

```text
full:  count=10100  bar_times=10100  plots=10100  series={fast:10100, slow:10100}   -> equal
deltas: tail_len == count - base_index for all 37
        times_len == tail_len for all 37 ; interval == "1m" for all 37
seq:   1..38, strictly +1 ; fulls=1 ; errors=0
tails:  (10099,10100,1) x7  -> (10100,10101,1) x29 -> (10101,10102,1) x1
```

The two count increases (10100→10101→10102) are the two bar boundaries.

## 3. Live proof — the pre-fix mismatch (captured on the prior image)

Captured before the 19:01 image swap, on image `8c3f52e5` / `live_ws.py` `137d2e14`. Kept
because it is the discriminating case; it was **not** re-run on `4537c056`.

`history_bars` is not part of the shared-session fingerprint, so a 10,022-bar session is
reused for a 10,100 request. Probe: subscribe `10022`, re-subscribe same id with `10100`.

Pre-fix (`git show 6ea1d35d^`) declared `int(ensured["count"])` = 10100 while columns were
10,022. Post-fix: `full.count=10022 == len(bar_times) == len(plots) == len(series)`, deltas
numbered 10021/10022, 10 deltas seq 3..12, 0 errors.

## 4. AXIS client replay — currently deployed build `db4840fa`

`https://axis.hoox.sh/version.json` → `version 2.28.1`, `git db4840fa131f`, `dirty:false`,
`buildTime 2026-11-11T18:14:50.328Z`.

Applier identity at `db4840fa` (not assumed from an older build):

| File | `db4840fa` sha256 | HEAD sha256 | |
|---|---|---|---|
| `src/engine/client-apply.ts` | `3e852f0b4d8e…` | `3e852f0b4d8e…` | identical |
| `src/engines/session-delta.ts` | `8133c8a0cad7…` | `8133c8a0cad7…` | identical |
| `src/engine/live-wire.ts` | times-injection present at lines 2139-2145 | differs only by the later `ad957103` interval guard | **not** in deployed build |

Replay of the raw JSONL through `Redesign2DeltaApplier` + `scriptDeltaTimeTail`, with the
`times` injection `live-wire.ts:2139-2145` performs:

| Capture | deltas | all_spliced | needsFull | explicit `times` used | finalCount |
|---|---|---|---|---|---|
| `p0-live-frames-2026-11-11.jsonl` | 37 | **true** | **0** | 37/37 | 10102 |
| mismatch (10022 / window 10100) | 10 | **true** | **0** | n/a (older server) | 10022 |

## 5. Rollback tag (Card B)

- Tag: `pynescript-api:rollback-2026-11-11` → image `sha256:4537c056431d…`
- Additive only: `docker tag`; no `rmi`, restart, recreate, or compose change
- Running container before == after: image id unchanged, `StartedAt` unchanged
  (`2026-11-11T19:02:35.133321068Z`), `RestartCount` `0`
- Rollback is now a re-tag (`docker tag pynescript-api:rollback-2026-11-11 pynescript-api:latest`
  + compose up), not a rebuild. The compose up itself is a restart and needs approval.

## 6. What was not done

- No rebuild, restart, or recreate of any container.
- No image removal, no compose edits, no migrations, no deletes.
- No key minted or deleted (operator-supplied key, read from a `0600` file, never echoed).
- No AXIS deploy.

## Checklist

```text
[1] artifact exists at the stated path ......................... pass (JSONL + this file)
[2] verified with command / before-after numbers ............... pass (sha256, raw frames, replay)
[3] every claim has a source ................................... pass (commands + file:line cited)
[4] nothing outside deploy was touched ......................... pass (read-only + one additive docker tag)
```

## Risk

- **Low:** a script `full` can be smaller than `history_bars` when a pooled session is shorter.
  AXIS `db4840fa` is proven to splice it; no other consumer of script `full` was identified.
- **Open:** the pre-fix mismatch case was not re-run on `4537c056`; it rests on the byte-identical
  `_script_full_columns` logic plus the unit test.
