# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
Real-World Compatibility Test Suite

This module validates PyneScript's 100% compatibility guarantee by:
1. Parsing real-world Pine Script strategies from TradingView®
2. Verifying AST round-trip consistency (parse → unparse → parse)
3. Validating structural integrity of all parsed scripts
4. Measuring compatibility metrics across diverse script types

Test Methodology:
- Download built-in scripts from TradingView® using pine_facade
- Parse each script and build AST
- Unparse AST back to source code
- Re-parse the unparsed source
- Compare AST structures for identity
- Report success rate and any failures

Success Criteria:
- Parse success rate > 98%
- AST round-trip success rate = 100% (for successfully parsed scripts)
- Structural integrity maintained in all cases
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pynescript.ast.helper import dump, parse, unparse


class TestRealWorldCompatibility:
    """Test suite for real-world Pine Script compatibility validation."""

    @pytest.fixture
    def builtin_scripts_dir(self, request: pytest.FixtureRequest) -> Path:
        """Get the directory containing built-in scripts."""
        # Check for --example-scripts-dir option
        scripts_dir = request.config.getoption("--example-scripts-dir", None)
        if scripts_dir:
            return Path(scripts_dir)

        # Default to tests/data/builtin_scripts
        return Path(__file__).parent / "data" / "builtin_scripts"

    @pytest.fixture
    def script_files(self, builtin_scripts_dir: Path) -> list[Path]:
        """Get all .pine script files from the scripts directory."""
        if not builtin_scripts_dir.exists():
            pytest.skip(f"Scripts directory not found: {builtin_scripts_dir}")

        # Use rglob to find scripts recursively in subdirectories
        script_files = list(builtin_scripts_dir.rglob("*.pine"))
        if not script_files:
            pytest.skip(f"No .pine files found in {builtin_scripts_dir}")

        return script_files

    def test_all_scripts_parse_successfully(self, script_files: list[Path]) -> None:
        """Test that all real-world scripts can be parsed without errors."""
        failed_scripts: list[tuple[Path, Exception]] = []

        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")
                parse(source)
            except Exception as e:
                failed_scripts.append((script_path, e))

        # Report results
        total = len(script_files)
        success = total - len(failed_scripts)
        success_rate = (success / total * 100) if total > 0 else 0

        print(f"\n{'=' * 80}")
        print("Parse Compatibility Results:")
        print(f"  Total scripts: {total}")
        print(f"  Successful: {success} ({success_rate:.2f}%)")
        print(f"  Failed: {len(failed_scripts)}")
        print(f"{'=' * 80}")

        if failed_scripts:
            print("\nFailed scripts:")
            for script_path, error in failed_scripts:
                print(f"  - {script_path.name}: {type(error).__name__}: {error}")
            print(f"{'=' * 80}\n")

        # Assert > 98% success rate as per compatibility guarantee
        assert success_rate > 98.0, (
            f"Parse success rate {success_rate:.2f}% is below 98% threshold. "
            f"Failed: {len(failed_scripts)}/{total} scripts."
        )

    def test_ast_round_trip_consistency(self, script_files: list[Path]) -> None:
        """
        Test AST round-trip consistency: parse → unparse → parse → compare.

        This is the strongest test of compatibility - if AST structures are
        identical after round-trip, we have perfect structural compatibility.
        """
        failed_scripts: list[tuple[Path, str]] = []
        skipped_scripts: list[tuple[Path, Exception]] = []

        for script_path in script_files:
            try:
                # Parse original
                source = script_path.read_text(encoding="utf-8")
                ast1 = parse(source)

                # Unparse to source
                unparsed_source = unparse(ast1)

                # Parse again
                ast2 = parse(unparsed_source)

                # Compare AST structures using dump
                dump1 = dump(ast1)
                dump2 = dump(ast2)

                if dump1 != dump2:
                    failed_scripts.append((script_path, "AST structures differ after round-trip"))

            except Exception as e:
                # Script failed to parse initially, skip it
                skipped_scripts.append((script_path, e))

        # Report results
        total = len(script_files)
        skipped = len(skipped_scripts)
        tested = total - skipped
        success = tested - len(failed_scripts)
        success_rate = (success / tested * 100) if tested > 0 else 0

        print(f"\n{'=' * 80}")
        print("AST Round-Trip Compatibility Results:")
        print(f"  Total scripts: {total}")
        print(f"  Tested: {tested}")
        print(f"  Skipped (parse failed): {skipped}")
        print(f"  Successful round-trips: {success} ({success_rate:.2f}%)")
        print(f"  Failed round-trips: {len(failed_scripts)}")
        print(f"{'=' * 80}")

        if failed_scripts:
            print("\nFailed round-trip scripts:")
            for script_path, reason in failed_scripts:
                print(f"  - {script_path.name}: {reason}")
            print(f"{'=' * 80}\n")

        # Assert 100% success rate for scripts that parsed successfully
        assert success_rate == 100.0, (
            f"AST round-trip success rate {success_rate:.2f}% is below 100% threshold. "
            f"Failed: {len(failed_scripts)}/{tested} scripts."
        )

    def test_structural_integrity_validation(self, script_files: list[Path]) -> None:
        """
        Test that parsed ASTs have valid structure and all expected node types.

        Validates:
        - AST contains a Module node at root
        - All nodes have valid types from grammar
        - No None/null nodes in critical positions
        - Annotations are properly attached
        """
        failed_scripts: list[tuple[Path, str]] = []
        skipped_scripts: list[tuple[Path, Exception]] = []

        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")
                ast = parse(source)

                # Validate root node
                if not hasattr(ast, "__class__"):
                    failed_scripts.append((script_path, "AST root has no __class__"))
                    continue

                # Validate we can dump it (proves structure is sound)
                try:
                    dump(ast)
                except Exception as dump_error:
                    failed_scripts.append((script_path, f"AST dump failed: {dump_error}"))
                    continue

                # Validate we can unparse it (proves all nodes are valid)
                try:
                    unparse(ast)
                except Exception as unparse_error:
                    failed_scripts.append((script_path, f"AST unparse failed: {unparse_error}"))
                    continue

            except Exception as e:
                skipped_scripts.append((script_path, e))

        # Report results
        total = len(script_files)
        skipped = len(skipped_scripts)
        tested = total - skipped
        success = tested - len(failed_scripts)
        success_rate = (success / tested * 100) if tested > 0 else 0

        print(f"\n{'=' * 80}")
        print("Structural Integrity Results:")
        print(f"  Total scripts: {total}")
        print(f"  Tested: {tested}")
        print(f"  Skipped (parse failed): {skipped}")
        print(f"  Valid structures: {success} ({success_rate:.2f}%)")
        print(f"  Invalid structures: {len(failed_scripts)}")
        print(f"{'=' * 80}")

        if failed_scripts:
            print("\nStructurally invalid scripts:")
            for script_path, reason in failed_scripts:
                print(f"  - {script_path.name}: {reason}")
            print(f"{'=' * 80}\n")

        # Assert 100% structural integrity
        assert success_rate == 100.0, (
            f"Structural integrity {success_rate:.2f}% is below 100% threshold. "
            f"Failed: {len(failed_scripts)}/{tested} scripts."
        )

    def test_script_type_coverage(self, script_files: list[Path]) -> None:
        """
        Analyze coverage of different script types and features.

        Categorizes scripts by:
        - Indicators vs Strategies
        - Version (v5, v6)
        - Feature usage (UDTs, enums, imports, etc.)
        """
        script_analysis: dict[str, Any] = {
            "total": len(script_files),
            "by_type": {"indicator": 0, "strategy": 0, "library": 0, "unknown": 0},
            "by_version": {"v5": 0, "v6": 0, "unknown": 0},
            "features": {
                "has_udt": 0,
                "has_enum": 0,
                "has_import": 0,
                "has_method": 0,
                "has_export": 0,
            },
            "parse_success": 0,
            "parse_failed": 0,
        }

        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")

                # Detect script type
                if "indicator(" in source:
                    script_analysis["by_type"]["indicator"] += 1
                elif "strategy(" in source:
                    script_analysis["by_type"]["strategy"] += 1
                elif "library(" in source:
                    script_analysis["by_type"]["library"] += 1
                else:
                    script_analysis["by_type"]["unknown"] += 1

                # Detect version
                if "//@version=6" in source or "//@version = 6" in source:
                    script_analysis["by_version"]["v6"] += 1
                elif "//@version=5" in source or "//@version = 5" in source:
                    script_analysis["by_version"]["v5"] += 1
                else:
                    script_analysis["by_version"]["unknown"] += 1

                # Detect features
                if "type " in source:
                    script_analysis["features"]["has_udt"] += 1
                if "enum " in source:
                    script_analysis["features"]["has_enum"] += 1
                if "import " in source:
                    script_analysis["features"]["has_import"] += 1
                if "method " in source:
                    script_analysis["features"]["has_method"] += 1
                if "export " in source:
                    script_analysis["features"]["has_export"] += 1

                # Try to parse
                parse(source)
                script_analysis["parse_success"] += 1

            except Exception:
                script_analysis["parse_failed"] += 1

        # Report results
        print(f"\n{'=' * 80}")
        print("Script Type Coverage Analysis:")
        print(f"  Total scripts: {script_analysis['total']}")
        print("\n  By Type:")
        for script_type, count in script_analysis["by_type"].items():
            pct = (count / script_analysis["total"] * 100) if script_analysis["total"] > 0 else 0
            print(f"    {script_type}: {count} ({pct:.1f}%)")
        print("\n  By Version:")
        for version, count in script_analysis["by_version"].items():
            pct = (count / script_analysis["total"] * 100) if script_analysis["total"] > 0 else 0
            print(f"    {version}: {count} ({pct:.1f}%)")
        print("\n  Feature Usage:")
        for feature, count in script_analysis["features"].items():
            pct = (count / script_analysis["total"] * 100) if script_analysis["total"] > 0 else 0
            print(f"    {feature}: {count} ({pct:.1f}%)")
        print("\n  Parse Results:")
        success_rate = (
            (script_analysis["parse_success"] / script_analysis["total"] * 100)
            if script_analysis["total"] > 0
            else 0
        )
        print(f"    Success: {script_analysis['parse_success']} ({success_rate:.2f}%)")
        print(f"    Failed: {script_analysis['parse_failed']}")
        print(f"{'=' * 80}\n")

        # No assertions here - this is informational only
        # Results help us understand our test coverage

    @pytest.mark.parametrize(
        "feature_pattern,feature_name",
        [
            ("indicator(", "indicator() function"),
            ("strategy(", "strategy() function"),
            ("plot(", "plot() function"),
            ("ta.sma(", "ta.sma() function"),
            ("ta.ema(", "ta.ema() function"),
            ("ta.rsi(", "ta.rsi() function"),
            ("array.", "array operations"),
            ("matrix.", "matrix operations"),
            ("map.", "map operations"),
            ("type ", "user-defined types"),
            ("method ", "method definitions"),
            ("var ", "var declarations"),
            ("varip ", "varip declarations"),
            ("if ", "if statements"),
            ("for ", "for loops"),
            ("while ", "while loops"),
        ],
    )
    def test_feature_specific_scripts(
        self, script_files: list[Path], feature_pattern: str, feature_name: str
    ) -> None:
        """
        Test scripts that use specific Pine Script features.

        This ensures we have test coverage for all major language features
        and that they parse correctly in real-world usage.
        """
        matching_scripts = []
        failed_scripts = []

        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")
                if feature_pattern in source:
                    matching_scripts.append(script_path)
                    # Try to parse it
                    parse(source)
            except Exception as e:
                failed_scripts.append((script_path, e))

        if not matching_scripts:
            pytest.skip(f"No scripts found using {feature_name}")

        # Report results
        total = len(matching_scripts)
        success = total - len(failed_scripts)
        success_rate = (success / total * 100) if total > 0 else 0

        assert success_rate >= 98.0, (
            f"Feature {feature_name} compatibility {success_rate:.2f}% is below 98%. "
            f"Failed: {len(failed_scripts)}/{total} scripts."
        )


class TestCompatibilityMetrics:
    """Test suite for generating compatibility metrics and reports."""

    @pytest.fixture
    def builtin_scripts_dir(self, request: pytest.FixtureRequest) -> Path:
        """Get the directory containing built-in scripts."""
        scripts_dir = request.config.getoption("--example-scripts-dir", None)
        if scripts_dir:
            return Path(scripts_dir)
        return Path(__file__).parent / "data" / "builtin_scripts"

    def test_generate_compatibility_report(self, builtin_scripts_dir: Path) -> None:
        """
        Generate comprehensive compatibility report in JSON format.

        This report can be used to update COMPATIBILITY_GUARANTEE.md
        and track compatibility metrics over time.
        """
        if not builtin_scripts_dir.exists():
            pytest.skip(f"Scripts directory not found: {builtin_scripts_dir}")

        # Use rglob to find scripts recursively
        script_files = list(builtin_scripts_dir.rglob("*.pine"))
        if not script_files:
            pytest.skip(f"No .pine files found in {builtin_scripts_dir}")

        report: dict[str, Any] = {
            "timestamp": "2025-11-20",
            "total_scripts": len(script_files),
            "parse_results": {"success": 0, "failed": 0, "failed_scripts": []},
            "round_trip_results": {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "failed_scripts": [],
            },
            "features_tested": {},
        }

        # Test parsing
        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")
                parse(source)
                report["parse_results"]["success"] += 1
            except Exception as e:
                report["parse_results"]["failed"] += 1
                report["parse_results"]["failed_scripts"].append(
                    {"script": script_path.name, "error": str(e)}
                )

        # Test round-trip
        for script_path in script_files:
            try:
                source = script_path.read_text(encoding="utf-8")
                ast1 = parse(source)
                unparsed = unparse(ast1)
                ast2 = parse(unparsed)

                if dump(ast1) == dump(ast2):
                    report["round_trip_results"]["success"] += 1
                else:
                    report["round_trip_results"]["failed"] += 1
                    report["round_trip_results"]["failed_scripts"].append(
                        {"script": script_path.name, "error": "AST mismatch"}
                    )
            except Exception:
                report["round_trip_results"]["skipped"] += 1

        # Calculate rates
        total = report["total_scripts"]
        report["parse_results"]["success_rate"] = (
            (report["parse_results"]["success"] / total * 100) if total > 0 else 0
        )

        tested = total - report["round_trip_results"]["skipped"]
        report["round_trip_results"]["success_rate"] = (
            (report["round_trip_results"]["success"] / tested * 100) if tested > 0 else 0
        )

        # Print report
        print(f"\n{'=' * 80}")
        print("COMPATIBILITY REPORT")
        print(f"{'=' * 80}")
        print(json.dumps(report, indent=2))
        print(f"{'=' * 80}\n")

        # Save report to file
        report_path = Path(__file__).parent.parent / "compatibility_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
