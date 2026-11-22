# Proof — gate hygiene + env protection (2026-11-17)

Owner: oo-spec-2 · Cards: `commit-githooks-verify-shims-com-047f5604`,
`env-bak-network-is-untracked-and-34fcf62e`, `working-tree-githooks-pre-commit-ea92a6ce`

Baseline at start: `origin/main` = `1baba894`, ahead 0. During the run a concurrent
session landed and pushed `88334c64..8e1f721a` (release 0.7.2 + sdist guard); none of
those commits touch these paths. Final base `8e1f721a`; `1baba894` is an ancestor.

## Commit 1 — `22c9d380` chore(gate): commit verify hook shims and rename OKF_SKIP to OO_SKIP

Files (6 M): `.githooks/pre-commit`, `.githooks/pre-push`, `scripts/install-hooks.sh`,
`CONTRIBUTING.md`, `okf/playbooks/read-this-first.md`, `scripts/okf/cli.ts`.

Hook, no `--no-verify`:

```text
✔ pre-commit passed (4 passed, 0 skipped)
[main 22c9d380] chore(gate): commit verify hook shims and rename OKF_SKIP to OO_SKIP
 6 files changed, 19 insertions(+), 58 deletions(-)
```

Env var: `grep -rn OKF_SKIP` over tracked text (excluding generated exports) → none.
`scripts/okf/cli.ts` reads **no** env var (`grep -n process.env scripts/okf/` → empty);
line 77 was usage text only. `scripts/verify.sh:76` implements `SKIP_LIST=",${OO_SKIP:-},"`
and the step key at line 189 is `run_step okf "OKF" "$OKF_CMD"` — so `OO_SKIP=okf` is
the working spelling. Code and docs now agree on the variable name.

`AGENTS.md:20` renamed locally but **not committed**: `33ca0cc8` ("stop tracking
AGENTS.md … remove it from the public tree") + `.gitignore:140` keep it untracked.
Force-adding it would reverse that decision on a public remote; flagged for the
operator instead of doing it silently.

## Commit 2 — `9ce57472` chore(security): ignore .env backups and tighten .env permissions

Files (1 M): `.gitignore`. `.gitignore` diff adds

```text
# Env files and backups (never commit secrets)
.env*
!.env.example
```

and also carries the pending `.oo/` ignore swap (`.openorchestrate/state.db*`,
`.openorchestrate/logs/` → `.oo/`), disclosed in the commit body, not split.

```text
✔ pre-commit passed (4 passed, 0 skipped)
[main 9ce57472] chore(security): ignore .env backups and tighten .env permissions
 1 file changed, 4 insertions(+), 3 deletions(-)
```

## Push — through the real pre-push hook

```text
✔ pre-push passed (5 passed, 0 skipped)
   8e1f721a..9ce57472  main -> main
```

`git rev-parse --short origin/main` → `9ce57472`; `git rev-list --count origin/main..HEAD` → `0`.

## Env verification (post-push)

```text
$ stat -c '%a %n' .env .env.bak-network .env.example
600 .env
600 .env.bak-network
644 .env.example

$ git check-ignore -v .env.bak-network .env .env.local
.gitignore:42:.env*	.env.bak-network
.gitignore:42:.env*	.env
.gitignore:155:.env.local	.env.local

$ git check-ignore -q .env.example; echo $?
1        # not ignored — correct
```

`.env.bak-network`: still present (4323 B, mode 600), untracked, now ignored. **Not
deleted and not moved** — deletion needs operator approval.

## Generated exports left alone

`docs/exports/axis-llm.txt` and `.cache/docs-exports/axis-devops.html` still contain
one `OKF_SKIP` mention each; neither is in either commit (`git diff --name-only
1baba894..HEAD -- <both>` → empty). They are regenerated artifacts and catch up on the
next export run.

## Checklist

```text
[1] PASS artifact exists: 22c9d380 + 9ce57472 on origin/main (HEAD == origin/main)
[2] PASS verified: pre-commit 4/4, pre-push 5/5 (pytest 347.9s), push 8e1f721a..9ce57472
[3] PASS nothing outside deploy touched: 7 files total, all gate/env hygiene;
         generated exports and AGENTS.md untouched
[4] PASS .env 600; .env.bak-network present, 600, ignored, untracked
[5] PASS .env.example not ignored
```

Re-check: `bash .oo/proof/env-hygiene-gate-2026-11-17.sh`
