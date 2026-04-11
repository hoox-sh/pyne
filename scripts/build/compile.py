#!/usr/bin/env python3
"""Nuitka compilation script for Pynescript LSP binary.

Usage:
    python scripts/build/compile.py              # Full build (onefile)
    python scripts/build/compile.py --check       # Check imports only (fast)
    python scripts/build/compile.py --standalone  # Standalone directory (faster)
    python scripts/build/compile.py --jobs 4      # Use 4 parallel jobs

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

ROOT = Path(__file__).parent.parent.parent.resolve()
DIST = ROOT / "dist"
BUILD_DIR = ROOT / "scripts" / "build"
SRC_LSP = ROOT / "src" / "pynescript" / "langserver"
PROVIDERS_DIR = SRC_LSP / "providers"
METADATA_JSON = PROVIDERS_DIR / "builtin_metadata.json"
KEY_FILE = BUILD_DIR / ".metadata.key"
BINARY_NAME = "pynescript-lsp"
VSCODE_EXT = ROOT / "vscode-extension"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    cmd_str = " ".join(str(c) for c in cmd)
    if len(cmd_str) > 200:
        cmd_str = cmd_str[:200] + "..."
    print(f"  $ {cmd_str}")
    kwargs.setdefault("check", False)
    return subprocess.run(cmd, **kwargs)


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


def generate_metadata() -> None:
    """Generate builtin metadata if not present."""
    if METADATA_JSON.exists():
        print(f"  Metadata exists at {METADATA_JSON}, skipping.")
        return
    gen_script = ROOT / "scripts" / "generate_builtin_metadata.py"
    if not gen_script.exists():
        print(f"  WARNING: Metadata generator not found at {gen_script}")
        return
    print(f"  Generating metadata...")
    result = run([sys.executable, str(gen_script)])
    if result.returncode != 0:
        print(f"  ERROR: Metadata generation failed")


def encrypt_metadata() -> bool:
    """Encrypt builtin_metadata.json with Fernet."""
    if not METADATA_JSON.exists():
        return False
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("  cryptography not installed, skipping encryption")
        print("  Run: pip install cryptography")
        return False

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)
    print(f"  Key: {KEY_FILE}")

    encrypted_path = PROVIDERS_DIR / "builtin_metadata.json.enc"
    fernet = Fernet(key)
    plaintext = METADATA_JSON.read_bytes()
    encrypted = fernet.encrypt(plaintext)
    encrypted_path.write_bytes(encrypted)

    sha = hashlib.sha256(plaintext).hexdigest()[:16]
    (PROVIDERS_DIR / "builtin_metadata.json.sha256").write_text(sha + "\n")
    print(f"  Encrypted: {METADATA_JSON.stat().st_size // 1024}KB -> {encrypted_path.stat().st_size // 1024}KB")
    return True


def nuitka_compile(
    onefile: bool = True,
    standalone: bool = False,
    check_only: bool = False,
    jobs: int | None = None,
    verbose: bool = False,
) -> Path | None:
    """Compile LSP with Nuitka."""
    DIST.mkdir(exist_ok=True)
    output_dir = DIST / "lsp"

    entry = ROOT / "src" / "pynescript" / "langserver"
    if not entry.exists():
        print(f"  ERROR: Entry point not found at {entry}")
        return None

    if jobs is None:
        jobs = max(1, multiprocessing.cpu_count() - 1)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        f"--output-dir={output_dir}",
        f"--python-flag=no_site,no_docstrings",
        "--static-libpython=no",
        "--follow-imports",
        f"--include-data-dir={PROVIDERS_DIR}=pynescript/langserver/providers",
        "--lto=auto",
        f"--product-name={BINARY_NAME}",
        f"--jobs={jobs}",
    ]

    if check_only:
        cmd += ["--unstripped"]
    else:
        cmd += ["--remove-output"]

    if onefile and not standalone:
        cmd += ["--onefile"]

    if standalone:
        cmd += ["--standalone"]

    if verbose:
        cmd += ["--verbose"]

    nuitka_version = get_nuitka_version()
    print(f"  Nuitka {nuitka_version}, jobs={jobs}, onefile={onefile and not standalone}, standalone={standalone}")
    print(f"  Entry: {entry}")
    result = run(cmd)

    if result.returncode != 0:
        print(f"  ERROR: Compilation failed (exit {result.returncode})")
        return None

    if check_only:
        print("  [check passed] All imports resolved")
        return None

    compiled = None
    if onefile and not standalone:
        candidates = [
            output_dir / f"{BINARY_NAME}.onefile.exe",
            output_dir / f"{BINARY_NAME}.bin",
        ]
        compiled = next((p for p in candidates if p.exists()), None)
    if not compiled:
        candidates = list(output_dir.glob(f"{BINARY_NAME}*"))
        compiled = candidates[0] if candidates else None

    if compiled and compiled.exists():
        size_mb = compiled.stat().st_size / 1024 / 1024
        print(f"  Binary: {compiled}")
        print(f"  Size: {size_mb:.1f} MB")
        return compiled
    else:
        print(f"  WARNING: Could not locate compiled binary")
        return None


def build_vsix(binary: Path | None) -> Path | None:
    """Package VSIX bundle."""
    if not VSCODE_EXT.exists():
        return None

    vsix_file = DIST / "vsix" / f"pynescript-{binary.name if binary else 'lsp'}.vsix"
    vsix_file.parent.mkdir(exist_ok=True)

    with zipfile.ZipFile(vsix_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(VSCODE_EXT):
            dirs[:] = [d for d in dirs if d not in (".git", ".vscode", "node_modules")]
            for file in files:
                if file.endswith(".map") or file.endswith(".ts"):
                    continue
                filepath = Path(root) / file
                arcname = filepath.relative_to(VSCODE_EXT)
                zf.write(filepath, arcname)

        if binary and binary.exists():
            lsp_dir = vsix_file.parent / "lsp_bin"
            lsp_dir.mkdir(exist_ok=True)
            bin_copy = lsp_dir / binary.name
            shutil.copy2(binary, bin_copy)
            print(f"  Bundled LSP binary: {bin_copy.name}")

    size_mb = vsix_file.stat().st_size / 1024 / 1024
    print(f"  VSIX: {vsix_file} ({size_mb:.1f} MB)")
    return vsix_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile Pynescript LSP with Nuitka",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--check", action="store_true", help="Check imports only (no compile)")
    parser.add_argument("--standalone", action="store_true", help="Build standalone dir (faster, no onefile)")
    parser.add_argument("--no-encrypt", action="store_true", help="Skip metadata encryption")
    parser.add_argument("--no-metadata", action="store_true", help="Skip metadata generation")
    parser.add_argument("--clean", action="store_true", help="Clean dist/ before building")
    parser.add_argument("--jobs", type=int, default=None, help=f"Parallel jobs (default: auto)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without running")
    args = parser.parse_args()

    print("=" * 60)
    print("Pynescript LSP — Nuitka Build")
    print("=" * 60)

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
        print(f"Cleaned {DIST}")

    steps = []
    if not args.no_metadata:
        steps.append("Generate metadata")
    if not args.no_encrypt:
        steps.append("Encrypt metadata")
    steps.append("Compile with Nuitka" + (" (check only)" if args.check else ""))
    steps.append("Build VSIX bundle")

    for i, step in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {step}...")

    if args.dry_run:
        print("  [dry-run] Would execute above steps")
        return

    if not args.no_metadata:
        generate_metadata()

    encrypted = False
    if not args.no_encrypt:
        encrypted = encrypt_metadata()

    binary = nuitka_compile(
        onefile=not args.standalone,
        standalone=args.standalone,
        check_only=args.check,
        jobs=args.jobs,
        verbose=args.verbose,
    )

    if not args.check:
        vsix = build_vsix(binary)
        print(f"\n[OK] Build complete!")
        print(f"  Binary: {binary or 'N/A'}")
        print(f"  VSIX:   {vsix or 'N/A'}")
        if encrypted:
            print(f"  Key:    {KEY_FILE} (keep this safe!)")
    else:
        print(f"\n[OK] Check complete.")


if __name__ == "__main__":
    main()
