#!/usr/bin/env bash
# Re-check for .oo/proof/env-hygiene-gate-2026-11-17.md
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
fail=0
ok() { printf 'PASS %s\n' "$*"; }
no() { printf 'FAIL %s\n' "$*"; fail=1; }

git cat-file -e '22c9d380^{commit}' 2>/dev/null && ok "commit 22c9d380 exists" || no "commit 22c9d380 missing"
git merge-base --is-ancestor 22c9d380 origin/main && ok "22c9d380 on origin/main" || no "22c9d380 not on origin/main"
git merge-base --is-ancestor 9ce57472 origin/main && ok "9ce57472 on origin/main" || no "9ce57472 not on origin/main"

want=".githooks/pre-commit .githooks/pre-push CONTRIBUTING.md okf/playbooks/read-this-first.md scripts/install-hooks.sh scripts/okf/cli.ts"
got="$(git show --name-only --format= 22c9d380 | sort | tr '\n' ' ' | sed 's/ $//')"
[ "$got" = "$(printf '%s\n' $want | sort | tr '\n' ' ' | sed 's/ $//')" ] && ok "commit 1 file set" || no "commit 1 file set: $got"
[ "$(git show --name-only --format= 9ce57472 | tr -d '\n')" = ".gitignore" ] && ok "commit 2 = .gitignore only" || no "commit 2 file set"

for f in CONTRIBUTING.md okf/playbooks/read-this-first.md scripts/okf/cli.ts; do
  grep -q 'OO_SKIP=okf' "$f" && ok "$f names OO_SKIP=okf" || no "$f missing OO_SKIP=okf"
  grep -q 'OKF_SKIP' "$f" && no "$f still mentions OKF_SKIP" || ok "$f free of OKF_SKIP"
done

git check-ignore -q .env && ok ".env ignored" || no ".env not ignored"
git check-ignore -q .env.bak-network && ok ".env.bak-network ignored" || no ".env.bak-network not ignored"
git check-ignore -q .env.local && ok ".env.local ignored" || no ".env.local not ignored"
git check-ignore -q .env.example && no ".env.example is ignored" || ok ".env.example not ignored"

[ "$(stat -c %a .env)" = "600" ] && ok ".env mode 600" || no ".env mode $(stat -c %a .env)"
[ -f .env.bak-network ] && ok ".env.bak-network present (not deleted)" || no ".env.bak-network missing"
git ls-files --error-unmatch .env.bak-network >/dev/null 2>&1 && no ".env.bak-network is tracked" || ok ".env.bak-network untracked"

[ "$fail" -eq 0 ] && echo "ALL PASS" || echo "FAILURES PRESENT"
exit "$fail"
