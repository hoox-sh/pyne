#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Nuitka compilation script for Pynescript LSP and CLI binaries.

Usage:
    python scripts/build/compile.py                  # Full LSP onefile build
    python scripts/build/compile.py --target cli     # CLI onefile binary
    python scripts/build/compile.py --target all     # LSP + CLI
    python scripts/build/compile.py --check          # Check imports only (fast)
    python scripts/build/compile.py --standalone     # Standalone directory (faster)
    python scripts/build/compile.py --jobs 4         # Use 4 parallel jobs

Prerequisites:
    pip install nuitka

For Anaconda environments, static libpython may not be available:
    conda install libpython-static
    # OR use: --static-libpython=no (default)
"""

from __future__ import annotations

import argparse
import hashlib
import multiprocessing
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).parent.parent.parent.resolve()
DIST = ROOT / "dist"
BUILD_DIR = ROOT / "scripts" / "build"
SRC = ROOT / "src" / "pynescript"
SRC_LSP = SRC / "langserver"
PROVIDERS_DIR = SRC_LSP / "providers"
METADATA_JSON = PROVIDERS_DIR / "builtin_metadata.json"
KEY_FILE = BUILD_DIR / ".metadata.key"
LSP_BINARY_NAME = "pynescript-lsp"
CLI_BINARY_NAME = "pynescript"
VSCODE_EXT = ROOT / "vscode-extension"


def run(cmd: Sequence[str | Path], **kwargs) -> subprocess.CompletedProcess:
    cmd_str = " ".join(str(c) for c in cmd)
    if len(cmd_str) > 200:
        cmd_str = cmd_str[:200] + "..."
    print(f"  $ {cmd_str}")
    kwargs.setdefault("check", False)
    return subprocess.run(list(cmd), **kwargs)


def get_nuitka_version() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if "Version" in line:
                return line.split("Version")[-1].strip().split()[0]
        return "unknown"
    except Exception:
        return "unknown"


def generate_metadata() -> bool:
    """Generate builtin metadata if not present. Returns False on failure."""
    if METADATA_JSON.exists():
        print(f"  Metadata exists at {METADATA_JSON}, skipping.")
        return True
    gen_script = ROOT / "scripts" / "generate_builtin_metadata.py"
    if not gen_script.exists():
        print(f"  WARNING: Metadata generator not found at {gen_script}")
        return True
    print("  Generating metadata...")
    result = run([sys.executable, str(gen_script)])
    if result.returncode != 0:
        print("  ERROR: Metadata generation failed")
        return False
    return True


def _resolve_fernet_key() -> bytes:
    """Resolve a stable Fernet key for metadata encryption.

    Priority:
    1. ``CRYPTO_KEY`` env (CI: GitHub ``secrets.METADATA_KEY``, Cloud Build ``_METADATA_KEY``)
    2. ``PYNESCRIPT_METADATA_KEY`` env (runtime decrypt fallback, same material)
    3. ``METADATA_KEY`` env
    4. Existing ``scripts/build/.metadata.key``
    5. Generate a new key and write it to ``.metadata.key`` (local first-time setup)

    Returns:
        Raw Fernet key bytes (url-safe base64, 44 chars when decoded as ascii).
    """
    for env_name in ("CRYPTO_KEY", "PYNESCRIPT_METADATA_KEY", "METADATA_KEY"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            key = raw.encode("ascii") if not isinstance(raw, bytes) else raw
            print(f"  Key: from env {env_name}")
            # Persist for tools that only read the file (Nuitka data embed path)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_bytes(key)
            os.chmod(KEY_FILE, 0o600)
            return key

    if KEY_FILE.exists():
        print(f"  Key: {KEY_FILE}")
        return KEY_FILE.read_bytes()

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)
    print(f"  Key: generated {KEY_FILE} (export as CRYPTO_KEY / GitHub secrets.METADATA_KEY)")
    return key


def encrypt_metadata() -> bool:
    """Encrypt builtin_metadata.json with Fernet using a stable key."""
    if not METADATA_JSON.exists():
        print(f"  ERROR: Metadata plaintext not found at {METADATA_JSON}")
        return False
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("  cryptography not installed, skipping encryption")
        print("  Run: pip install cryptography")
        return False

    key = _resolve_fernet_key()
    encrypted_path = PROVIDERS_DIR / "builtin_metadata.json.enc"
    fernet = Fernet(key)
    plaintext = METADATA_JSON.read_bytes()
    encrypted = fernet.encrypt(plaintext)
    encrypted_path.write_bytes(encrypted)

    sha = hashlib.sha256(plaintext).hexdigest()[:16]
    (PROVIDERS_DIR / "builtin_metadata.json.sha256").write_text(sha + "\n")
    print(f"  Encrypted: {METADATA_JSON.stat().st_size // 1024}KB -> {encrypted_path.stat().st_size // 1024}KB")
    return True


def _package_version() -> str:
    about = ROOT / "src" / "pynescript" / "__about__.py"
    if not about.is_file():
        return "0.0.0"
    version = "0.0.0"
    for line in about.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            version = line.split("=", 1)[1].strip().strip("\"'")
            break
    return version


def _product_version(version: str) -> str:
    """Nuitka Windows version resource requires dotted numeric product/file version."""
    version_core = version.split("+")[0].split("a")[0].split("b")[0].split("rc")[0]
    parts = [p for p in version_core.split(".") if p.isdigit()]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:4])  # Nuitka accepts up to 4 components


def _find_binary(output_dir: Path, binary_name: str) -> Path | None:
    """Locate a compiled binary by exact name (never confuse CLI with LSP).

    ``pynescript`` must not match ``pynescript-lsp`` via a naive ``name*`` glob.
    Accepts exact name plus common Nuitka suffixes (``.bin``, ``.exe``, …).
    """
    if not output_dir.is_dir():
        return None

    candidates = [
        output_dir / binary_name,
        output_dir / f"{binary_name}.bin",
        output_dir / f"{binary_name}.exe",
        output_dir / f"{binary_name}.onefile.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    # Fallback: exact name or name + extension only (not name-something).
    for path in sorted(output_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name == binary_name or name.startswith(f"{binary_name}."):
            return path
    return None


def nuitka_compile(
    *,
    target: str,
    onefile: bool = True,
    standalone: bool = False,
    check_only: bool = False,
    jobs: int | None = None,
    verbose: bool = False,
) -> Path | None:
    """Compile LSP or CLI with Nuitka.

    ``target`` is ``lsp`` or ``cli``.

    Returns:
        On successful compile: path to the binary.
        On successful ``check_only``: the entry-point path (truthy sentinel).
        On failure: ``None``.
    """
    if target not in ("lsp", "cli"):
        raise ValueError(f"Unknown compile target: {target}")

    DIST.mkdir(parents=True, exist_ok=True)
    output_dir = DIST / target
    output_dir.mkdir(parents=True, exist_ok=True)
    binary_name = LSP_BINARY_NAME if target == "lsp" else CLI_BINARY_NAME
    entry_py = (SRC_LSP / "__main__.py") if target == "lsp" else (SRC / "__main__.py")

    if not entry_py.is_file():
        print(f"  ERROR: Entry point not found at {entry_py}")
        return None

    if jobs is None:
        jobs = max(1, multiprocessing.cpu_count() - 1)

    product_version = _product_version(_package_version())
    file_description = (
        "PYNE Pine Script Language Server"
        if target == "lsp"
        else "PYNE Pine Script CLI"
    )

    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    if check_only:
        mod = "pynescript.langserver" if target == "lsp" else "pynescript"
        print(f"  [check] import {mod} via {sys.executable}")
        check = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import {mod}; print('ok', getattr({mod}, '__file__', {mod}))",
            ],
            cwd=ROOT,
            env=env,
        )
        if check.returncode != 0:
            print(f"  ERROR: Import check failed (exit {check.returncode})")
            return None
        # CLI entry point smoke
        if target == "cli":
            help_check = subprocess.run(
                [sys.executable, "-m", "pynescript", "--help"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            if help_check.returncode != 0:
                print(f"  ERROR: CLI --help failed (exit {help_check.returncode})")
                if help_check.stderr:
                    print(help_check.stderr)
                return None
            print("  [check] pynescript --help ok")
        print("  [check passed] All imports resolved")
        return entry_py

    cmd: list[str] = [
        sys.executable,
        "-m",
        "nuitka",
        "--assume-yes-for-downloads",  # Dependency Walker / ccache on CI (no TTY)
        f"--output-dir={output_dir}",
        f"--output-filename={binary_name}",
        "--python-flag=no_site,no_docstrings",
        "--static-libpython=no",
        "--follow-imports",
        # Portable binaries: avoid numba/llvmlite packaging pitfalls (macOS, etc.).
        # CLI interpret path still works; compile mode degrades if numba absent.
        "--nofollow-import-to=numba",
        "--nofollow-import-to=llvmlite",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=cryptography",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=ccxt",
        "--lto=auto",
        f"--product-name={binary_name}",
        f"--product-version={product_version}",
        f"--file-version={product_version}",
        f"--file-description={file_description}",
        "--company-name=HOOX",
        f"--jobs={jobs}",
        "--remove-output",
    ]

    if target == "lsp":
        # Slim editor binary: parse + lint + pygls only.
        cmd += [
            "--nofollow-import-to=pynescript.compiler",
            "--nofollow-import-to=pynescript.ast.evaluator",
            f"--include-data-dir={PROVIDERS_DIR}=pynescript/langserver/providers",
        ]
    else:
        # CLI needs evaluator for run/compile (interpret); skip heavy optional extras.
        cmd += [
            "--nofollow-import-to=pynescript.langserver",
            "--nofollow-import-to=pygls",
            "--nofollow-import-to=lsprotocol",
            "--nofollow-import-to=flask",
            "--nofollow-import-to=backend",
        ]

    if onefile and not standalone:
        cmd += ["--onefile"]

    if standalone:
        cmd += ["--standalone"]

    if verbose:
        cmd += ["--verbose"]

    cmd.append(str(entry_py))

    nuitka_version = get_nuitka_version()
    print(
        f"  Nuitka {nuitka_version}, target={target}, jobs={jobs}, "
        f"onefile={onefile and not standalone}, standalone={standalone}"
    )
    print(f"  Entry: {entry_py}")
    result = run(cmd, env=env)

    if result.returncode != 0:
        print(f"  ERROR: Compilation failed (exit {result.returncode})")
        return None

    compiled = _find_binary(output_dir, binary_name)
    if compiled is not None and compiled.is_file():
        size_mb = compiled.stat().st_size / 1024 / 1024
        print(f"  Binary: {compiled}")
        print(f"  Size: {size_mb:.1f} MB")
        return compiled
    print(f"  ERROR: Could not locate compiled binary under {output_dir} (looked for {binary_name})")
    return None


def build_vsix(binary: Path | None) -> Path | None:
    """Package VSIX bundle."""
    if not VSCODE_EXT.exists():
        print(f"  WARNING: VS Code extension not found at {VSCODE_EXT}")
        return None

    vsix_file = DIST / "vsix" / f"pynescript-{binary.name if binary else 'lsp'}.vsix"
    vsix_file.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(vsix_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(VSCODE_EXT):
            dirs[:] = [d for d in dirs if d not in (".git", ".vscode", "node_modules")]
            for file in files:
                if file.endswith(".map") or file.endswith(".ts"):
                    continue
                filepath = Path(root) / file
                arcname = filepath.relative_to(VSCODE_EXT)
                zf.write(filepath, arcname)

        if binary is not None and binary.is_file():
            lsp_dir = vsix_file.parent / "lsp_bin"
            lsp_dir.mkdir(parents=True, exist_ok=True)
            bin_copy = lsp_dir / binary.name
            shutil.copy2(binary, bin_copy)
            print(f"  Bundled LSP binary: {bin_copy.name}")

    size_mb = vsix_file.stat().st_size / 1024 / 1024
    print(f"  VSIX: {vsix_file} ({size_mb:.1f} MB)")
    return vsix_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile Pynescript LSP and/or CLI with Nuitka",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        choices=("lsp", "cli", "all"),
        default="lsp",
        help="Binary to build (default: lsp)",
    )
    parser.add_argument("--check", action="store_true", help="Check imports only (no compile)")
    parser.add_argument("--standalone", action="store_true", help="Build standalone dir (faster, no onefile)")
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Force metadata encryption (even with --check; default is skip encrypt on --check)",
    )
    parser.add_argument("--no-encrypt", action="store_true", help="Skip metadata encryption")
    parser.add_argument("--no-metadata", action="store_true", help="Skip metadata generation")
    parser.add_argument("--no-vsix", action="store_true", help="Skip VSIX packaging (LSP only)")
    parser.add_argument("--clean", action="store_true", help="Clean dist/ before building")
    parser.add_argument("--jobs", type=int, default=None, help="Parallel jobs (default: auto)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without running")
    args = parser.parse_args()

    if args.encrypt and args.no_encrypt:
        print("ERROR: --encrypt and --no-encrypt are mutually exclusive", file=sys.stderr)
        sys.exit(2)

    targets = ["lsp", "cli"] if args.target == "all" else [args.target]

    print("=" * 60)
    print(f"Pynescript — Nuitka Build ({', '.join(targets)})")
    print("=" * 60)

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
        print(f"Cleaned {DIST}")

    need_metadata = "lsp" in targets and not args.no_metadata
    # Skip encrypt on --check unless --encrypt is forced (Fernet IV churn dirties git).
    if args.no_encrypt:
        need_encrypt = False
    elif args.encrypt:
        need_encrypt = True
    elif args.check:
        need_encrypt = False
    else:
        need_encrypt = "lsp" in targets

    steps: list[str] = []
    if need_metadata:
        steps.append("Generate metadata")
    if need_encrypt:
        steps.append("Encrypt metadata")
    for t in targets:
        steps.append(f"Compile {t} with Nuitka" + (" (check only)" if args.check else ""))
    if "lsp" in targets and not args.check and not args.no_vsix:
        steps.append("Build VSIX bundle")

    for i, step in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {step}...")

    if args.dry_run:
        print("  [dry-run] Would execute above steps")
        return

    failed = False

    if need_metadata:
        if not generate_metadata():
            failed = True

    encrypted = False
    if need_encrypt and not failed:
        encrypted = encrypt_metadata()
        if not encrypted:
            # --encrypt is explicit: fail closed. Default LSP builds warn and continue
            # (plaintext metadata is preferred in dev; use --no-encrypt to skip quietly).
            if args.encrypt:
                print("  ERROR: Metadata encryption failed (--encrypt required)")
                failed = True
            else:
                print("  WARNING: Metadata encryption failed; continuing with plaintext if present")

    results: dict[str, Path | None] = {}
    if not failed:
        for t in targets:
            results[t] = nuitka_compile(
                target=t,
                onefile=not args.standalone,
                standalone=args.standalone,
                check_only=args.check,
                jobs=args.jobs,
                verbose=args.verbose,
            )
            if results[t] is None:
                failed = True

    vsix = None
    if not failed and "lsp" in targets and not args.check and not args.no_vsix:
        vsix = build_vsix(results.get("lsp"))

    if failed:
        print("\n[FAIL] Build/check failed for one or more targets.")
        for t, path in results.items():
            status = path if path is not None else "FAILED"
            print(f"  {t.upper()}: {status}")
        sys.exit(1)

    if not args.check:
        print("\n[OK] Build complete!")
        for t, path in results.items():
            print(f"  {t.upper()}: {path or 'N/A'}")
        if "lsp" in targets:
            print(f"  VSIX: {vsix or 'N/A'}")
        if encrypted:
            print(f"  Key:  {KEY_FILE} (keep this safe!)")
    else:
        print("\n[OK] Check complete.")


if __name__ == "__main__":
    main()
