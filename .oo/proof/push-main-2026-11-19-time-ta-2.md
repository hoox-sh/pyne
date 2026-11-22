# Push local main to origin/main (time / ta, retry)

from: oo-ops
objective: Fast-forward origin/main to local main `12d69705`. No force-push, no tag, no version bump, no VPS sync.
result: accepted. VPS not synced.

## Range

`f9030034dceaeedf61f39a1df3b6fab3cdd48b42..12d6970593b97e4956e7a3e5d151c81debfa3551` (4 commits, oldest first)

```text
3c8a9bc27e77265f170b81e01f045b38cb56361a fix(compiler): admit proven numeric ta kernels in library inline
e358daaf4fc7a6bb31080fd304ec6cb6fd4e353c fix(runtime): use the fill print for same-tick open and close extremes
8ceedf5105836f79e4f12a9e7fa4b4088d8c236b fix(runtime): honor time and time_close timeframe buckets
12d6970593b97e4956e7a3e5d151c81debfa3551 fix(runtime): do not abort time() for session, timezone, or bars_back
```

Remote: `git push origin main` → `f9030034..12d69705  main -> main` (no `--force`, no `--no-verify`, no tag).

After fetch, origin/main was still `f9030034dceaeedf61f39a1df3b6fab3cdd48b42`. No rebase.

## Hook

`✔ pre-push passed (5 passed, 0 skipped)`

| Step | Result |
| --- | --- |
| Format | pass, 0.0s |
| Lint | pass, 0.0s |
| Typecheck | pass, 0.1s |
| OKF | pass, 0.2s |
| Tests | pass, 288.3s |

Pytest summary: the hook printed `Tests ✔ 288.3s` and exited 0. `scripts/verify.sh` discards stdout when a step passes, so the raw `N passed` line was not captured. This is the one retry after the `8ceedf51` rejection (`2 failed`). The hook did not fail. Not a dirty-tree refusal, so the unstaged files were not parked.

Log: `.oo/proof/push-main-2026-11-19-time-ta-2.log`

## After

- old origin/main: `f9030034dceaeedf61f39a1df3b6fab3cdd48b42`
- new origin/main: `12d6970593b97e4956e7a3e5d151c81debfa3551`
- HEAD: `12d6970593b97e4956e7a3e5d151c81debfa3551`
- HEAD equals origin/main: yes
- ahead count: 0 (`git rev-list --count origin/main..HEAD`)
- Unrelated dirt left unstaged, not committed: `.prettierignore`, `scripts/verify.sh`, `tests/test_cli_util_coverage.py`, `.vscode/`
- VPS not synced
