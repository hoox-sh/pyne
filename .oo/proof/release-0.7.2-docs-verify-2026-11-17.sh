set -u
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }

echo "--- [1] changelog structure ---"
chk "line 1 [Unreleased]" "[ \"\$(sed -n '1p' CHANGELOG.md)\" = '## [Unreleased]' ]"
chk "Unreleased empty, line 3 is 0.7.2" "[ \"\$(sed -n '3p' CHANGELOG.md)\" = '## [0.7.2] — 2026-11-17' ]"
chk "0.7.2 unique" "[ \"\$(grep -c '^## \[0.7.2\] — 2026-11-17\$' CHANGELOG.md)\" = 1 ]"
chk "Added/Changed/Fixed all present" "[ \"\$(sed -n '/^## \[0.7.2\]/,/^## \[0.7.1\]/p' CHANGELOG.md | grep -cE '^### (Added|Changed|Fixed)')\" = 3 ]"

echo "--- [2] both hover entries present ---"
chk "short-card bullet once" "[ \"\$(grep -c 'LSP cards stay short where the widget is narrow' CHANGELOG.md)\" = 1 ]"
chk "short-card bullet in 0.7.2 Changed" "sed -n '/^### Changed/,/^### Fixed/p' CHANGELOG.md | grep -q 'LSP cards stay short'"
chk "short-card bullet names f8ad6ff0" "grep -q 'LSP cards stay short.*Ships as \`f8ad6ff0\`' CHANGELOG.md"
chk "typed-hover bullet once" "[ \"\$(grep -c 'Hover cards show exact parameter and return types' CHANGELOG.md)\" = 1 ]"
chk "typed-hover bullet in 0.7.2 Added" "sed -n '/^### Added/,/^### Changed/p' CHANGELOG.md | grep -q 'Hover cards show exact parameter and return types'"
chk "no hover bullet left under Unreleased" "! sed -n '1,/^## \[0.7.2\]/p' CHANGELOG.md | grep -q 'LSP cards stay short\|Hover cards show exact'"

echo "--- [3] commits backing both hover entries ---"
chk "f8ad6ff0 ancestor of origin/main" "git merge-base --is-ancestor f8ad6ff0 origin/main"
chk "f8ad6ff0 after v0.7.1" "git merge-base --is-ancestor v0.7.1 f8ad6ff0 && ! git merge-base --is-ancestor f8ad6ff0 v0.7.1"
chk "typed-hover commit 1baba894 exists" "git cat-file -e 1baba894^{commit}"
chk "1baba894 subject matches bullet" "git log -1 --format=%s 1baba894 | grep -q 'show exact parameter and return types in hover cards'"
chk "1baba894 typed param rows" "git show 1baba894 | grep -q '^+def _typed_rows'"
chk "1baba894 return-type arrow" "git show 1baba894 | grep -q '→ {return_type}'"
chk "1baba894 annotations" "git show 1baba894 | grep -q 'strategy_alert_message'"
chk "1baba894 pins tests" "git show --name-only --format= 1baba894 | grep -q 'tests/test_lsp_features.py'"

echo "--- [4] rest of 0.7.2 backed ---"
chk "key CLI 10763591" "git cat-file -e 10763591^{commit}"
chk "key CLI test" "git cat-file -e 10763591:tests/test_cli_key.py"
chk "plotshape 915b65ba" "git cat-file -e 915b65ba^{commit}"
chk "plotshape meta 62" "git show 915b65ba -- src/pynescript/compiler/engine.py | grep -q '^+_DISK_META_VERSION = 62'"
chk "ruff gate d912b88c" "git show d912b88c -- scripts/verify.sh | grep -q \"^+FORMAT_CMD='ruff format --check\""
chk "ruff pin a4ac409d" "git show a4ac409d -- pyproject.toml | grep -q 'ruff==0.15.20'"
chk "corpus skip 01a11897" "git show 01a11897 --stat | grep -q 'tests/test_set06'"
chk "version align 494fe98d" "git cat-file -e 494fe98d^{commit}"

echo "--- [5] version pins ---"
chk "README 0.7.2" "grep -q '^\*\*0.7.2\*\* · PyPI' README.md"
chk "ROADMAP 0.7.2" "grep -q 'hoox-pyne\` \*\*0.7.2\*\*' docs/ROADMAP.md"
chk "missing_features 0.7.2" "grep -q 'hoox-pyne\` \*\*0.7.2\*\*' docs/missing_features.md"
chk "impl_status 0.7.2" "grep -q 'hoox-pyne\` \*\*0.7.2\*\*' docs/pinescript_implementation_status.md"
chk "no live 0.7.1 in those files" "! grep -q '0\.7\.1' README.md docs/ROADMAP.md docs/missing_features.md docs/pinescript_implementation_status.md"
chk "historical 0.7.1 intact" "grep -q '^## \[0.7.1\] — 2026-11-15\$' CHANGELOG.md"
chk "historical 0.7.0 intact" "grep -q '^## \[0.7.0\] — 2026-11-13\$' CHANGELOG.md"
chk "__about__ untouched" "git diff --quiet HEAD -- src/pynescript/__about__.py"
chk "VERSION untouched" "git diff --quiet HEAD -- VERSION"

echo "--- [6] docs ---"
chk "pyne key section" "grep -q '^### \`pyne key\`\$' docs/pyne/enduser/reference/cli-commands.mdx"
chk "index row" "grep -q '^| \`key\`' docs/pyne/enduser/reference/cli-commands.mdx"
chk "guide mermaid node" "grep -q 'C --> K\[key\]' docs/pyne/enduser/guides/cli.mdx"
chk "docs.json unchanged" "git diff --quiet HEAD -- docs/pyne/docs.json"
chk "no untracked docs page" "[ -z \"\$(git status --porcelain docs/pyne | grep '^??')\" ]"

echo "--- [7] scope ---"
chk "exactly 7 files changed by me" "[ \"\$(git diff --name-only -- CHANGELOG.md README.md docs/ | wc -l)\" = 7 ]"
chk "only pre-existing dirty code file left" "[ \"\$(git diff --name-only -- src/ tests/ backend/ VERSION)\" = 'tests/test_cli_util_coverage.py' ]"
chk "that file predates my edits" "[ tests/test_cli_util_coverage.py -ot CHANGELOG.md ]"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
