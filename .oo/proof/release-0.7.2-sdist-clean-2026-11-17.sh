#!/usr/bin/env bash
# Proof for the 0.7.2 sdist secret-leak fix (deploy seat, 2026-11-17).
# Read-only. Asserts the exclude list, the guard's positive AND negative
# behaviour, the rebuilt artifact sizes, and the shipped commit.
#
#   bash .oo/proof/release-0.7.2-sdist-clean-2026-11-17.sh
#
set -u
cd "$(dirname "$0")/../.." || exit 2

pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }

SD=$(ls dist/hoox_pyne-0.7.2.tar.gz 2>/dev/null | head -1)
WHL=$(ls dist/hoox_pyne-0.7.2-*.whl 2>/dev/null | head -1)
PY=.venv/bin/python

echo "--- [1] pyproject sdist excludes cover every required path ---"
for pat in '/.env' '/.env.*' '/scripts/build/.metadata.key' '/node_modules' '/cf' '/tests/data' \
           '/.coverage' '/.coverage.*' '/dist' '/.venv' '/.git' '/.oo' '/.openorchestrate' \
           '/.pytest_cache' '/.ruff_cache' '/.numba_cache' '/data' '/.papers' '/.reddit' \
           '/okf' '/.cache' '/.playwright' '/.mypy_cache'; do
  chk "exclude $pat" "grep -qF '\"$pat\",' pyproject.toml"
done
chk "pre-existing excludes kept (/.github)" "grep -qF '\"/.github\",' pyproject.toml"
chk "pre-existing excludes kept (/packages/backend/dist)" "grep -qF '\"/packages/backend/dist\",' pyproject.toml"

echo "--- [2] wheel config untouched ---"
chk "wheel packages is still src/pynescript only" "$PY -c \"
import tomllib,sys
d=tomllib.load(open('pyproject.toml','rb'))
w=d['tool']['hatch']['build']['targets']['wheel']
sys.exit(0 if w=={'packages':['src/pynescript']} else 1)\""

echo "--- [3] guard passes on the real sdist ---"
chk "sdist exists"                "[ -n '$SD' ] && [ -f '$SD' ]"
chk "guard exits 0"               "$PY scripts/build/assert_sdist_clean.py '$SD'"

echo "--- [4] guard detects a dirty archive (negative test) ---"
TMPD=$(mktemp -d)
mkdir -p "$TMPD/pkg"
printf 'x' > "$TMPD/pkg/.env"
printf 'x' > "$TMPD/pkg/server.key"
printf 'x' > "$TMPD/pkg/cert.pem"
printf 'x' > "$TMPD/pkg/id_rsa"
printf 'x' > "$TMPD/pkg/.coverage"
printf 'ok' > "$TMPD/pkg/pyproject.toml"
tar -czf "$TMPD/dirty.tar.gz" -C "$TMPD" pkg
chk "guard exits 1 on dirty archive" "! $PY scripts/build/assert_sdist_clean.py '$TMPD/dirty.tar.gz'"
chk "guard names all 5 planted secrets" "[ \"\$($PY scripts/build/assert_sdist_clean.py '$TMPD/dirty.tar.gz' 2>&1 | grep -c '^FAIL .*secret-bearing')\" = 5 ]"
chk "guard exits 1 on missing path"  "! $PY scripts/build/assert_sdist_clean.py '$TMPD/nope.tar.gz'"
rm -rf "$TMPD"

echo "--- [5] rebuilt sdist is clean and under the limit ---"
chk "sdist has NO .env* members"   "! tar -tzf '$SD' | grep -qE '(^|/)\.env'"
chk "sdist has NO .metadata.key"   "! tar -tzf '$SD' | grep -q '\.metadata\.key'"
chk "sdist has NO *.key/*.pem/id_rsa" "! tar -tzf '$SD' | grep -qE '\.(key|pem)\$|(^|/)id_rsa\$'"
chk "sdist has NO .coverage*"      "! tar -tzf '$SD' | grep -qE '(^|/)\.coverage'"
chk "sdist has NO node_modules"    "! tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/node_modules/'"
chk "sdist has NO cf/"             "! tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/cf/'"
chk "sdist has NO tests/data"      "! tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/tests/data/'"
chk "sdist has NO .venv/.git/dist" "! tar -tzf '$SD' | grep -qE '^hoox_pyne-0.7.2/(\.venv|\.git|dist)/'"
chk "sdist under 100 MB"           "[ \"\$(stat -c %s '$SD')\" -lt 104857600 ]"

echo "--- [6] sdist still carries a buildable source tree ---"
for f in pyproject.toml README.md LICENSE VERSION CHANGELOG.md; do
  chk "sdist has $f" "tar -tzf '$SD' | grep -qx 'hoox_pyne-0.7.2/$f'"
done
chk "sdist has src/pynescript/"    "tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/src/pynescript/'"
chk "sdist has src/pynescript/__about__.py" "tar -tzf '$SD' | grep -qx 'hoox_pyne-0.7.2/src/pynescript/__about__.py'"

echo "--- [7] wheel unchanged and clean ---"
chk "wheel exists"                 "[ -n '$WHL' ] && [ -f '$WHL' ]"
chk "wheel version 0.7.2"          "$PY -c \"
import zipfile,glob,sys
z=zipfile.ZipFile(glob.glob('dist/*.whl')[0])
m=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')][0]
sys.exit(0 if 'Version: 0.7.2' in z.read(m).decode().splitlines() else 1)\""
chk "wheel has pynescript/"        "unzip -Z1 '$WHL' | grep -q '^pynescript/'"
chk "wheel has NO backend/"        "! unzip -Z1 '$WHL' | grep -q '^backend/'"
chk "wheel has NO secrets"         "! unzip -Z1 '$WHL' | grep -qE '(^|/)\.env|\.(key|pem)\$|(^|/)\.coverage'"

echo "--- [8] shipped commit shape ---"
chk "HEAD subject is the sdist fix" "[ \"\$(git log -1 --format=%s HEAD)\" = 'fix(build): exclude secrets and heavy paths from the sdist, and assert it before publish' ]"
chk "HEAD changes exactly 2 files"  "[ \"\$(git diff-tree --no-commit-id --name-only -r HEAD | grep -c .)\" = 2 ]"
chk "HEAD touches pyproject.toml"   "git diff-tree --no-commit-id --name-only -r HEAD | grep -qx 'pyproject.toml'"
chk "HEAD touches the guard"        "git diff-tree --no-commit-id --name-only -r HEAD | grep -qx 'scripts/build/assert_sdist_clean.py'"
chk "HEAD is pushed"                "[ \"\$(git rev-parse origin/main)\" = \"\$(git rev-parse HEAD)\" ]"
chk "no tag points at HEAD"         "[ -z \"\$(git tag --points-at HEAD)\" ]"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
