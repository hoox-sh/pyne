# Library-body `ta.*` allowlist — first slice (`ta.sma`, `ta.ema`)

**Date:** 2026-11-16
**Card:** `pyne-widen-library-body-allowlis-238ff0b2`
**Status:** Working — first slice, no commit/push

## Why

The inlined-library body guard allowed params/locals/literals, `math.*`,
`str.*`, and a small bare-call set. Any `ta.*` call was rejected as
`unsupported namespace ta`, even though the script-level `ta.*` emitters and
UDF series/state plumbing already exist.

**Choice:** allow `ta.sma` and `ta.ema` first. They are stateful moving-average
kernels the existing UDF series/state plumbing can carry (`__smaN_st` /
`__emaN_st` plus chart context); they are the smallest useful pair for library
indicators. Every other `ta.*` function stays fail-closed, so an unsupported
kernel cannot silently become `na`.

## Change

- `compiler.py` `_library_function_unsupported`: audited `allowed_ta =
  {"sma", "ema"}`; `ta.<other>` returns `calls unsupported ta function
  ta.<name>`. `math.*` / `str.*` behavior unchanged.
- `compiler.py` mapped library call site: use `_emit_user_func_call` instead of
  a direct `mapped(args)` call, so inlined library calls receive the same
  default fill, ta/series state, and chart-context plumbing as script-level
  calls. This is required for `ta.sma`/`ta.ema` inside a library body.
- `docs/missing_features.md`: document the allowlist contract.
- `tests/test_compiler_library_inline.py`: direct `lib.ind(close)` regressions
  for `ta.sma`, `ta.ema`, and fail-closed `ta.rsi`.

## Acceptance criteria

1. `lib.ind(close)` using `ta.sma(src, 3)` inside the library compiles and
   matches interpret (including warm-up na).
2. Same for `ta.ema(src, 3)`.
3. `ta.rsi` stays fail-closed with
   `unsupported ta function ta.rsi` (compile error, no silent na).
4. Missing required library args preserve compile's short-call `TypeError`
   (including a required arg before a default), matching pristine HEAD 380b8527;
   the pre-existing interpret `na` behavior is locked and documented.
5. Existing library defaults, cross-library, and method tests stay green.
6. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-library-ta-allowlist-2026-11-16.failing-before.txt` — 2 failed
(SMA/EMA) with `TypeError: __lib_lib_ind() missing 12 required positional
arguments` (ta state + chart context); `ta.rsi` already failed closed. Before
the allowlist change the same test failed at the guard with
`unsupported namespace ta`; the artifact captures the post-guard plumbing
failure that the full slice fixes.

`.oo/plans/pyne-library-ta-allowlist-2026-11-16.failing-before-missing-args.txt`
— 2 failed: the broad `_emit_user_func_call` switch silently padded missing
required library args with `np.nan` (no error, all-na) for both
`helper(a, k)` and `helper(a, b, k=2.0)`. Pristine HEAD 380b8527 raised the
short-call `TypeError`; the strict pre-check restores it.

## Results

- New library-ta + missing-arg tests — **5 passed**.
- Library suite (inline, fail-closed, export import, export method) — **69
  passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **507 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped** (single final run after the
  missing-arg fix).

## Proof

Card `pyne-widen-library-body-allowlis-238ff0b2` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named library-ta + missing-arg tests | `970cf329-da37-4fd2-9d75-6a9c3c4d6f11` | 5 tests PASSED (sma, ema, rsi closed, missing required, required-before-default) |
| named token | `26d742d5-b21e-458a-ad72-1b1e49cfb627` | `LIB_TA_OK sma=1 ema=1 unknown=fail_closed missing=typeerror required_before_default=typeerror` |
| targeted compiler/library | `aab2dc0f-9e6f-4785-bff4-fd55d4c0ccd7` | 507 passed |
| verify (no re-run) | `627734ca-a312-44f3-b941-796ea12fec3a` | recorded exit 0 |
| verify transcript | `4bbc901c-7db7-4a75-9b02-afe68974c64b` | `.oo/proof/verify-library-ta-2026-11-16.txt` |

SHA-256: compiler `2f6ef8bee46943bac7ec420ae97d8e5e896dd6fb1808d1596b70b6c021ca7924`,
tests `5b38da7668c065a0561a14efa3eb29bfa29b3fb2ab097819aff6840d448d776b`,
docs `ceca369121290ec27101b3e0ec2f1650d31debe692f9f983089ef2975dd8a523`,
patch `069fa6e1796d6906f75a64f55adee804fd32fb01f3f3a75e23a523275bde1ef0`.

## Files

- `src/pynescript/compiler/compiler.py`
- `tests/test_compiler_library_inline.py`
- `docs/missing_features.md`
- `.oo/plans/pyne-library-ta-allowlist-2026-11-16.{md,failing-before.txt,failing-before-missing-args.txt,proof.py}`

## Residual

- Only `ta.sma` / `ta.ema` are allowed in inlined library bodies; all other
  `ta.*` remain fail-closed. Wider allowlisting needs per-kernel state/context
  audits.
- Keyword arguments for inlined library calls remain fail-closed, unchanged.
- Interpret returns `na` for a missing required library argument (pre-existing,
  unchanged); compile preserves the short-call `TypeError`. This divergence is
  locked by the new tests and documented; a separate card can decide whether
  interpret should become strict.
- No commit/push for this slice.
