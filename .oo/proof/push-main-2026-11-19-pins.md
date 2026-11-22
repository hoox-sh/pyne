# Push local main to origin/main (scope pins)

from: oo-ops
objective: Fast-forward origin/main to local main `ffbfa5af`. No force-push, no tag, no version bump, no VPS sync.
result: accepted. VPS not synced.

## Range

`12d6970593b97e4956e7a3e5d151c81debfa3551..ffbfa5afdd5b819d338de3dd624fc1e8452bbd22` (2 commits, oldest first)

```text
c0a9b84a3d0b6b6d29f3adb879410438212aa864 test: pin square-bracket indent flexibility
ffbfa5afdd5b819d338de3dd624fc1e8452bbd22 test: pin that Pine scripts may exceed 550 local scopes
```

Remote: `git push origin main` → `12d69705..ffbfa5af  main -> main` (no `--force`, no `--no-verify`, no tag).

After fetch, origin/main was still `12d6970593b97e4956e7a3e5d151c81debfa3551`. No rebase.

## Hook

`✔ pre-push passed (5 passed, 0 skipped)`

| Step | Result |
| --- | --- |
| Format | pass, 0.0s |
| Lint | pass, 0.0s |
| Typecheck | pass, 0.2s |
| OKF | pass, 0.2s |
| Tests | pass, 370.4s |

Pytest summary: not printed. The hook printed `Tests ✔ 370.4s` and exited 0. `scripts/verify.sh` discards stdout when a step passes, so no raw `N passed` line was captured. The hook did not fail. Not a dirty-tree refusal, so the unstaged files were not parked.

## After

- old origin/main: `12d6970593b97e4956e7a3e5d151c81debfa3551`
- new origin/main: `ffbfa5afdd5b819d338de3dd624fc1e8452bbd22`
- HEAD: `ffbfa5afdd5b819d338de3dd624fc1e8452bbd22`
- HEAD equals origin/main: yes
- ahead count: 0 (`git rev-list --left-right --count origin/main...HEAD` → `0	0`)
- Unrelated dirt left unstaged, not committed: `.prettierignore`, `scripts/verify.sh`, `tests/test_cli_util_coverage.py`, `.vscode/`
- VPS not synced
