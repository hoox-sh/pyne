#!/usr/bin/env bash
# Proof for the 0.7.2 release bump + build inspection (deploy seat, 2026-11-17).
# Read-only and deterministic: asserts the shipped commit, the built artifacts,
# and their contents. Never tags, never publishes.
#
#   bash .oo/proof/release-0.7.2-build-verify-2026-11-17.sh
#
set -u
cd "$(dirname "$0")/../.." || exit 2

# The release-bump commit this script proves; HEAD moves on with later work.
BUMP=71a89edb

pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }

WHL=$(ls dist/hoox_pyne-0.7.2-*.whl 2>/dev/null | head -1)
SD=$(ls dist/hoox_pyne-0.7.2.tar.gz 2>/dev/null | head -1)

echo "--- [1] version sources ---"
chk "VERSION is 0.7.2"            "[ \"\$(cat VERSION)\" = '0.7.2' ]"
chk "__about__ is 0.7.2"          "grep -qx '__version__ = \"0.7.2\"' src/pynescript/__about__.py"
chk "runtime __version__ 0.7.2"   "PYTHONPATH=src .venv/bin/python -c 'import pynescript,sys; sys.exit(pynescript.__version__!=\"0.7.2\")'"
chk "VERSION at HEAD is 0.7.2"    "[ \"\$(git show $BUMP:VERSION)\" = '0.7.2' ]"
chk "__about__ at HEAD is 0.7.2"  "git show $BUMP:src/pynescript/__about__.py | grep -qx '__version__ = \"0.7.2\"'"

echo "--- [2] artifacts exist and self-report 0.7.2 ---"
chk "wheel exists"                "[ -n '$WHL' ] && [ -f '$WHL' ]"
chk "sdist exists"                "[ -n '$SD' ] && [ -f '$SD' ]"
chk "wheel name has 0.7.2"        "echo '$WHL' | grep -q 'hoox_pyne-0.7.2-py3-none-any.whl'"
chk "sdist name has 0.7.2"        "echo '$SD' | grep -q 'hoox_pyne-0.7.2.tar.gz'"
chk "wheel METADATA Version 0.7.2" ".venv/bin/python -c \"
import zipfile,glob,sys
z=zipfile.ZipFile(glob.glob('dist/*.whl')[0])
m=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')][0]
sys.exit(0 if 'Version: 0.7.2' in z.read(m).decode().splitlines() else 1)\""
chk "sdist PKG-INFO Version 0.7.2" ".venv/bin/python -c \"
import tarfile,glob,sys
t=tarfile.open(glob.glob('dist/*.tar.gz')[0])
m=[n for n in t.getnames() if n.endswith('/PKG-INFO')][0]
sys.exit(0 if 'Version: 0.7.2' in t.extractfile(m).read().decode().splitlines() else 1)\""

echo "--- [3] wheel contents ---"
chk "wheel top-level is exactly pynescript + dist-info" ".venv/bin/python -c \"
import zipfile,glob,sys
z=zipfile.ZipFile(glob.glob('dist/*.whl')[0])
top={n.split('/')[0] for n in z.namelist()}
sys.exit(0 if top=={'pynescript','hoox_pyne-0.7.2.dist-info'} else 1)\""
chk "wheel contains pynescript/"  "unzip -Z1 '$WHL' | grep -q '^pynescript/'"
chk "wheel has NO backend/"       "! unzip -Z1 '$WHL' | grep -q '^backend/'"
chk "wheel has no backend segment" "! unzip -Z1 '$WHL' | grep -q 'backend'"
chk "wheel has no .env / .metadata.key" "! unzip -Z1 '$WHL' | grep -qE '(^|/)\.env|\.metadata\.key'"

echo "--- [4] sdist contents: secrets gone, backend still carded for 0.7.3 ---"
chk "sdist CONTAINS backend/ (known defect, carded)" "tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/backend/'"
chk "sdist backend/ file count is 43" "[ \"\$(tar -tzf '$SD' | grep -c '^hoox_pyne-0.7.2/backend/.')\" = 43 ]"
chk "sdist has NO .env* members" "! tar -tzf '$SD' | grep -qE '(^|/)\.env'"
chk "sdist has NO .metadata.key" "! tar -tzf '$SD' | grep -q '\.metadata\.key'"
chk "sdist has NO *.key/*.pem/id_rsa" "! tar -tzf '$SD' | grep -qE '\.(key|pem)\$|(^|/)id_rsa\$'"
chk "sdist has NO .coverage*" "! tar -tzf '$SD' | grep -qE '(^|/)\.coverage'"
chk "sdist under 100 MB" "[ \"\$(stat -c %s '$SD')\" -lt 104857600 ]"
chk "sdist carries pyproject.toml" "tar -tzf '$SD' | grep -qx 'hoox_pyne-0.7.2/pyproject.toml'"
chk "sdist carries src/pynescript/" "tar -tzf '$SD' | grep -q '^hoox_pyne-0.7.2/src/pynescript/'"
chk "sdist carries README/LICENSE/VERSION/CHANGELOG" "for f in README.md LICENSE VERSION CHANGELOG.md; do tar -tzf '$SD' | grep -qx \"hoox_pyne-0.7.2/\$f\" || exit 1; done"
chk "pre-publish guard exits 0" ".venv/bin/python scripts/build/assert_sdist_clean.py '$SD'"

echo "--- [5] commit shape ---"
chk "HEAD subject is chore(release): 0.7.2" "[ \"\$(git log -1 --format=%s $BUMP)\" = 'chore(release): 0.7.2' ]"
chk "HEAD changes exactly 2 files" "[ \"\$(git show --name-only --format= $BUMP | grep -c .)\" = 2 ]"
# Compare as a set: default `sort` collation differs by locale, so an ordered
# string comparison here fails for reasons unrelated to the commit.
chk "HEAD changes only the 2 version files" "[ \"\$(git diff-tree --no-commit-id --name-only -r $BUMP | grep -c .)\" = 2 ] && git diff-tree --no-commit-id --name-only -r $BUMP | grep -qx 'VERSION' && git diff-tree --no-commit-id --name-only -r $BUMP | grep -qx 'src/pynescript/__about__.py'"
chk "HEAD is pushed (origin/main == HEAD)" "[ \"\$(git rev-parse origin/main)\" = \"\$(git rev-parse HEAD)\" ]"
chk "dist/ is not tracked"        "[ -z \"\$(git ls-files dist/)\" ]"

echo "--- [6] nothing tagged, nothing published ---"
chk "no local tag v0.7.2"         "[ -z \"\$(git tag -l 'v0.7.2')\" ]"
chk "no tag points at HEAD"       "[ -z \"\$(git tag --points-at HEAD)\" ]"
chk "newest tag is still v0.7.1"  "[ \"\$(git tag --sort=-creatordate | head -1)\" = 'v0.7.1' ]"

echo "--- [7] scope: forbidden paths untouched by my commit ---"
chk "no docs/ in commit"          "! git show --name-only --format= $BUMP | grep -q '^docs/'"
chk "no pyproject.toml in commit" "! git show --name-only --format= $BUMP | grep -qx 'pyproject.toml'"
chk "no .githooks/ in commit"     "! git show --name-only --format= $BUMP | grep -q '^\.githooks/'"
chk "no .gitignore in commit"     "! git show --name-only --format= $BUMP | grep -qx '\.gitignore'"
chk "no .openorchestrate/ in commit" "! git show --name-only --format= $BUMP | grep -q '^\.openorchestrate/'"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" = 0 ]
