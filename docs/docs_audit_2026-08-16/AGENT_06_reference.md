# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Docs audit Agent 06 — Reference + satellites

**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-11c9-7191-bf18-6828b9402fd1`  
**Package:** `hoox-pyne` **0.3.10** (`src/pynescript/__about__.py`)  
**Verdict:** **updated**

Did not commit. Did not edit `docs.json`.

---

## Verdict

Reference + satellite pages now match 0.3.10 facts: pine-worker is **not** in-tree, T2 volume kernels (`obv`/`wad`/`wvad`/`cmf`/`klinger`) are landed, H1 package Runtime SoT is **largely done**, PyneTS docs distinguish standalone **`@hoox-sh/pynets` 0.2.0** from the **0.1.0 interpret-only submodule pin**, agent/index does not claim `pyne-agent-worker` lives here, CONTRIBUTING release steps match `publish.yml` + `release.yml` + `ghcr.yml`, README capabilities mention 0.3.10 interpret + volume inc.

---

## Pages read

### Exclusive MDX
- `docs/pyne/reference/ecosystem.mdx`
- `docs/pyne/reference/compatibility.mdx`
- `docs/pyne/reference/implementation-status.mdx`
- `docs/pyne/reference/missing-features.mdx`
- `docs/pyne/reference/pine-v6-surface.mdx`
- `docs/pyne/reference/numerical-validation.mdx`
- `docs/pyne/reference/roadmap.mdx`
- `docs/pyne/contributing.mdx`
- `docs/pyne/pynets/{index,install,cli,runtime,compile,parity}.mdx`
- `docs/pyne/pine-worker/{index,converter,testing}.mdx`
- `docs/pyne/agent/index.mdx`

### Root / satellite SoT
- `README.md`, `CONTRIBUTING.md`, `COMPATIBILITY.md`
- `docs/ROADMAP.md`, `docs/missing_features.md`, `docs/pinescript_implementation_status.md`
- `docs/WRITING.md`, `docs/docs_audit_2026-08-16/PROMPT.md`, `CHANGELOG.md`
- `docs/compatibility_guarantee.md` (read; not exclusive — hole)
- `docs/pyne/docs.json` (read; not edited)

### Code / sisters checked
- `src/pynescript/__about__.py` → `0.3.10`
- `src/pynescript/runtime/__init__.py` + `backend/runtime.py` (shim)
- `pynets/package.json` (submodule: `@hoox/pynets` **0.1.0**, private, interpret-only)
- `pynets/src/index.ts` + `src/runtime/interpret.ts` (no compile)
- Standalone `/home/jango/Git/pynets/package.json` → `@hoox-sh/pynets` **0.2.0** + `src/runtime/compile/`
- `/home/jango/Git/pine-worker` (sister; README still talks as colocated — out of this repo)
- `/home/jango/Git/pyne-agent-worker` (sister 0.1.2; not in this tree)
- `.github/workflows/{publish,release,ghcr}.yml`
- `.gitmodules` — only `pynets`
- Incremental TA: `docs/perf_round9/AGENT_02_ta_incremental.md` + CHANGELOG 0.3.10 (`_obv/_wad/_cmf/_klinger_inc_update`; residual `nvi`/`pvi`)

---

## Pages edited

| Path | Why |
| --- | --- |
| `docs/pyne/reference/ecosystem.mdx` | Drop `/home/jango/Git/...` machine paths; 0.3.10 + PyneTS 0.2.0 vs submodule 0.1.0 |
| `docs/pyne/reference/compatibility.mdx` | Dist name 0.3.10; explicit no TV platform-identity |
| `docs/pyne/reference/implementation-status.mdx` | Submodule 0.1.0 vs standalone 0.2.0 |
| `docs/pyne/reference/missing-features.mdx` | H1 largely done; T2 0.3.10 volume; `pynescript.runtime` not `backend.runtime` |
| `docs/pyne/reference/roadmap.mdx` | H1 ✅ largely done; no in-tree `pine-worker/` internals; sister checkout example |
| `docs/pyne/contributing.mdx` | Runtime SoT `src/pynescript/runtime/host.py`; release steps; submodule lag |
| `docs/pyne/pynets/index.mdx` | Note: submodule 0.1.0 interpret-only vs npm 0.2.0 |
| `docs/pyne/pynets/install.mdx` | Same pin/lag |
| `docs/pyne/pynets/cli.mdx` | `--mode` is 0.2.0 only |
| `docs/pyne/pynets/runtime.mdx` | stream / compile / libraries are 0.2.0 |
| `docs/pyne/pynets/compile.mdx` | compile dir absent on submodule pin |
| `docs/pyne/pynets/parity.mdx` | compile tests live on 0.2.0 |
| `docs/pyne/agent/index.mdx` | Explicit not-in-repo; drop extra trademark (product `index.mdx` only) |
| `README.md` | CLI `pyne`; 0.3.10 volume inc + `PYNE_SERIES_RING` off; clone does not claim `pyne-lsp` submodule |
| `CONTRIBUTING.md` | `hoox-sh/axis`; make-first workflow; release = publish + release + GHCR; pyne-lsp in-tree |
| `COMPATIBILITY.md` | Rewrote stale 3-impl “100% identical” matrix; no TV identity; 0.3.10 corpus + residuals |
| `docs/missing_features.md` | T2 volume; pine-worker not colocated; dates 2026-08-16 |
| `docs/ROADMAP.md` | Last-updated line (IDs already correct) |
| `docs/pinescript_implementation_status.md` | Banner: SoT checklist, not TV parity; pine-worker sister |

### Read, no edit (already honest)
- `docs/pyne/reference/pine-v6-surface.mdx` (2026-07-25 inventory snapshot)
- `docs/pyne/reference/numerical-validation.mdx`
- `docs/pyne/pine-worker/{index,converter,testing}.mdx`

---

## Pages added / deleted

- **Added:** none
- **Deleted:** none

**Recommend delete (parent only — not done):** none of the exclusive MDX files. `pine-worker/converter.mdx` and `testing.mdx` are thin legacy satellites but they correctly redirect to PyneTS; keep. `pynets/compile.mdx` matches standalone 0.2.0 — keep, now labeled. Do **not** delete `COMPATIBILITY.md` (rewritten). Optional later: slim or retitle `docs/compatibility_guarantee.md` (stale Sphinx twin; still says PyPI `pyne`).

---

## Proposed `docs.json` nav

No add/remove. Current Reference tab is correct:

```text
Status & Parity
  reference/ecosystem
  reference/compatibility
  reference/implementation-status
  reference/missing-features
  reference/pine-v6-surface
  reference/numerical-validation
  reference/roadmap
  contributing
PyneTS
  pynets/index
  pynets/install
  pynets/cli
  pynets/runtime
  pynets/compile      ← keep (standalone 0.2.0)
  pynets/parity
pine-worker (legacy)
  pine-worker/index
  pine-worker/converter
  pine-worker/testing
Agent (write)
  agent/index
```

Optional parent polish (not required): add a one-line sidebar hint that pine-worker is a sister, or nest `contributing` under a “Contribute” group. No new pages.

---

## Remaining holes

1. **`docs/compatibility_guarantee.md`** still says PyPI `pyne` and 2026-08-03 metrics (138+ scripts). Not exclusive; parent or a follow-up should retitle to `hoox-pyne` 0.3.10 + corpus snapshot.
2. **Submodule vs published PyneTS** — this checkout pins `@hoox/pynets` 0.1.0. Docs now disclose the lag; bumping the submodule pointer is a **code** change, not a docs one.
3. **Sister `pine-worker` README** (`/home/jango/Git/pine-worker`) still describes itself as a colocated extra tool (`../src/pynescript/...`). Out of this repo.
4. **`docs/pyne/devops/index.mdx`** (Agent 05) still says “colocated edge workers”.
5. **Historical Phase 8 “100% complete / 997 tests”** tail of `docs/pinescript_implementation_status.md` left in place (banner now warns). Full rewrite would be a separate pass.
6. **Inventory counts** (640 callables, 2026-07-25) not re-run; `pine-v6-surface.mdx` still dated to that snapshot.
7. **AXIS repo URL split** — product README uses `hoox-sh/axis`; Makefile help still prints `jango-blockchained/axis`. CONTRIBUTING now prefers `hoox-sh/axis`.

---

## Code checked (fact table)

| Claim | Fact |
| --- | --- |
| Dist / version | `hoox-pyne` 0.3.10, import `pynescript`, CLIs `pyne` / `pyne-lsp` |
| Runtime SoT | `src/pynescript/runtime/`; `backend.runtime` re-exports host |
| T2 0.3.10 | Incremental `obv`/`wad`/`wvad`/`cmf`/`klinger`; residual `nvi`/`pvi` |
| H1 | Package SoT + backend shims + pyne-worker thin wrap; residual worker extras |
| H2 / T1 / F2 / L2 / C1 | Landed (ROADMAP) |
| pine-worker | Not in tree (removed 0.3.7); sister `hoox-sh/pine-worker` |
| pyne-agent-worker | Sister `hoox-sh/pyne-agent-worker` 0.1.2; not in this repo |
| PyneTS public API | `parse` / `unparse` / `Runtime.run`; Python oracle |
| PyneTS versions | Submodule `@hoox/pynets` 0.1.0; standalone `@hoox-sh/pynets` 0.2.0 |
| Release | `v*` → `publish.yml` (PyPI) + `release.yml` (Nuitka/VSIX) + `ghcr.yml` |
| Compatibility | Corpus 99.96% parse / 100% interpret excl. EXPECTED; **not** TV platform identity |
