# Agent 08 — Close Partial PyneTS 0.1.0 pin

**Path:** **A** (submodule bump)  
**Did not commit.** Did not implement a JS compile from scratch.

---

## Verdict

**Path A.** Annotated tag `v0.2.0` exists on `origin`, matches `origin/main` and published npm `@hoox-sh/pynets@0.2.0`, and is safe. This checkout’s `pynets/` gitlink is now that tag. The 0.1.0-vs-0.2.0 pin-lag hole is closed. PyneTS stays **Partial** because Python Runtime is the oracle — not because the vendor snapshot lags.

---

## Version evidence

| Fact | Value |
| --- | --- |
| Previous gitlink | `ce7b20387161f1a8978956a4e058561d54b809ed` (`heads/main` at initial import; **no tags**) |
| Previous `package.json` | `@hoox/pynets` **0.1.0**, private, interpret-only, no `src/runtime/compile/` |
| `git -C pynets fetch --tags origin` | fetched `v0.1.0`, `v0.2.0`; `main` `ce7b203` → `68b15de` |
| Tag `v0.2.0` | annotated, 2026-08-16, message `v0.2.0 @hoox-sh/pynets` |
| Tag peel | `68b15def96ddd0e31c12241a4c7c218447f92cb7` (`chore: release 0.2.0`) |
| `origin/main` | same commit as `v0.2.0` |
| New `package.json` | `@hoox-sh/pynets` **0.2.0**; `src/runtime/compile/` present |
| npm | `@hoox-sh/pynets` **0.2.0** published 2026-08-15T22:34:29Z |
| License | still AGPL-3.0-or-later |
| Distance | 21 commits `ce7b203..v0.2.0` (interpret wave + JS compile + publish) |

Safety: official annotated release by the same author, license unchanged, interpret kept, compile is additive JS emit (not Numba). No 0.2.0 tag would have forced Path B.

---

## Submodule

```
pynets  68b15def96ddd0e31c12241a4c7c218447f92cb7  (v0.2.0)
```

Staged gitlink only (`git add pynets`). Not committed.

---

## Verify

```
cd pynets && bun install && bun test
820 pass, 0 fail, 3638 expect() calls, 78 files
```

Bun 1.3.14. First-party PYNE fixtures resolved from the parent tree.

---

## Docs (pin rows only)

| Path | Change |
| --- | --- |
| `COMPATIBILITY.md` | Implementations: pin **v0.2.0** interpret + JS compile. Partial row is “sister TS / Python oracle”, not 0.1.0-vs-npm lag. |
| `docs/pyne/reference/compatibility.mdx` | Sister implementations: submodule pin **v0.2.0** = npm. Mermaid `PyneTS pin lag` → `PyneTS vs Python`. |
| `docs/pyne/reference/implementation-status.mdx` | PyneTS line: npm + submodule both **0.2.0**. |
| `docs/pyne/pynets/{index,install,cli,runtime,compile,parity}.mdx` | Drop 0.1.0 interpret-only / lag notes. Pin is v0.2.0. Python remains oracle. |

Out of ownership (still says submodule 0.1.0 if unread): `docs/pyne/reference/ecosystem.mdx`, `docs/pyne/contributing.mdx`.

---

## Not done (by design)

- No JS compile authored in this tree — vendored from hoox-sh/pynets `v0.2.0`.
- No Python TA / Flask / trail / plot-key edits.
- Did not commit.
