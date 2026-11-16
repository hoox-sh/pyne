#!/bin/sh
# Portability proof: run the updated verify-debt tests from a clean archive of
# HEAD's tracked src (the ignored pine_facade.py is absent) with the updated
# test files overlaid.
set -eu

ROOT=$(git rev-parse --show-toplevel)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/pyne-clean-checkout.XXXXXX")

git -C "$ROOT" archive HEAD \
  src \
  tests/conftest.py \
  tests/test_cli_util_coverage.py \
  tests/test_langserver_server_coverage.py \
  tests/test_mcp_ops_low_coverage.py | tar -x -C "$TMP"

cp "$ROOT/tests/test_cli_util_coverage.py" "$TMP/tests/"
cp "$ROOT/tests/test_langserver_server_coverage.py" "$TMP/tests/"
cp "$ROOT/tests/test_mcp_ops_low_coverage.py" "$TMP/tests/"

test ! -e "$TMP/src/pynescript/util/pine_facade.py"

PYTHONPATH="$TMP/src" "$ROOT/.venv/bin/python" -m pytest \
  "$TMP/tests/test_cli_util_coverage.py::test_download_builtins_available" \
  "$TMP/tests/test_cli_util_coverage.py::test_download_builtins_fails_closed_without_facade" \
  "$TMP/tests/test_langserver_server_coverage.py::TestLifecycle::test_pygls_initialize_advertises_semantic_token_legend" \
  "$TMP/tests/test_langserver_server_coverage.py::TestLifecycle::test_pyne_lsp_version_flag" \
  "$TMP/tests/test_mcp_ops_low_coverage.py::test_list_facade_templates_available" \
  "$TMP/tests/test_mcp_ops_low_coverage.py::test_list_facade_templates_fails_closed_without_facade" \
  -q

echo "CLEAN_CHECKOUT_TESTS_OK tests=6"
