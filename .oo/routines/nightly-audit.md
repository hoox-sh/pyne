# Nightly audit

- **Owner:** Deploy (`oo-spec-2`)
- **Schedule:** daily at 03:00
- **Input:** the repository and the last audit state file
- **Output:** small PRs with proof, never merged
- **Check:** the verify command passes and the PR links its evidence
- **Approval:** ask before merging, deploying, or deleting anything

## Prompt

```text
Run daily at 03:00 or when the trigger fires.

Audit the codebase: dead code, load time, bundle size, failing checks. Open small PRs with proof. Never merge.

Input: the repository and the last audit state file
Output: small PRs with proof, never merged

If nothing changed since the last run, say nothing.
If something needs me, send one message:
what happened, what you did, what you need from me.
If a step fails, say which step and stop.
Ask me before anything outside the approval list.
```
